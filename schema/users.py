from pydantic import BaseModel


class CreateRequestSchema(BaseModel):
    email: str
    password: str
    password_confirm: str
    name: str = None
    employee_id: str = None
    user_role_id: int = None


class CreateResponseSchema(BaseModel):
    id: int
    email: str
    name: str
    employee_id: str | None
    user_role_id: int | None


class UpdateRequestSchema(BaseModel):
    name: str = None
    employee_id: str = None


class GetResponseSchema(BaseModel):
    id: int
    email: str
    name: str
    organization_id: int
    employee_id: str | None
    user_role_id: int | None


class GetListResponseSchema(BaseModel):
    users: list[GetResponseSchema]
    total: int
    per_page: int
    current_page: int
