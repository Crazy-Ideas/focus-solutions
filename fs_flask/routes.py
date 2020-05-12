from flask import render_template, url_for, redirect, Response, flash
from flask_login import login_required, current_user

from config import Config, Date
from fs_flask import fs_app
from fs_flask.hotel import Hotel, HotelForm, AdminForm
from fs_flask.report import QueryForm
from fs_flask.usage import Usage, UsageForm


@fs_app.route("/")
@fs_app.route("/home")
@login_required
def home() -> Response:
    return render_template("home.html", title="Dashboard")


@fs_app.route("/reports/main", methods=["GET", "POST"])
@login_required
def main_report() -> Response:
    form = QueryForm()
    if not form.validate_on_submit():
        form.flash_form_errors()
        form.update_data()
        return render_template("main_report.html", form=form, title="Report")
    form.update_query()
    return render_template("main_report.html", form=form, title="Report")


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


@fs_app.route("/data_entry")
@login_required
def data_entry() -> Response:
    hotel = Hotel.objects.filter_by(city=current_user.city, name=current_user.hotel).first()
    date, timing = Usage.get_data_entry_date(hotel)
    if not date:
        flash("Error in data entry")
        return redirect(url_for("home"))
    if not timing:
        flash("All Done - Here are your last evening events")
        timing = Config.EVENING
    return redirect(url_for("usage_manage", hotel_id=hotel.id, date=Date(date).db_date, timing=timing))


@fs_app.route("/hotels/<hotel_id>/dates/<date>/timings/<timing>", methods=["GET", "POST"])
@login_required
def usage_manage(hotel_id: str, date: str, timing: str):
    hotel: Hotel = Hotel.get_by_id(hotel_id)
    date = Date(date).date
    if not hotel or not date or timing not in Config.TIMINGS:
        flash("Error in viewing events on this date")
        return redirect(url_for("home"))
    data_entry_date, data_entry_timing = Usage.get_data_entry_date(hotel)
    if (date == data_entry_date and timing == Config.EVENING and data_entry_timing == Config.MORNING) or \
            date > data_entry_date:
        message = "Please complete the data entry for events on this date" if data_entry_timing \
            else "All Done - Here are your last evening events"
        flash(message)
        date = data_entry_date
        timing = data_entry_timing if data_entry_timing else Config.EVENING
    if date < hotel.contract[0]:
        flash("Date reset to contract start date")
        date = hotel.contract[0]
    form = UsageForm(hotel, date, timing)
    if not form.validate_on_submit():
        form.flash_form_errors()
        return render_template("usage.html", form=form, title="Data Entry")
    form.update()
    return render_template("usage.html", form=form, title="Data Entry") if form.form_type.data != form.GOTO_DATE \
        else redirect(form.link_goto)
