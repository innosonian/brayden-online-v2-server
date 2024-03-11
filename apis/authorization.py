from fastapi import APIRouter, HTTPException, Depends, status

from models import User
from database import get_db
from bcrypt import checkpw

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from uuid import uuid1
from datetime import datetime, timedelta

from pydantic import BaseModel

router = APIRouter()


class LoginRequestSchema(BaseModel):
    email: str
    password: str


class LoginResponseSchema(BaseModel):
    email: str
    name: str
    token: str
    id: int


def get_user_by_email(email, db: Session = Depends(get_db)):
    query = select(User).options(joinedload(User.users_role)).where(email == User.email)
    return db.scalar(query)


def validate_login_data(user, password):
    if not user:
        raise HTTPException(
            status_code=403, detail="not matched id or password")

    if not checkpw(password.encode('utf-8'), user.password_hashed.encode('utf-8')):
        raise HTTPException(
            status_code=403, detail="not matched id or password")

    return user


@router.post('/login', status_code=status.HTTP_200_OK, response_model=LoginResponseSchema)
async def login(login_data: LoginRequestSchema, db: Session = Depends(get_db)):
    user_by_email = get_user_by_email(login_data.email, db)
    user = validate_login_data(user_by_email, login_data.password)
    # insert token value
    token = uuid1().__str__()
    user.token = token
    # 구체적인 토큰 유효기간 정책이 정해지지 않았으므로 긴 유효기간으로 설정
    user.token_expiration = datetime.now() + timedelta(days=365 * 999)

    db.add(user)
    db.commit()
    return user
