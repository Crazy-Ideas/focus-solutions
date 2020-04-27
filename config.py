import os
from base64 import b64encode

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google-cloud.json'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or b64encode(os.urandom(24)).decode()
