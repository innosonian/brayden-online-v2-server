import logging
import os
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, status, HTTPException, Request, Depends, UploadFile
from fastapi.responses import FileResponse

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import select, and_, update

from database import get_db
from exceptions import GetExceptionWithStatuscode, ExceptionType
from models.model import CertificationsTemplate, User

from schema.certifications_template import GetResponseSchema, UpdateRequestSchema
from boto3 import client

from pyhtml2pdf import converter

router = APIRouter(prefix='/certifications_template')

BUCKET_NAME = 'brayden-online-v2-api-storage'


def check_authorization(request: Request, db: Session = Depends(get_db)):
    headers = request.headers
    if not headers.get('Authorization'):
        raise GetExceptionWithStatuscode(status_code=status.HTTP_403_FORBIDDEN,
                                         exception_type=ExceptionType.NOT_FOUND,
                                         message='Authorization')
    token = headers.get('Authorization')
    token_query = select(User).where(User.token == token)
    user = db.scalar(token_query)
    if not user:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_401_UNAUTHORIZED,
                                         exception_type=ExceptionType.INVALID_TOKEN,
                                         message='invalid token')
    return user


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


def get_milliseconds():
    current_time = datetime.now()
    # 밀리초로 변환
    return int(current_time.timestamp() * 1000)


def upload_file_to_s3(file: UploadFile):
    s3 = authorize_aws_s3()
    buckets = [i['Name'] for i in s3.list_buckets()['Buckets']]
    if BUCKET_NAME in buckets:
        ret = s3.put_object(Bucket=BUCKET_NAME, Key=file.filename, Body=file.file)
        location = s3.get_bucket_location(Bucket=BUCKET_NAME)['LocationConstraint']
        return location
    return False


def upload_file_and_get_presigned_url(upload_file):
    url = None
    base_name, extension = os.path.splitext(upload_file.filename)
    upload_file.filename = f"{base_name}_{get_milliseconds()}{extension}"
    if upload_file_to_s3(upload_file):
        url = get_presigned_url_from_upload_file(upload_file.filename)
    return url, upload_file.filename


@router.get("/{manikin_type}", status_code=status.HTTP_200_OK, response_model=GetResponseSchema)
async def get_certifications_template(request: Request, manikin_type: str, db: Session = Depends(get_db)):
    token = request.headers['Authorization']
    # check user from token
    token_query = select(User).where(User.token == token)
    user = db.scalar(token_query)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    try:
        user = check_authorization(request, db)
        query = select(CertificationsTemplate).options(joinedload(CertificationsTemplate.user)).where(
            and_(User.id == user.id, CertificationsTemplate.manikin_type == manikin_type))
        certification = db.scalar(query)
        if certification:
            return certification.convert_to_schema
        else:
            return None
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.NOT_FOUND:
            logging.error(e)
            raise HTTPException(status_code=e.status_code, detail=e.message)
        elif e.exception_type == ExceptionType.INVALID_TOKEN:
            logging.error(e)
            raise HTTPException(status_code=e.status_code, detail=e.message)


