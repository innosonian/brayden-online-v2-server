import logging

from fastapi import APIRouter, Depends, status, HTTPException, Request
from exceptions import GetException, ExceptionType
from models.model import User

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_, func

from database import get_db

from pydantic import BaseModel
router = APIRouter(prefix="/users")
per_page = 10
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
