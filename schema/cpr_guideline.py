from pydantic import BaseModel


class ResponseSchema(BaseModel):
    title: str | None = None
    compression_depth: dict | None = None
    ventilation_volume: dict | None = None
