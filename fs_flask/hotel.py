import datetime as dt
from operator import itemgetter
from typing import List, Optional, Tuple, Union

from firestore_ci import FirestoreDocument
from flask import request
from flask_login import current_user
from flask_wtf.file import FileAllowed
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from wtforms import StringField, SelectMultipleField, HiddenField, SubmitField, ValidationError, SelectField, \
    DateField, IntegerField, FileField
from wtforms.validators import NumberRange, Regexp
from wtforms.validators import Optional as InputOptional

from config import Config, BaseMap, Date
from fs_flask import FSForm
from fs_flask.file import File


class BallroomMap(BaseMap):
    def __init__(self, name: str = None):
        self.name: str = name if name else str()
        self.used: bool = False


class Hotel(FirestoreDocument):
    FILE_EXTENSION = "pdf"

    def __init__(self, name: str = None, ballrooms: List[str] = None, primary_hotels: List[str] = None,
                 secondary_hotels: List[str] = None, city: str = None):
        super().__init__()
        self.name: str = name if name else str()
        self.ballroom_maps: List[dict] = [BallroomMap(room).to_dict() for room in ballrooms] if ballrooms \
            else [BallroomMap(Config.OTHER).to_dict()]
        self.city: str = city if city else str()
        self.primary_hotels: List[str] = primary_hotels[:9] if primary_hotels else list()
        self.secondary_hotels: List[str] = secondary_hotels[:9] if secondary_hotels else list()
        self.start_date: str = str()
        self.end_date: str = str()
        self.full_name: str = str()
        self.company: str = str()
        self.address: str = str()
        self.pin_code: str = str()
        self.pan: str = str()
        self.gst: str = str()
        self.room_count: int = int()
        self.set_contract(Date.today(), Date.today())
        self.last_date: str = str()
        self.last_timing: str = str()
        self.contract_file: str = str()

    def __repr__(self):
        return f"{self.city}:{self.name}:Ballrooms={len(self.ballrooms)}:Primary={len(self.primary_hotels)}"

    @property
    def ballrooms(self):
        return sorted([room["name"] for room in self.ballroom_maps])

    @property
    def used(self):
        return any(room["used"] for room in self.ballroom_maps)

    @property
    def contract(self) -> Tuple[dt.date, dt.date]:
        return Date(self.start_date).date, Date(self.end_date).date

    @property
    def formatted_contract(self) -> Tuple[str, str]:
        return Date(self.start_date).format_date, Date(self.end_date).format_date

    @property
    def display_default(self) -> str:
        return "table-warning font-weight-bold" if current_user.hotel == self.name else str()

    @property
    def display_delete(self) -> str:
        return "disabled" if self.used or self.name == current_user.hotel else str()

    @property
    def full_address(self) -> str:
        address = [self.address, self.city, self.pin_code, Config.CITIES.get(self.city, str())]
        address = [element for element in address if element]
        return " ".join(address)

    @property
    def contract_filename(self) -> str:
        return f"contract_{self.id}"

    @property
    def contract_full_filename(self) -> str:
        return f"{self.contract_filename}.{Hotel.FILE_EXTENSION}"

    @property
    def contract_new_filename(self) -> str:
        return f"{self.name} Contract.{Hotel.FILE_EXTENSION}"

    def display_ballroom(self, ballroom: str) -> str:
        room = self.get_ballroom(ballroom)
        if not room:
            return str()
        return "disabled" if room.used or ballroom == Config.OTHER else str()

    def get_ballroom(self, name) -> Optional[BallroomMap]:
        room = next((room for room in self.ballroom_maps if room["name"] == name), None)
        return BallroomMap.from_dict(room) if room else None

    def add_ballroom(self, name) -> bool:
        if self.get_ballroom(name):
            return False
        self.ballroom_maps.append(BallroomMap(name).to_dict())
        return True

    def remove_ballroom(self, name) -> bool:
        room = self.get_ballroom(name)
        if not room:
            return False
        self.ballroom_maps.remove(room.to_dict())
        return True

    def set_ballroom_used(self, names: List[str], used: bool = True) -> bool:
        room_changed = False
        for name in names:
            room = next((room for room in self.ballroom_maps if room["name"] == name and room["used"] != used), None)
            if room:
                room["used"] = used
                room_changed = True
        return room_changed

    def set_contract(self, start_date: dt.date, end_date: dt.date) -> None:
        self.start_date = Date(start_date).db_date
        self.end_date = Date(end_date).db_date

    def set_last_entry(self, date: Union[str, dt.date], timing: str) -> bool:
        date = Date(date).date
        if not date:
            return False
        last_date = Date(self.last_date).date
        if last_date and last_date > Date.today():
            last_date = None
        if not last_date or date > last_date:
            self.last_date = Date(date).db_date
            self.last_timing = timing
            return True
        elif date == last_date and self.last_timing == Config.MORNING and timing == Config.EVENING:
            self.last_timing = timing
            return True
        return False

    def remove_last_entry(self) -> None:
        if self.last_timing == Config.EVENING:
            self.last_timing = Config.MORNING
        else:
            last_date = Date(self.last_date).date
            if not last_date:
                return
            last_date -= dt.timedelta(days=1)
            self.last_timing = Config.EVENING
            self.last_date = Date(last_date).db_date
        return

    def is_contract_valid(self, date: dt.date) -> bool:
        return self.contract[0] <= date <= self.contract[1]


