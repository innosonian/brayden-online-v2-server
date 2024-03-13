from datetime import datetime

from models.model import TrainingResult, TrainingProgram, User


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


class TrainingProgramDetailSchema(TrainingProgramResponseSchema):
    training_type: str

    def __init__(self, training_program: TrainingProgram):
        super().__init__(training_program)
        self.training_type = training_program.training_type


class TrainingResponseSchema(TrainingBaseResponseSchema):
    training_program: TrainingProgramDetailSchema
    user: UserSchema

    def __init__(self, training_result: TrainingResult):
        super().__init__(training_result)
        self.training_program = TrainingProgramDetailSchema(training_result.training_program)
        self.user = UserSchema(training_result.users)


class TrainingResultResponseSchema(TrainingBaseResponseSchema):
    training_program: TrainingProgramResponseSchema
    user: UserSchema

    def __init__(self, training_result: TrainingResult):
        super().__init__(training_result)
        self.training_program = TrainingProgramResponseSchema(training_result.training_program)
        self.user = UserSchema(training_result.users)


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

    def __init__(self, training_result: TrainingResult):
        self.id = training_result.id
        self.training_date = training_result.date
        self.training_program = TrainingProgramLimitSchema(training_result.training_program)
        self.user = UserSchema(training_result.users)
        self.score = training_result.score
