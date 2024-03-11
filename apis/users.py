import os

from fastapi import APIRouter, Depends
from models.model import User

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_, func

from database import get_db

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
