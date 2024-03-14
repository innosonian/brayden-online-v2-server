import os
from fastapi import APIRouter, status, Depends, UploadFile, HTTPException, Request

from sqlalchemy.orm import Session
from sqlalchemy.sql import select, and_

from datetime import datetime
from database import get_db

from boto3 import client

from exceptions import GetExceptionWithStatuscode, ExceptionType
from models.model import TrainingProgramContent, OrganizationContent, User
from schema.content import CreateResponseSchema

router = APIRouter(prefix='/contents')

BUCKET_NAME = 'brayden-online-v2-api-storage'


def authorize_aws_s3():
    if os.environ.get('aws_access_key_id') and os.environ.get('aws_secret_access_key'):
        access_key = os.environ.get('aws_access_key_id')
        secret_access_key = os.environ.get('aws_secret_access_key')
        s3 = client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)
    else:
        s3 = client('s3')
    return s3


# TODO common file로 따로 빼놓기
def get_milliseconds():
    current_time = datetime.now()
    # 밀리초로 변환
    return int(current_time.timestamp() * 1000)


def upload_file_to_s3(file: UploadFile):
    s3 = authorize_aws_s3()
    buckets = [i['Name'] for i in s3.list_buckets()['Buckets']]
    if BUCKET_NAME in buckets:
        base_name, extension = os.path.splitext(file.filename)
        dir = 'content/'
        key = f"{dir}{base_name}_{get_milliseconds()}{extension}"

        ret = s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=file.file)
        if ret:
            return key
        else:
            return False
    return False


def check_exist_token(request: Request):
    headers = request.headers
    if 'Authorization' not in headers:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         message='invalid token',
                                         exception_type=ExceptionType.INVALID_TOKEN
                                         )
    return headers.get('Authorization')


def get_user_by_token(token: str, db: Session = Depends(get_db)):
    if not token:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         exception_type=ExceptionType.INVALID_TOKEN,
                                         message='invalid token')

    select_query = select(User).where(User.token == token)
    user = db.scalar(select_query)
    if not user:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         exception_type=ExceptionType.NOT_MATCHED,
                                         message='there is no user')
    return user

def get_authorized_user_by_token(token: str, db: Session = Depends(get_db)):
    if not token:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         exception_type=ExceptionType.INVALID_TOKEN,
                                         message='invalid token')

    select_query = select(User).where(User.token == token)
    user = db.scalar(select_query)
    if not user:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         exception_type=ExceptionType.NOT_MATCHED,
                                         message='there is no user')
    elif user.user_role_id != 3:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_401_UNAUTHORIZED,
                                         exception_type=ExceptionType.INVALID_PERMISSION,
                                         message='no authorization')

    return user


@router.post('/training-programs', status_code=status.HTTP_201_CREATED, response_model=CreateResponseSchema)
async def create_training_content(request: Request, content: UploadFile, db: Session = Depends(get_db)):
    try:
        token = check_exist_token(request)
        get_authorized_user_by_token(token, db)
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.INVALID_PERMISSION:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_MATCHED:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.INVALID_TOKEN:
            raise HTTPException(e.status_code, e.message)
        return

    # upload file to s3
    s3_key = upload_file_to_s3(content)
    if not s3_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='could not upload file')

    # db insert
    training_content = TrainingProgramContent(s3_key=s3_key, file_name=content.filename)
    db.add(training_content)
    db.commit()
    db.refresh(training_content)

    return training_content.convert_to_schema


def check_exist_training_content(content_id: int, db: Session = Depends(get_db)):
    query = select(TrainingProgramContent).where(TrainingProgramContent.id == content_id)
    training_content = db.execute(query).scalar()
    if training_content is None:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         message='there is no content',
                                         exception_type=ExceptionType.NOT_FOUND)
    return training_content


@router.get('/training-programs/{content_id}', response_model=CreateResponseSchema)
async def get_training_content(request: Request, content_id: int, db: Session = Depends(get_db)):
    try:
        token = check_exist_token(request)
        get_user_by_token(token, db)

        training_content = check_exist_training_content(content_id, db)
        return training_content.convert_to_schema
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.INVALID_PERMISSION:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_MATCHED:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.INVALID_TOKEN:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_FOUND:
            return None
        return


