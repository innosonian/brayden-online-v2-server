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
from models.model import Training, TrainingsDownloadOptions
from schema.trainings import TrainingResultResponseSchema, TrainingListSchema, TrainingResponseSchema

router = APIRouter(prefix='/trainings')

per_page = 30


class CreateRequestSchema(BaseModel):
    training_program_id: int
    rawHexBPfile: UploadFile
    training_data: str

    @classmethod
    def as_form(cls, training_program_id: int = Form(...), rawHexBPfile: Optional[UploadFile] = None,
                training_data: str = Form(...)):
        return cls(training_program_id=training_program_id, rawHexBPfile=rawHexBPfile, training_data=training_data)


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

    trainings = Training(score=total_score, date=create_epoch, result=training_result_data,
                         data=json.loads(training_data.training_data), user_id=user.id,
                         training_program_id=training_data.training_program_id)

    db.add(trainings)
    db.commit()
    db.refresh(trainings)

    query = (select(Training).where(Training.id == trainings.id)
             .options(joinedload(Training.user)).options(joinedload(Training.training_program)))
    training_result = db.scalar(query)
    return TrainingResultResponseSchema(training_result)


def make_dataframe_from_list(data: list, column: list):
    return DataFrame(data, columns=column)


def store_training_data_to_excel(training_data: list, column: list):
    file_name = 'training_records.xlsx'
    # dataframe from model list
    dataframe = make_dataframe_from_list(training_data, column)
    # make excel
    dataframe.to_excel(file_name)
    return file_name


def get_columns_from_options(option: TrainingsDownloadOptions):
    column = []
    if option.email:
        column.append('email')
    if option.datetime:
        column.append('datetime')
    if option.username:
        column.append('username')
    if option.score:
        column.append('score')
    if option.overall_ccf:
        column.append('overall_ccf')
    if option.overall_recoil:
        column.append('overall_recoil')
    if option.overall_hand_position:
        column.append('overall_hand_position')
    if option.overall_compression_depth:
        column.append('overall_compression_depth')
    if option.overall_compression_rate:
        column.append('overall_compression_rate')
    if option.overall_ventilation_rate:
        column.append('overall_ventilation_rate')
    if option.overall_ventilation_volume:
        column.append('overall_ventilation_volume')
    if option.judge_result:
        column.append('judge_result')
    if option.manikin_model:
        column.append('manikin_model')
    if option.event_time:
        column.append('event_time')
    if option.compression_number:
        column.append('compression_number')
    if option.overall_ventilation_speed:
        column.append('overall_ventilation_speed')
    if option.target:
        column.append('target')
    if option.device_id:
        column.append('device_id')
    if option.name:
        column.append('name')
    if option.average_volume:
        column.append('average_volume')
    if option.average_hands_off_time:
        column.append('average_hands_off_time')
    if option.average_compression_rate:
        column.append('average_compression_rate')
    if option.average_compression_depth:
        column.append('average_compression_depth')
    if option.cycle_number:
        column.append('cycle_number')
    if option.percentage_ccf:
        column.append('percentage_ccf')

    return column


