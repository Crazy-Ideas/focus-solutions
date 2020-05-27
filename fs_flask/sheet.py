import io
import os
import re
from typing import List, Dict

from google.cloud.storage import Client, Blob
# noinspection PyPackageRequirements
from googleapiclient.discovery import build
# noinspection PyPackageRequirements
from googleapiclient.http import MediaIoBaseDownload

from config import Config, BaseMap


class Sheet:
    SHEETS = build("sheets", "v4")
    DRIVE = build("drive", "v3")
    SHEET_ID = {'Report': 0, 'Data': 1}
    BUCKET = Client().bucket("focus-solutions-files")

    def __init__(self, sheet_id: str = None, extension: str = None):
        self.sheet_id: str = sheet_id if sheet_id else str()
        self.extension: str = extension if extension else str()

    @classmethod
    def create(cls) -> "Sheet":
        body = {"properties": {"title": "Reports"}}
        spreadsheet = cls.SHEETS.spreadsheets().create(body=body, fields="spreadsheetId").execute()
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

    @property
    def local_path(self):
        file_name = f"{self.sheet_id}.{self.extension}"
        return os.path.join(Config.DOWNLOAD_PATH, file_name)

    def prepare(self, data_rows: int = 1000):
        body = {"requests": [
            {"updateSheetProperties": {
                "properties": {"sheetId": 0, "title": "Report"},
                "fields": "title"
            }},
            {"addSheet": {
                "properties": {"title": "Data", "gridProperties": {"rowCount": data_rows, "columnCount": 26}}
            }}
        ]}
        self.SHEETS.spreadsheets().batchUpdate(spreadsheetId=self.sheet_id, body=body).execute()

    def update_range(self, range_name: str, values: List[List[str]]):
        self.SHEETS.spreadsheets().values().update(spreadsheetId=self.sheet_id, valueInputOption="USER_ENTERED",
                                                   body={"values": values}, range=range_name).execute()

    def delete(self):
        if not self.sheet_id:
            print("Nothing to delete")
        self.DRIVE.files().delete(fileId=self.sheet_id).execute()
        print(f"Sheet with ID {self.sheet_id} deleted")

    def download(self) -> str:
        if not self.sheet_id:
            print("Nothing to download")
            return str()
        if self.extension not in Config.MIME_TYPES:
            print("Invalid extension")
            return str()
        request = self.DRIVE.files().export_media(fileId=self.sheet_id, mimeType=Config.MIME_TYPES[self.extension])
        file_path = self.local_path
        file_handle = io.FileIO(file_path, "w")
        downloader = MediaIoBaseDownload(file_handle, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk()
        print(f"File {file_path} downloaded")
        return file_path

    def download_from_cloud(self) -> str:
        if not self.sheet_id:
            print("Nothing to download")
            return str()
        if self.extension not in Config.MIME_TYPES:
            print("Invalid extension")
            return str()
        file_path = self.local_path
        if os.path.exists(file_path):
            return file_path
        blob: Blob = self.BUCKET.blob(self.sheet_id)
        if not blob.exists():
            print(f"File {self.sheet_id}.{self.extension} not found on cloud storage")
            return str()
        blob.download_to_filename(file_path)
        self.download()
        return file_path

    @staticmethod
    def pie_spec(headers: List[Dict[str, int]], values: List[Dict[str, int]], anchor: Dict[str, int]) -> dict:
        return {
            "spec": {
                "title": "Hotel Count Report",
                "pieChart": {
                    "legendPosition": "LEFT_LEGEND",
                    "domain": {"sourceRange": {"sources": headers}},
                    "series": {"sourceRange": {"sources": values}},
                }
            },
            "position": {"overlayPosition": {"anchorCell": anchor, "offsetXPixels": 0, "offsetYPixels": 0}}
        }

    @staticmethod
    def trend_spec(headers: List[Dict[str, int]], values: List[Dict[str, int]], anchor: Dict[str, int]) -> dict:
        return {
            "spec": {
                "title": "Hotel Trends Report",
                "basicChart": {
                    "chartType": "LINE",
                    "legendPosition": "BOTTOM_LEGEND",
                    "axis": [{"position": "BOTTOM_AXIS"}, {"position": "LEFT_AXIS", "title": "Event Count"}],
                    "domains": [{"domain": {"sourceRange": {"sources": headers}}}],
                    "series": [{"series": {"sourceRange": {"sources": [values[0]]}}, "targetAxis": "LEFT_AXIS"},
                               {"series": {"sourceRange": {"sources": [values[1]]}}, "targetAxis": "LEFT_AXIS"}],
                    "headerCount": 1
                }
            },
            "position": {"overlayPosition": {"anchorCell": anchor, "offsetXPixels": 0, "offsetYPixels": 0}}
        }

    def update_chart(self, pie: dict, trend: dict):
        body = {"requests": [{"addChart": {"chart": pie}}, {"addChart": {"chart": trend}}]}
        self.SHEETS.spreadsheets().batchUpdate(spreadsheetId=self.sheet_id, body=body).execute()
        print("Chart updated")


class GridRange(BaseMap):
    def __init__(self):
        self.sheetId: int = 0
        self.startRowIndex: int = 0
        self.endRowIndex: int = 0
        self.startColumnIndex: int = 0
        self.endColumnIndex: int = 0

    @classmethod
    def from_range(cls, range_name: str) -> 'GridRange':
        grid = cls()
        try:
            sheet, start_col, start_row, end_col, end_row = re.findall(r"([^!]+)!([A-Z])([\d]+):([A-Z])([\d]+)",
                                                                       range_name)[0]
        except IndexError:
            return grid
        if sheet not in Sheet.SHEET_ID:
            return grid
        grid.sheetId = Sheet.SHEET_ID[sheet]
        grid.startRowIndex = int(start_row) - 1
        grid.endRowIndex = int(end_row)
        grid.startColumnIndex = ord(start_col) - ord("A")
        grid.endColumnIndex = ord(end_col) - ord("A") + 1
        return grid


class GridCoordinate(BaseMap):
    def __init__(self):
        self.sheetId: int = 0
        self.rowIndex: int = 0
        self.columnIndex: int = 0

    @classmethod
    def from_cell(cls, cell_address) -> 'GridCoordinate':
        grid = cls()
        try:
            sheet, column, row = re.findall(r"([^!]+)!([A-Z])([\d]+)", cell_address)[0]
        except IndexError:
            return grid
        if sheet not in Sheet.SHEET_ID:
            return grid
        grid.sheetId = Sheet.SHEET_ID[sheet]
        grid.rowIndex = int(row) - 1
        grid.columnIndex = ord(column) - ord("A")
        return grid
