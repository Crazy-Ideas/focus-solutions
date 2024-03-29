import datetime as dt
import os
from typing import Union, Optional

from pytz import timezone

from secret import SecretConfig

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-cloud.json"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or SecretConfig.SECRET_KEY
    CI_SECURITY = True if os.environ.get("ENVIRONMENT") == "prod" else False
    SESSION_COOKIE_SECURE = CI_SECURITY
    PROJECT_ROOT = os.getcwd()
    APP_ROOT = os.path.join(PROJECT_ROOT, "fs_flask")
    DOWNLOAD_PATH = os.path.join(os.path.abspath(os.sep), "tmp")
    TOKEN_EXPIRY = 3600  # 1 hour = 3600 seconds
    # noinspection SpellCheckingInspection
    MIME_TYPES = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    # noinspection SpellCheckingInspection
    SHEET_ID = "1OnvVprC_RSlsKxgAgve-dliPGJydj--qkmvnRUfyGYM"
    # FBR specific constants
    ADMIN, HOTEL = "Admin", "Hotel"
    ROLES = (ADMIN, HOTEL)
    DEFAULT_CITY = "Mumbai"
    EMPTY_CHOICE = (str(), str())
    CITIES = {"Mumbai": "Maharashtra", "Pune": "Maharashtra", "Kolkata": "West Bengal"}
    NO_MEAL, BREAKFAST, LUNCH, DINNER, HI_TEA = "No Meal", "Breakfast", "Lunch", "Dinner", "Hi Tea"
    BREAKFAST_LUNCH, HI_TEA_DINNER = "Breakfast and Lunch", "Hi Tea and Dinner"
    MEALS = (BREAKFAST, LUNCH, HI_TEA, DINNER, NO_MEAL)
    MORNING_MEALS = (BREAKFAST, LUNCH, BREAKFAST_LUNCH, NO_MEAL)
    EVENING_MEALS = (HI_TEA, DINNER, HI_TEA_DINNER, NO_MEAL)
    MORNING, EVENING = "Morning", "Evening"
    TIMINGS = (MORNING, EVENING)
    MICE, SOCIAL, OTHER = "Corporate Event", "Social Event", "Other"
    EVENTS = (MICE, SOCIAL, OTHER)
    STAR_CATEGORY = ("5 Star Deluxe", "5 Star", "4 Star", "3 Star", "2 Star", "1 Star", "Heritage Grand",
                     "Heritage Classic", "Heritage Basic")
    DEFAULT_DAYS = ["1"]
    # noinspection SpellCheckingInspection
    TEMPLATE_SHEET_ID = "1nLTQftpPTpnPBL3yLpcLdT8N_4B7RjtBeXDD4aRrdb4"


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
    TODAY = None
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
    def previous_lock_in(cls) -> dt.date:
        date = cls.today()
        previous_sunday = date - dt.timedelta(days=date.isoweekday())
        last_date_previous_month = date.replace(day=1) - dt.timedelta(days=1)
        return previous_sunday if previous_sunday > last_date_previous_month else last_date_previous_month

    @classmethod
    def next_lock_in(cls) -> dt.date:
        date = cls.today()
        next_sunday = date + dt.timedelta(days=(7 - date.isoweekday()))
        next_month = date.replace(day=28) + dt.timedelta(days=4)
        last_date_this_month = next_month - dt.timedelta(days=next_month.day)
        return next_sunday if next_sunday < last_date_this_month else last_date_this_month

    @classmethod
    def from_dd_mmm_yyyy(cls, dd_mmm_yyyy):
        try:
            date = dt.datetime.strptime(dd_mmm_yyyy, "%d-%b-%Y")
        except (ValueError, TypeError):
            date = str()
        return cls(date)

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
