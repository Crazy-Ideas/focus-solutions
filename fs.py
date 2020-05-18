import datetime as dt
import io
import time
from concurrent.futures import as_completed, ThreadPoolExecutor
from typing import List

# noinspection PyPackageRequirements
from googleapiclient.discovery import build
# noinspection PyPackageRequirements
from googleapiclient.http import MediaIoBaseDownload

from config import Config, local_path
from fs_flask.hotel import Hotel
from fs_flask.usage import Usage
from fs_flask.user import User


def create_user(email: str, name: str, role: str, hotel_name: str = None):
    if role not in Config.ROLES:
        print("Invalid role")
        return
    if role == Config.ADMIN and not hotel_name:
        print("Hotel name required for ADMIN")
        return
    hotel_name = name if Config.HOTEL else hotel_name
    hotel: Hotel = Hotel.objects.filter_by(name=hotel_name).first()
    if not hotel:
        print("Hotel not found in the database")
        return
    password = User.create_user(email, name, role, hotel_name)
    if not password:
        print("Invalid email")
    else:
        print(f"User {email} created. Your password is {password}")
    return


def mumbai_hotels():
    sheet = build("sheets", "v4").spreadsheets().values()
    hotel_table = sheet.get(spreadsheetId=Config.SHEET_ID, range="Hotels!A1:Z30").execute().get("values", list())
    hotel_dict = {str(index): {"name": hotel, "rooms": list(), "competitions": list()}
                  for index, hotel in enumerate(hotel_table[0])}
    for rooms in hotel_table[1:]:
        for index, room in enumerate(rooms):
            if room:
                hotel_dict[str(index)]["rooms"].append(room)
    hotel_table = sheet.get(spreadsheetId=Config.SHEET_ID, range="Hotels!A31:Z45").execute().get("values", list())
    for hotels in hotel_table[1:]:
        for index, hotel in enumerate(hotels):
            if hotel:
                hotel_dict[str(index)]["competitions"].append(hotel)
                if hotel not in hotel_table[0]:
                    raise TypeError
    hotels = [Hotel(hotel["name"], hotel["rooms"], hotel["competitions"], "Mumbai").doc_to_dict()
              for _, hotel in hotel_dict.items()]
    for hotel in hotels:
        hotel["start_date"] = "2020-01-01"
        hotel["end_date"] = "2020-03-31"
        print(hotel)
    Hotel.objects.delete()
    Hotel.create_from_list_of_dict(hotels)
    print(f"{len(hotels)} hotels created")


def mumbai_usage():
    sheet = build("sheets", "v4").spreadsheets().values()
    hotel_table = sheet.get(spreadsheetId=Config.SHEET_ID, range="Usage!A1:H2000").execute().get("values", list())
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
            errors.append(f"{index + 1}:DATE_ERROR:{usage}")
            continue
        if usage.timing not in Config.TIMINGS:
            errors.append(f"{index + 1}:TIMING_ERROR:{usage}")
            continue
        if usage.event_type not in Config.EVENTS:
            errors.append(f"{index + 1}:EVENT_TYPE_ERROR:{usage}")
            continue
        usage.meals = usage.meals[0].split(",")
        usage.meals = [meal.strip() for meal in usage.meals]
        if any(meal not in Config.MEALS for meal in usage.meals):
            errors.append(f"{index + 1}:TIMING_ERROR:{usage}")
            continue
        if usage.hotel not in hotel_names:
            errors.append(f"{index + 1}:HOTEL_ERROR:{usage}")
            continue
        usage.ballrooms = usage.ballrooms[0].split(",")
        usage.ballrooms = [room.strip() for room in usage.ballrooms]
        hotel = next(hotel for hotel in hotels if hotel.name == usage.hotel)
        if any(room not in hotel.ballrooms for room in usage.ballrooms):
            errors.append(f"{index + 1}:BALL_ROOM_ERROR:{usage}")
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
    Usage.objects.delete()
    Usage.create_from_list_of_dict(usages)
    end = time.perf_counter() - start
    print(f"{len(usages)} occupancy records created in {end:0.2f} seconds")
    Hotel.save_all(hotels)
    print(f"{len(hotels)} hotel occupancy updated")


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


def download_excel_file():
    sheet = Sheet.create()
    sheet.update_chart()
    sheet.download()
    sheet.delete()


class Sheet:
    SHEETS = build("sheets", "v4")
    DRIVE = build("drive", "v3")

    def __init__(self, sheet_id: str = None):
        self.sheet_id: str = sheet_id if sheet_id else str()

    @classmethod
    def create(cls) -> "Sheet":
        spreadsheet = cls.SHEETS.spreadsheets().create(body={"properties": {"title": "Hotel Count Report"}},
                                                       fields="spreadsheetId").execute()
        sheet_id = spreadsheet.get("spreadsheetId")
        print(f"Sheet with ID {sheet_id} created")
        return cls(sheet_id)

    @classmethod
    def create_with_permission(cls) -> "Sheet":
        sheet = cls.create()

        def callback(_, __, exception):
            if exception:
                print(exception)
                return
            print(f"Permission granted for sheet ID {sheet.sheet_id}")

        batch = cls.DRIVE.new_batch_http_request(callback=callback)
        permission = {"type": "user", "role": "writer", "emailAddress": "nayan@crazyideas.co.in"}
        batch.add(cls.DRIVE.permissions().create(fileId=sheet.sheet_id, body=permission, fields="id"))
        batch.execute()
        return sheet

    def update_range(self, range_name: str, values: List[List[str]]):
        self.SHEETS.spreadsheets().values().update(spreadsheetId=self.sheet_id, valueInputOption="USER_ENTERED",
                                                   body={"values": values}, range=range_name).execute()

    def delete(self):
        if not self.sheet_id:
            print("Nothing to delete")
        self.DRIVE.files().delete(fileId=self.sheet_id).execute()
        print(f"Sheet with ID {self.sheet_id} deleted")

    def download(self):
        if not self.sheet_id:
            print("Nothing to download")
        request = self.DRIVE.files().export_media(fileId=self.sheet_id, mimeType=Config.EXCEL_MIME)
        file_handle = io.FileIO(local_path(f"{self.sheet_id}.xlsx"), "w")
        downloader = MediaIoBaseDownload(file_handle, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk()
        print("Download complete")

    def update_chart(self):
        sample_data = [["Hotels", "Counts"], ["Courtyard By Marriott", 35], ["Taj Lands End", 58]]
        self.update_range("Sheet1!I1:J3", sample_data)
        legends = [{"sheetId": 0, "startRowIndex": 1, "endRowIndex": 3, "startColumnIndex": 8, "endColumnIndex": 9}]
        data = [{"sheetId": 0, "startRowIndex": 1, "endRowIndex": 3, "startColumnIndex": 9, "endColumnIndex": 10}]
        chart = {
            "spec": {
                "title": "Hotel Count Report",
                "pieChart": {
                    "legendPosition": "LEFT_LEGEND",
                    "threeDimensional": False,
                    "domain": {"sourceRange": {"sources": legends}},
                    "series": {"sourceRange": {"sources": data}},
                }
            },
            "position": {
                "overlayPosition": {
                    "anchorCell": {"sheetId": 0, "rowIndex": 0, "columnIndex": 0},
                    "offsetXPixels": 50,
                    "offsetYPixels": 50
                }
            }
        }
        body = {"requests": [{"addChart": {"chart": chart}}]}
        self.SHEETS.spreadsheets().batchUpdate(spreadsheetId=self.sheet_id, body=body).execute()
        print("Chart updated")
