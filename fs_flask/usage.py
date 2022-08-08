import csv
import datetime as dt
import itertools
from typing import Optional, List, Tuple

from firestore_ci import FirestoreDocument
from flask import url_for, request
from flask_login import current_user
from flask_wtf.file import FileAllowed
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from wtforms import SelectMultipleField, ValidationError, HiddenField, \
    StringField, RadioField, DateField, FileField

from config import Config, Date
from fs_flask import FSForm
from fs_flask.file import File
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
        return f"{self.hotel}:{self.formatted_date}:{self.timing}:{self.client}:{self.formatted_ballroom}"

    @classmethod
    def get_data_entry_date(cls, hotel: Hotel) -> Tuple[Optional[dt.date], str]:
        start_date, end_date = hotel.contract
        today = Date.next_lock_in()
        data_entry_date = Date(hotel.last_date).date
        if end_date < start_date:
            return None, "Invalid Contract"
        if today < start_date:
            return None, "Cannot enter events for future contract"
        if not data_entry_date or data_entry_date < start_date:
            return start_date, Config.MORNING
        if today > end_date and data_entry_date > end_date:
            return end_date, str()
        if hotel.last_timing == Config.EVENING and (data_entry_date == end_date or data_entry_date == today):
            return data_entry_date, str()
        if hotel.last_timing == Config.MORNING and data_entry_date <= today:
            return data_entry_date, Config.EVENING
        if hotel.last_timing == Config.EVENING and data_entry_date < today:
            return data_entry_date + dt.timedelta(days=1), Config.MORNING
        return start_date, Config.MORNING

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


class HDR:
    DATE = "Date"
    TIMING = "Timing"
    NO_EVENT = "No_Event"
    CLIENT = "Client"
    MEAL = "Meal"
    TYPE = "Event_Type"
    BALLROOM = "Ballroom"
    EVENT = "Event Description"


