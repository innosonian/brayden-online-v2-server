from fastapi import APIRouter, Depends, Request, HTTPException, status

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from database import get_db

from datetime import datetime

from models import User

router = APIRouter(prefix='/accounts')


@router.get('')
def get_my_account_info(request: Request, db: Session = Depends(get_db)):
    token = request.headers['Authorization']
    query = select(User).where(and_(User.token == token, User.token_expiration > datetime.now()))
    user = db.scalar(query)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    # TODO token refresh
    return {
        "token": user.token,
        "email": user.email,
        "name": user.name,
        "role": {
            "id": user.users_role.id,
            "title": user.users_role.role
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
