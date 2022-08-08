import datetime as dt
import os
from base64 import b64encode
from functools import wraps
from typing import Optional

import pytz
from firestore_ci import FirestoreDocument
from flask import flash, redirect, url_for, render_template, request, Response, make_response, current_app
from flask_login import UserMixin, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.urls import url_parse
from wtforms import PasswordField, SubmitField
from wtforms.fields.html5 import EmailField
from wtforms.validators import InputRequired

from config import Config
from fs_flask import fs_app, login, FSForm


def cookie_login_required(route_function):
    @wraps(route_function)
    def decorated_route(*args, **kwargs):
        if current_user.is_authenticated:
            return route_function(*args, **kwargs)
        user = User.check_token(request.cookies.get("token"))
        if user:
            login_user(user=user)
            return route_function(*args, **kwargs)
        return current_app.login_manager.unauthorized()

    return decorated_route


class User(FirestoreDocument, UserMixin):

    def __init__(self):
        super().__init__()
        self.email: str = str()
        self.password_hash: str = str()
        self.name: str = str()
        self.token: str = str()
        self.token_expiration: dt.datetime = dt.datetime.utcnow().replace(tzinfo=pytz.UTC)
        self.city: str = Config.DEFAULT_CITY
        self.hotel: str = str()
        self.role: str = str()

    def __repr__(self) -> str:
        return f"{self.email.lower()}"

    @classmethod
    def create_user(cls, email: str, name: str, role: str, hotel: str, city: str) -> str:
        if not isinstance(email, str) or sum(1 for char in email if char == "@") != 1:
            return str()
        if cls.objects.filter_by(email=email).first():
            return str()
        user = cls()
        user.email = email
        user.name = name
        user.hotel = hotel
        user.role = role
        user.city = city
        password = b64encode(os.urandom(24)).decode()
        user.set_password(password)
        user.set_id(email.replace("@", "_").replace(".", "-"))
        user.save()
        return password

    @classmethod
    def check_token(cls, token) -> Optional["User"]:
        if not token:
            return None
        user: User = cls.objects.filter_by(token=token).first()
        if user is None or user.token_expiration < dt.datetime.utcnow().replace(tzinfo=pytz.UTC):
            return None
        return user

    def get_token(self, expires_in=Config.TOKEN_EXPIRY) -> str:
        now = dt.datetime.utcnow().replace(tzinfo=pytz.UTC)
        if self.token and self.token_expiration > now + dt.timedelta(seconds=60):
            return self.token
        self.token = b64encode(os.urandom(24)).decode()
        self.token_expiration = now + dt.timedelta(seconds=expires_in)
        self.save()
        return self.token

    def revoke_token(self):
        self.token_expiration = dt.datetime.utcnow() - dt.timedelta(seconds=1)
        self.save()

    def set_password(self, password) -> None:
        self.password_hash = generate_password_hash(password)
        self.save()

    def check_password(self, password) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str:
        return self.email


User.init()


@login.user_loader
def load_user(email: str) -> Optional[User]:
    user = User.objects.filter_by(email=email.lower()).first()
    return user


class LoginForm(FSForm):
    email = EmailField("Email", validators=[InputRequired()])
    password = PasswordField("Password", validators=[InputRequired()])
    submit = SubmitField("Sign In")


@fs_app.route("/login", methods=["GET", "POST"])
def login() -> Response:
    if current_user.is_authenticated:
        return redirect(url_for("view_dashboard"))
    form = LoginForm()
    if not form.validate_on_submit():
        form.flash_form_errors()
        return render_template("form_template.html", title="Focus Solutions", form=form)
    user = User.objects.filter_by(email=form.email.data).first()
    if not user or not user.check_password(form.password.data):
        flash(f"Invalid email or password.")
        return redirect(url_for("login"))
    token = user.get_token()
    login_user(user=user)
    next_page = request.args.get("next")
    if not next_page or url_parse(next_page).netloc != str():
        next_page = url_for("view_dashboard")
    response: Response = make_response(redirect(next_page))
    response.set_cookie("token", token, max_age=Config.TOKEN_EXPIRY, secure=Config.CI_SECURITY, httponly=True,
                        samesite="Strict")
    return response


@fs_app.route("/logout")
@cookie_login_required
def logout():
    current_user.revoke_token()
    logout_user()
    return redirect(url_for("home"))
