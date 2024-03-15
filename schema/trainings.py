from datetime import datetime

from models.model import Training, TrainingProgram, User
from pydantic import BaseModel
from schema.cpr_guideline import ResponseSchema


class TrainingBaseResponseSchema:
    id: int
    datetime: datetime
    is_passed: bool
    guide_prompt: list[str]
    score: dict
    training_data: dict

    def __init__(self, training_result: Training):
        self.id = training_result.id
        self.datetime = training_result.date
        self.guide_prompt = training_result.result["guide_prompt"]
        self.score = training_result.result['score']
        self.training_data = training_result.data
        self.is_passed = training_result.result['is_passed']


class TrainingProgramResponseSchema:
    id: int
    title: str | None = None
    manikin_type: str | None = None
    # training_type: str | None = None
    feedback_type: str | None = None
    training_mode: str | None = None
    duration: int | None = None
    compression_limit: int | None = None
    cycle_limit: int | None = None
    ventilation_limit: int | None = None
    cvr_compression: int | None = None
    cvr_ventilation: int | None = None
    compression_ventilation_ratio: str | None = None
    cpr_guideline: ResponseSchema | None = None

    def __init__(self, training_program: TrainingProgram):
        self.id = training_program.id
        self.title = training_program.title
        self.manikin_type = training_program.manikin_type
        self.feedback_type = training_program.feedback_type
        self.training_mode = training_program.training_mode
        self.duration = training_program.duration
        self.compression_limit = training_program.compression_limit
        self.cycle_limit = training_program.cycle_limit
        self.ventilation_limit = training_program.ventilation_limit
        self.cvr_compression = training_program.cvr_compression
        self.cvr_ventilation = training_program.cvr_ventilation
        self.compression_ventilation_ratio = \
            f'{training_program.cvr_compression}:{training_program.cvr_ventilation}' if training_program.cvr_ventilation and training_program.cvr_compression else None
        self.cpr_guideline = ResponseSchema(id=training_program.cpr_guideline.id,
                                            title=training_program.cpr_guideline.title,
                                            compression_depth=training_program.cpr_guideline.compression_depth,
                                            ventilation_volume=training_program.cpr_guideline.ventilation_volume)


class UserSchema:
    id: int
    email: str
    name: str
    employee_id: str
    organization_id: int
    user_role_id: int

    def __init__(self, user: User):
        self.id = user.id
        self.email = user.email
        self.name = user.name
        self.employee_id = user.employee_id
        self.organization_id = user.organization_id
        self.user_role_id = user.user_role_id


class TrainingProgramDetailSchema(TrainingProgramResponseSchema):
    training_type: str

    def __init__(self, training_program: TrainingProgram):
        super().__init__(training_program)
        self.training_type = training_program.training_type


class TrainingResponseSchema(TrainingBaseResponseSchema):
    training_program: TrainingProgramDetailSchema
    user: UserSchema

    def __init__(self, training_result: Training):
        super().__init__(training_result)
        self.training_program = TrainingProgramDetailSchema(training_result.training_program)
        self.user = UserSchema(training_result.user)


class TrainingResultResponseSchema(TrainingBaseResponseSchema):
    training_program: TrainingProgramResponseSchema
    user: UserSchema

    def __init__(self, training_result: Training):
        super().__init__(training_result)
        self.training_program = TrainingProgramResponseSchema(training_result.training_program)
        self.user = UserSchema(training_result.user)


class TrainingProgramLimitSchema(TrainingProgramResponseSchema):
    training_type: str
    feedback_type: str
    training_mode: str
    duration: int
    cycle_limit: int
    compression_limit: int
    ventilation_limit: int

    def __init__(self, training_program: TrainingProgram):
        super().__init__(training_program)
        self.training_type = training_program.training_type
        self.feedback_type = training_program.feedback_type
        self.training_mode = training_program.training_mode
        self.duration = training_program.duration
        self.cycle_limit = training_program.cycle_limit
        self.compression_limit = training_program.compression_limit
        self.ventilation_limit = training_program.ventilation_limit


class TrainingListSchema:
    id: int
    training_date: datetime
    training_program: TrainingProgramLimitSchema
    user: UserSchema
    score: int

    def __init__(self, training_result: Training):
        self.id = training_result.id
        self.training_date = training_result.date
        self.training_program = TrainingProgramLimitSchema(training_result.training_program)
        self.user = UserSchema(training_result.user)
        self.score = training_result.score
