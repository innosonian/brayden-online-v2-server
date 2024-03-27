import logging

from fastapi import APIRouter, HTTPException, Depends, status

from exceptions import ExceptionType, GetExceptionWithStatuscode
from models import User
from database import get_db
from bcrypt import checkpw

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from uuid import uuid1
from datetime import datetime, timedelta

from schema.authorization import RoleResponse, UserResponseSchema, LoginRequestSchema

router = APIRouter()


def convert_to_schema(user: User):
    if not user:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         message='user not found',
                                         exception_type=ExceptionType.NOT_FOUND)
    role = RoleResponse(
        id=user.user_role.id,
        title=user.user_role.role
    )
    return UserResponseSchema(
        email=user.email,
        name=user.name,
        token=user.token,
        id=user.id,
        role=role
    )


def get_user_by_email(email, db: Session = Depends(get_db)):
    query = select(User).options(joinedload(User.user_role)).where(email == User.email)
    return db.scalar(query)


def validate_login_data(user, password):
    if not user:
        raise GetExceptionWithStatuscode(status.HTTP_403_FORBIDDEN,
                                         'not matched id or password',
                                         ExceptionType.NOT_MATCHED)

    if not checkpw(password.encode('utf-8'), user.password_hashed.encode('utf-8')):
        raise GetExceptionWithStatuscode(status.HTTP_403_FORBIDDEN,
                                         'not matched id or password',
                                         ExceptionType.NOT_MATCHED)
    return user


@router.post('/login', status_code=status.HTTP_200_OK, response_model=UserResponseSchema)
async def login(login_data: LoginRequestSchema, db: Session = Depends(get_db)):
    try:
        user_by_email = get_user_by_email(login_data.email, db)
        user = validate_login_data(user_by_email, login_data.password)
        # insert token value
        token = uuid1().__str__()
        user.token = token
        # 구체적인 토큰 유효기간 정책이 정해지지 않았으므로 긴 유효기간으로 설정
        user.token_expiration = datetime.now() + timedelta(days=365 * 999)

        db.add(user)
        db.commit()
        return convert_to_schema(user)
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.NOT_MATCHED:
            logging.error(e.message)
            raise HTTPException(e.status_code, detail=e.message)
        elif e.exception_type == ExceptionType.NOT_FOUND:
            logging.error(e)
            raise HTTPException(e.status_code, detail=e.message)


def check_admin_by_role(user):
    if not user.user_role or user.user_role.role != 'administrator' or user.user_role.role != 'instructor':
        raise GetExceptionWithStatuscode(status.HTTP_401_UNAUTHORIZED,
                                         'login fail',
                                         ExceptionType.INVALID_PERMISSION)


@router.post('/login/admin', response_model=UserResponseSchema)
async def admin_login(login_data: LoginRequestSchema, db: Session = Depends(get_db)):
    try:
        user_by_email = get_user_by_email(login_data.email, db)
        user = validate_login_data(user_by_email, login_data.password)
        check_admin_by_role(user)

        # insert token value
        token = uuid1().__str__()
        user.token = token
        # 구체적인 토큰 유효기간 정책이 정해지지 않았으므로 긴 유효기간으로 설정
        user.token_expiration = datetime.now() + timedelta(days=365 * 999)

        db.add(user)
        db.commit()
        return convert_to_schema(user)
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.NOT_MATCHED:
            logging.error(e.message)
            raise HTTPException(e.status_code, detail=e.message)
        elif e.exception_type == ExceptionType.INVALID_PERMISSION:
            logging.error(e.message)
            raise HTTPException(e.status_code, detail=e.message)


