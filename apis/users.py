import logging
import os

import regex
from fastapi import APIRouter, Depends, status, HTTPException, Request, UploadFile

from exceptions import GetException, ExceptionType, GetExceptionWithStatuscode
from models.model import User

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_, func, insert

from bcrypt import hashpw

from database import get_db
from pandas import read_excel, DataFrame

from boto3 import client

from schema.users import GetListResponseSchema, CreateResponseSchema, CreateRequestSchema, UpdateRequestSchema

router = APIRouter(prefix="/users")
per_page = 10
salt = b'$2b$12$apcpayF3r/A/kKo2dlRk8O'
BUCKET_NAME = 'brayden-online-v2-api-storage'


def get_token_by_header(headers):
    if 'Authorization' not in headers:
        raise GetExceptionWithStatuscode(status.HTTP_401_UNAUTHORIZED,
                                         'there is no token',
                                         ExceptionType.INVALID_TOKEN)
    return headers.get('Authorization')


@router.post('', status_code=status.HTTP_201_CREATED, response_model=CreateResponseSchema)
async def create_user(request: Request, user: CreateRequestSchema, db: Session = Depends(get_db)):
    db.expire_on_commit = False
    # get organization id by token
    organization_id = None
    try:
        token = get_token_by_header(request.headers)
        me = get_user_by_token(token, db)
        organization_id = me.organization_id
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.INVALID_TOKEN:
            logging.error(e.message)
            raise HTTPException(e.status_code, detail=e.message)
    except GetException as e:
        if e.exception_type == ExceptionType.INVALID_TOKEN:
            logging.error(e.message)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'invalid token')
        elif e.exception_type == ExceptionType.INVALID_PERMISSION:
            logging.error(e.message)
            raise HTTPException(status.HTTP_403_FORBIDDEN, 'invalid token')
        elif e.exception_type == ExceptionType.NOT_FOUND:
            logging.error(e.message)
            raise HTTPException(status.HTTP_404_NOT_FOUND, 'there is no user')

    # check email duplicate
    email_check_query = select(User).where(User.email == user.email)
    check_user = db.execute(email_check_query).scalar()
    if check_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email duplicate")

    def hashed_password(password: str):
        return hashpw(password.encode('utf-8'), salt)

    # check user role exist if no value insert student
    if user.user_role_id is None:
        user.user_role_id = 1

    password_hashed = hashed_password(user.password).decode('utf-8')
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


@router.post('/upload')
async def user_upload(request: Request, file: UploadFile, db: Session = Depends(get_db)):
    file_name = 'user_upload_fail_with_reason.xlsx'
    try:
        token = get_token_by_header(request.headers)
        me = get_user_by_token(token, db)
        validate_file_extension(file.filename)
        validate_file_format(file)
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.INCORRECT_FORMAT:
            logging.error(e)
            raise HTTPException(e.status_code, detail=e.message)
        elif e.exception_type == ExceptionType.INVALID_TOKEN:
            logging.error(e)
            raise HTTPException(e.status_code, e.message)
    except GetException as e:
        if e.exception_type == ExceptionType.INVALID_TOKEN:
            logging.error(e)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
        elif e.exception_type == ExceptionType.NOT_FOUND:
            logging.error(e)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)

    organization_id = me.organization_id

    users = read_excel(file.file.read())
    failure_users = DataFrame()
    failure_count = 0
    success_count = 0
    # 삽입
    for i, r in users.iterrows():
        user = {}
        # DB에 있는 이메일과 중복되는지 확인
        # TODO bulk로 넣고 실패한 걸 체크하는 방향으로 가야함.
        if db.scalar(select(User).where(User.email == r['email'])):
            failure_count += 1
            r['reason'] = 'email duplicated'
            failure_users = failure_users._append(r, ignore_index=True)
            continue
        if not validate_email(r['email']):
            failure_count += 1
            r['reason'] = 'email invalid'
            failure_users = failure_users._append(r, ignore_index=True)
            continue

        for k, v in r.items():
            if k == 'password':
                v = hashpw(v.encode('utf-8'), salt).decode('utf-8')
                k = "password_hashed"
                user['organization_id'] = organization_id
            user[k] = v

        ret = db.execute(insert(User).values(user))
        if ret.rowcount == 1:
            success_count += 1
        else:
            failure_count += 1
            r['reason'] = 'insert fail'
            failure_users = failure_users._append(r, ignore_index=True)

    def make_excel_data_from_dataframe(failure_users, file_name):
        failure_users.to_excel(file_name)

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
    db.commit()

    return {"success_count": success_count, "failure_count": failure_count,
            "failure_detail": url}


@router.get('', status_code=status.HTTP_200_OK, response_model=GetListResponseSchema)
async def get_users(page: int = 1, search_keyword: str = None, db: Session = Depends(get_db)):
    def get_users_by_search_keyword(search_keyword):
        def all_users(offset: int = 0):
            query = select(User).order_by(User.id.desc()).offset(offset).fetch(per_page)
            users = db.execute(query).scalars().all()
            return users, query

        def filtered_users(search_keyword, offset: int = 0):
            query = (select(User).where(or_(User.email.contains(search_keyword),
                                            User.employee_id.contains(search_keyword),
                                            User.name.contains(search_keyword))).order_by(User.id.desc()))
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


@router.get('/{user_id}')
async def get_user(user_id: int, db: Session = Depends(get_db)):
    # options(joinedload(User.training_result))
    query = select(User).where(User.id == user_id)
    user = db.execute(query).scalar()
    if not user:
        return None

    return user
    # if user.training_result:
    #     date = user.training_result.pop().date
    # else:
    #     date = None
    # return {
    #     "name": user.name,
    #     "email": user.email,
    #     "employee_id": user.employee_id,
    #     "last_training_date": date,
    #     "certifications": {
    #         "adult": {
    #             "expiration": "2023-11-23"
    #         },
    #         "child": {
    #             "expiration": None
    #         },
    #         "baby": {
    #             "expiration": "2025-11-23"
    #         }
    #     }
    # }


def get_user_by_token(token: str, db: Session = Depends(get_db)):
    if not token:
        raise GetException('invalid token', ExceptionType.INVALID_TOKEN)
    select_user = select(User).options(joinedload(User.user_role)).where(User.token == token)
    user = db.scalar(select_user)
    if not user:
        raise GetException("invalid token", ExceptionType.NOT_FOUND)
    return user


def check_user_permission(user: User):
    if user.user_role.role != 'administrator':
        raise GetException('invalid token', ExceptionType.INVALID_PERMISSION)


def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    # get update user data
    user = db.query(User).get(user_id)
    if not user:
        raise GetException('there is no user', ExceptionType.NOT_FOUND)
    return user


@router.patch('/{user_id}')
async def update_user(request: Request, user_id: int, user_data: UpdateRequestSchema,
                      db: Session = Depends(get_db)):
    try:
        token = get_token_by_header(request.headers)
        me = get_user_by_token(token, db)
        # check user_id me id
        if me.id != user_id:
            check_user_permission(me)
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.INVALID_TOKEN:
            raise HTTPException(e.status_code, e.message)
    except GetException as e:
        if e.exception_type == ExceptionType.INVALID_TOKEN:
            logging.error(e.message)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'invalid token')
        elif e.exception_type == ExceptionType.INVALID_PERMISSION:
            logging.error(e.message)
            raise HTTPException(status.HTTP_403_FORBIDDEN, 'invalid token')

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