def choose_training_data_from_options(training_data: list, option: TrainingsDownloadOptions):
    result = []
    for data in training_data:
        result_data = {}
        # TODO 쓸데없이 고정 데이터 넣은거 제거
        if option.email:
            result_data['email'] = data.users.email
        if option.datetime:
            result_data['datetime'] = data.date
        if option.username:
            result_data['username'] = data.users.name
        if option.score:
            result_data['score'] = data.score
        if option.overall_ccf:
            result_data['overall_ccf'] = data.result['score']['ccf']
        if option.overall_recoil:
            result_data['overall_recoil'] = data.result['score']['compression_recoil']
        if option.overall_hand_position:
            result_data['overall_hand_position'] = data.result['score']['handposition']
        if option.overall_compression_depth:
            result_data['overall_compression_depth'] = data.result['score']['compression_depth']
        if option.overall_compression_rate:
            result_data['overall_compression_rate'] = data.result['score']['compression_rate']
        if option.overall_ventilation_rate:
            result_data['overall_ventilation_rate'] = data.result['score']['ventilation_rate']
        if option.overall_ventilation_volume:
            result_data['overall_ventilation_volume'] = data.result['score']['ventilation_volume']
        if option.judge_result:
            result_data['judge_result'] = data.result['is_passed']
        if option.manikin_model:
            result_data['manikin_model'] = 'Adult'
        if option.event_time:
            result_data['event_time'] = '2024-01-09'
        if option.compression_number:
            result_data['compression_number'] = 90
        if option.overall_ventilation_speed:
            result_data['overall_ventilation_speed'] = 90
        if option.target:
            result_data['target'] = 'SDL'
        if option.device_id:
            result_data['device_id'] = 's11se1'
        if option.name:
            result_data['name'] = 'skfn'
        if option.average_volume:
            result_data['average_volume'] = 80
        if option.average_hands_off_time:
            result_data['average_hands_off_time'] = 82
        if option.average_compression_rate:
            result_data['average_compression_rate'] = 77
        if option.average_compression_depth:
            result_data['average_compression_depth'] = 73
        if option.cycle_number:
            result_data['cycle_number'] = 3
        if option.percentage_ccf:
            result_data['percentage_ccf'] = 90
        result.append(result_data)
    return result


@router.get('/download')
async def download_file(request: Request, start_date: str = None, end_date: str = None, db: Session = Depends(get_db)):
    token = request.headers['Authorization']
    user_select_query = select(User).where(User.token == token)
    user = db.scalar(user_select_query)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    options = db.query(TrainingsDownloadOptions).get(user.id)
    if not options:
        # create options
        options = TrainingsDownloadOptions(user_id=user.id)
        db.add(options)
        db.commit()
        db.refresh(options)

    query = (select(Training)
             .options(joinedload(Training.training_program).joinedload(TrainingProgram.cpr_guideline))
             .options(joinedload(Training.user)))

    if start_date:
        datetime_start_date = start_date_to_datetime(start_date)
        query = query.where(Training.date >= datetime_start_date)
    if end_date:
        datetime_end_date = end_date_to_datetime(end_date)
        query = query.where(Training.date <= datetime_end_date)

    query = query.order_by(Training.id.desc())
    training_data = db.scalars(query).all()
    # choose training history from option
    column = get_columns_from_options(options)
    data = choose_training_data_from_options(training_data, options)

    file_name = store_training_data_to_excel(data, column)
    return FileResponse(file_name, filename="records.xlsx")


@router.post('/download/options')
def add_download_options(options: dict, request: Request, db: Session = Depends(get_db)):
    token = request.headers['Authorization']
    user_select_query = select(User).where(User.token == token)
    user = db.scalar(user_select_query)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    download_options = TrainingsDownloadOptions(user_id=user.id, email=options['email'], score=options['score'],
                                                username=options['username'], datetime=options['datetime'],
                                                average_compression_depth=options['average_compression_depth'],
                                                average_hands_off_time=options['average_hands_off_time'],
                                                compression_number=options['compression_number'],
                                                event_time=options['event_time'],
                                                manikin_model=options['manikin_model'],
                                                overall_ccf=options['overall_ccf'],
                                                overall_compression_no=options['overall_compression_no'],
                                                overall_hand_position=options['overall_hand_position'],
                                                overall_ventilation_rate=options['overall_ventilation_rate'],
                                                overall_ventilation_volume=options['overall_ventilation_volume'],
                                                average_compression_rate=options['average_compression_rate'],
                                                average_volume=options['average_volume'],
                                                cycle_number=options['cycle_number'],
                                                judge_result=options['judge_result'],
                                                overall_compression_depth=options['overall_compression_depth'],
                                                overall_compression_rate=options['overall_compression_rate'],
                                                overall_recoil=options['overall_recoil'],
                                                overall_ventilation_speed=options['overall_ventilation_speed'],
                                                percentage_ccf=options['percentage_ccf'],
                                                target=options['target'],
                                                type=options['type'],
                                                device_id=options['device_id'],
                                                name=options['name']
                                                )
    db.add(download_options)
    db.commit()
    db.refresh(download_options)
    return download_options


