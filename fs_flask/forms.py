from operator import itemgetter
from typing import List

from flask import flash, request
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, SelectMultipleField, StringField, HiddenField, ValidationError

from config import Config
from fs_flask.hotel import Usage, Hotel


class FSForm(FlaskForm):
    def flash_form_errors(self) -> None:
        for _, errors in self.errors.items():
            for error in errors:
                flash(error)
        return


class QueryForm(FSForm):
    timing = SelectField("Select timing", choices=list())
    meals = SelectMultipleField("Select meals", choices=list())
    event = SelectField("Select event type", choices=list())
    hotels = SelectMultipleField("Select hotels", choices=list())
    submit = SubmitField("Query")

    def populate_choices(self) -> None:
        any_choice = (Config.ANY, Config.ANY)
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

    def get_usage(self) -> List[Usage]:
        query = Usage.objects.filter_by(city=current_user.city)
        filter_meals = False
        if self.validate_on_submit():
            if self.timing.data != Config.ANY:
                query = query.filter_by(timing=self.timing.data)
            if self.event.data != Config.ANY:
                query = query.filter_by(event_type=self.event.data)
            self.meals.data = self.meals.data if self.meals.data else [Config.ANY]
            if self.meals.data[0] == Config.ANY and len(self.meals.data) > 1:
                self.meals.data.remove(Config.ANY)
            if self.meals.data[0] != Config.ANY:
                filter_meals = True
            if not self.hotels.data:
                self.hotels.data = Hotel.get_competitions(current_user.city, current_user.hotel)
        else:
            self.timing.data = Config.ANY
            self.event.data = Config.ANY
            self.meals.data = [Config.ANY]
            self.hotels.data = Hotel.get_competitions(current_user.city, current_user.hotel)
        hotels = self.hotels.data[:9]
        hotels.append(current_user.hotel)
        query = query.filter("hotel", query.IN, hotels)
        usage_data = query.get()
        if filter_meals:
            usage_data = [usage for usage in usage_data if any(meal in usage.meals for meal in self.meals.data)]
        return usage_data

    def get_selection(self) -> dict:
        return {
            "timing": self.timing.data,
            "event": self.event.data,
            "meals": self.meals.data,
            "hotels": self.hotels.data,
        }


class AdminForm(FSForm):
    CITY = "city"
    HOTEL = "hotel"
    NEW_HOTEL = "new_hotel"
    city = SelectField("Select City", choices=list())
    hotel = SelectField("Select Hotel", choices=list())
    new_hotel = StringField("Enter hotel name (It must be unique)")
    select_type = HiddenField()
    submit = SubmitField("Delete")

    def populate_choices(self) -> List[Hotel]:
        self.hotel.choices.append((current_user.hotel, current_user.hotel))
        hotels = Hotel.objects.filter_by(city=current_user.city).get()
        hotels.sort(key=lambda hotel: hotel.name)
        self.hotel.choices.extend([(hotel.name, hotel.name) for hotel in hotels if hotel.name != current_user.hotel])
        self.city.choices.append((current_user.city, current_user.city))
        cities = [(city, city) for city in Config.CITIES if city != current_user.city]
        cities.sort(key=itemgetter(0))
        self.city.choices.extend(cities)
        hotels = Hotel.objects.filter_by(city=current_user.city).get()
        hotels.sort(key=lambda hotel: hotel.name)
        return hotels

    def update_user(self) -> bool:
        if self.select_type.data == self.HOTEL:
            if current_user.hotel == self.hotel.data:
                flash("No changes made")
                return False
            current_user.hotel = self.hotel.data
            return current_user.save()
        elif self.select_type.data == self.CITY:
            if current_user.city == self.city.data:
                flash("No changes made")
                return False
            current_user.city = self.city.data
            hotel = Hotel.objects.filter_by(city=current_user.city).first()
            current_user.hotel = hotel.name if hotel else str()
            return current_user.save()
        elif self.select_type.data == self.NEW_HOTEL:
            if not self.new_hotel.data:
                flash("Hotel name cannot be blank")
                return False
            if Hotel.objects.filter_by(city=current_user.city, name=self.new_hotel.data).first():
                flash("Hotel name must be unique")
                return False
            hotel = Hotel(name=self.new_hotel.data, city=current_user.city).doc_to_dict()
            Hotel.create_from_dict(hotel)
            return True
        return False


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
        hotels = Hotel.objects.filter_by(city=hotel.city).get()
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
            if Usage.objects.filter_by(city=self.hotel.city, hotel=self.hotel.name) \
                    .filter("ballrooms", Usage.objects.ARRAY_CONTAINS, self.old_ballroom.data).first():
                raise ValidationError("Cannot edit a ballroom with an event")
        if self.form_type.data == self.NEW_BALLROOM and ballroom.data in self.hotel.ballrooms:
            raise ValidationError("Duplicate ball room")

    def validate_old_ballroom(self, old_ballroom: HiddenField):
        if self.form_type.data == self.REMOVE_BALLROOM:
            if old_ballroom.data not in self.hotel.ballrooms:
                raise ValidationError("Error in removing ball rooms")
            if Usage.objects.filter_by(city=self.hotel.city, hotel=self.hotel.name) \
                    .filter("ballrooms", Usage.objects.ARRAY_CONTAINS, old_ballroom.data).first():
                raise ValidationError("Cannot remove a ballroom with an event")

    def update(self):
        if self.form_type.data == self.INITIAL:
            self.hotel.initial = self.initial.data
            current_user.update_initial(self.initial.data)
        elif self.form_type.data == self.COMPETITION:
            self.hotel.competitions = self.competitions.data[:9]
        elif self.form_type.data == self.NEW_BALLROOM:
            self.hotel.ballrooms.append(self.ballroom.data)
        elif self.form_type.data == self.EDIT_BALLROOM:
            self.hotel.ballrooms = [self.ballroom.data if room == self.old_ballroom.data else room
                                    for room in self.hotel.ballrooms]
        elif self.form_type.data == self.REMOVE_BALLROOM:
            self.hotel.ballrooms.remove(self.old_ballroom.data)
        self.hotel.save()
