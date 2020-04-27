from flask import Flask
from flask_login import LoginManager

from config import Config

fs_app: Flask = Flask(__name__)
fs_app.config.from_object(Config)
login = LoginManager(fs_app)
login.login_view = 'login'

from fs_flask.user import login, logout
from fs_flask.routes import *
