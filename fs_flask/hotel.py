import datetime as dt
from typing import List, Optional

from firestore_ci import FirestoreDocument
from flask_login import current_user

from config import Config


class Hotel(FirestoreDocument):
    def __init__(self, name: str = None, ballrooms: List[str] = None, competitions: List[str] = None,
                 city: str = None):
        super().__init__()
        self.name: str = name if name else str()
        self.ballrooms: List[str] = ballrooms if ballrooms else [Config.OTHER]
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

    @property
    def display(self):
        return "list-group-item-primary" if current_user.hotel == self.name else str()


Hotel.init()


class Usage(FirestoreDocument):
    def __init__(self):
        super().__init__()
        self.hotel: str = str()
        self.city: str = str()
        self.date: str = str()
        self.day: str = str()
        self.weekday: Optional[bool] = None
        self.timing: str = str()
        self.company: str = str()
        self.event_type: str = str()
        self.meals: List[str] = list()
        self.ballrooms: List[str] = list()
        self.event_description: str = str()

    def __repr__(self):
        return f"{self.hotel}:{self.date}:{self.timing}:{self.company}:{self.event_type}"

    def set_date(self, mm_dd_yyyy: str) -> bool:
        try:
            date = dt.datetime.strptime(mm_dd_yyyy, "%m/%d/%Y")
        except ValueError:
            return False
        self.date = date.strftime("%Y-%m-%d")
        self.day = date.strftime("%A")
        self.weekday = self.day not in ("Saturday", "Sunday")
        return True

    @property
    def formatted_date(self):
        return dt.datetime.strptime(self.date, "%Y-%m-%d").strftime("%d-%b-%Y")

    @property
    def formatted_meal(self):
        return ", ".join(self.meals)

    @property
    def formatted_ballroom(self):
        return ", ".join(self.ballrooms)


Usage.init()
