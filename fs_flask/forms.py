from operator import itemgetter
from typing import List

from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, SelectMultipleField

from config import Config
from fs_flask.hotel import Usage, Hotel
from fs_flask.user import User


class EventForm(FlaskForm):
    timing = SelectField("Select timing", choices=list())
    meals = SelectMultipleField("Select meals", choices=list())
    event = SelectField("Select event type", choices=list())
    submit = SubmitField("Query")

    def populate_choices(self) -> None:
        any_choice = (Config.ANY, Config.ANY)
        self.timing.choices.append(any_choice)
        self.meals.choices.append(any_choice)
        self.event.choices.append(any_choice)
        self.timing.choices.extend([(timing, timing) for timing in Config.TIMINGS])
        self.meals.choices.extend([(meal, meal) for meal in Config.MEALS])
        self.event.choices.extend([(event, event) for event in Config.EVENTS])

    def get_usage(self, city: str) -> List[Usage]:
        query = Usage.objects.filter_by(city=city)
        if self.validate_on_submit():
            if self.timing.data != Config.ANY:
                query = query.filter_by(timing=self.timing.data)
            if self.event.data != Config.ANY:
                query = query.filter_by(event_type=self.event.data)
            if self.meals.data[0] != Config.ANY:
                query = query.filter("meals", query.ARRAY_CONTAINS_ANY, self.meals.data)
        else:
            self.timing.data = Config.ANY
            self.event.data = Config.ANY
            self.meals.data = [Config.ANY]
        return query.get()

    def get_selection(self) -> dict:
        return {
            "timing": self.timing.data,
            "event": self.event.data,
            "meals": self.meals.data
        }


class ProfileForm(FlaskForm):
    city = SelectField("Select City", choices=list())
    hotel = SelectField("Select Hotel", choices=list())
    save = SubmitField("Save")

    def populate_choices(self, user: User) -> None:
        self.hotel.choices.append((user.hotel, user.hotel))
        if user.hotel != Config.ANY:
            self.hotel.choices.append((Config.ANY, Config.ANY))
        hotels = Hotel.objects.filter_by(city=user.city).get()
        hotels.sort(key=lambda hotel: hotel.name)
        self.hotel.choices.extend([(hotel.name, hotel.name) for hotel in hotels if hotel.name != user.hotel])
        self.city.choices.append((user.city, user.city))
        cities = [(city, city) for city in Config.CITIES if city != user.city]
        cities.sort(key=itemgetter(0))
        self.city.choices.extend(cities)

    def update_user(self, user: User) -> bool:
        if user.hotel != self.hotel.data:
            user.hotel = self.hotel.data
            return user.save()
        elif user.city != self.city.data:
            user.city = self.city.data
            user.hotel = Config.ANY
            return user.save()
        return False
