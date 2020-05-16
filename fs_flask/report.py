import datetime as dt
from operator import itemgetter
from typing import List, Tuple

from flask import request
from flask_login import current_user
from wtforms import SelectField, SelectMultipleField, DateField, SubmitField, ValidationError

from config import Config, Date
from fs_flask import FSForm
from fs_flask.hotel import Hotel
from fs_flask.usage import Usage


class QueryForm(FSForm):
    MAX_ALL_DAYS = 100
    MAX_WEEKDAYS = int(MAX_ALL_DAYS * 7 / 5)
    MAX_WEEKENDS = int(MAX_ALL_DAYS * 7 / 2)
    MAX_SPECIFIC_DAYS = int(MAX_ALL_DAYS * 7 / 1)
    DEFAULT_DATE = Date.last_sunday()
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
        if end_date.data > Date.last_sunday():
            self.raise_date_error(f"To Date cannot be greater than last Sunday "
                                  f"({Date(Date.last_sunday()).format_date})")
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
        self.query = self.query.filter("date", ">=", Date(self.start_date.data).db_date)
        self.query = self.query.filter("date", "<=", Date(self.end_date.data).db_date)
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
    def format_start_date(self) -> str:
        return Date(self.start_date.data).format_week if self.start_date.data else "Invalid date"

    @property
    def format_end_date(self) -> str:
        return Date(self.end_date.data).format_week if self.end_date.data else "Invalid date"


class Dashboard:
    PAST_DAYS = 14
    DONE = ["oi oi-check", "bg-success text-white"]
    NOT_DONE = ["oi oi-x", "bg-danger text-white"]
    PARTIAL = ["oi oi-minus", "bg-warning"]
    NA = ["oi oi-ban", "bg-secondary text-white"]
    STATUS_ALL_DONE = ("All Done", "list-group-item-success")
    STATUS_PARTIAL = ("Yesterday evening entry remaining", "list-group-item-warning")
    STATUS_ERROR = ("Error", "list-group-item-danger")
    STATUS_NO_CONTRACT = ("No Contract", "list-group-item-secondary")

    def __init__(self):
        self.hotels: List[Tuple[str, List[List[str]]]] = list()
        self.header: List[Tuple[int, str]] = self.generate_header()
        self.hotel: str = current_user.hotel
        self.today: str = Date().format_week
        self.status: Tuple[str, str] = self.STATUS_ERROR
        self.display_status: str = "list-group-item-danger"
        self.generate_hotel_status()

    def generate_hotel_status(self):
        hotels = Hotel.objects.filter_by(city=current_user.city).get()
        self.hotels = [(hotel.name, list()) for hotel in hotels]
        for index, hotel in enumerate(hotels):
            last_date = Date(hotel.last_date).date
            if last_date and last_date < hotel.contract[0]:
                last_date = None
            for day in range(self.PAST_DAYS, 0, -1):
                date = Date.today() - dt.timedelta(days=day)
                if not last_date:
                    self.add_status(index, day, self.NOT_DONE if hotel.is_contract_valid(date) else self.NA)
                    continue
                if date < last_date:
                    self.add_status(index, day, self.DONE if hotel.is_contract_valid(date) else self.NA)
                elif date > last_date:
                    self.add_status(index, day, self.NOT_DONE if hotel.is_contract_valid(date) else self.NA)
                else:
                    self.add_status(index, day, self.DONE if hotel.last_timing == Config.EVENING else self.PARTIAL)
            if current_user.hotel != hotel.name:
                continue
            end_date = min(Date.yesterday(), hotel.contract[1])
            last_date = last_date or hotel.contract[0]
            if hotel.contract[0] > Date.today():
                self.status = self.STATUS_NO_CONTRACT
                continue
            if last_date >= end_date:
                self.status = self.STATUS_ALL_DONE if last_date > end_date or hotel.last_timing == Config.EVENING \
                    else self.STATUS_PARTIAL
                continue
            days = (end_date - last_date).days
            self.status = (f"{days} days entry remaining", "list-group-item-danger")
        self.hotels.sort(key=itemgetter(0))
        return

    def add_status(self, index: int, day: int, status: List[str]):
        status = status.copy()
        status.append("d-none d-lg-table-cell" if day > 2 else str())
        self.hotels[index][1].append(status)

    def generate_header(self) -> List[Tuple[int, str]]:
        return [((Date.today() - dt.timedelta(days=day)).day, "d-none d-lg-table-cell" if day > 2 else str())
                for day in range(self.PAST_DAYS, 0, -1)]
