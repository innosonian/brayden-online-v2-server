from database import Base

from sqlalchemy import Column, Integer, String, ForeignKey, DATETIME, BOOLEAN
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True)
    password_hashed = Column(String(200))
    name = Column(String(50))
    employee_id = Column(String(100))
    token = Column(String(100))
    token_expiration = Column(DATETIME)
    users_role_id = Column(Integer, ForeignKey("users_role.id"))
    organization_id = Column(Integer, ForeignKey('organization.id'))

    organization = relationship('Organization', back_populates='users')
    users_role = relationship('UserRole', back_populates='users')
    training_result = relationship('TrainingResult', back_populates='users')
    trainings = relationship('Training', back_populates='users')
    trainings_download_options = relationship('TrainingsDownloadOptions', back_populates='users')


class UserRole(Base):
    __tablename__ = "users_role"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(50), unique=True)
    users = relationship('User', back_populates="users_role")


class Organization(Base):
    __tablename__ = 'organization'

    id = Column(Integer, primary_key=True, index=True)
    organization_name = Column(String(200), unique=True)

    users = relationship('User', back_populates='organization')
    training_program = relationship('TrainingProgram', back_populates='organization')
    organization_content = relationship('OrganizationContent', back_populates='organization')
    certifications_template = relationship('CertificationsTemplate', back_populates='organization')


class CPRGuideline(Base):
    __tablename__ = "cpr_guideline"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100))
    compression_depth = Column(JSON)
    ventilation_volume = Column(JSON)

    training_program = relationship('TrainingProgram', back_populates='cpr_guideline')


class TrainingProgram(Base):
    __tablename__ = "training_program"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(50))
    manikin_type = Column(String(50))
    training_type = Column(String(50))
    feedback_type = Column(String(50))
    training_mode = Column(String(50))
    duration = Column(Integer)
    compression_limit = Column(Integer)
    cycle_limit = Column(Integer)
    ventilation_limit = Column(Integer)
    cvr_compression = Column(Integer)
    cvr_ventilation = Column(Integer)
    organization_id = Column(Integer, ForeignKey('organization.id'))
    cpr_guideline_id = Column(Integer, ForeignKey("cpr_guideline.id"))

    cpr_guideline = relationship('CPRGuideline', back_populates='training_program')
    organization = relationship('Organization', back_populates='training_program')
    training_program_content = relationship('TrainingProgramContent', back_populates='training_program')
    training_result = relationship('TrainingResult', back_populates='training_program')
    trainings = relationship('Training', back_populates='training_program')


class TrainingProgramContent(Base):
    __tablename__ = "training_program_content"

    id = Column(Integer, primary_key=True, index=True)
    s3_key = Column(String(100))
    file_name = Column(String(100))
    training_program_id = Column(Integer, ForeignKey('training_program.id'))

    training_program = relationship('TrainingProgram', back_populates='training_program_content')

    @property
    def presigned_url(self):
        # TODO: DELETE THIS
        def authorize_aws_s3():
            import os
            from boto3 import client
            if os.environ.get('aws_access_key_id') and os.environ.get('aws_secret_access_key'):
                access_key = os.environ.get('aws_access_key_id')
                secret_access_key = os.environ.get('aws_secret_access_key')
                s3 = client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)
            else:
                s3 = client('s3')
            return s3

        # TODO: DELETE THIS
        BUCKET_NAME = 'brayden-online-v2-api-storage'

        s3 = authorize_aws_s3()
        return s3.generate_presigned_url('get_object',
                                         Params={'Bucket': BUCKET_NAME,
                                                 'Key': self.s3_key},
                                         ExpiresIn=3600)

    @property
    def convert_to_schema(self):
        from schema.content import CreateResponseSchema
        return CreateResponseSchema(
            id=self.id,
            file_name=self.file_name,
            url=self.presigned_url
        )


class OrganizationContent(Base):
    __tablename__ = 'organization_content'

    id = Column(Integer, primary_key=True, index=True)
    s3_key = Column(String(100))
    file_name = Column(String(100))
    content_type = Column(String(50))
    organization_id = Column(Integer, ForeignKey('organization.id'))

    organization = relationship('Organization', back_populates='organization_content')

    @property
    def presigned_url(self):
        # TODO: DELETE THIS
        def authorize_aws_s3():
            import os
            from boto3 import client
            if os.environ.get('aws_access_key_id') and os.environ.get('aws_secret_access_key'):
                access_key = os.environ.get('aws_access_key_id')
                secret_access_key = os.environ.get('aws_secret_access_key')
                s3 = client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)
            else:
                s3 = client('s3')
            return s3

        # TODO: DELETE THIS
        BUCKET_NAME = 'brayden-online-v2-api-storage'

        s3 = authorize_aws_s3()
        return s3.generate_presigned_url('get_object',
                                         Params={'Bucket': BUCKET_NAME,
                                                 'Key': self.s3_key},
                                         ExpiresIn=3600)

    @property
    def convert_to_schema(self):
        from schema.content import CreateResponseSchema
        return CreateResponseSchema(
            id=self.id,
            file_name=self.file_name,
            url=self.presigned_url
        )


