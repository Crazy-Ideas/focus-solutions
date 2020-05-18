import datetime as dt
import os
from base64 import b64encode
from typing import Union, Optional

from pytz import timezone

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google-cloud.json'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or b64encode(os.urandom(24)).decode()
    PROJECT_ROOT = os.getcwd()
    APP_ROOT = os.path.join(PROJECT_ROOT, 'fs_flask')
    DOWNLOAD_PATH = os.path.join(APP_ROOT, 'downloads')
    EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    SHEET_ID = "1OnvVprC_RSlsKxgAgve-dliPGJydj--qkmvnRUfyGYM"
    ADMIN = "Admin"
    HOTEL = "Hotel"
    ROLES = (ADMIN, HOTEL)
    DEFAULT_CITY = "Mumbai"
    EMPTY_CHOICE = (str(), str())
    ANY = "Any"
    CITIES = ("Mumbai", "Pune")
    NO_MEAL = "No Meal"
    BREAKFAST = "Breakfast"
    LUNCH = "Lunch"
    DINNER = "Dinner"
    HI_TEA = "Hi Tea"
    MEALS = (BREAKFAST, LUNCH, HI_TEA, DINNER, NO_MEAL)
    MORNING = "Morning"
    EVENING = "Evening"
    TIMINGS = (MORNING, EVENING)
    MICE = "MICE Event"
    SOCIAL = "Social Event"
    OTHER = "Other"
    EVENTS = (MICE, SOCIAL, OTHER)


def local_path(file_name: str):
    return os.path.join(Config.DOWNLOAD_PATH, file_name)


class BaseMap:
    def to_dict(self):
        return self.__dict__

    @classmethod
    def from_dict(cls, input_dict: dict):
        map_object = cls()
        map_fields = set(map_object.to_dict())
        for field, value in input_dict.items():
            if field not in map_fields:
                continue
            if not isinstance(value, type(getattr(map_object, field))):
                continue
            setattr(map_object, field, value)
        return map_object

    def __repr__(self):
        return ':'.join(str(value) for _, value in self.to_dict().items())


class Date:
    TODAY = dt.date(2020, 3, 3)
    INDIA_TIME_ZONE = timezone("Asia/Kolkata")

    def __init__(self, date: Union[dt.date, str] = None):
        self._date = date if date is not None else self.today()

    @classmethod
    def today(cls) -> dt.date:
        return cls.TODAY or dt.datetime.now(tz=cls.INDIA_TIME_ZONE).date()

    @classmethod
    def yesterday(cls) -> dt.date:
        return cls.today() - dt.timedelta(days=1)

    @classmethod
    def last_sunday(cls) -> dt.date:
        date = cls.today()
        return date - dt.timedelta(days=date.isoweekday())

    @classmethod
    def last_monday(cls) -> Optional[dt.date]:
        date = cls.last_sunday()
        return date - dt.timedelta(days=6)

    @property
    def date(self) -> Optional[dt.date]:
        if isinstance(self._date, dt.date):
            return self._date
        try:
            date = dt.datetime.strptime(self._date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
        return date

    @property
    def db_date(self) -> str:
        return self._date.strftime("%Y-%m-%d") if isinstance(self._date, dt.date) else str()

    @property
    def format_date(self) -> str:
        date = self.date
        return date.strftime("%d-%b-%Y") if isinstance(date, dt.date) else str()

    @property
    def format_week(self) -> str:
        date = self.date
        return date.strftime("%a, %d-%b-%Y") if isinstance(date, dt.date) else str()
