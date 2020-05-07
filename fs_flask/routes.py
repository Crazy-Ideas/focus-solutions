from flask import render_template, url_for, redirect, Response, flash
from flask_login import login_required, current_user

from config import Config
from fs_flask import fs_app
from fs_flask.hotel import Hotel, HotelForm, AdminForm
from fs_flask.usage import QueryForm


@fs_app.route("/")
@fs_app.route("/home")
@login_required
def home() -> Response:
    return render_template("home.html", title="Dashboard")


@fs_app.route("/hotel_count", methods=["GET", "POST"])
@login_required
def hotel_count() -> Response:
    form = QueryForm()
    if not form.validate_on_submit():
        form.flash_form_errors()
        return render_template("hotel_count.html", form=form, title="Report")
    form.update_query()
    return render_template("hotel_count.html", form=form, title="Report")


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
    if not form.validate_on_submit():
        form.flash_form_errors()
        return render_template("admin.html", form=form, title="Admin")
    form.update()
    return render_template("admin.html", form=form, title="Admin")


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
    return render_template("hotel.html", title=hotel.name, form=form, hotel=hotel)
