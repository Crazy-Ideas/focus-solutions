import datetime as dt
from operator import itemgetter
from typing import List, Optional, Tuple, Union

from firestore_ci import FirestoreDocument
from flask import request
from flask_login import current_user
from wtforms import StringField, SelectMultipleField, HiddenField, SubmitField, ValidationError, SelectField, DateField

from config import Config, BaseMap, Date
from fs_flask import FSForm


class BallroomMap(BaseMap):
    def __init__(self, name: str = None):
        self.name: str = name if name else str()
        self.used: bool = False


class Hotel(FirestoreDocument):
    def __init__(self, name: str = None, ballrooms: List[str] = None, primary_hotels: List[str] = None,
                 secondary_hotels: List[str] = None, city: str = None):
        super().__init__()
        self.name: str = name if name else str()
        self.ballroom_maps: List[dict] = [BallroomMap(room).to_dict() for room in ballrooms] if ballrooms \
            else [BallroomMap(Config.OTHER).to_dict()]
        self.city: str = city if city else str()
        self.primary_hotels: List[str] = primary_hotels[:9] if primary_hotels else list()
        self.secondary_hotels: List[str] = secondary_hotels[:9] if secondary_hotels else list()
        self.email: str = str()
        self.start_date: str = str()
        self.end_date: str = str()
        self.set_contract(Date.today(), Date.today())
        self.last_date: str = str()
        self.last_timing: str = str()

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
        if not self.last_date or date > last_date:
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
            self.last_timing = Config.EVENING
            last_date = Date(self.last_date).date
            if not last_date:
                last_date = Date(self.start_date).date
                if not last_date:
                    return
            last_date -= dt.timedelta(days=1)
            self.last_date = Date(last_date).db_date
        return

    def is_contract_valid(self, date: dt.date) -> bool:
        return self.contract[0] <= date <= self.contract[1]


Hotel.init()


class HotelForm(FSForm):
    DEFAULT_DATE = Date.today()
    EDIT_HOTEL = "edit_hotel"
    EDIT_BALLROOM = "edit_ballroom"
    NEW_BALLROOM = "new_ballroom"
    REMOVE_BALLROOM = "remove_ballroom"
    EDIT_PRIMARY_HOTEL = "primary_hotel"
    EDIT_SECONDARY_HOTEL = "secondary_hotel"
    start_date = DateField("Select contract start date")
    end_date = DateField("Select contract end date")
    ballroom = StringField("Ball room name")
    primaries = SelectMultipleField("Select Primary Hotels", choices=list())
    secondaries = SelectMultipleField("Select Secondary Hotels", choices=list())
    old_ballroom = HiddenField()
    form_type = HiddenField()
    submit = SubmitField()

    def __init__(self, hotel: Hotel, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

    def raise_date_error(self, message):
        self.start_date.data, self.end_date.data = self.hotel.contract
        raise ValidationError(message)

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

    def update(self):
        if self.form_type.data == self.EDIT_HOTEL:
            self.hotel.set_contract(self.start_date.data, self.end_date.data)
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
