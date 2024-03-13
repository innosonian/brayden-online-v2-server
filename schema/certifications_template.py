from typing import Optional

from pydantic import BaseModel
from fastapi import UploadFile

class CertificationImages(BaseModel):
    top_left: str | None
    top_right: str | None
    bottom_left: str | None
    bottom_right: str | None


class GetResponseSchema(BaseModel):
    id: int
    title: str
    organization: str
    manikin_type: str
    images: CertificationImages | None


class UpdateRequestSchema(BaseModel):
    title: Optional[str]
    top_left: Optional[UploadFile]
    top_right: Optional[UploadFile]
    bottom_left: Optional[UploadFile]
    bottom_right: Optional[UploadFile]

    @classmethod
    def as_form(cls, title: Optional[str] = None, top_right: Optional[UploadFile] = None,
                top_left: Optional[UploadFile] = None, bottom_left: Optional[UploadFile] = None,
                bottom_right: Optional[UploadFile] = None):
        return cls(title=title, top_left=top_left, top_right=top_right, bottom_left=bottom_left,
                   bottom_right=bottom_right)