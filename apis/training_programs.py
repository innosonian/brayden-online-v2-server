from fastapi import APIRouter, Depends, status

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import select

from database import get_db
from models import TrainingProgram
from schema.cpr_guideline import ResponseSchema

from schema.training_program import CreateRequestSchema, CreateResponseSchema, GetResponseSchema

router = APIRouter(prefix='/training-programs')


@router.post('', response_model=CreateResponseSchema)
async def create_training_program(data: CreateRequestSchema, db: Session = Depends(get_db)):
    training_program = data.convert_to_model

    db.add(training_program)
    db.commit()
    db.refresh(training_program)
    return training_program


def convert_model_to_cpr_guideline(training_program: TrainingProgram):
    return ResponseSchema(title=training_program.cpr_guideline.title,
                          compression_depth=training_program.cpr_guideline.compression_depth,
                          ventilation_volume=training_program.cpr_guideline.ventilation_volume)


def convert_model_to_get_response_schema(training_program: TrainingProgram):
    return GetResponseSchema(
        id=training_program.id,
        title=training_program.title,
        manikin_type=training_program.manikin_type,
        training_type=training_program.training_type,
        feedback_type=training_program.feedback_type,
        training_mode=training_program.training_mode,
        duration=training_program.duration,
        compression_limit=training_program.compression_limit,
        cycle_limit=training_program.cycle_limit,
        ventilation_limit=training_program.ventilation_limit,
        cvr_compression=training_program.cvr_compression,
        cvr_ventilation=training_program.cvr_ventilation,
        compression_ventilation_ratio=
        f'{training_program.cvr_compression}:{training_program.cvr_ventilation}' if training_program.cvr_ventilation and training_program.cvr_compression else None,
        cpr_guideline=convert_model_to_cpr_guideline(training_program)
    )


@router.get('', response_model=list[GetResponseSchema])
async def get_training_programs(db: Session = Depends(get_db)):
    query = select(TrainingProgram).options(joinedload(TrainingProgram.cpr_guideline))
    training_programs = db.execute(query).scalars().all()
    return [convert_model_to_get_response_schema(t) for t in training_programs]