class CertificationsTemplate(Base):
    __tablename__ = 'certifications_template'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100))
    manikin_type = Column(String(50))
    organization_name = Column(String(50))
    images = Column(JSON)
    organization_id = Column(Integer, ForeignKey('organization.id'))

    organization = relationship('Organization', back_populates='certifications_template')

    @property
    def presigned_url(self):
        # TODO: DELETE THIS
        def authorize_aws_s3():
            import os
            from boto3 import client
            if os.environ.get('aws_access_key_id') and os.environ.get('aws_secret_access_key'):
                access_key = os.environ.get('aws_access_key_id')
                secret_access_key = os.environ.get('aws_secret_access_key')
                s3 = client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)
            else:
                s3 = client('s3')
            return s3

        # TODO: DELETE THIS
        BUCKET_NAME = 'brayden-online-v2-api-storage'

        s3 = authorize_aws_s3()
        images_url = dict()
        for k in self.images.keys():
            images_url[k] = None
            if self.images[k]:
                images_url[k] = s3.generate_presigned_url('get_object',
                                                          Params={'Bucket': BUCKET_NAME,
                                                                  'Key': self.images[k]},
                                                          ExpiresIn=3600)
        return images_url

    @property
    def convert_to_schema(self):
        from schema.certifications_template import GetResponseSchema
        images_url = self.presigned_url
        return GetResponseSchema(id=self.id, title=self.title, organization=self.organization, images=images_url,
                                 manikin_type=self.manikin_type)


class TrainingResult(Base):
    __tablename__ = "training_result"

    id = Column(Integer, primary_key=True, index=True)
    result = Column(JSON)
    data = Column(JSON)
    date = Column(DATETIME)
    score = Column(Integer)
    user_id = Column(Integer, ForeignKey("users.id"))
    training_program_id = Column(Integer, ForeignKey('training_program.id'))

    users = relationship("User", back_populates="training_result")
    training_program = relationship("TrainingProgram", back_populates="training_result")


class Training(Base):
    __tablename__ = "trainings"

    id = Column(Integer, primary_key=True, index=True)
    training_date = Column(DATETIME)
    training_program_id = Column(Integer, ForeignKey("training_program.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    score = Column(Integer)

    users = relationship("User", back_populates="trainings")
    training_program = relationship("TrainingProgram", back_populates="trainings")


class TrainingsDownloadOptions(Base):
    __tablename__ = "trainings_download_options"

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True, index=True)
    email = Column(BOOLEAN, default=True)
    score = Column(BOOLEAN, default=True)
    username = Column(BOOLEAN, default=True)
    datetime = Column(BOOLEAN, default=True)
    average_compression_depth = Column(BOOLEAN, default=False)
    average_hands_off_time = Column(BOOLEAN, default=False)
    compression_number = Column(BOOLEAN, default=False)
    event_time = Column(BOOLEAN, default=False)
    manikin_model = Column(BOOLEAN, default=False)
    overall_ccf = Column(BOOLEAN, default=False)
    overall_compression_no = Column(BOOLEAN, default=False)
    overall_hand_position = Column(BOOLEAN, default=False)
    overall_ventilation_rate = Column(BOOLEAN, default=False)
    overall_ventilation_volume = Column(BOOLEAN, default=False)
    average_compression_rate = Column(BOOLEAN, default=False)
    average_volume = Column(BOOLEAN, default=False)
    cycle_number = Column(BOOLEAN, default=False)
    judge_result = Column(BOOLEAN, default=False)
    overall_compression_depth = Column(BOOLEAN, default=False)
    overall_compression_rate = Column(BOOLEAN, default=False)
    overall_recoil = Column(BOOLEAN, default=False)
    overall_ventilation_speed = Column(BOOLEAN, default=False)
    percentage_ccf = Column(BOOLEAN, default=False)
    target = Column(BOOLEAN, default=False)
    type = Column(BOOLEAN, default=False)
    device_id = Column(BOOLEAN, default=False)
    name = Column(BOOLEAN, default=False)

    users = relationship('User', back_populates='trainings_download_options')
