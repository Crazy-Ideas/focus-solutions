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
