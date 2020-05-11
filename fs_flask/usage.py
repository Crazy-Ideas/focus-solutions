import datetime as dt
from typing import Optional, List, Tuple

from firestore_ci import FirestoreDocument
from flask import url_for
from wtforms import SelectMultipleField, ValidationError, HiddenField, \
    StringField, RadioField

from config import Config, today
from fs_flask import FSForm
from fs_flask.hotel import Hotel


class Usage(FirestoreDocument):
    def __init__(self):
        super().__init__()
        self.hotel: str = str()
        self.city: str = str()
        self.date: str = str()
        self.day: str = str()
        self.month: str = str()
        self.weekday: Optional[bool] = None
        self.timing: str = str()
        self.company: str = str()
        self.event_type: str = str()
        self.meals: List[str] = list()
        self.ballrooms: List[str] = list()
        self.event_description: str = str()
        self.no_event: bool = False

    def __repr__(self):
        return f"{self.hotel}:{self.date}:{self.timing}:{self.company}:{self.event_type}"

    @classmethod
    def db_date(cls, date: dt.date) -> str:
        return date.strftime("%Y-%m-%d")

    @classmethod
    def to_date(cls, yyyy_mm_dd: str) -> Optional[dt.date]:
        try:
            return dt.datetime.strptime(yyyy_mm_dd, "%Y-%m-%d").date()
        except ValueError:
            return None

    @classmethod
    def get_data_entry_date(cls, hotel: Hotel) -> Tuple[Optional[dt.date], str]:
        start_date, end_date = hotel.contract
        end_date = today() if end_date > today() else end_date
        query = cls.objects.filter_by(city=hotel.city, hotel=hotel.name)
        query = query.filter("date", ">=", cls.db_date(start_date)).filter("date", "<=", cls.db_date(end_date))
        last_usage = query.order_by("date", cls.objects.ORDER_DESCENDING).first()
        if not last_usage:
            return start_date, Config.MORNING
        last_day_usage = cls.objects.filter_by(city=hotel.city, hotel=hotel.name, date=last_usage.date).get()
        data_entry_date = cls.to_date(last_day_usage[0].date)
        if not data_entry_date:
            return None, str()
        if any(usage.timing == Config.EVENING for usage in last_day_usage):
            data_entry_date = data_entry_date + dt.timedelta(days=1)
            if data_entry_date > end_date:
                return end_date, str()
            else:
                return data_entry_date, Config.MORNING
        else:
            return data_entry_date, Config.EVENING

    @property
    def formatted_date(self) -> str:
        date = self.to_date(self.date)
        return date.strftime("%d-%b-%Y") if date else str()

    @property
    def formatted_meal(self) -> str:
        return ", ".join(self.meals)

    @property
    def formatted_ballroom(self) -> str:
        return ", ".join(self.ballrooms)

    def set_date(self, date: dt.date) -> bool:
        self.date = date.strftime("%Y-%m-%d")
        self.day = date.strftime("%A")
        self.weekday = self.day not in ("Saturday", "Sunday")
        self.month = date.strftime("%Y-%m")
        return True


Usage.init()


