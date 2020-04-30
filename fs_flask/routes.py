from operator import itemgetter
from typing import List

from flask import render_template, url_for, redirect
from flask_login import login_required, current_user

from config import Config
from fs_flask import fs_app
from fs_flask.forms import EventForm, ProfileForm
from fs_flask.hotel import Usage


@fs_app.route("/")
@fs_app.route("/home")
@login_required
def home():
    return render_template("home.html", title="Dashboard")


@fs_app.route("/hotel_count", methods=["GET", "POST"])
@login_required
def hotel_count():
    form = EventForm()
    form.populate_choices()
    usage_data: List[Usage] = form.get_usage(current_user.city)
    hotels = {usage.hotel for usage in usage_data}
    hotel_counts = [(hotel, sum(1 for usage in usage_data if usage.hotel == hotel)) for hotel in hotels]
    hotel_counts.sort(key=itemgetter(1), reverse=True)
    return render_template("hotel_count.html", form=form, hotel_counts=hotel_counts, title="Report",
                           selection=form.get_selection(), total=len(usage_data))


@fs_app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm()
    form.populate_choices(current_user)
    if not form.validate_on_submit() or current_user.role != Config.ADMIN:
        return render_template("profile.html", user=current_user, form=form)
    form.update_user(current_user)
    return redirect(url_for("profile"))
