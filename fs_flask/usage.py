import datetime as dt
from operator import itemgetter
from typing import Optional, List, Tuple

from firestore_ci import FirestoreDocument
from flask import request
from flask_login import current_user
from wtforms import SelectField, SelectMultipleField, SubmitField

from config import Config
from fs_flask import FSForm
from fs_flask.hotel import Hotel


class Usage(FirestoreDocument):
    def __init__(self):
        super().__init__()
        self.hotel: str = str()
        self.city: str = str()
        self.date: str = str()
        self.day: str = str()
        self.weekday: Optional[bool] = None
        self.timing: str = str()
        self.company: str = str()
        self.event_type: str = str()
        self.meals: List[str] = list()
        self.ballrooms: List[str] = list()
        self.event_description: str = str()

    def __repr__(self):
        return f"{self.hotel}:{self.date}:{self.timing}:{self.company}:{self.event_type}"

    def set_date(self, dd_mm_yyyy: str) -> bool:
        try:
            date = dt.datetime.strptime(dd_mm_yyyy, "%d/%m/%Y")
        except ValueError:
            return False
        self.date = date.strftime("%Y-%m-%d")
        self.day = date.strftime("%A")
        self.weekday = self.day not in ("Saturday", "Sunday")
        return True

    @property
    def formatted_date(self):
        return dt.datetime.strptime(self.date, "%Y-%m-%d").strftime("%d-%b-%Y")

    @property
    def formatted_meal(self):
        return ", ".join(self.meals)

    @property
    def formatted_ballroom(self):
        return ", ".join(self.ballrooms)


Usage.init()


class QueryForm(FSForm):
    timing = SelectField("Select timing", choices=list())
    meals = SelectMultipleField("Select meals", choices=list())
    event = SelectField("Select event type", choices=list())
    hotels = SelectMultipleField("Select hotels", choices=list())
    submit = SubmitField("Query")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
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
        self.competitions = Hotel.get_competitions(current_user.city, current_user.hotel)
        self.query = Usage.objects.filter_by(city=current_user.city)
        self.usage_data: List[Usage] = list()
        self.hotel_counts: List[Tuple[Hotel, int]] = list()
        if request.method == "GET":
            self.timing.data = Config.ANY
            self.event.data = Config.ANY
            self.meals.data = [Config.ANY]
            self.hotels.data = self.competitions
            self.update_data()
        return

    def update_data(self, filter_meals: bool = False):
        hotels = self.hotels.data[:9]
        hotels.append(current_user.hotel)
        self.query = self.query.filter("hotel", self.query.IN, hotels)
        self.usage_data.extend(self.query.get())
        if filter_meals:
            self.usage_data = [usage for usage in self.usage_data
                               if any(meal in usage.meals for meal in self.meals.data)]
        hotels = {usage.hotel for usage in self.usage_data}
        self.hotel_counts = [(hotel, sum(1 for usage in self.usage_data if usage.hotel == hotel)) for hotel in hotels]
        self.hotel_counts.sort(key=itemgetter(1), reverse=True)
        if current_user.hotel in hotels:
            current_hotel = next(hotel for hotel in self.hotel_counts if hotel[0] == current_user.hotel)
            self.hotel_counts.remove(current_hotel)
        else:
            current_hotel = (current_user.hotel, 0)
        self.hotel_counts.insert(0, current_hotel)

    def update_query(self) -> None:
        filter_meals = False
        if self.timing.data != Config.ANY:
            self.query = self.query.filter_by(timing=self.timing.data)
        if self.event.data != Config.ANY:
            self.query = self.query.filter_by(event_type=self.event.data)
        self.meals.data = self.meals.data if self.meals.data else [Config.ANY]
        if self.meals.data[0] == Config.ANY and len(self.meals.data) > 1:
            self.meals.data.remove(Config.ANY)
        if self.meals.data[0] != Config.ANY:
            filter_meals = True
        if not self.hotels.data:
            self.hotels.data = self.competitions
        self.update_data(filter_meals)

    @property
    def selection(self) -> dict:
        return {
            "timing": self.timing.data,
            "event": self.event.data,
            "meals": self.meals.data,
            "hotels": self.hotels.data,
        }
