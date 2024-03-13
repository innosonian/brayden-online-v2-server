import json
from datetime import datetime

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, Form
from fastapi.responses import FileResponse

import requests

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import select, func

from pydantic import BaseModel

from pandas import DataFrame, Timestamp

from database import get_db
from models import User, TrainingProgram
from models.model import TrainingResult

router = APIRouter(prefix='/trainings')


class CreateRequestSchema(BaseModel):
    training_program_id: int
    rawHexBPfile: UploadFile
    training_data: str

    @classmethod
    def as_form(cls, training_program_id: int = Form(...), rawHexBPfile: Optional[UploadFile] = None,
                training_data: str = Form(...)):
        return cls(training_program_id=training_program_id, rawHexBPfile=rawHexBPfile, training_data=training_data)


class TrainingBaseResponseSchema:
    id: int
    datetime: datetime
    is_passed: bool
    guide_prompt: list[str]
    score: dict
    training_data: dict

    def __init__(self, training_result: TrainingResult):
        self.id = training_result.id
        self.datetime = training_result.date
        self.guide_prompt = training_result.result["guide_prompt"]
        self.score = training_result.result['score']
        self.training_data = training_result.data
        self.is_passed = training_result.result['is_passed']


class TrainingProgramResponseSchema:
    title: str
    manikin_type: str
    id: int
    cpr_guideline: dict

    def __init__(self, training_program: TrainingProgram):
        self.id = training_program.id
        self.title = training_program.title
        self.cpr_guideline = training_program.cpr_guideline
        self.manikin_type = training_program.manikin_type


class UserSchema:
    email: str
    name: str
    employee_id: str

    def __init__(self, user: User):
        self.email = user.email
        self.name = user.name
        self.employee_id = user.employee_id


class TrainingResultResponseSchema(TrainingBaseResponseSchema):
    training_program: TrainingProgramResponseSchema
    user: UserSchema

    def __init__(self, training_result: TrainingResult):
        super().__init__(training_result)
        self.training_program = TrainingProgramResponseSchema(training_result.training_program)
        self.user = UserSchema(training_result.users)


def get_calculate_type_from_training_type(training_type: str):
    # TODO 키에 해당하는 값이 없을 때 예외처리 필요
    calculate_type = {
        'chest compression only': 'Chest compression only',
        'ventilation only': 'Ventilation only',
        'CPR Training': 'CPR Training'
    }
    return calculate_type[training_type]


def is_training(training_mode: str):
    if training_mode in ['dry-run', 'assessment']:
        return True

    return False


