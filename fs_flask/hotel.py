from operator import itemgetter
from typing import List, Optional

from firestore_ci import FirestoreDocument
from flask import request
from flask_login import current_user
from wtforms import StringField, SelectMultipleField, HiddenField, SubmitField, ValidationError, SelectField

from config import Config, BaseMap
from fs_flask import FSForm


class BallroomMap(BaseMap):
    def __init__(self, name: str = None):
        self.name: str = name if name else str()
        self.used: bool = False


class Hotel(FirestoreDocument):
    def __init__(self, name: str = None, ballrooms: List[str] = None, competitions: List[str] = None,
                 city: str = None):
        super().__init__()
        self.name: str = name if name else str()
        self.ballroom_maps: List[dict] = [BallroomMap(room).to_dict() for room in ballrooms] if ballrooms \
            else [BallroomMap(Config.OTHER).to_dict()]
        self.city: str = city if city else str()
        self.competitions: List[str] = competitions if competitions else list()
        self.initial: str = "".join([word[0] for word in name.split()][:3]).upper() if name else str()
        self.email: str = str()

    def __repr__(self):
        return f"{self.city}:{self.name}:Ballrooms={len(self.ballrooms)}:Competitions={len(self.competitions)}"

    @classmethod
    def get_competitions(cls, city: str, hotel: str) -> List[str]:
        competitions = list()
        my_hotel: Hotel = cls.objects.filter_by(city=city, name=hotel).first()
        if my_hotel:
            competitions.extend(sorted(my_hotel.competitions))
        return competitions[:9]

    @classmethod
    def get_hotels(cls, city: str) -> List['Hotel']:
        hotels = cls.objects.filter_by(city=city).get()
        hotels.sort(key=lambda hotel: hotel.name)
        return hotels

    @property
    def ballrooms(self):
        return sorted([room["name"] for room in self.ballroom_maps])

    @property
    def used(self):
        return any(room["used"] for room in self.ballroom_maps)

    @property
    def display(self):
        return "list-group-item-primary" if current_user.hotel == self.name else str()

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

    def set_ballroom_used(self, names: List[str]) -> bool:
        room_changed = False
        for name in names:
            room = next((room for room in self.ballroom_maps if room["name"] == name and not room["used"]), None)
            if room:
                room["used"] = True
                room_changed = True
        return room_changed


Hotel.init()


class HotelForm(FSForm):
    INITIAL = "initial"
    EDIT_BALLROOM = "edit_ballroom"
    NEW_BALLROOM = "new_ballroom"
    REMOVE_BALLROOM = "remove_ballroom"
    COMPETITION = "hotel"
    initial = StringField("Enter Initial (Can be 2 or 3 alphabets)")
    ballroom = StringField("Ball room name")
    competitions = SelectMultipleField("Select hotels", choices=list())
    old_ballroom = HiddenField()
    form_type = HiddenField()
    submit = SubmitField()

    def __init__(self, hotel: Hotel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hotel = hotel
        hotels = Hotel.get_hotels(hotel.city)
        self.competitions.choices.extend([(hotel.name, hotel.name) for hotel in hotels])
        self.competitions.choices.remove((hotel.name, hotel.name))
        if request.method == "GET":
            self.competitions.data = hotel.competitions
            self.initial.data = hotel.initial

    def validate_initial(self, initial: StringField):
        if self.form_type.data != self.INITIAL:
            return
        initial.data = initial.data.strip().upper()
        if not initial.data.isalpha() or not 2 <= len(initial.data) <= 3:
            raise ValidationError("Invalid Initial")

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
        if self.form_type.data == self.INITIAL:
            self.hotel.initial = self.initial.data
            current_user.update_initial(self.initial.data)
        elif self.form_type.data == self.COMPETITION:
            self.hotel.competitions = self.competitions.data[:9]
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
    default_hotel = SelectField("Select Hotel", choices=list())
    new_hotel = StringField("Enter hotel name (It must be unique)")
    delete_hotel = HiddenField()
    form_type = HiddenField()
    submit = SubmitField("Delete")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, "hotels"):
            self.hotels = Hotel.get_hotels(current_user.city)
        self.default_hotel.choices = [(hotel.name, hotel.name) for hotel in self.hotels] if self.hotels else [("", "")]
        cities = [(city, city) for city in Config.CITIES]
        cities.sort(key=itemgetter(0))
        self.default_city.choices = cities
        if request.method == "GET":
            self.default_city.data = current_user.city
            self.default_hotel.data = current_user.hotel

    def validate_default_city(self, city: SelectField):
        if self.form_type.data != self.EDIT_DEFAULT_CITY:
            return
        if current_user.city == city.data:
            raise ValidationError("No changes made in default city")

    def validate_default_hotel(self, hotel: SelectField):
        if self.form_type.data != self.EDIT_DEFAULT_HOTEL:
            return
        if current_user.hotel == hotel.data:
            raise ValidationError("No changes made in default hotel")

    def validate_new_hotel(self, hotel: StringField):
        if self.form_type.data != self.NEW_HOTEL:
            return
        hotel.data = hotel.data.strip()
        if not hotel.data:
            raise ValidationError("Hotel name cannot be blank")
        if Hotel.objects.filter_by(city=current_user.city, name=hotel.data).first():
            raise ValidationError("Hotel name must be unique")

    def validate_delete_hotel(self, delete_hotel: StringField):
        if self.form_type.data != self.DELETE_HOTEL:
            return
        hotel: Hotel = next((hotel for hotel in self.hotels if delete_hotel.data == hotel.name), None)
        if not hotel:
            raise ValidationError("Hotel not found")
        if hotel.used:
            raise ValidationError("Cannot delete a hotel with an event")
        if hotel.name == current_user.hotel:
            raise ValidationError("Cannot delete the hotel with default view")

    def update(self) -> bool:
        if self.form_type.data == self.EDIT_DEFAULT_HOTEL:
            current_user.hotel = self.default_hotel.data
            return current_user.save()
        elif self.form_type.data == self.EDIT_DEFAULT_CITY:
            current_user.city = self.default_city.data
            self.hotels = Hotel.get_hotels(current_user.city)
            current_user.hotel = self.hotels[0].name if self.hotels else str()
            self.default_hotel.data = current_user.hotel
            self.default_hotel.choices = [(hotel.name, hotel.name) for hotel in self.hotels]
            return current_user.save()
        elif self.form_type.data == self.NEW_HOTEL:
            hotel = Hotel(name=self.new_hotel.data, city=current_user.city)
            hotel.create()
            self.hotels.append(hotel)
            self.hotels.sort(key=lambda hotel_item: hotel_item.name)
            self.default_hotel.choices.append((hotel.name, hotel.name))
            if not self.default_hotel.data:
                self.default_hotel.data = hotel.name
                self.default_hotel.choices.remove(("", ""))
            if not current_user.hotel:
                current_user.hotel = hotel.name
                current_user.save()
            return True
        elif self.form_type.data == self.DELETE_HOTEL:
            hotel: Hotel = next((hotel for hotel in self.hotels if self.delete_hotel.data == hotel.name), None)
            hotel.delete()
            self.hotels.remove(hotel)
            self.default_hotel.choices.remove((hotel.name, hotel.name))
            return True
        return False
