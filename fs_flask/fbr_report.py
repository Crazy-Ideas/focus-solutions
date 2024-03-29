import datetime as dt
import itertools
from operator import itemgetter
from typing import List, Tuple

from flask_login import current_user
from wtforms import SelectMultipleField, DateField, SubmitField, ValidationError, RadioField, HiddenField

from config import Config, Date
from fs_flask import FSForm
from fs_flask.file import File, GridRange, GridCoordinate
from fs_flask.hotel import Hotel
from fs_flask.usage import Usage


class QueryForm(FSForm):
    # Constants
    MAX_ALL_DAYS = 100
    MAX_WEEKDAYS = int(MAX_ALL_DAYS * 7 / 5)
    MAX_WEEKENDS = int(MAX_ALL_DAYS * 7 / 2)
    MAX_SPECIFIC_DAYS = int(MAX_ALL_DAYS * 7 / 1)
    DEFAULT_DATE = Date.previous_lock_in()
    PRIMARY_HOTEL = "Primary Comp Set"
    SECONDARY_HOTEL = "Secondary Comp Set"
    CUSTOM_HOTEL = "Custom Comp Set"
    HOTEL_CHOICES = (PRIMARY_HOTEL, SECONDARY_HOTEL, CUSTOM_HOTEL)
    ALL_TIMING = "All Timings"
    TIMING_CHOICES = tuple([ALL_TIMING] + list(Config.TIMINGS))
    ALL_MEAL = "All Meals"
    ALL_MEAL_CHOICES = tuple([ALL_MEAL] + list(Config.MEALS))
    MORNING_MEAL_CHOICES = tuple([ALL_MEAL] + list(Config.MORNING_MEALS))
    EVENING_MEAL_CHOICES = tuple([ALL_MEAL] + list(Config.EVENING_MEALS))
    ALL_DAY = "All Days"
    WEEKDAY = "Weekdays"
    WEEKEND = "Weekends"
    DAY_CHOICES = (ALL_DAY, WEEKDAY, WEEKEND)
    ALL_EVENT = "All Events"
    EVENT_CHOICES = tuple([ALL_EVENT] + list(Config.EVENTS))
    # Form type
    DOWNLOAD = "download"
    HOTEL_QUERY = "hotel_query"
    FILTER_QUERY = "filter_query"
    # Form elements
    hotel_select = RadioField("Comp Set Type", choices=[(choice, choice) for choice in HOTEL_CHOICES],
                              default=PRIMARY_HOTEL)
    custom_hotels = SelectMultipleField("Select hotels", choices=list())
    start_date = DateField("From Date", default=DEFAULT_DATE, format="%d/%m/%Y")
    end_date = DateField("To Date", default=DEFAULT_DATE, format="%d/%m/%Y")
    timing = RadioField("Select timing", choices=[(timing, timing) for timing in TIMING_CHOICES], default=ALL_TIMING)
    all_meal = RadioField("Select meals", choices=[(meal, meal) for meal in ALL_MEAL_CHOICES], default=ALL_MEAL)
    morning_meal = RadioField("Select morning meals", choices=[(meal, meal) for meal in MORNING_MEAL_CHOICES],
                              default=ALL_MEAL)
    evening_meal = RadioField("Select evening meals", choices=[(meal, meal) for meal in EVENING_MEAL_CHOICES],
                              default=ALL_MEAL)
    day = RadioField("Select the day(s) of the week", choices=[(day, day) for day in DAY_CHOICES], default=ALL_DAY)
    event = RadioField("Select event type", choices=[(event, event) for event in EVENT_CHOICES], default=ALL_EVENT)
    form_type = HiddenField()
    submit = SubmitField("Query")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.error_message: str = str()
        hotels = Hotel.objects.filter_by(city=current_user.city).get()
        hotels.sort(key=lambda hotel: hotel.name)
        self.custom_hotels.choices.extend([(hotel.name, hotel.name) for hotel in hotels
                                           if hotel.name != current_user.hotel])
        hotel: Hotel = next((hotel for hotel in hotels if hotel.name == current_user.hotel), None)
        if not hotel:
            self.error_message = "Error in retrieving the hotel information"
            return
        if current_user.role == Config.HOTEL:
            date, _ = Usage.get_data_entry_date(hotel)
            if not date:
                self.error_message = "Error in retrieving last update date"
                return
            if date <= Date.previous_lock_in() and Date.today() <= hotel.contract.end_date:
                self.error_message = "There are pending data entry for previous lock in period"
                return
        self.primaries = hotel.primary_hotels if hotel else list()
        self.secondaries = hotel.secondary_hotels if hotel else list()
        self.usage_data: List[Usage] = list()
        self.hotel_counts: List[Tuple[Hotel, int]] = list()
        self.hotel_trends: List[Tuple[str, int, float]] = list()
        self.file_path: str = str()

    def raise_date_error(self, message):
        self.start_date.data = self.end_date.data = self.DEFAULT_DATE
        raise ValidationError(message)

    def validate_end_date(self, end_date: DateField):
        if not self.start_date.data or not self.end_date.data:
            self.raise_date_error(str())
        if end_date.data > Date.previous_lock_in():
            self.raise_date_error(f"To Date cannot be greater than previous lock in date "
                                  f"({Date(Date.previous_lock_in()).format_date})")
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

    def get_filter_meals(self) -> List[str]:
        if self.timing.data == self.ALL_TIMING:
            return [self.all_meal.data] if self.all_meal.data != self.ALL_MEAL else list()
        elif self.timing.data == Config.MORNING:
            if self.morning_meal.data == Config.BREAKFAST_LUNCH:
                return [Config.BREAKFAST, Config.LUNCH]
            return [self.morning_meal.data] if self.morning_meal.data != self.ALL_MEAL else list()
        if self.evening_meal.data == Config.HI_TEA_DINNER:
            return [Config.HI_TEA, Config.DINNER]
        return [self.evening_meal.data] if self.evening_meal.data != self.ALL_MEAL else list()

    def update_data(self):
        query = Usage.objects.filter_by(city=current_user.city, no_event=False)
        if self.day.data != self.ALL_DAY:
            query = query.filter_by(weekday=self.day.data == self.WEEKDAY)
        if self.timing.data != self.ALL_TIMING:
            query = query.filter_by(timing=self.timing.data)
        if self.event.data != self.ALL_EVENT:
            query = query.filter_by(event_type=self.event.data)
        if self.hotel_select.data == self.PRIMARY_HOTEL:
            hotels = self.primaries[:]
        elif self.hotel_select.data == self.SECONDARY_HOTEL:
            hotels = self.secondaries[:]
        else:
            hotels = self.custom_hotels.data[:] if self.custom_hotels.data else list()
        hotels.append(current_user.hotel)
        query = query.filter("hotel", query.IN, hotels)
        query = query.filter("date", ">=", Date(self.start_date.data).db_date)
        query = query.filter("date", "<=", Date(self.end_date.data).db_date)
        self.usage_data = query.get()
        filter_meals = self.get_filter_meals()
        if filter_meals:
            self.usage_data = [usage for usage in self.usage_data if any(meal in usage.meals for meal in filter_meals)]
        self.usage_data.sort(key=lambda usage: usage.timing, reverse=True)
        self.usage_data.sort(key=lambda usage: usage.date)
        self.determine_hotel_counts()
        self.determine_hotel_trends()
        if self.form_type.data == self.DOWNLOAD and len(self.usage_data) > 0:
            self.download()

    def download(self):
        sheet = File.create_sheet()
        data_rows = len(self.usage_data) + 4
        sheet.prepare(data_rows=data_rows)
        header = ["Hotel Name", "Date", "Timing", "Client", "Meal", "Event Type", "Ballroom", "BTR"]
        data = [[u.hotel, u.formatted_date, u.timing, u.client, u.formatted_meal, u.event_type, u.formatted_ballroom,
                 u.event_description] for u in self.usage_data]
        data.insert(0, header)
        range_name = f"Data!A1:H{data_rows}"
        sheet.update_range(range_name, data)
        row1 = self.selected_hotels
        row1.extend([str()] * (9 - len(row1)))
        row1.insert(0, self.hotel_select.data)
        row2 = ["From Date", "To Date", "Days", "Timing", "Meal", "Event"] + [str()] * 4
        row3 = [Date(self.start_date.data).format_date, Date(self.end_date.data).format_date, self.day.data,
                self.timing.data, " and ".join(self.meals), self.event.data] + [str()] * 4
        sheet.update_range(f"Report!A1:J3", [row1, row2, row3])
        hotel_counts: List[list] = [list(hotel_count) for hotel_count in self.hotel_counts]
        hotel_counts.insert(0, ["Hotel", f"Total Count={len(self.usage_data)}"])
        row_end = len(self.hotel_counts) + 5
        sheet.update_range(f"Report!H5:I{row_end}", hotel_counts)
        headers = [GridRange.from_range(f"Report!H6:H{row_end}").to_dict()]
        values = [GridRange.from_range(f"Report!I6:I{row_end}").to_dict()]
        anchor = GridCoordinate.from_cell(f"Report!A5").to_dict()
        pie = sheet.pie_spec(headers, values, anchor)
        hotel_trends: List[list] = [list(hotel_trend) for hotel_trend in self.hotel_trends]
        hotel_trends.insert(0, ["Date", "My Prop", "Comp Set Avg"])
        row_end = len(self.hotel_trends) + 25
        sheet.update_range(f"Report!H25:J{row_end}", hotel_trends)
        headers = [GridRange.from_range(f"Report!H25:H{row_end}").to_dict()]
        values = [GridRange.from_range(f"Report!I25:I{row_end}").to_dict(),
                  GridRange.from_range(f"Report!J25:J{row_end}").to_dict()]
        anchor = GridCoordinate.from_cell(f"Report!A25").to_dict()
        trend = sheet.trend_spec(headers, values, anchor)
        sheet.update_chart(pie, trend)
        self.file_path = sheet.download_from_drive()
        sheet.delete_sheet()

    def determine_hotel_trends(self):
        self.usage_data.sort(key=lambda usage: usage.date)
        total_hotel_count = len(self.selected_hotels) + 1
        for date, usages in itertools.groupby(self.usage_data, lambda usage: usage.date):
            date = Date(date).format_date[:6]
            usages = list(usages)
            my_count = sum(1 for usage in usages if usage.hotel == current_user.hotel)
            other_count = sum(1 for usage in usages if usage.hotel != current_user.hotel)
            other_average = round(other_count / total_hotel_count, 1)
            self.hotel_trends.append((date, my_count, other_average))
        return

    def determine_hotel_counts(self):
        hotels = {usage.hotel for usage in self.usage_data}
        self.hotel_counts = [(hotel, sum(1 for usage in self.usage_data if usage.hotel == hotel)) for hotel in hotels]
        self.hotel_counts.sort(key=itemgetter(1), reverse=True)
        if current_user.hotel in hotels:
            current_hotel = next(hotel for hotel in self.hotel_counts if hotel[0] == current_user.hotel)
            self.hotel_counts.remove(current_hotel)
        else:
            current_hotel = (current_user.hotel, 0)
        self.hotel_counts.insert(0, current_hotel)

    @property
    def format_start_date(self) -> str:
        return Date(self.start_date.data).format_week if self.start_date.data else "Invalid date"

    @property
    def format_end_date(self) -> str:
        return Date(self.end_date.data).format_week if self.end_date.data else "Invalid date"

    @property
    def selected_hotels(self) -> List[str]:
        if self.hotel_select.data == self.PRIMARY_HOTEL:
            hotels = self.primaries
        elif self.hotel_select.data == self.SECONDARY_HOTEL:
            hotels = self.secondaries
        else:
            hotels = self.custom_hotels.data
        return hotels if hotels else ["No Hotel"]

    @property
    def meals(self) -> List[str]:
        filter_meals = self.get_filter_meals()
        return filter_meals if filter_meals else [self.ALL_MEAL]


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
        self.header: List[Tuple[int, str, str, str]] = self.generate_header()
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
            if last_date and (last_date < hotel.contract[0] or last_date > Date.next_lock_in()):
                last_date = None
            for day in range(self.PAST_DAYS, -1, -1):
                date = Date.next_lock_in() - dt.timedelta(days=day)
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
        hotel = next((hotel for hotel in self.hotels if hotel[0] == current_user.hotel))
        if hotel:
            self.hotels.remove(hotel)
            self.hotels.insert(0, hotel)
        return

    def add_status(self, index: int, day: int, status: List[str]):
        status = status.copy()
        status.append("d-none d-lg-table-cell" if day > 2 else str())
        self.hotels[index][1].append(status)

    def generate_header(self) -> List[Tuple[int, str, str, str]]:
        return [((Date.next_lock_in() - dt.timedelta(days=day)).day, "d-none d-lg-table-cell" if day > 2 else str(),
                 (Date.next_lock_in() - dt.timedelta(days=day)).strftime("%a")[:2],
                 "bg-warning text-dark" if Date.next_lock_in() - dt.timedelta(days=day) == Date.today() else str())
                for day in range(self.PAST_DAYS, -1, -1)]
