from fastapi import status, Request, Depends
from exceptions import GetExceptionWithStatuscode, ExceptionType
from models import User

from sqlalchemy.orm import Session
from sqlalchemy import select

from database import get_db

AUTHORIZATION = 'Authorization'
ADMIN = 3
STUDENT = 1


def get_token_by_header(request: Request):
    headers = request.headers
    if AUTHORIZATION not in headers:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         message='invalid token',
                                         exception_type=ExceptionType.INVALID_TOKEN
                                         )
    return headers.get(AUTHORIZATION)


def get_user_by_token(token: str, db: Session = Depends(get_db)) -> User:
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


def check_authorized_by_user(user: User):
    if not user:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         exception_type=ExceptionType.NOT_MATCHED,
                                         message='there is no user')
    elif user.user_role_id == STUDENT:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_401_UNAUTHORIZED,
                                         exception_type=ExceptionType.INVALID_PERMISSION,
                                         message='no authorization')

    return user


def check_admin_authorized_by_user(user: User):
    if not user:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         exception_type=ExceptionType.NOT_MATCHED,
                                         message='there is no user')
    elif user.user_role_id != ADMIN:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_401_UNAUTHORIZED,
                                         exception_type=ExceptionType.INVALID_PERMISSION,
                                         message='no authorization')
    return user