Hotel.init()


class HotelForm(FSForm):
    # Form Types
    EDIT_HOTEL = "edit_hotel"
    EDIT_BALLROOM = "edit_ballroom"
    NEW_BALLROOM = "new_ballroom"
    REMOVE_BALLROOM = "remove_ballroom"
    EDIT_PRIMARY_HOTEL = "primary_hotel"
    EDIT_SECONDARY_HOTEL = "secondary_hotel"
    UPLOAD_CONTRACT = "upload_contract"
    DELETE_CONTRACT = "delete_contract"
    # Form Fields
    start_date = DateField("Contract start date", format="%d/%m/%Y")
    end_date = DateField("Contract end date", format="%d/%m/%Y")
    full_name = StringField("Hotel Full Name")
    company = StringField("Company Name")
    address = StringField("Address (Exclude City, State, Pincode here)")
    pin_code = StringField("PIN Code (6 digit number)", validators=[
        InputOptional(), Regexp(r"^\d{6}$", message="PIN Code must be 6 digit number")])
    room_count = IntegerField("Number of rooms", default=0, validators=[
        NumberRange(min=0, max=10000, message="Number of rooms must be between 0 and 10000")])
    pan = StringField("PAN # (10 characters, first 5 alpha, next 4 numbers, last alpha)", validators=[
        InputOptional(), Regexp(r"^[A-Z]{5}\d{4}[A-Z]$", message="Invalid PAN format")])
    gst = StringField("GST # (15 characters, first 2 numbers, next 10 PAN, last 3 alpha numeric)", validators=[
        InputOptional(), Regexp(r"^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]{3}$", message="Invalid GST format")])
    contract_filename = FileField(validators=[FileAllowed([Hotel.FILE_EXTENSION])])
    ballroom = StringField("Ball room name")
    primaries = SelectMultipleField("Select Primary Hotels", choices=list())
    secondaries = SelectMultipleField("Select Secondary Hotels", choices=list())
    old_ballroom = HiddenField()
    form_type = HiddenField()

    def __init__(self, hotel: Hotel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.contract_file_path: str = str()
        self.hotel = hotel
        hotels = Hotel.objects.filter_by(city=current_user.city).get()
        hotels.sort(key=lambda hotel_item: hotel_item.name)
        self.primaries.choices.extend([(hotel.name, hotel.name) for hotel in hotels])
        self.primaries.choices.remove((hotel.name, hotel.name))
        self.secondaries.choices = self.primaries.choices
        if request.method == "GET":
            self.primaries.data = hotel.primary_hotels
            self.secondaries.data = hotel.secondary_hotels
            self.start_date.data, self.end_date.data = hotel.contract
            self.full_name.data = hotel.full_name
            self.company.data = hotel.company
            self.address.data = hotel.address
            self.pin_code.data = hotel.pin_code
            self.pan.data = hotel.pan
            self.gst.data = hotel.gst
            self.room_count.data = hotel.room_count

    def raise_date_error(self, message):
        self.start_date.data, self.end_date.data = self.hotel.contract
        raise ValidationError(message)

    def validate_form_type(self, form_type: HiddenField):
        if form_type.data != self.DELETE_CONTRACT:
            return
        if not self.hotel.contract_file:
            raise ValidationError("Contract file does not exists")
        file = File(self.hotel.contract_filename, Hotel.FILE_EXTENSION)
        if not file.delete_from_cloud():
            raise ValidationError("Error in deleting contract")

    def validate_end_date(self, end_date: DateField):
        if self.form_type.data != self.EDIT_HOTEL:
            return
        if not self.start_date.data or not end_date.data:
            self.raise_date_error(str())
        if self.start_date.data > self.end_date.data:
            self.raise_date_error("Contract start date cannot be greater than contract end date")

    def validate_ballroom(self, ballroom: StringField):
        if self.form_type.data == self.EDIT_BALLROOM:
            if ballroom.data in self.hotel.ballrooms:
                raise ValidationError("Duplicate ball room")
            if ballroom.data == self.old_ballroom.data:
                raise ValidationError("Ball room is not changed")
            if self.old_ballroom.data not in self.hotel.ballrooms:
                raise ValidationError("Error in editing ball room")
            if self.hotel.get_ballroom(self.old_ballroom.data).used:
                raise ValidationError("Cannot edit a ballroom with an event")
        if self.form_type.data == self.NEW_BALLROOM and ballroom.data in self.hotel.ballrooms:
            raise ValidationError("Duplicate ball room")

    def validate_old_ballroom(self, old_ballroom: HiddenField):
        if self.form_type.data == self.REMOVE_BALLROOM:
            if old_ballroom.data not in self.hotel.ballrooms:
                raise ValidationError("Error in removing ball rooms")
            if self.hotel.get_ballroom(old_ballroom.data).used:
                raise ValidationError("Cannot remove a ballroom with an event")

    def validate_contract_filename(self, contract_filename: FileField):
        if self.form_type.data != self.UPLOAD_CONTRACT:
            return
        if self.hotel.contract_file:
            raise ValidationError("A contract file already exists")
        file_storage: FileStorage = contract_filename.data
        if not secure_filename(file_storage.filename):
            raise ValidationError("No file selected for upload")
        file = File(self.hotel.contract_filename, Hotel.FILE_EXTENSION)
        file_path = file.local_path
        file_storage.save(file_path)
        if not file.upload_to_cloud():
            raise ValidationError("Error in upload")

    def update(self):
        if self.form_type.data == self.EDIT_HOTEL:
            self.hotel.set_contract(self.start_date.data, self.end_date.data)
            self.hotel.full_name = self.full_name.data
            self.hotel.company = self.company.data
            self.hotel.address = self.address.data
            self.hotel.pin_code = self.pin_code.data
            self.hotel.pan = self.pan.data
            self.hotel.gst = self.gst.data
            self.hotel.room_count = self.room_count.data
        elif self.form_type.data == self.EDIT_PRIMARY_HOTEL:
            self.hotel.primary_hotels = self.primaries.data[:9]
        elif self.form_type.data == self.EDIT_SECONDARY_HOTEL:
            self.hotel.secondary_hotels = self.secondaries.data[:9]
        elif self.form_type.data == self.NEW_BALLROOM:
            self.hotel.add_ballroom(self.ballroom.data)
        elif self.form_type.data == self.EDIT_BALLROOM:
            self.hotel.remove_ballroom(self.old_ballroom.data)
            self.hotel.add_ballroom(self.ballroom.data)
        elif self.form_type.data == self.REMOVE_BALLROOM:
            self.hotel.remove_ballroom(self.old_ballroom.data)
        elif self.form_type.data == self.UPLOAD_CONTRACT:
            self.hotel.contract_file = self.hotel.contract_full_filename
        elif self.form_type.data == self.DELETE_CONTRACT:
            self.hotel.contract_file = str()
        self.hotel.save()


class AdminForm(FSForm):
    EDIT_DEFAULT_CITY = "city"
    EDIT_DEFAULT_HOTEL = "hotel"
    NEW_HOTEL = "new_hotel"
    DELETE_HOTEL = "delete_hotel"
    default_city = SelectField("Select City", choices=list())
    new_hotel = StringField("Enter hotel name (It must be unique)")
    hotel_id = HiddenField()
    form_type = HiddenField()
    submit = SubmitField("Delete")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hotel: Optional[Hotel] = None
        self.hotels = Hotel.objects.filter_by(city=current_user.city).get()
        self.sort_hotels()
        cities = [(city, city) for city in Config.CITIES]
        cities.sort(key=itemgetter(0))
        self.default_city.choices = cities
        if request.method == "GET":
            self.default_city.data = current_user.city

    def sort_hotels(self):
        self.hotels.sort(key=lambda hotel: hotel.name)

    def validate_default_city(self, city: SelectField):
        if self.form_type.data != self.EDIT_DEFAULT_CITY:
            return
        if current_user.city == city.data:
            raise ValidationError("No changes made in default city")

    def validate_new_hotel(self, hotel: StringField):
        if self.form_type.data != self.NEW_HOTEL:
            return
        hotel.data = hotel.data.strip()
        if not hotel.data:
            raise ValidationError("Hotel name cannot be blank")
        if Hotel.objects.filter_by(city=current_user.city, name=hotel.data).first():
            raise ValidationError("Hotel name must be unique")

    def validate_hotel_id(self, hotel_id: HiddenField):
        if self.form_type.data not in (self.DELETE_HOTEL, self.EDIT_DEFAULT_HOTEL):
            return
        self.hotel: Hotel = Hotel.get_by_id(hotel_id.data)
        if not self.hotel:
            raise ValidationError("Hotel not found")
        if self.form_type.data == self.DELETE_HOTEL:
            if self.hotel.used:
                raise ValidationError("Cannot delete a hotel with an event")
            if self.hotel.name == current_user.hotel:
                raise ValidationError("Cannot delete the hotel with default view")
        else:
            if self.hotel.name == current_user.hotel:
                raise ValidationError("No changes made in default hotel")

    def update(self) -> bool:
        if self.form_type.data == self.EDIT_DEFAULT_HOTEL:
            current_user.hotel = self.hotel.name
            return current_user.save()
        elif self.form_type.data == self.EDIT_DEFAULT_CITY:
            current_user.city = self.default_city.data
            self.hotels = Hotel.objects.filter_by(city=current_user.city).get()
            self.sort_hotels()
            current_user.hotel = self.hotels[0].name if self.hotels else str()
            return current_user.save()
        elif self.form_type.data == self.NEW_HOTEL:
            hotel = Hotel(name=self.new_hotel.data, city=current_user.city)
            hotel.create()
            self.hotels.append(hotel)
            self.sort_hotels()
            if not current_user.hotel:
                current_user.hotel = hotel.name
                current_user.save()
            return True
        elif self.form_type.data == self.DELETE_HOTEL:
            self.hotels.remove(self.hotel)
            self.sort_hotels()
            self.hotel.delete()
            return True
        return False
