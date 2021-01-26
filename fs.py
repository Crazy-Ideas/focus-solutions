import csv
import datetime as dt
import time
from concurrent.futures import as_completed, ThreadPoolExecutor
# noinspection PyPackageRequirements
from copy import deepcopy
from typing import List

from googleapiclient.discovery import build

from config import Config, Date
from fs_flask.hotel import Hotel
from fs_flask.usage import Usage
from fs_flask.user import User


def create_user(email: str, name: str, role: str, hotel_name_input: str = str(), city: str = str()):
    if role not in Config.ROLES:
        print("Invalid role")
        return
    if role == Config.ADMIN and not hotel_name_input:
        print("Hotel name required for ADMIN")
        return
    hotel_name = name if role == Config.HOTEL else hotel_name_input
    hotel_city = city if city else Config.DEFAULT_CITY
    if hotel_city not in Config.CITIES:
        print("Invalid city")
    hotel: Hotel = Hotel.objects.filter_by(name=hotel_name, city=hotel_city).first()
    if not hotel:
        print("Hotel not found in the database")
        return
    password = User.create_user(email, name, role, hotel_name, hotel_city)
    if not password:
        print("Invalid email")
    else:
        print(f"User {email} created. Your password is {password}")
    return


def mumbai_hotels():
    sheet = build("sheets", "v4").spreadsheets().values()
    hotel_table = sheet.get(spreadsheetId=Config.SHEET_ID, range="Hotels!A1:Z39").execute().get("values", list())
    hotel_dict = {str(index): {"name": hotel, "rooms": list(), "competitions": list()}
                  for index, hotel in enumerate(hotel_table[0])}
    for rooms in hotel_table[1:]:
        for index, room in enumerate(rooms):
            if room:
                hotel_dict[str(index)]["rooms"].append(room)
    hotel_table = sheet.get(spreadsheetId=Config.SHEET_ID, range="Hotels!A40:Z60").execute().get("values", list())
    for hotels in hotel_table[1:]:
        for index, hotel in enumerate(hotels):
            if hotel:
                hotel_dict[str(index)]["competitions"].append(hotel)
                if hotel not in hotel_table[0]:
                    raise TypeError
    hotels = [Hotel(name=hotel["name"], ballrooms=hotel["rooms"], primary_hotels=hotel["competitions"][:9],
                    secondary_hotels=hotel["competitions"][9:18] if len(hotel["competitions"]) > 9 else list(),
                    city="Mumbai").doc_to_dict() for _, hotel in hotel_dict.items()]
    for hotel in hotels:
        hotel["start_date"] = "2019-01-01"
        hotel["end_date"] = "2020-03-31"
        print(hotel)
    # Hotel.objects.delete()
    # Hotel.create_from_list_of_dict(hotels)
    print(f"{len(hotels)} hotels created")