class UsageForm(FSForm):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    NO_EVENT = "no event"
    GOTO_DATE = "goto date"
    UPLOAD = "upload"
    form_type = HiddenField()
    usage_id = HiddenField()
    client = StringField("Enter client name")
    event_description = StringField("Enter BTR")
    event_type = RadioField("Select event type", choices=[(event, event) for event in Config.EVENTS])
    morning_meal = RadioField("Select morning meal", choices=[(meal, meal) for meal in Config.MORNING_MEALS])
    evening_meal = RadioField("Select evening meal", choices=[(meal, meal) for meal in Config.EVENING_MEALS])
    ballrooms = SelectMultipleField("Select ballrooms", choices=list())
    goto_date = DateField("Select date", format="%d/%m/%Y")
    goto_timing = RadioField("Select timing", choices=[(timing, timing) for timing in Config.TIMINGS])
    filename = FileField("Choose a csv file to upload", validators=[FileAllowed(["csv"])])

    def __init__(self, hotel_id: str, date: str, timing: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_message: str = str()
        self.redirect: bool = False
        self.upload_errors: list = list()
        self.upload_data: list = list()
        self.hotel: Hotel = Hotel.get_by_id(hotel_id)
        if not self.hotel:
            self._error_redirect("Error in retrieving hotel details")
            return
        self.date = Date(date).date
        self.timing = timing
        if not self.date or self.timing not in Config.TIMINGS:
            self._error_redirect("Error in retrieving event details")
            return
        if current_user.role != Config.ADMIN:
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
        if form_type.data == self.UPLOAD and self.disable_upload:
            raise ValidationError(f"Cannot upload when upload is disabled")

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
        if self.form_type.data != self.GOTO_DATE:
            return
        if current_user.role == Config.ADMIN:
            return
        self._validate_date(goto_date.data, self.goto_timing.data)

    def _check_start_period_of_uploaded_file(self):
        first_date, first_timing = Date(self.upload_data[0].date).date, self.upload_data[0].timing
        next_date, next_timing = Usage.get_data_entry_date(self.hotel)
        if (first_date, first_timing) != (next_date, next_timing):
            raise ValidationError(f"Start period ({Date(first_date).format_date} - {first_timing}) does not match with "
                                  f"the next data entry period ({Date(next_date).format_date} - {next_timing})")

    def validate_filename(self, filename: FileField):
        if self.form_type.data != self.UPLOAD:
            return
        file: FileStorage = filename.data
        if not secure_filename(file.filename):
            raise ValidationError("No file selected for upload")
        file_path = File(current_user.id, "csv").local_path
        file.save(file_path)
        with open(file_path) as csv_file:
            csv_reader = csv.DictReader(csv_file)
            columns = set(csv_reader.fieldnames)
            csv_reader = [row for row in csv_reader]
        if columns != {HDR.DATE, HDR.TIMING, HDR.NO_EVENT, HDR.CLIENT, HDR.MEAL, HDR.TYPE, HDR.BALLROOM, HDR.EVENT}:
            raise ValidationError("Invalid column names in the csv file")
        for row in csv_reader:
            usage = Usage()
            usage.hotel = self.hotel.name
            usage.city = self.hotel.city
            date = Date.from_dd_mmm_yyyy(row[HDR.DATE]).date
            if not date:
                self.add_errors(row, HDR.DATE)
                continue
            usage.set_date(date)
            if row[HDR.TIMING] not in Config.TIMINGS:
                self.add_errors(row, HDR.TIMING)
                continue
            usage.timing = row[HDR.TIMING]
            if row[HDR.NO_EVENT] == HDR.NO_EVENT:
                usage.no_event = True
                self.upload_data.append(usage)
                continue
            if not row[HDR.CLIENT]:
                self.add_errors(row, HDR.CLIENT)
                continue
            usage.client = row[HDR.CLIENT]
            if usage.timing == Config.MORNING:
                if row[HDR.MEAL] not in Config.MORNING_MEALS:
                    self.add_errors(row, HDR.MEAL)
                    continue
                usage.meals = [Config.BREAKFAST, Config.LUNCH] if row[HDR.MEAL] == Config.BREAKFAST_LUNCH \
                    else [row[HDR.MEAL]]
            else:
                if row[HDR.MEAL] not in Config.EVENING_MEALS:
                    self.add_errors(row, HDR.MEAL)
                    continue
                usage.meals = [Config.HI_TEA, Config.DINNER] if row[HDR.MEAL] == Config.HI_TEA_DINNER \
                    else [row[HDR.MEAL]]
            if row[HDR.TYPE] not in Config.EVENTS:
                self.add_errors(row, HDR.TYPE)
                continue
            usage.event_type = row[HDR.TYPE]
            ballrooms = [room.strip() for room in row[HDR.BALLROOM].split(",")]
            if any(room not in self.hotel.ballrooms for room in ballrooms):
                self.add_errors(row, HDR.BALLROOM)
                continue
            usage.ballrooms = ballrooms
            self.hotel.set_ballroom_used(ballrooms)
            usage.event_description = row[HDR.EVENT]
            self.upload_data.append(usage)
        if self.upload_errors:
            raise ValidationError("Field specific errors. Fields with red highlight have errors.")
        if not self.upload_data:
            raise ValidationError("There are no events in the csv file")
        self.upload_data.sort(key=lambda usage_item: usage_item.timing, reverse=True)
        self.upload_data.sort(key=lambda usage_item: usage_item.date)
        if current_user.role != Config.ADMIN:
            self._check_start_period_of_uploaded_file()
            last_date = Date(self.upload_data[-1].date).date
            lock_in = Date.next_lock_in()
            end_date = self.hotel.contract[1]
            if last_date > lock_in:
                raise ValidationError(f"End period ({Date(last_date).format_date}) cannot be greater than the "
                                      f"next lock in period ({Date(lock_in).format_date})")
            if last_date > end_date:
                raise ValidationError(f"End period ({Date(last_date).format_date}) cannot be greater than the "
                                      f"contract end date ({Date(end_date).format_date})")
        previous_date = None
        for date, date_usages in itertools.groupby(self.upload_data, key=lambda usage_item: usage_item.date):
            date = Date(date).date
            date_usages = list(date_usages)
            if not any(usage.timing == Config.MORNING for usage in date_usages):
                raise ValidationError(f"Date {Date(date).format_date} does not have {Config.MORNING} events")
            if not any(usage.timing == Config.EVENING for usage in date_usages):
                raise ValidationError(f"Date {Date(date).format_date} does not have {Config.EVENING} events")
            for timing, timing_usages in itertools.groupby(date_usages, key=lambda usage_item: usage_item.timing):
                seen = set()
                for usage in timing_usages:
                    if usage.client in seen:
                        raise ValidationError(f"Duplicate client name {usage.client} for the period "
                                              f"{Date(date).format_date} - {timing}")
                    seen.add(usage.client)
            if previous_date and (date - previous_date).days != 1:
                raise ValidationError(f"There are missing events between {Date(previous_date).format_date} and "
                                      f"{Date(date).format_date}")
            previous_date = date
        return

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

    def add_errors(self, row: dict, field: str):
        self.upload_errors.append({field_name: {"data": data, "error": "table-danger" if field_name == field else str()}
                                   for field_name, data in row.items()})

    def update(self):
        if self.form_type.data == self.GOTO_DATE:
            self.redirect = True
            return
        elif self.form_type.data == self.UPLOAD:
            self.hotel.set_last_entry(self.upload_data[-1].date, self.upload_data[-1].timing)
            usages = Usage.create_from_list_of_dict([usage.doc_to_dict() for usage in self.upload_data])
            self.hotel.save()
            if not self.usages:
                self.usages = [u for u in usages if Date(self.date).db_date == u.date and self.timing == u.timing]
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
        if current_user.role == Config.ADMIN:
            return str()
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
        if current_user.role == Config.ADMIN:
            return str()
        if not self.usages:
            return "disabled"
        end_date = min(self.hotel.contract[1], Date.next_lock_in())
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

    @property
    def display_upload(self) -> str:
        return "disabled" if self.disable_upload else str()

    @property
    def display_bug(self) -> str:
        return "disabled" if not self.filename.errors else str()

    @property
    def disable_upload(self) -> bool:
        if current_user.role == Config.ADMIN:
            return False
        if self.timing == Config.EVENING:
            return True
        if Usage.get_data_entry_date(self.hotel) != (self.date, self.timing) or self.usages:
            return True
        return False

    @property
    def display_edit_delete(self) -> str:
        return "disabled" if current_user.role == Config.HOTEL and self.date < Date.previous_lock_in() else str()
