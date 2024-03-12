from pydantic import BaseModel


class CreateResponseSchema(BaseModel):
    id: int
    file_name: str
    url: str