def mumbai_usage():
    sheet = build("sheets", "v4").spreadsheets().values()
    hotel_table = sheet.get(spreadsheetId=Config.SHEET_ID, range="Usage!A1:H5100").execute().get("values", list())
    hotels = Hotel.objects.filter_by(city="Mumbai").get()
    hotel_names = [hotel.name for hotel in hotels]
    usages = list()
    errors = list()
    for index, row in enumerate(hotel_table[1:]):
        usage = Usage()
        usage.city = "Mumbai"
        date_pass = usage.set_date(dt.datetime.strptime(row[0], "%d/%m/%Y").date())
        usage.timing = row[1]
        usage.client = row[2]
        usage.event_description = row[3]
        usage.meals = [row[4]]
        usage.event_type = row[5]
        usage.hotel = row[6]
        usage.ballrooms = [row[7]]
        if not date_pass:
            errors.append(f"{index + 2}:DATE_ERROR:{usage}")
            continue
        if usage.timing not in Config.TIMINGS:
            errors.append(f"{index + 2}:TIMING_ERROR:{usage}")
            continue
        if usage.event_type not in Config.EVENTS:
            errors.append(f"{index + 2}:EVENT_TYPE_ERROR:{usage}")
            continue
        usage.meals = usage.meals[0].split(",")
        usage.meals = [meal.strip() for meal in usage.meals]
        if any(meal not in Config.MEALS for meal in usage.meals):
            errors.append(f"{index + 2}:TIMING_ERROR:{usage}")
            continue
        if usage.hotel not in hotel_names:
            errors.append(f"{index + 2}:HOTEL_ERROR:{usage}")
            continue
        usage.ballrooms = usage.ballrooms[0].split(",")
        usage.ballrooms = [room.strip() for room in usage.ballrooms]
        hotel = next(hotel for hotel in hotels if hotel.name == usage.hotel)
        if any(room not in hotel.ballrooms for room in usage.ballrooms):
            errors.append(f"{index + 2}:BALL_ROOM_ERROR:{usage}")
            continue
        hotel.set_ballroom_used(usage.ballrooms)
        hotel.set_last_entry(usage.date, usage.timing)
        usages.append(usage.doc_to_dict())
    if errors:
        for error in errors:
            print(error)
        return
    for usage in usages:
        print(usage)
    start = time.perf_counter()
    # Usage.objects.delete()
    # Usage.create_from_list_of_dict(usages)
    end = time.perf_counter() - start
    print(f"{len(usages)} occupancy records created in {end:0.2f} seconds")
    Hotel.save_all(hotels)
    print(f"{len(hotels)} hotel occupancy updated")


def mumbai_no_event():
    start_date = "2020-01-01"
    end_date = "2020-03-31"
    city = "Mumbai"
    query = Usage.objects.filter_by(city=city).filter("date", ">=", start_date)
    usage_data = query.filter("date", "<=", end_date).get()
    usage_data.sort(key=lambda usage: (usage.hotel, usage.date))
    hotels = Hotel.objects.get()
    no_events = list()
    start_date = Date(start_date).date
    days = (Date(end_date).date - start_date).days + 1
    periods = [(day, timing) for day in range(days) for timing in Config.TIMINGS]
    for day, timing in periods:
        date = start_date + dt.timedelta(days=day)
        date = Date(date).db_date
        date_usages = [usage for usage in usage_data if usage.date == date and usage.timing == timing]
        for hotel in hotels:
            if any(usage.hotel == hotel.name for usage in date_usages):
                continue
            usage = Usage()
            usage.hotel = hotel.name
            usage.city = city
            usage.set_date(Date(date).date)
            usage.timing = timing
            usage.no_event = True
            no_events.append(usage.doc_to_dict())
    for usage in no_events:
        print(usage)
    # Usage.create_from_list_of_dict(no_events)
    print(f"{len(no_events)} no events created")


def check_room(hotel: Hotel, ballroom: str):
    query = Usage.objects.filter_by(city=hotel.city, hotel=hotel.name)
    usage = query.filter('ballrooms', Usage.objects.ARRAY_CONTAINS, ballroom).first()
    used = True if usage else False
    changed = hotel.set_ballroom_used([ballroom], used)
    return hotel, ballroom, changed


def update_ballroom_maps(workers: int = 200):
    hotels = Hotel.objects.get()
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        threads = [executor.submit(check_room, hotel, room)
                   for hotel in hotels for room in hotel.ballrooms]
        rooms = [future.result() for future in as_completed(threads)]
    end = time.perf_counter() - start
    print(f"{len(rooms)} checked in {end:0.2f} seconds")
    updated_hotels = {room[0].name for room in rooms if room[2]}
    hotels = [hotel for hotel in hotels if hotel.name in updated_hotels]
    if hotels:
        Hotel.save_all(hotels)
    print(f"{len(hotels)} updated")


def hotel_backup():
    for city in list(Config.CITIES):
        hotels = Hotel.objects.filter_by(city=city).get()
        file_name = f"Hotels-{city}.csv"
        with open(file_name, "w", newline="", encoding="utf-8") as csv_file:
            field_names = list(Hotel().doc_to_dict())
            writer = csv.DictWriter(csv_file, fieldnames=field_names)
            writer.writeheader()
            for hotel in hotels:
                writer.writerow(hotel.doc_to_dict())
        print(f"{file_name} created with {len(hotels)} rows")
    return


