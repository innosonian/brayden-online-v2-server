from pydantic import BaseModel


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
    user_role_id: int | None


class UserUpdateRequestSchema(BaseModel):
    name: str = None
    employee_id: str = None
