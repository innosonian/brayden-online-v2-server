import logging
import os
from io import BytesIO
from datetime import datetime, timedelta

import regex
from fastapi import APIRouter, Depends, status, HTTPException, Request, UploadFile

from apis.util import get_token_by_header, STUDENT, get_user_by_token, check_authorized_by_user
from exceptions import GetException, ExceptionType, GetExceptionWithStatuscode
from models.model import User, Training, Certification, TrainingProgram, Organization

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_, func, insert, and_
from sqlalchemy.exc import IntegrityError

from bcrypt import hashpw

from database import get_db
from pandas import read_excel, DataFrame

from boto3 import client

from schema.users import GetListResponseSchema, CreateResponseSchema, CreateRequestSchema, UpdateRequestSchema, \
    GetResponseSchema

router = APIRouter(prefix="/users")
per_page = 10
salt = b'$2b$12$apcpayF3r/A/kKo2dlRk8O'
BUCKET_NAME = 'brayden-online-v2-api-storage'


def hashed_data(password: str):
    return hashpw(password.encode('utf-8'), salt)


@router.post('', status_code=status.HTTP_201_CREATED, response_model=CreateResponseSchema)
async def create_user(request: Request, user: CreateRequestSchema, db: Session = Depends(get_db)):
    db.expire_on_commit = False
    # get organization id by token
    organization_id = None
    try:
        token = get_token_by_header(request)
        me = get_user_by_token(token, db)
        check_authorized_by_user(me)
        organization_id = me.organization_id
    except GetExceptionWithStatuscode as e:
        logging.error(e)
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # check email duplicate
    email_check_query = select(User).where(User.email == user.email)
    check_user = db.execute(email_check_query).scalar()
    if check_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email duplicate")

    # check user role exist if no value insert student
    if user.user_role_id is None:
        user.user_role_id = STUDENT

    password_hashed = hashed_data(user.password).decode('utf-8')
    insert_user = User(email=user.email, name=user.name, password_hashed=password_hashed, employee_id=user.employee_id,
                       user_role_id=user.user_role_id, organization_id=organization_id)
    db.add(insert_user)
    db.commit()
    db.refresh(insert_user)

    return insert_user


def validate_file_format(upload_file: UploadFile):
    # validate file format
    if '[Content_Types].xml'.encode('utf-8') not in upload_file.file.read():
        raise GetExceptionWithStatuscode(status.HTTP_400_BAD_REQUEST,
                                         'incorrect file format',
                                         ExceptionType.INCORRECT_FORMAT)

    upload_file.file.seek(0)


def validate_email(email):
    if not regex.match(r"^\S+@\S+$", email):
        return False
    return True


def validate_file_extension(name: str):
    split_name = name.split(".")
    if split_name[1] != "xlsx":
        raise GetExceptionWithStatuscode(status.HTTP_400_BAD_REQUEST,
                                         'incorrect file format',
                                         ExceptionType.INCORRECT_FORMAT)


def authorize_aws_s3():
    if os.environ.get('aws_access_key_id') and os.environ.get('aws_secret_access_key'):
        access_key = os.environ.get('aws_access_key_id')
        secret_access_key = os.environ.get('aws_secret_access_key')
        s3 = client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)
    else:
        s3 = client('s3')
    return s3


def upload_excel_to_s3(file):
    s3 = authorize_aws_s3()
    buckets = [i['Name'] for i in s3.list_buckets()['Buckets']]
    if BUCKET_NAME in buckets:
        ret = s3.upload_fileobj(file, BUCKET_NAME, file.name)
        location = s3.get_bucket_location(Bucket=BUCKET_NAME)['LocationConstraint']
        return location
    return None


def get_presigned_url_from_upload_file(filename):
    s3 = authorize_aws_s3()
    return s3.generate_presigned_url('get_object', Params={'Bucket': BUCKET_NAME, 'Key': filename}, ExpiresIn=3600)


def insert_each_user(users, organization_id, db: Session = Depends(get_db)):
    failure_count = 0
    failure_users = DataFrame()
    for i, r in users.iterrows():
        user = {}
        try:
            row_to_dict = r.to_dict()
            password_hashed = hashed_data(row_to_dict['password']).decode('utf-8')
            for key, value in row_to_dict.items():
                if key == 'password':
                    user['password_hashed'] = password_hashed
                    user['organization_id'] = organization_id
                    user['user_role_id'] = STUDENT
                    continue
                user[key] = value
            db.execute(insert(User).values(user))
            db.commit()
        except IntegrityError as e:
            logging.error(e)
            failure_count += 1
            db.rollback()
            r['reason'] = 'email duplicated'
            failure_users = failure_users._append(r, ignore_index=True)
    return failure_count, failure_users