@router.patch("/{manikin_type}")
async def update_certification_template(
        request: Request, manikin_type: str,
        data: UpdateRequestSchema = Depends(UpdateRequestSchema.as_form),
        db: Session = Depends(get_db)):
    update_value = {}
    images_url = {}

    token = request.headers['Authorization']
    # check user from token
    token_query = select(User).where(User.token == token)
    user = db.scalar(token_query)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    title = request._form.get('title')
    query = select(CertificationsTemplate).options(joinedload(CertificationsTemplate.user)).where(
        and_(User.id == user.id, CertificationsTemplate.manikin_type == manikin_type))
    certification = db.scalar(query)
    file_names = certification.images

    if data.top_left and data.top_left.filename:
        image_url, update_filename = upload_file_and_get_presigned_url(data.top_left)
        file_names['top_left'] = update_filename
        images_url['top_left'] = image_url
    elif data.top_left and not data.top_left.filename:
        file_names['top_left'] = None
        images_url['top_left'] = None

    if data.top_right and data.top_right.filename:
        image_url, update_filename = upload_file_and_get_presigned_url(data.top_right)
        file_names['top_right'] = update_filename
        images_url['top_right'] = image_url
    elif data.top_right and not data.top_right.filename:
        file_names['top_right'] = None
        images_url['top_right'] = None

    if data.bottom_left and data.bottom_left.filename:
        image_url, update_filename = upload_file_and_get_presigned_url(data.bottom_left)
        file_names['bottom_left'] = update_filename
        images_url['bottom_left'] = image_url
    elif data.bottom_left and not data.bottom_left.filename:
        file_names['bottom_left'] = None
        images_url['bottom_left'] = None

    if data.bottom_right and data.bottom_right.filename:
        image_url, update_filename = upload_file_and_get_presigned_url(data.bottom_right)
        file_names['bottom_right'] = update_filename
        images_url['bottom_right'] = image_url
    elif data.bottom_right and not data.bottom_right.filename:
        file_names['bottom_right'] = None
        images_url['bottom_right'] = None

    update_value['images'] = file_names
    for k, v in data.__dict__.items():
        if k in ['top_left', 'top_right', 'bottom_left', 'bottom_right']:
            continue
        if v:
            update_value[k] = v
    if title:
        update_value['title'] = title
    query = (update(CertificationsTemplate).where(CertificationsTemplate.id == certification.id).values(update_value))
    db.execute(query)
    db.commit()
    certification = db.get(CertificationsTemplate, certification.id)
    images_name = certification.images
    for k in images_name.keys():
        if images_name[k]:
            images_url[k] = get_presigned_url_from_upload_file(images_name[k])
        else:
            images_url[k] = None
    return (CertificationsTemplate
            (title=certification.title, organization=certification.organization, images=images_url,
             manikin_type=certification.manikin_type))


def replace_certificate_format_from_data(issued_certificate_format, template, user):
    class DefaultTemplateIdentifier(Enum):
        user_name = 'user_name'
        certification = 'certification_title'
        manikin_type = 'manikin_type'
        organization = 'organization'
        formatted_date = 'formatted_date'

    # assign certificate format to certification template, user data
    result = issued_certificate_format

    # TODO 리팩토링 해야함!
    for idx, str in enumerate([user.name,
                               template.title if template.title else "",
                               template.manikin_type,
                               template.organization,
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


def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    if not user:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         message="there is no user",
                                         exception_type=ExceptionType.NOT_FOUND)
    return user


def get_certification_template_by_manikin_type(db, manikin_type):
    # get certification template data
    query = select(CertificationsTemplate).where(CertificationsTemplate.manikin_type == manikin_type)
    template = db.scalar(query)
    if not template:
        raise GetExceptionWithStatuscode(status_code=status.HTTP_404_NOT_FOUND,
                                         message="there is no user",
                                         exception_type=ExceptionType.NOT_FOUND)
    return template


def save_certification(issued_certification):
    # save update format
    with open('certificate_download_format_update.html', 'w') as f:
        f.write(issued_certification)


def read_certificate_download_format():
    with open('certificate_download_format.html', 'r') as f:
        issued_certificate_format = f.read()
    return issued_certificate_format


def convert_html_to_pdf():
    html_path = os.path.abspath('certificate_download_format_update.html')
    file_name = 'issued_certificate.pdf'
    converter.convert(f'file:///{html_path}', file_name, print_options={"landscape": True})
    return file_name

#TODO 발급 받은 인증서는 따로 빼야할거 같음
@router.get('/download/{user_id}')
def get_issued_certificate(user_id: int, manikin_type: str = 'adult', db: Session = Depends(get_db)):
    try:
        user = get_user_by_id(user_id, db)
        template = get_certification_template_by_manikin_type(db, manikin_type)
    except GetExceptionWithStatuscode as e:
        if e.exception_type == ExceptionType.NOT_FOUND:
            logging.error(e)
            raise HTTPException(e.status_code, e.message)
        return

    issued_certificate_format = replace_certificate_format_from_data(read_certificate_download_format(),
                                                                     template,
                                                                     user)

    save_certification(issued_certificate_format)

    file_name = convert_html_to_pdf()

    return FileResponse(file_name)
