from fastapi import APIRouter

from . import users, authorization, training_programs, content, certifications_template

api_router = APIRouter()

api_router.include_router(users.router, tags=["users"])
api_router.include_router(authorization.router, tags=["authorization"])
api_router.include_router(training_programs.router, tags=["training-programs"])
api_router.include_router(content.router, tags=["content"])
api_router.include_router(certifications_template.router, tags=["certification_template"])
