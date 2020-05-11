import datetime as dt
from operator import itemgetter
from typing import List, Tuple

from flask import request
from flask_login import current_user
from wtforms import SelectField, SelectMultipleField, DateField, SubmitField, ValidationError

from config import Config, today
from fs_flask import FSForm
from fs_flask.hotel import Hotel
from fs_flask.usage import Usage


class QueryForm(FSForm):
    MAX_ALL_DAYS = 100
    MAX_WEEKDAYS = int(MAX_ALL_DAYS * 7 / 5)
    MAX_WEEKENDS = int(MAX_ALL_DAYS * 7 / 2)
    MAX_SPECIFIC_DAYS = int(MAX_ALL_DAYS * 7 / 1)
    DEFAULT_DATE = dt.date(year=2018, month=8, day=1)
    ALL_DAY = "All Days"
    WEEKDAY = "Weekdays"
    WEEKEND = "Weekends"
    DAY_CHOICES = (ALL_DAY, WEEKDAY, WEEKEND, "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
                   "Sunday")
    timing = SelectField("Select timing", choices=list())
    meals = SelectMultipleField("Select meals", choices=list())
    event = SelectField("Select event type", choices=list())
    hotels = SelectMultipleField("Select hotels", choices=list())
    start_date = DateField("From Date")
    end_date = DateField("To Date")
    day = SelectField("Select the day(s) of the week", choices=list())
    submit = SubmitField("Query")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        any_choice = (Config.ANY, Config.ANY)
        self.day.choices.extend([(day, day) for day in self.DAY_CHOICES])
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
        self.query = Usage.objects.filter_by(city=current_user.city, no_event=False)
        self.usage_data: List[Usage] = list()
        self.hotel_counts: List[Tuple[Hotel, int]] = list()
        if request.method == "GET":
            self.timing.data = Config.ANY
            self.event.data = Config.ANY
            self.meals.data = [Config.ANY]
            self.hotels.data = self.competitions
            self.start_date.data = self.end_date.data = self.DEFAULT_DATE
            self.day.data = self.ALL_DAY
        return

    def raise_date_error(self, message):
        self.start_date.data = self.end_date.data = self.DEFAULT_DATE
        raise ValidationError(message)

    def validate_end_date(self, end_date: DateField):
        if not self.start_date.data or not self.end_date.data:
            self.raise_date_error(str())
        if end_date.data > today():
            self.raise_date_error("To Date cannot be greater than today")
        if self.start_date.data > end_date.data:
            self.raise_date_error("From Date cannot be greater than To Date")
        days = (end_date.data - self.start_date.data).days + 1
        if self.day.data == self.ALL_DAY and days > self.MAX_ALL_DAYS:
            self.raise_date_error(f"For All Days query, the date range cannot be greater than {self.MAX_ALL_DAYS} days")
        if self.day.data == self.WEEKDAY and days > self.MAX_WEEKDAYS:
            self.raise_date_error(f"For Weekdays query, the date range cannot be greater than {self.MAX_WEEKDAYS} days")
        if self.day.data == self.WEEKEND and days > self.MAX_WEEKENDS:
            self.raise_date_error(f"For Weekends query, the date range cannot be greater than {self.MAX_WEEKENDS} days")
        if self.day.data not in (self.ALL_DAY, self.WEEKDAY, self.WEEKEND) and days > self.MAX_SPECIFIC_DAYS:
            self.raise_date_error(f"For specific day query, the date range cannot be greater than "
                                  f"{self.MAX_SPECIFIC_DAYS} days")

    def update_data(self, filter_meals: bool = False):
        hotels = self.hotels.data[:9]
        hotels.append(current_user.hotel)
        self.query = self.query.filter("hotel", self.query.IN, hotels)
        self.query = self.query.filter("date", ">=", Hotel.db_date(self.start_date.data))
        self.query = self.query.filter("date", "<=", Hotel.db_date(self.end_date.data))
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
        if self.day.data != self.ALL_DAY:
            if self.day.data == self.WEEKDAY:
                self.query = self.query.filter_by(weekday=True)
            elif self.day.data == self.WEEKEND:
                self.query = self.query.filter_by(weekday=False)
            else:
                self.query = self.query.filter_by(day=self.day.data)
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
    def formatted_start_date(self) -> str:
        return self.start_date.data.strftime("%d-%b-%Y") if self.start_date.data else "Invalid date"

    @property
    def formatted_end_date(self) -> str:
        return self.end_date.data.strftime("%d-%b-%Y") if self.end_date.data else "Invalid date"
