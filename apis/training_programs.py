from fastapi import APIRouter, Depends, status

from sqlalchemy.orm import Session

from database import get_db
from models import TrainingProgram

from schema.training_program import CreateRequestSchema, CreateResponseSchema

router = APIRouter(prefix='/training-programs')


@router.post('', response_model=CreateResponseSchema)
async def create_training_program(data: CreateRequestSchema, db: Session = Depends(get_db)):
    training_program = data.convert_to_model

    db.add(training_program)
    db.commit()
    db.refresh(training_program)
    return training_program
