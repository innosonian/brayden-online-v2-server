from pydantic import BaseModel


class LoginRequestSchema(BaseModel):
    email: str
    password: str


class BaseResponseSchema(BaseModel):
    email: str
    name: str
    token: str
    id: int


class RoleResponse(BaseModel):
    id: int
    title: str


class UserResponseSchema(BaseResponseSchema):
    role: RoleResponse