def event_backup(month: str):
    events = Usage.objects.filter_by(month=month).get()
    if not events:
        print("No events found")
        return
    events.sort(key=lambda item: (item.city, item.hotel, item.date))
    file_name = f"Events-{month}.csv"
    with open(file_name, "w", newline="", encoding="utf-8") as csv_file:
        field_names = list(Usage().doc_to_dict())
        writer = csv.DictWriter(csv_file, fieldnames=field_names)
        writer.writeheader()
        for event in events:
            writer.writerow(event.doc_to_dict())
    print(f"{file_name} created with {len(events)} rows")
    return


def update_data_entry_dates():
    hotels = Hotel.objects.get()
    updated_hotels = list()
    for hotel in hotels:
        query = Usage.objects.filter_by(city=hotel.city, hotel=hotel.name, timing=Config.MORNING)
        morning_usage: Usage = query.order_by("date", Usage.objects.ORDER_DESCENDING).first()
        if not morning_usage:
            print(f"{hotel.city} {hotel.name} {hotel.last_date} {hotel.last_timing} "
                  f"does not have an morning event")
            return
        query = Usage.objects.filter_by(city=hotel.city, hotel=hotel.name)
        evening_usage: Usage = query.filter_by(date=morning_usage.date, timing=Config.EVENING).first()
        hotel_copy = deepcopy(hotel)
        hotel_copy.last_date = evening_usage.date if evening_usage else morning_usage.date
        hotel_copy.last_timing = Config.EVENING if evening_usage else Config.MORNING
        if hotel.last_timing == Config.MORNING:
            if morning_usage.date != hotel.last_date:
                print(f"{hotel.city} {hotel.name} {hotel.last_date} {hotel.last_timing} "
                      f"date is {hotel.last_date} but last event date is {morning_usage.date}")
                updated_hotels.append(hotel_copy)
            elif evening_usage:
                print(f"{hotel.city} {hotel.name} {hotel.last_date} {hotel.last_timing} "
                      f"has an evening event")
                updated_hotels.append(hotel_copy)
        elif hotel.last_timing == Config.EVENING:
            if morning_usage.date != hotel.last_date:
                print(f"{hotel.city} {hotel.name} {hotel.last_date} {hotel.last_timing} "
                      f"last event date is {morning_usage.date} {Config.EVENING if evening_usage else Config.MORNING}")
                updated_hotels.append(hotel_copy)
            elif not evening_usage:
                print(f"{hotel.city} {hotel.name} {hotel.last_date} {hotel.last_timing} "
                      f"does not have an evening event")
                updated_hotels.append(hotel_copy)
            elif evening_usage.date != hotel.last_date:
                print(f"{hotel.city} {hotel.name} {hotel.last_date} {hotel.last_timing} "
                      f"last event date is {evening_usage.date} - Evening")
                updated_hotels.append(hotel_copy)
        else:
            print(f"{hotel.city} {hotel.name} {hotel.last_date} {hotel.last_timing} "
                  f"has an invalid last timing")
            updated_hotels.append(hotel_copy)
    Hotel.save_all(updated_hotels)
    print(f"{len(updated_hotels)} of {len(hotels)} updated")
    return


def rename_hotel(old_name: str, new_name: str, city: str):
    hotel: Hotel = Hotel.objects.filter_by(name=old_name, city=city).first()
    if not hotel:
        print(f"Hotel {old_name} not found.")
    if Hotel.objects.filter_by(name=new_name, city=city).first():
        print(f"Hotel with the name {new_name} already exists.")
    hotel.name = new_name
    events: List[Usage] = Usage.objects.filter_by(hotel=old_name, city=city).get()
    for event in events:
        event.hotel = new_name
    hotel.save()
    Usage.save_all(events)
    print(f"Hotel renamed to {new_name}. {len(events) + 1} documents updated.")
