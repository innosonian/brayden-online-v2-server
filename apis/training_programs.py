from fastapi import APIRouter, Depends, status

from pydantic import BaseModel

from sqlalchemy.orm import Session

from database import get_db
from models import TrainingProgram

router = APIRouter(prefix='/training-programs')


class CreateRequestSchema(BaseModel):
    title: str | None = None
    manikin_type: str | None = None
    training_type: str | None = None
    feedback_type: str | None = None
    training_mode: str | None = None
    duration: int | None = None
    compression_limit: int | None = None
    cycle_limit: int | None = None
    ventilation_limit: int | None = None
    per_compression: int | None = None
    per_ventilation: int | None = None
    organization_id: int
    cpr_guideline_id: int


@router.post('', response_model=CreateRequestSchema)
async def create_training_program(data: CreateRequestSchema, db: Session = Depends(get_db)):
    training_program = TrainingProgram(
        title=data.title,
        manikin_type=data.manikin_type,
        training_type=data.training_type,
        feedback_type=data.feedback_type,
        training_mode=data.training_mode,
        duration=data.duration,
        compression_limit=data.compression_limit,
        cycle_limit=data.cycle_limit,
        ventilation_limit=data.ventilation_limit,
        per_compression=data.per_compression,
        per_ventilation=data.per_ventilation,
        cpr_guideline_id=data.cpr_guideline_id if data.cpr_guideline_id else 2,
        organization_id=data.organization_id
    )

    db.add(training_program)
    db.commit()
    db.refresh(training_program)
    return training_program