@router.delete('/training-programs/{content_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_training_content(request: Request, content_id: int, db: Session = Depends(get_db)):
    try:
        token = check_exist_token(request)
        get_authorized_user_by_token(token, db)

        training_content = check_exist_training_content(content_id, db)
        db.delete(training_content)

        # s3 delete
        s3 = authorize_aws_s3()
        ret = s3.delete_object(Bucket=BUCKET_NAME, Key=training_content.s3_key)
        db.commit()
        return
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.INVALID_PERMISSION:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_MATCHED:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.INVALID_TOKEN:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_FOUND:
            return None
        else:
            raise HTTPException(e.status_code, detail=e.message)


@router.post('/manikin_connected/{manikin_type}', status_code=status.HTTP_201_CREATED,
             response_model=CreateResponseSchema)
async def create_manikin_connected(request: Request, manikin_type: str, content: UploadFile,
                                   db: Session = Depends(get_db)):
    try:
        token = check_exist_token(request)
        user = get_authorized_user_by_token(token, db)

    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.INVALID_PERMISSION:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_MATCHED:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.INVALID_TOKEN:
            raise HTTPException(e.status_code, e.message)
        return

    # upload file to s3
    s3_key = upload_file_to_s3(content)
    if not s3_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='could not upload file')

    # db insert
    organization_content = OrganizationContent(s3_key=s3_key, file_name=content.filename,
                                               content_type=f'manikin_connected_{manikin_type}',
                                               organization_id=user.organization_id)
    db.add(organization_content)
    db.commit()
    db.refresh(organization_content)

    return organization_content.convert_to_schema


@router.get('/manikin_connected/{content_id}')
async def get_manikin_connected(request: Request, content_id: int, db: Session = Depends(get_db)):
    try:
        token = check_exist_token(request)
        user = get_user_by_token(token, db)

    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.INVALID_PERMISSION:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_MATCHED:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.INVALID_TOKEN:
            raise HTTPException(e.status_code, e.message)
        return

    query = select(OrganizationContent).where(
        and_(OrganizationContent.id == content_id, OrganizationContent.organization_id == user.organization_id))

    organization_content = db.execute(query).scalar()
    if organization_content:
        return organization_content.convert_to_schema
    else:
        return None


def check_exist_organization_content(content_id: int, db: Session = Depends(get_db)):
    query = select(OrganizationContent).where(OrganizationContent.id == content_id)
    organization_content = db.execute(query).scalar()
    if organization_content is None:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         message='there is no content',
                                         exception_type=ExceptionType.NOT_FOUND)
    return organization_content


@router.delete('/manikin_connected/{content_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_manikin_connected(request: Request, content_id: int, db: Session = Depends(get_db)):
    try:
        token = check_exist_token(request)
        get_authorized_user_by_token(token, db)
        organization_content = check_exist_organization_content(content_id, db)
        db.delete(organization_content)

        # s3 delete
        s3 = authorize_aws_s3()
        ret = s3.delete_object(Bucket=BUCKET_NAME, Key=organization_content.s3_key)
        db.commit()
        return
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.INVALID_PERMISSION:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_MATCHED:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.INVALID_TOKEN:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_FOUND:
            raise HTTPException(e.status_code, detail=e.message)
        return


@router.post('/login', status_code=status.HTTP_201_CREATED, response_model=CreateResponseSchema)
async def create_login_content(request: Request, content: UploadFile, db: Session = Depends(get_db)):
    try:
        token = check_exist_token(request)
        user = get_authorized_user_by_token(token, db)

    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.INVALID_PERMISSION:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_MATCHED:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.INVALID_TOKEN:
            raise HTTPException(e.status_code, e.message)
        return
    # upload file to s3
    s3_key = upload_file_to_s3(content)
    if not s3_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='could not upload file')

    # db insert

    login_content = OrganizationContent(s3_key=s3_key, file_name=content.filename,
                                        content_type='login', organization_id=user.organization_id)
    db.add(login_content)
    db.commit()
    db.refresh(login_content)

    return login_content.convert_to_schema


@router.get('/login/{content_id}')
async def get_login_content(request: Request, content_id: int, db: Session = Depends(get_db)):
    try:
        token = check_exist_token(request)
        get_user_by_token(token, db)

        login_content = check_exist_organization_content(content_id, db)
        return login_content.convert_to_schema
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.INVALID_PERMISSION:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_MATCHED:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.INVALID_TOKEN:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_FOUND:
            return None
        return


@router.delete('/login/{content_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_login_content(request: Request, content_id: int, db: Session = Depends(get_db)):
    try:
        token = check_exist_token(request)
        get_authorized_user_by_token(token, db)

        organization_content = check_exist_organization_content(content_id, db)
        db.delete(organization_content)

        # s3 delete
        s3 = authorize_aws_s3()
        ret = s3.delete_object(Bucket=BUCKET_NAME, Key=organization_content.s3_key)
        db.commit()
        return
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.INVALID_PERMISSION:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_MATCHED:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.INVALID_TOKEN:
            raise HTTPException(e.status_code, e.message)
        elif e.exception_type == ExceptionType.NOT_FOUND:
            raise HTTPException(e.status_code, detail=e.message)

        return