@router.post('/upload')
async def user_upload(request: Request, file: UploadFile, db: Session = Depends(get_db)):
    file_name = 'user_upload_fail_with_reason.xlsx'
    try:
        token = get_token_by_header(request)
        me = get_user_by_token(token, db)
        check_authorized_by_user(me)
        validate_file_extension(file.filename)
        validate_file_format(file)
    except GetExceptionWithStatuscode as e:
        logging.error(e)
        raise HTTPException(status_code=e.status_code, detail=e.message)

    organization_id = me.organization_id

    df = read_excel(BytesIO(file.file.read()), engine='openpyxl')
    failure_users = DataFrame()
    failure_count = 0
    users = df.to_dict('records')
    success_count = users.__len__()
    try:
        for user in users:
            if 'user_role_id' not in user.keys():
                user['user_role_id'] = STUDENT
            if 'organization_id' not in user.keys():
                user['organization_id'] = organization_id

        return_users = db.scalars(insert(User).returning(User), users)
        # return_users = return_users.all()
        db.commit()
    except IntegrityError as e:
        # 중복 오류 발생
        logging.error(e)
        db.rollback()
        failure_count, failure_users = insert_each_user(df, organization_id, db)
        success_count = success_count - failure_count
    except Exception as e:
        print(e.__dict__)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)

    def make_excel_data_from_dataframe(failure_users, file_name):
        failure_users.to_excel(file_name, index=False)

    # 실패 사유가 담긴 파일 만들기
    url = None
    if failure_count > 0:
        failure_users.pop('employee_id')
        failure_users.pop('password')
        # 파일 생성
        make_excel_data_from_dataframe(failure_users, file_name)
        with open(file_name, 'rb') as f:
            # 파일 업로드
            if upload_excel_to_s3(f):
                # 파일 링크 얻어오기
                url = get_presigned_url_from_upload_file(f.name)
        # 생성한 파일 삭제
        os.remove(file_name)

    return {"success_count": success_count, "failure_count": failure_count,
            "failure_detail": url}


@router.get('', status_code=status.HTTP_200_OK, response_model=GetListResponseSchema)
async def get_users(request: Request, page: int = 1, search_keyword: str = None, db: Session = Depends(get_db)):
    organization_id = None
    try:
        token = get_token_by_header(request)
        me = get_user_by_token(token, db)
        organization_id = me.organization_id
    except GetExceptionWithStatuscode as e:
        logging.error(e)
        raise HTTPException(status_code=e.status_code, detail=e.message)

    def get_users_by_search_keyword(search_keyword):
        def all_users(offset: int = 0):
            query = select(User).order_by(User.id.desc()).where(
                and_(User.organization_id == organization_id, User.user_role_id == STUDENT))
            users = db.execute(query.offset(offset).fetch(per_page)).scalars().all()
            return users, query

        def filtered_users(search_keyword, offset: int = 0):
            query = (select(User).where(and_(or_(User.email.contains(search_keyword),
                                                 User.employee_id.contains(search_keyword),
                                                 User.name.contains(search_keyword)),
                                             User.organization_id == organization_id, User.user_role_id == STUDENT))
                     .order_by(User.id.desc()))
            return db.scalars(query.fetch(per_page).offset(offset)).all(), query

        offset = (page - 1) * per_page

        if search_keyword:
            users, query = filtered_users(search_keyword, offset)
        else:
            users, query = all_users(offset)

        # all user count
        filtered_data_count = db.scalar(select(func.count('*')).select_from(query))

        return {"users": users, "total": filtered_data_count, "per_page": per_page, "current_page": page}

    return get_users_by_search_keyword(search_keyword)


