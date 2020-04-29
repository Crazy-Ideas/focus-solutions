import os
from base64 import b64encode

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google-cloud.json'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or b64encode(os.urandom(24)).decode()
    SHEET_ID = "1OnvVprC_RSlsKxgAgve-dliPGJydj--qkmvnRUfyGYM"
    ADMIN = "admin"
    HOTEL = "hotel"
    ROLES = (ADMIN, HOTEL)
    DEFAULT_CITY = "Mumbai"
    ANY = "Any"
    CITIES = ("Mumbai", "Pune")
    NO_MEAL = "No Meal"
    MEALS = ("Breakfast", "Lunch", "Dinner", "Hi Tea", NO_MEAL)
    TIMINGS = ("Morning", "Evening")
    MICE = "Meetings & Conference (MICE)"
    SOCIAL = "Social Event"
    EXHIBITION = "Exhibition"
    OTHER_EVENT = "Other Event"
    EVENTS = (MICE, SOCIAL, EXHIBITION, OTHER_EVENT)
