from fastapi import APIRouter

from . import users, authorization

api_router = APIRouter()

api_router.include_router(users.router, tags=["users"])
api_router.include_router(authorization.router, tags=["authorization"])