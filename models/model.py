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


class CPRGuideline(Base):
    __tablename__ = "cpr_guideline"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100))
    compression_depth = Column(JSON)
    ventilation_volume = Column(JSON)
