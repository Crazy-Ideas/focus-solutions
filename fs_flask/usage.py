import datetime as dt
from typing import Optional, List, Tuple

from firestore_ci import FirestoreDocument
from wtforms import SelectField, SelectMultipleField, ValidationError, HiddenField, \
    StringField, BooleanField

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

    def __repr__(self):
        return f"{self.hotel}:{self.date}:{self.timing}:{self.company}:{self.event_type}"

    @classmethod
    def db_date(cls, date: dt.datetime) -> str:
        return date.strftime("%Y-%m-%d")

    @classmethod
    def date_in_datetime(cls, yyyy_mm_dd: str) -> Optional[dt.datetime]:
        try:
            return dt.datetime.strptime(yyyy_mm_dd, "%Y-%m-%d")
        except ValueError:
            return None

    @classmethod
    def get_data_entry_date(cls, hotel: Hotel) -> Tuple[Optional[dt.datetime], str]:
        start_date, end_date = hotel.contract
        end_date = today() if end_date > today() else end_date
        query = cls.objects.filter_by(city=hotel.city, hotel=hotel.name)
        query = query.filter("date", ">=", cls.db_date(start_date)).filter("date", "<=", cls.db_date(end_date))
        last_usage = query.order_by("date", cls.objects.ORDER_DESCENDING).first()
        if not last_usage:
            return start_date, Config.MORNING
        last_day_usage = cls.objects.filter_by(city=hotel.city, hotel=hotel.name, date=last_usage.date).get()
        data_entry_date = cls.date_in_datetime(last_day_usage[0].date)
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
        date = self.date_in_datetime(self.date)
        return date.strftime("%d-%b-%Y") if date else str()

    @property
    def formatted_meal(self) -> str:
        return ", ".join(self.meals)

    @property
    def formatted_ballroom(self) -> str:
        return ", ".join(self.ballrooms)

    def set_date(self, date: dt.datetime) -> bool:
        self.date = date.strftime("%Y-%m-%d")
        self.day = date.strftime("%A")
        self.weekday = self.day not in ("Saturday", "Sunday")
        self.month = date.strftime("%Y-%m")
        return True


Usage.init()


class UsageForm(FSForm):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    form_type = HiddenField()
    usage_id = HiddenField()
    client = StringField("Enter client name")
    event_description = StringField("Enter event description")
    event_type = SelectField("Select event type", choices=[(event, event) for event in Config.EVENTS])
    breakfast = BooleanField(Config.BREAKFAST)
    lunch = BooleanField(Config.LUNCH)
    hi_tea = BooleanField(Config.HI_TEA)
    dinner = BooleanField(Config.DINNER)
    no_meal = BooleanField(Config.NO_MEAL)
    ballrooms = SelectMultipleField("Select ballrooms", choices=list())

    def __init__(self, hotel: Hotel, date: dt.datetime, timing: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hotel: Hotel = hotel
        self.date: dt.datetime = date
        self.timing: str = timing
        self.ballrooms.choices.extend([(room, room) for room in hotel.ballrooms])
        self.usage: Optional[Usage] = None
        self.usages = Usage.objects.filter_by(city=hotel.city, hotel=hotel.name, date=Usage.db_date(date)).get()

    def validate_usage_id(self, usage_id: StringField):
        if self.form_type.data != self.UPDATE and self.form_type.data != self.DELETE:
            return
        if usage_id.data not in [usage.id for usage in self.usages]:
            raise ValidationError("Error in processing data")
        self.usage = next(usage for usage in self.usages if usage_id == usage.id)

    def validate_client(self, client: StringField):
        if self.form_type.data != self.UPDATE and self.form_type.data != self.CREATE:
            return
        if not client.data:
            raise ValidationError("Client name cannot be left blank")

    def validate_no_meal(self, no_meal: BooleanField):
        if self.form_type.data != self.UPDATE and self.form_type.data != self.CREATE:
            return
        if no_meal.data:
            if self.breakfast.data or self.lunch.data or self.hi_tea.data or self.dinner.data:
                raise ValidationError(f"Cannot select a meal with a {Config.NO_MEAL} option")
        elif self.timing == Config.MORNING:
            if not self.breakfast.data and not self.lunch.data:
                raise ValidationError(f"Please select {Config.BREAKFAST} or {Config.LUNCH} or {Config.NO_MEAL} for "
                                      f"{Config.MORNING} events")
            if self.hi_tea.data or self.dinner.data:
                raise ValidationError(f"Cannot select {Config.HI_TEA} or {Config.DINNER} for {Config.MORNING} events")
        elif self.timing == Config.EVENING:
            if not self.hi_tea.data and not self.dinner.data:
                raise ValidationError(f"Please select {Config.HI_TEA} or {Config.DINNER} or {Config.NO_MEAL} for "
                                      f"{Config.EVENING} events")
            if self.breakfast.data or self.lunch.data:
                raise ValidationError(f"Cannot select {Config.BREAKFAST} or {Config.LUNCH} for {Config.EVENING} events")

    def update_from_form(self):
        self.usage.company = self.client.data
        self.usage.event_description = self.event_description.data
        self.usage.event_type = self.event_type.data
        self.usage.ballrooms = self.ballrooms.data
        self.usage.meals = [
            Config.BREAKFAST if self.breakfast.data else str(),
            Config.LUNCH if self.lunch.data else str(),
            Config.HI_TEA if self.hi_tea.data else str(),
            Config.DINNER if self.dinner.data else str(),
            Config.NO_MEAL if self.no_meal.data else str(),
        ]
        self.usage.meals = [meal for meal in self.usage.meals if meal]

    def update(self):
        if self.form_type.data == self.CREATE:
            self.usage = Usage()
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
