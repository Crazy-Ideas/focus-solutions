# noinspection PyPackageRequirements
from googleapiclient.discovery import build

from config import Config
from fs_flask.hotel import Hotel, Usage
from fs_flask.user import User


def create_user(email: str, name: str, initial: str, role: str):
    password = User.create_user(email, name, initial, role)
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
    hotels = [Hotel(hotel["name"], hotel["rooms"], "Mumbai").doc_to_dict() for _, hotel in hotel_dict.items()]
    for hotel in hotels:
        print(hotel)
    Hotel.objects.delete()
    Hotel.create_from_list_of_dict(hotels)
    print(f"{len(hotels)} hotels created")


def mumbai_1_aug():
    sheet = build("sheets", "v4").spreadsheets().values()
    hotel_table = sheet.get(spreadsheetId=Config.SHEET_ID, range="1-Aug!A1:H100").execute().get("values", list())
    usages = list()
    for row in hotel_table[1:]:
        usage = Usage()
        usage.hotel = row[6]
        usage.city = "Mumbai"
        usage.set_date(row[0])
        if row[1] not in Config.TIMINGS:
            raise TypeError
        usage.timing = row[1]
        usage.company = row[2]
        usage.event_description = row[3]
        if row[5] not in Config.EVENTS:
            raise TypeError
        usage.event_type = row[5]
        meals = row[4].split(",") if "," in row[4] else [row[4]]
        meals = [meal.strip() for meal in meals]
        if any(meal not in Config.MEALS for meal in meals):
            raise TypeError
        usage.meals = meals
        usage.ball_rooms = [row[7]]
        usages.append(usage.doc_to_dict())
    for usage in usages:
        print(usage)
    Usage.objects.delete()
    Usage.create_from_list_of_dict(usages)
    print(f"{len(usages)} occupancy records created")
