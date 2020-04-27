from flask import render_template
from flask_login import login_required

from fs_flask import fs_app


@fs_app.route("/")
@fs_app.route("/home")
@login_required
def home():
    return render_template("home.html", title="Dashboard")
