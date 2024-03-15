from pydantic import BaseModel


class ContentCreateResponseSchema(BaseModel):
    id: int
    file_name: str
    url: str
