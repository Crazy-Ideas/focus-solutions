from typing import Callable, List

from config import Config
from fs_flask.usage import Usage


class QueryAttribute:
    PRIMARY = "primary_hotels"
    SECONDARY = "secondary_hotels"
    DAYS = "days"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    def __init__(self, name: str, nav_method: Callable = None, comp_set: str = str(),
                 period: str = str()):
        self.name: str = name
        self.nav_method: Callable = nav_method
        self.comp_set: str = comp_set
        self.period: str = period


class DataAttribute:
    MY_PROP = "My Property"
    COMPSET = "Comp set"

    def __init__(self, usages: List[Usage], my_hotel: str, comp_set: List[str], total_days: float):
        self.my_prop = [u for u in usages if u.hotel == my_hotel]
        self.comp_set = [u for u in usages if u.hotel in comp_set]
        self.timing_count = total_days * 2


class ReportTag:
    # Occupancy
    FULL_DAY_OCCUPANCY_BAR_GRAPH = "full_day_occupancy_bar_graph"
    FULL_DAY_OCCUPANCY_DATA_POINT = "full_day_occupancy_data_point"
    MORNING_OCCUPANCY_BAR_GRAPH = "morning_occupancy_bar_graph"
    MORNING_OCCUPANCY_DATA_POINT = "morning_occupancy_data_point"
    EVENING_OCCUPANCY_BAR_GRAPH = "evening_occupancy_bar_graph"
    EVENING_OCCUPANCY_DATA_POINT = "evening_occupancy_data_point"
    # Events
    FULL_DAY_EVENTS_BAR_GRAPH = "full_day_events_bar_graph"
    MORNING_EVENTS_BAR_GRAPH = "morning_events_bar_graph"
    EVENING_EVENTS_BAR_GRAPH = "evening_events_bar_graph"
    FULL_DAY_EVENTS_DATA_POINT = "full_day_events_data_point"
    MORNING_EVENTS_DATA_POINT = "morning_events_data_point"
    EVENING_EVENTS_DATA_POINT = "evening_events_data_point"
    CORPORATE_EVENTS_BAR_GRAPH = "corporate_events_bar_graph"
    CORPORATE_EVENTS_DATA_POINT = "corporate_events_data_point"
    SOCIAL_EVENTS_BAR_GRAPH = "social_events_bar_graph"
    SOCIAL_EVENTS_DATA_POINT = "social_events_data_point"
    WEEKDAY_EVENTS_BAR_GRAPH = "weekday_events_bar_graph"
    WEEKDAY_EVENTS_DATA_POINT = "weekday_events_data_point"
    WEEKEND_EVENTS_BAR_GRAPH = "weekend_events_bar_graph"
    WEEKEND_EVENTS_DATA_POINT = "weekend_events_data_point"


class ReportAttribute:
    # Sheet name
    BAR_GRAPH = "Bar Graph"
    DATA_POINT = "Data Points"
    RBD = "Reader Board Data"
    TOP5 = "Top 5 Clients"
    # Event type
    FULL_DAY = "Full Day"
    MORNING = Config.MORNING
    EVENING = Config.EVENING
    CORPORATE = Config.MICE
    SOCIAL = Config.SOCIAL
    WEEKDAY = "Weekday"
    WEEKEND = "Weekend"

    # Data type

    def __init__(self, name: str, sheet_range: str, sheet: str, event: str, cache_to: str = str(),
                 cache_from: str = str(), occupancy: bool = False):
        self.name = name
        self.range = sheet_range
        self.sheet = sheet
        self.event = event
        self.cache_to = cache_to
        self.cache_from = cache_from
        self.occupancy = occupancy


