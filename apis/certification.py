import logging
import os
from datetime import timedelta, datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from sqlalchemy.orm import Session
from sqlalchemy.sql import select, and_

from database import get_db
from exceptions import GetExceptionWithStatuscode, ExceptionType

from boto3 import client
from pyhtml2pdf import converter

from models.model import CertificationsTemplate, User, Certification, Training, TrainingProgram

router = APIRouter(prefix='/certifications')
BUCKET_NAME = 'brayden-online-v2-api-storage'


def save_certification(issued_certification):
    # save update format
    with open('certificate_download_format_update.html', 'w') as f:
        f.write(issued_certification)


def get_certification_template_by_manikin_type(db, manikin_type):
    # get certification template data
    query = select(CertificationsTemplate).where(CertificationsTemplate.manikin_type == manikin_type)
    template = db.scalar(query)
    if not template:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         message="there is no user",
                                         exception_type=ExceptionType.NOT_FOUND)
    return template


def read_certificate_download_format():
    with open('certificate_download_format.html', 'r') as f:
        issued_certificate_format = f.read()
    return issued_certificate_format


def convert_html_to_pdf():
    html_path = os.path.abspath('certificate_download_format_update.html')
    file_name = 'issued_certificate.pdf'
    converter.convert(f'file:///{html_path}', file_name, print_options={"landscape": True})
    return file_name


def authorize_aws_s3():
    if os.environ.get('aws_access_key_id') and os.environ.get('aws_secret_access_key'):
        access_key = os.environ.get('aws_access_key_id')
        secret_access_key = os.environ.get('aws_secret_access_key')
        s3 = client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)
    else:
        s3 = client('s3')
    return s3


def get_presigned_url_from_upload_file(filename):
    if not filename:
        return
    s3 = authorize_aws_s3()
    return s3.generate_presigned_url('get_object', Params={'Bucket': BUCKET_NAME, 'Key': filename}, ExpiresIn=3600)


def replace_certificate_format_from_data(issued_certificate_format, template, user):
    class DefaultTemplateIdentifier(Enum):
        user_name = 'user_name'
        certification = 'certification_title'
        manikin_type = 'manikin_type'
        organization_name = 'organization_name'
        formatted_date = 'formatted_date'

    # assign certificate format to certification template, user data
    result = issued_certificate_format

    # TODO 리팩토링 해야함!
    for idx, str in enumerate([user.name,
                               template.title if template.title else "",
                               template.manikin_type,
                               template.organization_name,
                               '2023-12-20']):
        result = result.replace([e.value for e in DefaultTemplateIdentifier][idx], str)
    # get image url from s3
    if template.images['top_left']:
        result = (result.replace
                  ('top_left',
                   f"\"{get_presigned_url_from_upload_file(template.images['top_left'])}\""))
    else:
        result = result.replace('<img class="logo" src=top_left alt="로고">', "")
    if template.images['top_right']:
        result = (result.replace
                  ('top_right',
                   f"\"{get_presigned_url_from_upload_file(template.images['top_right'])}\""))
    else:
        result = result.replace('<img class="logo" src=top_right alt="로고">', "")
    if template.images['bottom_left']:
        result = (result.replace
                  ('bottom_left',
                   f"\"{get_presigned_url_from_upload_file(template.images['bottom_left'])}\""))
    else:
        result = result.replace('<img class="logo" src=bottom_left alt="로고">', "")
    if template.images['bottom_right']:
        result = (result.replace
                  ('bottom_right',
                   f"\"{get_presigned_url_from_upload_file(template.images['bottom_right'])}\""))
    else:
        result = result.replace('<img class="logo" src=bottom_right alt="로고">', "")
    return result


def check_expired_certificates(certification: Certification):
    if certification.issued_date + timedelta(days=365) <= datetime.now():
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         message="Certification expired",
                                         exception_type=ExceptionType.NOT_MATCHED)
    return


def get_user_by_id(user_id: int, manikin_type: str, db: Session = Depends(get_db)):
    # 다운받기 전 발급받은 인증서가 있는지 확인
    users = (db.query(User, Certification, Training, TrainingProgram)
             .outerjoin(Training, User.id == Training.user_id)
             .outerjoin(TrainingProgram, TrainingProgram.id == Training.training_program_id)
             .outerjoin(Certification, Certification.training_id == Training.id)
             .filter(and_(User.id == user_id, TrainingProgram.manikin_type == manikin_type))
             .order_by(Training.date.desc()))
    user, certification, training, training_program = users[0]
    if not user:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         message="there is no user",
                                         exception_type=ExceptionType.NOT_FOUND)
    # 다운받기 전 인증서 기한이 만료됐는지 확인
    check_expired_certificates(certification)
    return user


@router.get('/download/{user_id}')
def get_issued_certificate(user_id: int, manikin_type: str = 'adult', db: Session = Depends(get_db)):
    try:
        user = get_user_by_id(user_id, manikin_type, db)
        template = get_certification_template_by_manikin_type(db, manikin_type)
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.NOT_FOUND:
            logging.error(e)
            raise HTTPException(e.status_code, e.message)
        return
    except Exception as e:
        print(e)
        return

    issued_certificate_format = replace_certificate_format_from_data(read_certificate_download_format(),
                                                                     template,
                                                                     user)

    save_certification(issued_certificate_format)

    file_name = convert_html_to_pdf()

    return FileResponse(file_name)