@router.get('/download/options')
def get_download_options(request: Request, db: Session = Depends(get_db)):
    token = request.headers['Authorization']
    user_select_query = select(User).where(User.token == token)
    user = db.scalar(user_select_query)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    option_select_query = select(TrainingsDownloadOptions).where(user.id == TrainingsDownloadOptions.user_id)
    options = db.scalar(option_select_query)
    if not options:
        new_options = TrainingsDownloadOptions(user_id=user.id)
        db.add(new_options)
        db.commit()
        db.refresh(new_options)
        return new_options

    return options


@router.put('/download/options')
def update_download_options(options_param: dict, request: Request, db: Session = Depends(get_db)):
    token = request.headers['Authorization']
    user_select_query = select(User).where(User.token == token)
    user = db.scalar(user_select_query)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    option_select_query = select(TrainingsDownloadOptions).where(user.id == TrainingsDownloadOptions.user_id)
    options = db.scalar(option_select_query)
    options.user_id = user.id
    options.email = options_param['email']
    options.score = options_param['score']
    options.username = options_param['username']
    options.datetime = options_param['datetime']
    options.average_compression_depth = options_param['average_compression_depth']
    options.average_hands_off_time = options_param['average_hands_off_time']
    options.compression_number = options_param['compression_number']
    options.event_time = options_param['event_time']
    options.manikin_model = options_param['manikin_model']
    options.overall_ccf = options_param['overall_ccf']
    options.overall_compression_no = options_param['overall_compression_no']
    options.overall_hand_position = options_param['overall_hand_position']
    options.overall_ventilation_rate = options_param['overall_ventilation_rate']
    options.overall_ventilation_volume = options_param['overall_ventilation_volume']
    options.average_compression_rate = options_param['average_compression_rate']
    options.average_volume = options_param['average_volume']
    options.cycle_number = options_param['cycle_number']
    options.judge_result = options_param['judge_result']
    options.overall_compression_depth = options_param['overall_compression_depth']
    options.overall_compression_rate = options_param['overall_compression_rate']
    options.overall_recoil = options_param['overall_recoil']
    options.overall_ventilation_speed = options_param['overall_ventilation_speed']
    options.percentage_ccf = options_param['percentage_ccf']
    options.target = options_param['target']
    options.type = options_param['type']

    db.add(options)
    db.commit()
    db.refresh(options)

    return options


def start_date_to_datetime(start_date):
    return datetime.strptime(start_date, "%Y-%m-%d")


def datetime_to_str(date_time: datetime):
    return date_time.strftime("%Y-%m-%dT%H:%M:%S")


def end_date_to_datetime(end_date):
    return datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)


@router.get('')
async def get_trainings(page: int = 1, user_id: int = None, start_date: str = None, end_date: str = None,
                        db: Session = Depends(get_db)):
    offset = (page - 1) * per_page

    query = (select(Training).options(joinedload(Training.user))
             .options(joinedload(Training.training_program)))
    if user_id:
        query = query.where(Training.user_id == user_id)

    if start_date:
        datetime_start_date = start_date_to_datetime(start_date)
        query = query.where(Training.date >= datetime_start_date)
    if end_date:
        datetime_end_date = end_date_to_datetime(end_date)
        query = query.where(Training.date <= datetime_end_date)

    filtered_data_count = db.scalar(select(func.count('*')).select_from(query))

    query = query.offset(offset).fetch(per_page).order_by(Training.id.desc())
    training_data = db.scalars(query).all()
    result = []
    for t in training_data:
        result.append(TrainingListSchema(t))

    return {"records": result, "total": filtered_data_count, "per_page": per_page, "current_page": page}


@router.get("/{training_id}")
async def get_training(training_id: int, db: Session = Depends(get_db)):
    training_result = (db.query(Training).options(joinedload(Training.user))
                       .options(joinedload(Training.training_program)).get(training_id))
    if not training_result:
        return None

    return TrainingResponseSchema(training_result)
