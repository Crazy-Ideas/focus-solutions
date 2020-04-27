from config import os
from fs_flask.user import User


def check_env():
    for key, value in os.environ.items():
        print(f"{key}: {value}")


def create_user(email: str, name: str, initial: str):
    password = User.create_user(email, name, initial)
    if not password:
        print("Invalid email")
    else:
        print(f"User {email} created. Your password is {password}")
    return
