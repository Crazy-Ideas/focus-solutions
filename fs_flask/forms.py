from typing import List

from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField

from config import Config
from fs_flask.hotel import Usage


class QueryForm(FlaskForm):
    timing = SelectField("Select timing", choices=list())
    meal = SelectField("Select meals", choices=list())
    event = SelectField("Select event type", choices=list())
    submit = SubmitField("Query")

    def populate_choices(self):
        any_choice = (Config.ANY, Config.ANY)
        self.timing.choices.append(any_choice)
        self.meal.choices.append(any_choice)
        self.event.choices.append(any_choice)
        self.timing.choices.extend([(timing, timing) for timing in Config.TIMINGS])
        self.meal.choices.extend([(meal, meal) for meal in Config.MEALS])
        self.event.choices.extend([(event, event) for event in Config.EVENTS])

    def get_usage(self, city: str) -> List[Usage]:
        query = Usage.objects.filter_by(city=city)
        if self.timing.data != Config.ANY:
            query = query.filter_by(timing=self.timing.data)
        if self.event.data != Config.ANY:
            query = query.filter_by(event_type=self.event.data)
        if self.meal.data != Config.ANY:
            query = query.filter("meals", query.ARRAY_CONTAINS, self.meal.data)
        return query.get()