@router.post('', status_code=status.HTTP_201_CREATED)
async def create_training(request: Request, training_data: CreateRequestSchema = Depends(CreateRequestSchema.as_form),
                          db: Session = Depends(get_db)):
    token = request.headers["Authorization"]
    timestamp = Timestamp(datetime.now())
    # get user by token
    query = select(User).where(User.token == token)
    user = db.scalar(query)

    # get training program
    query = (select(TrainingProgram).options(joinedload(TrainingProgram.cpr_guideline))
             .where(TrainingProgram.id == training_data.training_program_id))
    training_program = db.scalar(query)

    # make calculate json file
    with open('genk-adult-pass_train_condition.json', 'r') as f:
        data = json.load(f)
        data["Usage"]["Email"] = user.email
        data["Usage"]["Type"] = get_calculate_type_from_training_type(training_program.training_type)
        data["Usage"]["Timestamp"] = int(timestamp.timestamp())
        data["Usage"]["CreateEpoch"] = int(timestamp.timestamp())
        data["Custom"]["TrainCourse"]["Certification"] = is_training(training_program.training_mode)
        data["Custom"]["TrainCourse"]["Guideline"] = training_program.cpr_guideline.title
        data["Custom"]["TrainCourse"]["Feedback"] = training_program.feedback_type
        data["Custom"]["TrainCourse"]["Type"] = get_calculate_type_from_training_type(training_program.training_type)
        data["Custom"]["TrainCourse"]["CardTitle"] = training_program.title

    files = [('data', ('genk-adult-pass_train_condition.json', json.dumps(data), 'application/json')),
             ('rawHexBPfile', ('genk-adult-pass_rawHexBPfile.bin', training_data.rawHexBPfile.file,
                               'application/octet-stream'))]
    response = requests.post("https://beta.braydenonline.cc/cpr-sequence-analysis",
                             headers={}, files=files, data={})
    response_data = json.loads(response.content)
    # make datetime
    create_epoch = datetime.fromtimestamp(response_data['Usage']['Timestamp'])

    # extract score
    total_score = response_data['ResultByCycle']['ScoreByCycle']['Overall']

    # process calculate data
    training_result_data = dict()
    training_result_data['guide_prompt'] = response_data['Guide_prompts']

    is_passed = None
    if is_training(training_program.training_mode):
        is_passed = False if response_data['ResultSummary']['JudgResult'] == 'Fail' else True
    training_result_data['is_passed'] = is_passed
    training_result_data['score'] = {}
    training_result_data['score']['total'] = response_data['ResultByCycle']['ScoreByCycle']['Overall']

    replace = json.dumps(response_data).replace('N/A', "Not Applicable")
    response_data = json.loads(replace)
    if response_data['ResultByCycle']:
        if response_data['ResultByCycle']['Recoil'] \
                and response_data['ResultByCycle']['Recoil']['Overall'] is not None:
            training_result_data['score']['compression_recoil'] = \
                response_data['ResultByCycle']['Recoil']['Overall']
        else:
            training_result_data['score']['compression_recoil'] = None

        if response_data['ResultByCycle']['CompressionDepth'] \
                and response_data['ResultByCycle']['CompressionDepth']['Overall'] is not None:
            training_result_data['score']['compression_depth'] = \
                response_data['ResultByCycle']['CompressionDepth']['Overall']
        else:
            training_result_data['score']['compression_depth'] = None

        if response_data['ResultByCycle']['CompressionRate'] \
                and response_data['ResultByCycle']['CompressionRate']['Overall'] is not None:
            training_result_data['score']['compression_rate'] = \
                response_data['ResultByCycle']['CompressionRate']['Overall']
        else:
            training_result_data['score']['compression_rate'] = None

        if response_data['ResultByCycle']['VentilationVolume'] \
                and response_data['ResultByCycle']['VentilationVolume']['Overall'] is not None:
            training_result_data['score']['ventilation_volume'] = \
                response_data['ResultByCycle']['VentilationVolume']['Overall']
        else:
            training_result_data['score']['ventilation_volume'] = None

        if response_data['ResultByCycle']['VentilationRate'] \
                and response_data['ResultByCycle']['VentilationRate']['Overall'] is not None:
            training_result_data['score']['ventilation_rate'] = \
                response_data['ResultByCycle']['VentilationRate']['Overall']
        else:
            training_result_data['score']['ventilation_rate'] = None

        if response_data['ResultByCycle']['HandPosition'] \
                and response_data['ResultByCycle']['HandPosition']['Overall'] is not None:
            training_result_data['score']['handposition'] = \
                response_data['ResultByCycle']['HandPosition']['Overall']
        else:
            training_result_data['score']['handposition'] = None

        if response_data['ResultByCycle']['ScoreOfCCF'] \
                and response_data['ResultByCycle']['ScoreOfCCF'] != "Not Applicable" \
                and response_data['ResultByCycle']['ScoreOfCCF']['Overall'] is not None:
            # print(response_data['ResultByCycle']['ScoreOfCCF'])
            training_result_data['score']['ccf'] = response_data['ResultByCycle']['ScoreOfCCF']['Overall']
        else:
            training_result_data['score']['ccf'] = None
    cycle_length = len(response_data['ResultByCycle']['ScoreByCycle']['ByCycle'])
    training_result_data['score']['by_cycle'] = []

    for cycle in range(cycle_length):
        by_cycle = dict()
        if response_data['ResultByCycle'] \
                and response_data['ResultByCycle']['ScoreByCycle'] \
                and response_data['ResultByCycle']['ScoreByCycle']['ByCycle'] \
                and response_data['ResultByCycle']['ScoreByCycle']['ByCycle'][cycle] is not None:
            by_cycle['total'] = response_data['ResultByCycle']['ScoreByCycle']['ByCycle'][cycle]
        else:
            by_cycle['total'] = None

        if response_data['ResultByCycle'] \
                and response_data['ResultByCycle']['ScoreOfCCF'] \
                and response_data['ResultByCycle']['ScoreOfCCF'] != "Not Applicable" \
                and response_data['ResultByCycle']['ScoreOfCCF']['ByCycle'] \
                and response_data['ResultByCycle']['ScoreOfCCF']['ByCycle'][cycle] is not None:
            by_cycle['ccf'] = response_data['ResultByCycle']['ScoreOfCCF']['ByCycle'][cycle]
        else:
            by_cycle['ccf'] = None

        if response_data['ResultByCycle'] \
                and response_data['ResultByCycle']['Recoil'] \
                and response_data['ResultByCycle']['Recoil']['ByCycle'] \
                and response_data['ResultByCycle']['Recoil']['ByCycle'][cycle] is not None:
            by_cycle['compression_recoil'] = response_data['ResultByCycle']['Recoil']['ByCycle'][cycle]
        else:
            by_cycle['compression_recoil'] = None

        if response_data['ResultByCycle'] \
                and response_data['ResultByCycle']['CompressionDepth'] \
                and response_data['ResultByCycle']['CompressionDepth']['ByCycle'] \
                and response_data['ResultByCycle']['CompressionDepth']['ByCycle'][cycle] is not None:
            by_cycle['compression_depth'] = \
                response_data['ResultByCycle']['CompressionDepth']['ByCycle'][cycle]
        else:
            by_cycle['compression_depth'] = None

        if response_data['ResultByCycle'] \
                and response_data['ResultByCycle']['CompressionRate'] \
                and response_data['ResultByCycle']['CompressionRate']['ByCycle'] \
                and response_data['ResultByCycle']['CompressionRate']['ByCycle'][cycle] is not None:
            by_cycle['compression_rate'] = \
                response_data['ResultByCycle']['CompressionRate']['ByCycle'][cycle]
        else:
            by_cycle['compression_rate'] = None

        if response_data['ResultByCycle'] \
                and response_data['ResultByCycle']['VentilationVolume'] \
                and response_data['ResultByCycle']['VentilationVolume']['ByCycle'] \
                and response_data['ResultByCycle']['VentilationVolume']['ByCycle'][cycle] is not None:
            by_cycle['ventilation_volume'] = \
                response_data['ResultByCycle']['VentilationVolume']['ByCycle'][cycle]
        else:
            by_cycle['ventilation_volume'] = None

        if response_data['ResultByCycle'] \
                and response_data['ResultByCycle']['VentilationRate'] \
                and response_data['ResultByCycle']['VentilationRate']['ByCycle'] \
                and response_data['ResultByCycle']['VentilationRate']['ByCycle'][cycle] is not None:
            by_cycle['ventilation_rate'] = \
                response_data['ResultByCycle']['VentilationRate']['ByCycle'][cycle]
        else:
            by_cycle['ventilation_rate'] = None

        if response_data['ResultByCycle'] \
                and response_data['ResultByCycle']['HandPosition'] \
                and response_data['ResultByCycle']['HandPosition']['ByCycle'] \
                and response_data['ResultByCycle']['HandPosition']['ByCycle'][cycle] is not None:
            by_cycle['handposition'] = response_data['ResultByCycle']['HandPosition']['ByCycle'][cycle]
        else:
            by_cycle['handposition'] = None

        training_result_data['score']['by_cycle'].append(by_cycle)

    trainings = TrainingResult(score=total_score, date=create_epoch, result=training_result_data,
                               data=json.loads(training_data.training_data), user_id=user.id,
                               training_program_id=training_data.training_program_id)

    db.add(trainings)
    db.commit()
    db.refresh(trainings)

    query = (select(TrainingResult).where(TrainingResult.id == trainings.id)
             .options(joinedload(TrainingResult.users)).options(joinedload(TrainingResult.training_program)))
    training_result = db.scalar(query)
    return TrainingResultResponseSchema(training_result)