def get_report_attributes() -> List[ReportAttribute]:
    return [
        ReportAttribute(name=ReportTag.FULL_DAY_OCCUPANCY_BAR_GRAPH,
                        sheet=ReportAttribute.BAR_GRAPH,
                        event=ReportAttribute.FULL_DAY,
                        cache_to=ReportTag.FULL_DAY_OCCUPANCY_DATA_POINT,
                        occupancy=True,
                        sheet_range=f"'{ReportAttribute.BAR_GRAPH}'!F32:G41"
                        ),
        ReportAttribute(name=ReportTag.FULL_DAY_OCCUPANCY_DATA_POINT,
                        sheet=ReportAttribute.DATA_POINT,
                        event=ReportAttribute.FULL_DAY,
                        cache_from=ReportTag.FULL_DAY_OCCUPANCY_DATA_POINT,
                        occupancy=True,
                        sheet_range=f"'{ReportAttribute.DATA_POINT}'!A5:E5"
                        ),
        ReportAttribute(name=ReportTag.MORNING_OCCUPANCY_BAR_GRAPH,
                        sheet=ReportAttribute.BAR_GRAPH,
                        event=ReportAttribute.MORNING,
                        cache_to=ReportTag.MORNING_OCCUPANCY_DATA_POINT,
                        occupancy=True,
                        sheet_range=f"'{ReportAttribute.BAR_GRAPH}'!J18:K27"
                        ),
        ReportAttribute(name=ReportTag.MORNING_OCCUPANCY_DATA_POINT,
                        sheet=ReportAttribute.DATA_POINT,
                        event=ReportAttribute.MORNING,
                        cache_from=ReportTag.MORNING_OCCUPANCY_DATA_POINT,
                        occupancy=True,
                        sheet_range=f"'{ReportAttribute.DATA_POINT}'!A9:E9"
                        ),
        ReportAttribute(name=ReportTag.EVENING_OCCUPANCY_BAR_GRAPH,
                        sheet=ReportAttribute.BAR_GRAPH,
                        event=ReportAttribute.EVENING,
                        cache_to=ReportTag.EVENING_OCCUPANCY_DATA_POINT,
                        occupancy=True,
                        sheet_range=f"'{ReportAttribute.BAR_GRAPH}'!M18:N27"
                        ),
        ReportAttribute(name=ReportTag.EVENING_OCCUPANCY_DATA_POINT,
                        sheet=ReportAttribute.DATA_POINT,
                        event=ReportAttribute.EVENING,
                        cache_from=ReportTag.EVENING_OCCUPANCY_DATA_POINT,
                        occupancy=True,
                        sheet_range=f"'{ReportAttribute.DATA_POINT}'!A13:E13"
                        ),
        ReportAttribute(name=ReportTag.FULL_DAY_EVENTS_BAR_GRAPH,
                        sheet=ReportAttribute.BAR_GRAPH,
                        event=ReportAttribute.FULL_DAY,
                        cache_to=ReportTag.FULL_DAY_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.BAR_GRAPH}'!A2:B11"
                        ),
        ReportAttribute(name=ReportTag.FULL_DAY_EVENTS_DATA_POINT,
                        sheet=ReportAttribute.DATA_POINT,
                        event=ReportAttribute.FULL_DAY,
                        cache_from=ReportTag.FULL_DAY_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.DATA_POINT}'!A17:D17"
                        ),
        ReportAttribute(name=ReportTag.MORNING_EVENTS_BAR_GRAPH,
                        sheet=ReportAttribute.BAR_GRAPH,
                        event=ReportAttribute.MORNING,
                        cache_to=ReportTag.MORNING_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.BAR_GRAPH}'!A18:B27"
                        ),
        ReportAttribute(name=ReportTag.MORNING_EVENTS_DATA_POINT,
                        sheet=ReportAttribute.DATA_POINT,
                        event=ReportAttribute.MORNING,
                        cache_from=ReportTag.MORNING_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.DATA_POINT}'!A21:D21"
                        ),
        ReportAttribute(name=ReportTag.EVENING_EVENTS_BAR_GRAPH,
                        sheet=ReportAttribute.BAR_GRAPH,
                        event=ReportAttribute.EVENING,
                        cache_to=ReportTag.EVENING_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.BAR_GRAPH}'!E2:F11"
                        ),
        ReportAttribute(name=ReportTag.EVENING_EVENTS_DATA_POINT,
                        sheet=ReportAttribute.DATA_POINT,
                        event=ReportAttribute.EVENING,
                        cache_from=ReportTag.EVENING_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.DATA_POINT}'!A25:D25"
                        ),
        ReportAttribute(name=ReportTag.CORPORATE_EVENTS_BAR_GRAPH,
                        sheet=ReportAttribute.BAR_GRAPH,
                        event=ReportAttribute.CORPORATE,
                        cache_to=ReportTag.CORPORATE_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.BAR_GRAPH}'!J3:K12"
                        ),
        ReportAttribute(name=ReportTag.CORPORATE_EVENTS_DATA_POINT,
                        sheet=ReportAttribute.DATA_POINT,
                        event=ReportAttribute.CORPORATE,
                        cache_from=ReportTag.CORPORATE_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.DATA_POINT}'!A29:D29"
                        ),
        ReportAttribute(name=ReportTag.SOCIAL_EVENTS_BAR_GRAPH,
                        sheet=ReportAttribute.BAR_GRAPH,
                        event=ReportAttribute.SOCIAL,
                        cache_to=ReportTag.SOCIAL_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.BAR_GRAPH}'!R3:S12"
                        ),
        ReportAttribute(name=ReportTag.SOCIAL_EVENTS_DATA_POINT,
                        sheet=ReportAttribute.DATA_POINT,
                        event=ReportAttribute.SOCIAL,
                        cache_from=ReportTag.SOCIAL_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.DATA_POINT}'!A33:D33"
                        ),
        ReportAttribute(name=ReportTag.WEEKDAY_EVENTS_BAR_GRAPH,
                        sheet=ReportAttribute.BAR_GRAPH,
                        event=ReportAttribute.WEEKDAY,
                        cache_to=ReportTag.WEEKDAY_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.BAR_GRAPH}'!F18:E27"
                        ),
        ReportAttribute(name=ReportTag.WEEKDAY_EVENTS_DATA_POINT,
                        sheet=ReportAttribute.DATA_POINT,
                        event=ReportAttribute.WEEKDAY,
                        cache_from=ReportTag.WEEKDAY_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.DATA_POINT}'!A37:D37"
                        ),
        ReportAttribute(name=ReportTag.WEEKEND_EVENTS_BAR_GRAPH,
                        sheet=ReportAttribute.BAR_GRAPH,
                        event=ReportAttribute.WEEKEND,
                        cache_to=ReportTag.WEEKEND_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.BAR_GRAPH}'!R18:S27"
                        ),
        ReportAttribute(name=ReportTag.WEEKEND_EVENTS_DATA_POINT,
                        sheet=ReportAttribute.DATA_POINT,
                        event=ReportAttribute.WEEKEND,
                        cache_from=ReportTag.WEEKEND_EVENTS_DATA_POINT,
                        occupancy=False,
                        sheet_range=f"'{ReportAttribute.DATA_POINT}'!A41:D41"
                        ),
    ]
