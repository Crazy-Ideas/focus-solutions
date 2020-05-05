from operator import itemgetter
from typing import List

from flask import render_template, url_for, redirect, Response, flash
from flask_login import login_required, current_user

from config import Config
from fs_flask import fs_app
from fs_flask.forms import QueryForm, AdminForm, HotelForm
from fs_flask.hotel import Usage, Hotel


@fs_app.route("/")
@fs_app.route("/home")
@login_required
def home() -> Response:
    return render_template("home.html", title="Dashboard")


@fs_app.route("/hotel_count", methods=["GET", "POST"])
@login_required
def hotel_count() -> Response:
    form = QueryForm()
    form.populate_choices()
    usage_data: List[Usage] = form.get_usage()
    hotels = {usage.hotel for usage in usage_data}
    hotel_counts = [(hotel, sum(1 for usage in usage_data if usage.hotel == hotel)) for hotel in hotels]
    hotel_counts.sort(key=itemgetter(1), reverse=True)
    if current_user.hotel in hotels:
        current_hotel = next(hotel for hotel in hotel_counts if hotel[0] == current_user.hotel)
        hotel_counts.remove(current_hotel)
        hotel_counts.insert(0, current_hotel)
    return render_template("hotel_count.html", form=form, hotel_counts=hotel_counts, title="Report",
                           selection=form.get_selection(), total=len(usage_data), usages=usage_data)


@fs_app.route("/profile")
@login_required
def profile() -> Response:
    if current_user.role == Config.ADMIN:
        return redirect(url_for("admin_manage"))
    hotel = Hotel.objects.filter_by(city=current_user.city, name=current_user.hotel).first()
    if not hotel:
        flash("Error in retrieving hotel profile")
        return redirect(url_for("home"))
    return redirect(url_for("hotel_manage", hotel_id=hotel.id))


@fs_app.route("/hotels/admin", methods=["GET", "POST"])
@login_required
def admin_manage() -> Response:
    if current_user.role != Config.ADMIN:
        flash("Insufficient privilege")
        return redirect(url_for("home"))
    form = AdminForm()
    hotels = form.populate_choices()
    if not form.validate_on_submit():
        return render_template("admin.html", form=form, hotels=hotels)
    form.update_user()
    return redirect(url_for("admin_manage"))


@fs_app.route("/hotels/<hotel_id>", methods=["GET", "POST"])
@login_required
def hotel_manage(hotel_id: str) -> Response:
    hotel = Hotel.get_by_id(hotel_id)
    if not hotel or (current_user.role == Config.HOTEL and current_user.hotel != hotel.name):
        flash("Error in retrieving hotel")
        return redirect(url_for("home"))
    form = HotelForm(hotel)
    if not form.validate_on_submit():
        form.flash_form_errors()
        return render_template("hotel.html", title=hotel.name, form=form, hotel=hotel)
    form.update()
    return redirect(url_for("hotel_manage", hotel_id=hotel.id))
