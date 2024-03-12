from database import Base

from sqlalchemy import Column, Integer, String, ForeignKey, DATETIME
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
