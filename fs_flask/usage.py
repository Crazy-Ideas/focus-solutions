import datetime as dt
from typing import Optional, List, Tuple

from firestore_ci import FirestoreDocument
from flask import url_for, request
from wtforms import SelectMultipleField, ValidationError, HiddenField, \
    StringField, RadioField, DateField

from config import Config, Date
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
        self.client: str = str()
        self.event_type: str = str()
        self.meals: List[str] = list()
        self.ballrooms: List[str] = list()
        self.event_description: str = str()
        self.no_event: bool = False

    def __repr__(self):
        return f"{self.hotel}:{self.date}:{self.timing}:{self.client}:{self.event_type}"

    @classmethod
    def get_data_entry_date(cls, hotel: Hotel) -> Tuple[Optional[dt.date], str]:
        start_date, end_date = hotel.contract
        today = Date.today()
        data_entry_date = Date(hotel.last_date).date
        if end_date < start_date:
            return None, "Invalid Contract"
        if today < start_date:
            return None, "Cannot enter events for future contract"
        if not data_entry_date or data_entry_date < start_date:
            return start_date, Config.MORNING
        if today > end_date and data_entry_date > end_date:
            return end_date, str()
        if data_entry_date < today:
            return (data_entry_date + dt.timedelta(days=1), Config.MORNING) if hotel.last_timing == Config.EVENING \
                else (data_entry_date, Config.EVENING)
        elif data_entry_date == today:
            return (data_entry_date, str()) if hotel.last_timing == Config.EVENING \
                else (data_entry_date, Config.EVENING)
        else:
            return today, Config.EVENING

    @property
    def formatted_date(self) -> str:
        return Date(self.date).format_date

    @property
    def formatted_meal(self) -> str:
        return " and ".join(self.meals)

    @property
    def formatted_ballroom(self) -> str:
        return ", ".join(self.ballrooms)

    def set_date(self, date: dt.date) -> bool:
        self.date = Date(date).db_date
        self.day = date.strftime("%A")
        self.weekday = self.day not in ("Saturday", "Sunday")
        self.month = date.strftime("%Y-%m")
        return True


Usage.init()


