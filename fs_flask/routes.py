from operator import itemgetter
from typing import List

from flask import render_template, url_for
from flask_login import login_required, current_user

from fs_flask import fs_app
from fs_flask.forms import QueryForm
from fs_flask.hotel import Usage


@fs_app.route("/")
@fs_app.route("/home")
@login_required
def home():
    return render_template("home.html", title="Dashboard")


@fs_app.route("/query", methods=["GET", "POST"])
@login_required
def query():
    form = QueryForm()
    form.populate_choices()
    if not form.validate_on_submit():
        return render_template("form_template.html", title="Query", name="Dashboard", name_url=url_for("home"),
                               form=form)
    return view_report(form.get_usage(current_user.city))


def view_report(usage_data: List[Usage]):
    hotels = {usage.hotel for usage in usage_data}
    hotel_counts = [(hotel, sum(1 for usage in usage_data if usage.hotel == hotel)) for hotel in hotels]
    hotel_counts.sort(key=itemgetter(1), reverse=True)
    return render_template("view_report.html", hotel_counts=hotel_counts, title="Report")
