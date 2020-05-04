from operator import itemgetter
from typing import List

from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, SelectMultipleField

from config import Config
from fs_flask.hotel import Usage, Hotel


class QueryForm(FlaskForm):
    timing = SelectField("Select timing", choices=list())
    meals = SelectMultipleField("Select meals", choices=list())
    event = SelectField("Select event type", choices=list())
    hotels = SelectMultipleField("Select hotels", choices=list())
    submit = SubmitField("Query")

    def populate_choices(self) -> None:
        any_choice = (Config.ANY, Config.ANY)
        self.timing.choices.append(any_choice)
        self.meals.choices.append(any_choice)
        self.event.choices.append(any_choice)
        self.hotels.choices.append((current_user.hotel, current_user.hotel))
        self.timing.choices.extend([(timing, timing) for timing in Config.TIMINGS])
        self.meals.choices.extend([(meal, meal) for meal in Config.MEALS])
        self.event.choices.extend([(event, event) for event in Config.EVENTS])
        hotels = Hotel.objects.filter_by(city=current_user.city).get()
        hotels.sort(key=lambda hotel: hotel.name)
        self.hotels.choices.extend([(hotel.name, hotel.name) for hotel in hotels if hotel.name != current_user.hotel])

    def get_usage(self) -> List[Usage]:
        query = Usage.objects.filter_by(city=current_user.city)
        filter_meals = False
        if self.validate_on_submit():
            if self.timing.data != Config.ANY:
                query = query.filter_by(timing=self.timing.data)
            if self.event.data != Config.ANY:
                query = query.filter_by(event_type=self.event.data)
            self.meals.data = self.meals.data if self.meals.data else [Config.ANY]
            if self.meals.data[0] == Config.ANY and len(self.meals.data) > 1:
                self.meals.data.remove(Config.ANY)
            if self.meals.data[0] != Config.ANY:
                filter_meals = True
            if not self.hotels.data:
                self.hotels.data = Hotel.get_competitions(current_user.city, current_user.hotel)
            if current_user.hotel not in self.hotels.data:
                self.hotels.data.insert(0, current_user.hotel)
            self.hotels.data = self.hotels.data[:10]
            query = query.filter("hotel", query.IN, self.hotels.data)
        else:
            self.timing.data = Config.ANY
            self.event.data = Config.ANY
            self.meals.data = [Config.ANY]
            self.hotels.data = Hotel.get_competitions(current_user.city, current_user.hotel)
            query = query.filter("hotel", query.IN, self.hotels.data)
        usage_data = query.get()
        if filter_meals:
            usage_data = [usage for usage in usage_data if any(meal in usage.meals for meal in self.meals.data)]
        return usage_data

    def get_selection(self) -> dict:
        return {
            "timing": self.timing.data,
            "event": self.event.data,
            "meals": self.meals.data,
            "hotels": self.hotels.data,
        }


class ProfileForm(FlaskForm):
    city = SelectField("Select City", choices=list())
    hotel = SelectField("Select Hotel", choices=list())
    save = SubmitField("Save")

    def populate_choices(self) -> None:
        self.hotel.choices.append((current_user.hotel, current_user.hotel))
        hotels = Hotel.objects.filter_by(city=current_user.city).get()
        hotels.sort(key=lambda hotel: hotel.name)
        self.hotel.choices.extend([(hotel.name, hotel.name) for hotel in hotels if hotel.name != current_user.hotel])
        self.city.choices.append((current_user.city, current_user.city))
        cities = [(city, city) for city in Config.CITIES if city != current_user.city]
        cities.sort(key=itemgetter(0))
        self.city.choices.extend(cities)

    def update_user(self) -> bool:
        if current_user.hotel != self.hotel.data:
            current_user.hotel = self.hotel.data
            return current_user.save()
        elif current_user.city != self.city.data:
            current_user.city = self.city.data
            hotel = Hotel.objects.filter_by(city=current_user.city).first()
            current_user.hotel = hotel.name if hotel else str()
            return current_user.save()
        return False