@router.get('/me')
async def get_my_information(request: Request, db: Session = Depends(get_db)):
    try:
        token = get_token_by_header(request)
        me = get_my_information_by_token(token, db)
        return {
            "token": me.token,
            "email": me.email,
            "name": me.name,
            "role": {
                "id": me.user_role.id,
                "title": me.user_role.role
            },
            "last_training_date": "2023-12-11",
            "certifications": {
                "adult": {
                    "expiration": "2023-11-23"
                },
                "child": {
                    "expiration": None
                },
                "baby": {
                    "expiration": "2025-11-23"
                }
            }
        }
    except GetExceptionWithStatuscode as e:
        logging.error(e)
        raise HTTPException(status_code=e.status_code, detail=e.message)


def check_permission(me, user_id, db: Session = Depends(get_db)):
    check_same_organization(user_id, me.organization_id, db)
    check_has_permission(me, user_id, db)


def check_has_permission(me, user_id, db: Session = Depends(get_db)):
    query = select(User).where(and_(User.id == user_id, User.organization_id == me.organization_id))
    user = db.execute(query).scalar()
    if user.user_role_id > me.user_role_id:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_401_UNAUTHORIZED,
                                         message='invalid permission',
                                         exception_type=ExceptionType.INVALID_PERMISSION)


@router.get('/{user_id}')
async def get_user(request: Request, user_id: int, db: Session = Depends(get_db)):
    try:
        token = get_token_by_header(request)
        me = get_my_information_by_token(token, db)
        check_permission(me, user_id, db)

        result_list = (
            db.query(User, Training, Certification, TrainingProgram).outerjoin(Training, User.id == Training.user_id)
            .outerjoin(Certification, User.id == Certification.user_id)
            .outerjoin(TrainingProgram, TrainingProgram.id == Training.training_program_id)
            .filter(User.id == user_id).order_by(Training.date.desc()))
        if not result_list:
            return None
        # recent training history
        user, training, certification, training_program = result_list[0]
        # check certification expired date
        certificate = {'adult': {'expiration': None}, 'child': {'expiration': None}, 'baby': {'expiration': None}}
        for i, result in enumerate(result_list):
            u, t, c, tp = result
            # check manikin type
            if tp and certificate[tp.manikin_type]['expiration'] is None:
                certificate[tp.manikin_type] = {"expiration": c.issued_date + timedelta(days=365)}
        # TODO compare expiration date to current date

        return {
            "name": user.name,
            "email": user.email,
            "employee_id": user.employee_id,
            "last_training_date": training.date if training else None,
            "certifications": certificate
        }
    except GetExceptionWithStatuscode as e:
        logging.error(e.message)
        raise HTTPException(e.status_code, detail=e.message)
    except GetException as e:
        if e.exception_type == ExceptionType.NOT_FOUND:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail='there is no user')


def check_same_organization(user_id, organization_id, db: Session = Depends(get_db)):
    query = select(User).where(and_(User.id == user_id, User.organization_id == organization_id))
    user = db.execute(query).scalar()
    if not user:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_401_UNAUTHORIZED,
                                         message='invalid permission',
                                         exception_type=ExceptionType.INVALID_PERMISSION)


def get_my_information_by_token(token: str, db: Session = Depends(get_db)):
    user = get_user_by_token(token, db)
    if user.token_expiration <= datetime.now():
        raise GetExceptionWithStatuscode(status_code=status.HTTP_403_FORBIDDEN,
                                         message='token is expired',
                                         exception_type=ExceptionType.INVALID_TOKEN)
    return user


def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    # get update user data
    user = db.query(User).get(user_id)
    if not user:
        raise GetException('there is no user', ExceptionType.NOT_FOUND)
    return user


@router.patch('/{user_id}', response_model=GetResponseSchema)
async def update_user(request: Request, user_id: int, user_data: UpdateRequestSchema,
                      db: Session = Depends(get_db)):
    try:
        token = get_token_by_header(request)
        me = get_user_by_token(token, db)
        # check user_id me id
        if me.id != user_id:
            check_authorized_by_user(me)
    except GetExceptionWithStatuscode as e:
        logging.error(e)
        raise HTTPException(e.status_code, detail=e.message)

    result = dict()
    user = None
    try:
        user = get_user_by_id(user_id, db)
        # update
        if user_data.name:
            user.name = user_data.name
            result['name'] = user.name
        if user_data.employee_id:
            user.employee_id = user_data.employee_id
            result['employee_id'] = user.employee_id
        db.add(user)
        db.commit()
        db.refresh(user)

    except GetException as e:
        if e.exception_type == ExceptionType.NOT_FOUND:
            logging.error(e.message)
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'there is no user')

    return user