class UsageForm(FSForm):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    NO_EVENT = "no event"
    GOTO_DATE = "goto date"
    form_type = HiddenField()
    usage_id = HiddenField()
    client = StringField("Enter client name")
    event_description = StringField("Enter event description")
    event_type = RadioField("Select event type", choices=[(event, event) for event in Config.EVENTS])
    morning_meal = RadioField("Select morning meal", choices=[(meal, meal) for meal in Config.MORNING_MEALS])
    evening_meal = RadioField("Select evening meal", choices=[(meal, meal) for meal in Config.EVENING_MEALS])
    ballrooms = SelectMultipleField("Select ballrooms", choices=list())
    goto_date = DateField("Select date", format="%d/%m/%Y")
    goto_timing = RadioField("Select timing", choices=[(timing, timing) for timing in Config.TIMINGS])

    def __init__(self, hotel_id: str, date: str, timing: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_message: str = str()
        self.redirect: bool = False
        self.hotel: Hotel = Hotel.get_by_id(hotel_id)
        if not self.hotel:
            self._error_redirect("Error in retrieving hotel details")
            return
        self.date = Date(date).date
        self.timing = timing
        if not self.date or self.timing not in Config.TIMINGS:
            self._error_redirect("Error in retrieving event details")
            return
        try:
            self._validate_date(self.date, self.timing)
        except ValidationError as error:
            self._error_redirect(str(error))
            return
        self.format_week: str = Date(self.date).format_week
        self.ballrooms.choices.extend([(room, room) for room in self.hotel.ballrooms])
        self.usage: Optional[Usage] = None
        query = Usage.objects.filter_by(city=self.hotel.city, hotel=self.hotel.name)
        self.usages = query.filter_by(date=Date(self.date).db_date, timing=timing).get()
        self.sort_usages()
        if request.method == "GET" or self.form_type.data != self.GOTO_DATE:
            self.goto_date.data = self.date
            self.goto_timing.data = self.timing

    def _error_redirect(self, message: str):
        self.error_message = message
        self.redirect = True

    def validate_form_type(self, form_type: HiddenField):
        if form_type.data == self.NO_EVENT and self.usages:
            raise ValidationError("Cannot create a no event when there are already events present")

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
        client_exists = any(client.data == usage.client for usage in self.usages)
        if (self.form_type.data == self.CREATE and client_exists) or \
                (self.form_type.data == self.UPDATE and client_exists and self.usage.client != client.data):
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

    def _validate_date(self, date: dt.date, timing: str):
        if not date:
            raise ValidationError(str())
        start_date = Date(self.hotel.start_date).date
        if date < start_date:
            raise ValidationError(f"Date is before the contract start date ({Date(start_date).format_date})")
        data_entry_date, data_entry_timing = Usage.get_data_entry_date(self.hotel)
        if not data_entry_date:
            raise ValidationError(data_entry_timing)
        if date > data_entry_date:
            raise ValidationError(f"Date is beyond the last data entry date ({Date(data_entry_date).format_date})")
        if date == data_entry_date and data_entry_timing == Config.MORNING and timing == Config.EVENING:
            raise ValidationError(f"Cannot goto Evening till the data entry of Morning is completed")

    def validate_goto_date(self, goto_date: DateField):
        self._validate_date(goto_date.data, self.goto_timing.data)

    def update_from_form(self):
        self.usage.client = self.client.data
        self.usage.event_description = self.event_description.data
        self.usage.event_type = self.event_type.data
        self.usage.ballrooms = self.ballrooms.data
        if self.hotel.set_ballroom_used(self.usage.ballrooms):
            self.hotel.save()
        if self.timing == Config.MORNING:
            self.usage.meals = [Config.BREAKFAST, Config.LUNCH] if self.morning_meal.data == Config.BREAKFAST_LUNCH \
                else [self.morning_meal.data]
        else:
            self.usage.meals = [Config.HI_TEA, Config.DINNER] if self.evening_meal.data == Config.HI_TEA_DINNER \
                else [self.evening_meal.data]

    def update_default_fields(self):
        self.usage = Usage()
        self.usage.city = self.hotel.city
        self.usage.hotel = self.hotel.name
        self.usage.set_date(self.date)
        self.usage.timing = self.timing
        if self.hotel.set_last_entry(self.usage.date, self.usage.timing):
            self.hotel.save()

    def sort_usages(self):
        self.usages.sort(key=lambda usage: usage.client)

    def update(self):
        if self.form_type.data == self.GOTO_DATE:
            self.redirect = True
            return
        elif self.form_type.data == self.CREATE:
            self.update_default_fields()
            self.update_from_form()
            self.usage.create()
            self.usages.append(self.usage)
            no_event = next((usage for usage in self.usages if usage.no_event), None)
            if no_event:
                self.usages.remove(no_event)
                no_event.delete()
        elif self.form_type.data == self.UPDATE:
            self.update_from_form()
            self.usage.save()
        elif self.form_type.data == self.DELETE:
            self.usages.remove(self.usage)
            self.usage.delete()
            last_date = Date(self.hotel.last_date).date
            if self.date == last_date and not self.usages:
                self.hotel.remove_last_entry()
                self.hotel.save()
        elif self.form_type.data == self.NO_EVENT:
            self.update_default_fields()
            self.usage.no_event = True
            self.usage.create()
            self.usages.append(self.usage)
        self.sort_usages()
        return

    @property
    def display_previous(self) -> str:
        return "disabled" if (self.date == self.hotel.contract[0] and self.timing == Config.MORNING) \
                             or self.date < self.hotel.contract[0] else str()

    @property
    def link_previous(self) -> str:
        if self.timing == Config.EVENING:
            date = self.date
            timing = Config.MORNING
        else:
            date = self.date - dt.timedelta(days=1)
            timing = Config.EVENING
        return url_for("usage_manage", hotel_id=self.hotel.id, date=Date(date).db_date, timing=timing)

    @property
    def title_previous(self) -> str:
        return "Previous Day Evening" if self.timing == Config.MORNING else "This Day Morning"

    @property
    def display_next(self) -> str:
        if not self.usages:
            return "disabled"
        end_date = min(self.hotel.contract[1], Date.today())
        return "disabled" if (self.date == end_date and self.timing == Config.EVENING) or self.date > end_date \
            else str()

    @property
    def link_next(self) -> str:
        if self.timing == Config.EVENING:
            date = self.date + dt.timedelta(days=1)
            timing = Config.MORNING
        else:
            date = self.date
            timing = Config.EVENING
        return url_for("usage_manage", hotel_id=self.hotel.id, date=Date(date).db_date, timing=timing)

    @property
    def title_next(self) -> str:
        return "This Day Evening" if self.timing == Config.MORNING else "Next Day Morning"

    @property
    def display_no_event(self) -> str:
        return "disabled" if self.usages else str()

    @property
    def link_goto(self) -> str:
        return url_for("usage_manage", hotel_id=self.hotel.id, date=Date(self.goto_date.data).db_date,
                       timing=self.goto_timing.data)