class UsageForm(FSForm):
    BREAKFAST_LUNCH = f"{Config.BREAKFAST} & {Config.LUNCH}"
    HI_TEA_DINNER = f"{Config.HI_TEA} & {Config.DINNER}"
    MORNING_MEALS = [Config.BREAKFAST, Config.LUNCH, BREAKFAST_LUNCH, Config.NO_MEAL]
    EVENING_MEALS = [Config.HI_TEA, Config.DINNER, HI_TEA_DINNER, Config.NO_MEAL]
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    form_type = HiddenField()
    usage_id = HiddenField()
    client = StringField("Enter client name")
    event_description = StringField("Enter event description")
    event_type = RadioField("Select event type", choices=[(event, event) for event in Config.EVENTS])
    morning_meal = RadioField("Select meal", choices=[(meal, meal) for meal in MORNING_MEALS])
    evening_meal = RadioField("Select meal", choices=[(meal, meal) for meal in EVENING_MEALS])
    ballrooms = SelectMultipleField("Select ballrooms", choices=list())

    def __init__(self, hotel: Hotel, date: dt.date, timing: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hotel: Hotel = hotel
        self.date: dt.date = date
        self.timing: str = timing
        self.ballrooms.choices.extend([(room, room) for room in hotel.ballrooms])
        self.usage: Optional[Usage] = None
        query = Usage.objects.filter_by(city=hotel.city, hotel=hotel.name)
        self.usages = query.filter_by(date=Usage.db_date(date), timing=timing).get()

    def validate_usage_id(self, usage_id: StringField):
        if self.form_type.data != self.UPDATE and self.form_type.data != self.DELETE:
            return
        if usage_id.data not in [usage.id for usage in self.usages]:
            raise ValidationError("Error in processing data")
        self.usage = next(usage for usage in self.usages if usage_id.data == usage.id)

    def validate_client(self, client: StringField):
        if self.form_type.data != self.UPDATE and self.form_type.data != self.CREATE:
            return
        if not client.data:
            raise ValidationError("Client name cannot be left blank")
        if self.form_type.data == self.CREATE and any(client.data == usage.company for usage in self.usages):
            raise ValidationError("Client name must be unique within a day")

    def validate_ballrooms(self, ballrooms: SelectMultipleField):
        if self.form_type.data != self.UPDATE and self.form_type.data != self.CREATE:
            return
        if not ballrooms.data:
            raise ValidationError("At least one ballroom needs to be selected")

    def validate_morning_meal(self, morning_meal: RadioField):
        if self.form_type.data != self.UPDATE and self.form_type.data != self.CREATE:
            return
        if not morning_meal.data or not self.evening_meal.data:
            morning_meal.data = self.evening_meal.data = Config.NO_MEAL
            raise ValidationError(f"One meal option needs to be selected")
        elif self.timing == Config.MORNING:
            if self.evening_meal.data != Config.NO_MEAL:
                raise ValidationError(f"Cannot select {Config.HI_TEA} or {Config.DINNER} for {Config.MORNING} events")
        elif self.timing == Config.EVENING:
            if morning_meal.data != Config.NO_MEAL:
                raise ValidationError(f"Cannot select {Config.BREAKFAST} or {Config.LUNCH} for {Config.EVENING} events")

    def update_from_form(self):
        self.usage.company = self.client.data
        self.usage.event_description = self.event_description.data
        self.usage.event_type = self.event_type.data
        self.usage.ballrooms = self.ballrooms.data
        if self.timing == Config.MORNING:
            self.usage.meals = [Config.BREAKFAST, Config.LUNCH] if self.morning_meal.data == self.BREAKFAST_LUNCH \
                else [self.morning_meal.data]
        else:
            self.usage.meals = [Config.HI_TEA, Config.DINNER] if self.evening_meal.data == self.HI_TEA_DINNER \
                else [self.evening_meal.data]

    def update(self):
        if self.form_type.data == self.CREATE:
            self.usage = Usage()
            self.usage.city = self.hotel.city
            self.usage.hotel = self.hotel.name
            self.usage.set_date(self.date)
            self.usage.timing = self.timing
            self.update_from_form()
            self.usage.create()
            self.usages.append(self.usage)
        elif self.form_type.data == self.UPDATE:
            self.update_from_form()
            self.usage.save()
        elif self.form_type.data == self.DELETE:
            self.usages.remove(self.usage)
            self.usage.delete()

    @property
    def formatted_date(self) -> str:
        return self.date.strftime("%a, %d-%b-%Y")

    @property
    def display_previous(self) -> str:
        return "disabled" if self.date <= self.hotel.contract[0] else str()

    @property
    def link_previous(self) -> str:
        if self.timing == Config.EVENING:
            date = self.date
            timing = Config.MORNING
        else:
            date = self.date - dt.timedelta(days=1)
            timing = Config.EVENING
        return url_for("usage_manage", hotel_id=self.hotel.id, date=Usage.db_date(date), timing=timing)

    @property
    def display_next(self) -> str:
        if not self.usages:
            return "disabled"
        end_date = max(self.hotel.contract[1], today())
        return "disabled" if self.date >= end_date else str()

    @property
    def link_next(self) -> str:
        if self.timing == Config.EVENING:
            date = self.date + dt.timedelta(days=1)
            timing = Config.MORNING
        else:
            date = self.date
            timing = Config.EVENING
        return url_for("usage_manage", hotel_id=self.hotel.id, date=Usage.db_date(date), timing=timing)

    @property
    def display_no_event(self) -> str:
        return "disabled" if self.usages else str()
