import os

from fastapi import APIRouter, Depends
from models.model import User

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from database import get_db

router = APIRouter(prefix="/users")
per_page = 10


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
