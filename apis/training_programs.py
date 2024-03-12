import logging

from fastapi import APIRouter, Depends, status, HTTPException

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import select, and_, update

from database import get_db
from exceptions import GetExceptionWithStatuscode, ExceptionType
from models import TrainingProgram
from schema.cpr_guideline import ResponseSchema

from schema.training_program import CreateRequestSchema, CreateResponseSchema, GetResponseSchema, UpdateRequestSchema

router = APIRouter(prefix='/training-programs')

#TODO training program을 작업할 때 권한 확인
@router.post('', response_model=CreateResponseSchema, status_code=status.HTTP_201_CREATED)
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


def check_exist_training_program(id: int, db: Session = Depends(get_db)):
    query = select(TrainingProgram).where(TrainingProgram.id == id)
    training_program = db.scalar(query)
    if not training_program:
        raise GetExceptionWithStatuscode(
            status_code=status.HTTP_404_NOT_FOUND,
            message="there is no training program",
            exception_type=ExceptionType.NOT_FOUND)
    return training_program


@router.put('/{training_program_id}')
async def update_training_program(training_program_id: int, data: UpdateRequestSchema,
                                  db: Session = Depends(get_db)):
    try:
        training_program = check_exist_training_program(training_program_id, db)
        training_data = dict()
        #TODO 데이터 변환을 어떻게 하면 좋을지
        if data.compression_ventilation_ratio:
            cvr = data.compression_ventilation_ratio
            split_cvr = cvr.split(':')
            training_data['cvr_compression'] = split_cvr[0]
            training_data['cvr_ventilation'] = split_cvr[1]

        training_data['title'] = training_program.title
        training_data['manikin_type'] = training_program.manikin_type
        training_data['cpr_guideline_id'] = training_program.cpr_guideline_id
        training_data['training_type'] = training_program.training_type
        training_data['feedback_type'] = training_program.feedback_type
        training_data['training_mode'] = training_program.training_mode
        training_data['duration'] = training_program.duration
        training_data['compression_limit'] = training_program.compression_limit
        training_data['cycle_limit'] = training_program.cycle_limit
        training_data['ventilation_limit'] = training_program.ventilation_limit
        training_data['organization_id'] = training_program.organization_id
        # data.organization_id = user.organization_id

        parameter = data.__dict__
        for k in parameter.keys():
            if parameter[k] is not None:
                if k == 'compression_ventilation_ratio':
                    continue
                training_data[k] = parameter[k]

        query = (update(TrainingProgram).where(TrainingProgram.id == training_program_id).values(training_data))
        db.execute(query)
        db.commit()

        return db.get(TrainingProgram, training_program_id)
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.NOT_FOUND:
            raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logging.error(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Internal Server Error')


@router.delete('/{training_program_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_training_program(training_program_id: int, db: Session = Depends(get_db)):
    try:
        training_program = check_exist_training_program(training_program_id, db)
        db.delete(training_program)
        db.commit()
        return
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.NOT_FOUND:
            raise HTTPException(status_code=e.status_code, detail=e.message)
