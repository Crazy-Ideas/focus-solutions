from typing import List

from flask import request
from flask_login import current_user
from wtforms import HiddenField, SelectMultipleField

from fs_flask import FSForm
from fs_flask.date_methods import get_days_from_month


class ReportForm(FSForm):
    action_type = HiddenField()
    days = SelectMultipleField("Select Saaya days of the month")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        days: List[str] = get_days_from_month(current_user.report_month, current_user.report_year)
        self.days.choices = [(day, day) for day in days]
        if request.method == "GET":
            self.days.data = current_user.report_days[:]
        return
