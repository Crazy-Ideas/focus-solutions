from flask import Flask
from flask_login import LoginManager
from flask_wtf import FlaskForm

from config import Config

fs_app: Flask = Flask(__name__)
fs_app.config.from_object(Config)
login = LoginManager(fs_app)
login.login_view = "login"
login.session_protection = "strong" if Config.CI_SECURITY else "basic"


class FSForm(FlaskForm):
    def flash_form_errors(self) -> None:
        for _, errors in self.errors.items():
            for error in errors:
                if error:
                    flash(error)
        return


from fs_flask.user import login, logout
from fs_flask.routes import *


@fs_app.shell_context_processor
def make_shell_context():
    from fs_flask.usage import Usage
    from fs_flask.hotel import Hotel
    from fs_flask import methods
    return {
        "Config": Config,
        "Usage": Usage,
        "Hotel": Hotel,
        "m": methods,
    }
