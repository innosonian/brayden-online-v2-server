import logging

from fastapi import APIRouter, Depends, status, HTTPException, Request

from exceptions import GetException, ExceptionType
from models.model import User

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_, func

from bcrypt import hashpw

from database import get_db

from pydantic import BaseModel

router = APIRouter(prefix="/users")
per_page = 10
salt = b'$2b$12$apcpayF3r/A/kKo2dlRk8O'


class UserCreateRequestSchema(BaseModel):
    email: str
    password: str
    password_confirm: str
    name: str = None
    employee_id: str = None
    user_role_id: int = None


class UserCreateResponseSchema(BaseModel):
    id: int
    email: str
    name: str
    employee_id: str | None
    users_role_id: int | None


@router.post('', status_code=status.HTTP_201_CREATED, response_model=UserCreateResponseSchema)
async def create_user(request: Request, user: UserCreateRequestSchema, db: Session = Depends(get_db)):
    db.expire_on_commit = False
    # get organization id by token
    token = request.headers.get('Authorization')
    organization_id = None
    try:
        me = get_user_by_token(token, db)
        organization_id = me.organization_id
    except GetException as e:
        if e.exception_type == ExceptionType.INVALID_TOKEN:
            logging.error(e.message)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'invalid token')
        elif e.exception_type == ExceptionType.INVALID_PERMISSION:
            logging.error(e.message)
            raise HTTPException(status.HTTP_403_FORBIDDEN, 'invalid token')

    # check email duplicate
    email_check_query = select(User).where(User.email == user.email)
    check_user = db.execute(email_check_query).scalar()
    if check_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email duplicate")


    def hashed_password(password: str):
        return hashpw(password.encode('utf-8'), salt)

    password_hashed = hashed_password(user.password).decode('utf-8')
    insert_user = User(email=user.email, name=user.name, password_hashed=password_hashed, employee_id=user.employee_id,
                       users_role_id=user.user_role_id, organization_id=organization_id)
    db.add(insert_user)
    db.commit()
    db.refresh(insert_user)

    return insert_user


@router.get('', status_code=status.HTTP_200_OK)
async def get_users(page: int = 1, search_keyword: str = None, db: Session = Depends(get_db)):
    def get_users_by_search_keyword(search_keyword):
        def all_users(limit: int, offset: int = 0):
            query = select(User).order_by(User.id.desc())
            return db.scalars(query.offset(offset).limit(limit)).all(), query

        def filtered_users(search_keyword, limit: int, offset: int = 0):
            query = (select(User).where(or_(User.email.contains(search_keyword),
                                            User.employee_id.contains(search_keyword),
                                            User.name.contains(search_keyword))).order_by(User.id.desc()))
            return db.scalars(query.limit(limit).offset(offset)).all(), query

        offset = (page - 1) * per_page
        limit = page * per_page

        if search_keyword:
            users, query = filtered_users(search_keyword, limit, offset)
        else:
            users, query = all_users(limit, offset)

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
    select_user = select(User).options(joinedload(User.users_role)).where(User.token == token)
    user = db.scalar(select_user)
    if not user:
        raise GetException("invalid token", ExceptionType.NOT_FOUND)
    return user


def check_user_permission(user: User):
    if user.users_role.role != 'administrator':
        raise GetException('invalid token', ExceptionType.INVALID_PERMISSION)


def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    # get update user data
    user = db.query(User).get(user_id)
    if not user:
        raise GetException('there is no user', ExceptionType.NOT_FOUND)
    return user


class UserUpdateRequestSchema(BaseModel):
    name: str = None
    employee_id: str = None


@router.patch('/{user_id}')
async def update_user(request: Request, user_id: int, user_data: UserUpdateRequestSchema,
                      db: Session = Depends(get_db)):
    token = request.headers.get('Authorization')
    try:
        me = get_user_by_token(token, db)
        # check user_id me id
        if me.id != user_id:
            check_user_permission(me)

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
