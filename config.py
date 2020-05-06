import os
from base64 import b64encode

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google-cloud.json'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or b64encode(os.urandom(24)).decode()
    SHEET_ID = "1OnvVprC_RSlsKxgAgve-dliPGJydj--qkmvnRUfyGYM"
    ADMIN = "Admin"
    HOTEL = "Hotel"
    ROLES = (ADMIN, HOTEL)
    DEFAULT_CITY = "Mumbai"
    ANY = "Any"
    CITIES = ("Mumbai", "Pune")
    NO_MEAL = "No Meal"
    MEALS = ("Breakfast", "Lunch", "Dinner", "Hi Tea", NO_MEAL)
    TIMINGS = ("Morning", "Evening")
    MICE = "MICE Event"
    SOCIAL = "Social Event"
    OTHER = "Other"
    EVENTS = (MICE, SOCIAL, OTHER)


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
