from flask import Flask
from flask_login import LoginManager
from flask_wtf import FlaskForm

from config import Config

fs_app: Flask = Flask(__name__)
fs_app.config.from_object(Config)
login = LoginManager(fs_app)
login.login_view = 'login'


class FSForm(FlaskForm):
    def flash_form_errors(self) -> None:
        for _, errors in self.errors.items():
            for error in errors:
                if error:
                    flash(error)
        return


from fs_flask.user import login, logout
from fs_flask.routes import *
