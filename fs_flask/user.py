import os
from base64 import b64encode
from typing import Optional

from firestore_ci import FirestoreDocument
from flask import flash, redirect, url_for, render_template, request
from flask_login import UserMixin, current_user, login_user, logout_user
from flask_wtf import FlaskForm
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.urls import url_parse
from wtforms import PasswordField, SubmitField
from wtforms.fields.html5 import EmailField
from wtforms.validators import InputRequired

from config import Config
from fs_flask import fs_app, login


class User(FirestoreDocument, UserMixin):

    def __init__(self):
        super().__init__()
        self.email: str = str()
        self.password_hash: str = str()
        self.name: str = str()
        self.initial: str = str()
        self.city: str = Config.DEFAULT_CITY
        self.hotel: str = str()
        self.role: str = str()

    def __repr__(self) -> str:
        return f"{self.email.lower()}"

    @classmethod
    def create_user(cls, email: str, name: str, initial: str, role: str, hotel: str) -> str:
        if not isinstance(email, str) or sum(1 for char in email if char == "@") != 1:
            return str()
        db_user = cls.objects.filter_by(email=email).first()
        if db_user:
            return str()
        user = cls()
        user.email = email
        user.name = name
        user.hotel = hotel
        user.initial = initial.upper()[:2]
        user.role = role
        password = b64encode(os.urandom(24)).decode()
        user.set_password(password)
        user.set_id(email.replace("@", "_").replace(".", "-"))
        user.save()
        return password

    def set_password(self, password) -> None:
        self.password_hash = generate_password_hash(password)
        self.save()

    def check_password(self, password) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str:
        return self.email

    def update_initial(self, initial: str) -> bool:
        user = self
        if self.role == Config.ADMIN:
            user = User.objects.filter_by(name=self.hotel).first()
        if user:
            user.initial = initial
            return user.save()
        return False


User.init()


@login.user_loader
def load_user(email: str) -> Optional[User]:
    user = User.objects.filter_by(email=email.lower()).first()
    return user


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[InputRequired()])
    password = PasswordField("Password", validators=[InputRequired()])
    submit = SubmitField("Sign In")


@fs_app.route("/login", methods=["GET", "POST"])
def login() -> str:
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    form = LoginForm()
    if not form.validate_on_submit():
        return render_template("form_template.html", title="Focus Solutions - Sign In", form=form)
    user = User.objects.filter_by(email=form.email.data).first()
    if not user or not user.check_password(form.password.data):
        flash(f"Invalid email or password.")
        return redirect(url_for("login"))
    login_user(user=user)
    next_page = request.args.get("next")
    if not next_page or url_parse(next_page).netloc != "":
        next_page = url_for("home")
    return redirect(next_page)


@fs_app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))
