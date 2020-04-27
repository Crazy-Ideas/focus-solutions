# noinspection PyPackageRequirements
from googleapiclient.discovery import build

from config import Config
from fs_flask.user import User


def create_user(email: str, name: str, initial: str):
    password = User.create_user(email, name, initial)
    if not password:
        print("Invalid email")
    else:
        print(f"User {email} created. Your password is {password}")
    return


def mumbai_hotels():
    sheet = build("sheets", "v4").spreadsheets().values()
    hotel_table = sheet.get(spreadsheetId=Config.SHEET_ID, range="Mumbai!A1:Z50").execute().get("values", list())
    hotel_dict = {str(index): {"name": hotel, "rooms": list()} for index, hotel in enumerate(hotel_table[0])}
    for rooms in hotel_table[1:]:
        for index, room in enumerate(rooms):
            if room:
                hotel_dict[str(index)]["rooms"].append(room)
    for _, hotel in hotel_dict.items():
        print(hotel)
