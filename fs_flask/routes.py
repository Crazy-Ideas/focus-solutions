from flask import render_template, url_for, redirect, Response, flash, send_file, request
from flask_login import current_user

from config import Config, Date
from fs_flask import fs_app
from fs_flask.file import File
from fs_flask.hotel import Hotel, HotelForm, AdminForm
from fs_flask.report import QueryForm, Dashboard
from fs_flask.usage import Usage, UsageForm
from fs_flask.user import cookie_login_required


@fs_app.route("/")
@fs_app.route("/home")
def home() -> Response:
    return render_template("home.html", title="Home")


@fs_app.route("/privacy")
def privacy_policy() -> Response:
    return render_template("privacy.html", title="Privacy Policy")


@fs_app.route("/dashboard")
@cookie_login_required
def view_dashboard() -> Response:
    return render_template("dashboard.html", d=Dashboard(), title="Dashboard")


@fs_app.route("/reports/main", methods=["GET", "POST"])
@cookie_login_required
def main_report() -> Response:
    form = QueryForm()
    if form.error_message:
        flash(form.error_message)
        return redirect(url_for("view_dashboard"))
    if not form.validate_on_submit():
        form.flash_form_errors()
    form.update_data()
    if form.file_path:
        return send_file(form.file_path, as_attachment=True, attachment_filename="Report.xlsx")
    return render_template("main_report.html", form=form, title="Reports")


@fs_app.route("/hotels/profile")
@cookie_login_required
def hotel_profile() -> Response:
    hotel: Hotel = Hotel.objects.filter_by(city=current_user.city, name=current_user.hotel).first()
    if not hotel:
        flash("Error in retrieving hotel profile")
        return redirect(url_for("view_dashboard"))
    return redirect(url_for("hotel_manage", hotel_id=hotel.id))


@fs_app.route("/hotels/admin", methods=["GET", "POST"])
@cookie_login_required
def admin_manage() -> Response:
    if current_user.role != Config.ADMIN:
        flash("Insufficient privilege")
        return redirect(url_for("view_dashboard"))
    form = AdminForm()
    if not form.validate_on_submit():
        form.flash_form_errors()
        return render_template("admin.html", form=form, title="Admin")
    form.update()
    return render_template("admin.html", form=form, title="Admin")


@fs_app.route("/hotels/<hotel_id>", methods=["GET", "POST"])
@cookie_login_required
def hotel_manage(hotel_id: str) -> Response:
    hotel = Hotel.get_by_id(hotel_id)
    if not hotel or (current_user.role == Config.HOTEL and current_user.hotel != hotel.name):
        flash("Error in retrieving hotel")
        return redirect(url_for("view_dashboard"))
    form = HotelForm(hotel)
    admin: bool = current_user.role == Config.ADMIN
    if not form.validate_on_submit():
        form.flash_form_errors()
        return render_template("hotel.html", title=hotel.name, form=form, hotel=hotel, admin=admin)
    form.update()
    return render_template("hotel.html", title=hotel.name, form=form, hotel=hotel, admin=admin)


@fs_app.route("/data_entry")
@cookie_login_required
def data_entry() -> Response:
    hotel = Hotel.objects.filter_by(city=current_user.city, name=current_user.hotel).first()
    date, timing = Usage.get_data_entry_date(hotel)
    if not date:
        flash(timing)
        return redirect(url_for("view_dashboard"))
    if not timing:
        flash("All Done - Here are your last evening events")
        timing = Config.EVENING
    return redirect(url_for("usage_manage", hotel_id=hotel.id, date=Date(date).db_date, timing=timing))


@fs_app.route("/hotels/<hotel_id>/dates/<date>/timings/<timing>", methods=["GET", "POST"])
@cookie_login_required
def usage_manage(hotel_id: str, date: str, timing: str) -> Response:
    form = UsageForm(hotel_id, date, timing)
    if form.error_message:
        flash(form.error_message)
        return redirect(url_for("view_dashboard"))
    if not form.validate_on_submit():
        form.flash_form_errors()
        return render_template("usage.html", form=form, title="Events")
    form.update()
    if form.redirect:
        return redirect(form.link_goto)
    return render_template("usage.html", form=form, title="Events")


@fs_app.route("/download")
@cookie_login_required
def download() -> Response:
    filename = request.args.get("filename", default=str())
    extension = request.args.get("extension", default=str())
    attachment = request.args.get("attachment", type=bool, default=False)
    new_filename = request.args.get("new_filename", default=str())
    new_filename = new_filename or f"{filename}.{extension}"
    file = File(filename, extension)
    file_path = file.download_from_cloud()
    if not file_path:
        flash("Error in downloading")
        return redirect(request.referrer) if request.referrer else redirect(url_for("view_dashboard"))
    return send_file(file_path, as_attachment=attachment, attachment_filename=new_filename)
