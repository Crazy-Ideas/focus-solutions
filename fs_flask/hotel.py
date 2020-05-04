import datetime as dt
from typing import List, Optional

from firestore_ci import FirestoreDocument


class Hotel(FirestoreDocument):
    def __init__(self, name: str = None, ball_rooms: List[str] = None, city: str = None):
        super().__init__()
        self.name: str = name if name else str()
        self.ball_rooms: List[str] = ball_rooms if ball_rooms else list()
        self.city: str = city if city else str()

    def __repr__(self):
        return f"{self.city}:{self.name}:{self.ball_rooms}"


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
        self.ball_rooms: List[str] = list()
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


Usage.init()
