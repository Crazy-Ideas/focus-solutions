from itertools import groupby
from operator import itemgetter
from typing import List, Dict

from flask_login import current_user

from config import Config
from fs_flask.date_methods import get_db_date_range_for_week, get_db_date_range_for_month, get_db_date_list_for_days, \
    get_days_count_from_month, get_days_count_from_days, Days, format_start_end_date_from_month, format_days, \
    unpack_week_range
from fs_flask.file import File, RangeValues
from fs_flask.hotel import Hotel
from fs_flask.report_helpers import QueryAttribute, DataAttribute, ReportAttribute, get_report_attributes
from fs_flask.usage import Usage


def execute_report_action(query_tag: str, my_hotel: Hotel, days: List[int]) -> tuple:
    action: QueryAttribute = get_query_attribute(query_tag)
    # Navigation Methods
    if action.nav_method:
        if action.name == QueryTag.UPDATE_DAYS:
            action.nav_method(days)
        else:
            action.nav_method()
        current_user.save()
        return None, None

    # Init copy of template sheet
    sheet = File(Config.TEMPLATE_SHEET_ID, "xlsx")
    sheet.async_copy()

    # Get period string
    def get_title(period_tag: str) -> str:
        return f"{compset_tag} Compset - {current_user.report_month} {period_tag} Performance Data"

    compset_tag = "Primary" if action.comp_set == QueryAttribute.PRIMARY else "Secondary"
    if action.period == QueryAttribute.WEEKLY:
        period = current_user.report_week
        title = get_title("Month Weekly")
        week_number, _, _ = unpack_week_range(period)
        short_title = f"Week {week_number}"
    elif action.period == QueryAttribute.MONTHLY:
        period = format_start_end_date_from_month(current_user.report_month, current_user.report_year)
        title = get_title("Monthly")
        short_title = "Monthly"
    else:
        period = format_days(current_user.report_month, current_user.report_year, current_user.report_days)
        title = get_title("Month Saaya Days")
        short_title = "Saaya Days"

    # Update title
    comp_set: List[str] = getattr(my_hotel, action.comp_set)
    title = f"{title}\n({period})"
    subtitle = f"My Property: {my_hotel.name}\nComp Set: {', '.join(comp_set)}"
    update_ranges: List[dict] = list()
    update_ranges.append(RangeValues(f"'{ReportAttribute.DATA_POINT}'!A1:A2", [[title], [subtitle]]).to_dict())

    # Get Usages from db
    usages: List[Usage] = get_usages_from_query(action, comp_set)

    # Start of Event Reports
    # Get ballroom count for each hotel which is used by occupancy report
    hotels: List[Hotel] = Hotel.objects.filter("name", Hotel.objects.IN, comp_set).get() if comp_set else list()
    ballroom_info: dict = {my_hotel.name: my_hotel.ballroom_count}
    for hotel in hotels:
        ballroom_info[hotel.name] = hotel.ballroom_count
    # Get total days for data attributes
    day_counts: Days = get_days_from_period(action.period)
    # Filter data for data attributes
    full_day_events = usages
    morning_events = [u for u in usages if u.timing == Config.MORNING]
    evening_events = [u for u in usages if u.timing == Config.EVENING]
    corp_events = [u for u in usages if u.event_type == Config.MICE]
    social_events = [u for u in usages if u.event_type == Config.SOCIAL]
    weekday_events = [u for u in usages if u.weekday]
    weekend_events = [u for u in usages if not u.weekday]
    # Setup data attributes
    data: Dict[str, DataAttribute] = dict()
    data[ReportAttribute.FULL_DAY] = DataAttribute(full_day_events, current_user.hotel, comp_set, day_counts.total_days)
    data[ReportAttribute.MORNING] = DataAttribute(morning_events, current_user.hotel, comp_set,
                                                  day_counts.total_days / 2)
    data[ReportAttribute.EVENING] = DataAttribute(evening_events, current_user.hotel, comp_set,
                                                  day_counts.total_days / 2)
    data[ReportAttribute.CORPORATE] = DataAttribute(corp_events, current_user.hotel, comp_set, day_counts.total_days)
    data[ReportAttribute.SOCIAL] = DataAttribute(social_events, current_user.hotel, comp_set, day_counts.total_days)
    data[ReportAttribute.WEEKDAY] = DataAttribute(weekday_events, current_user.hotel, comp_set, day_counts.week_days)
    data[ReportAttribute.WEEKEND] = DataAttribute(weekend_events, current_user.hotel, comp_set, day_counts.weekend_days)
    # Occupancy & Event Report
    cache: dict = dict()
    for report_attr in get_report_attributes():
        my_prop_data: List[Usage] = data[report_attr.event].my_prop
        comp_set_data: List[Usage] = data[report_attr.event].comp_set
        if not report_attr.occupancy:
            if not report_attr.cache_from:
                values = [[my_hotel.name, len(my_prop_data)]]
                values.extend([[hotel_name, sum(1 for u in comp_set_data if u.hotel == hotel_name)]
                               for hotel_name in comp_set])
                if report_attr.cache_to:
                    cache[report_attr.cache_to] = values
            else:  # cache is available
                values = cache[report_attr.cache_from]
            if report_attr.sheet == ReportAttribute.DATA_POINT:
                values = get_data_point_values(values, len(comp_set), period)
        else:  # Occupancy Reports
            if not report_attr.cache_from:
                timing_count = data[report_attr.event].timing_count
                my_value = get_occupancy_values(my_prop_data, my_hotel.name, timing_count, ballroom_info[my_hotel.name])
                values = [my_value]
                values.extend([get_occupancy_values(comp_set_data, hotel_name, timing_count, ballroom_info[hotel_name])
                               for hotel_name in comp_set])
                if report_attr.cache_to:
                    cache[report_attr.cache_to] = values
            else:  # cache is available
                values = cache[report_attr.cache_from]
            if report_attr.sheet == ReportAttribute.DATA_POINT:
                # noinspection PyTypeChecker
                aggregate_value: float = sum(value[1] for value in values) / (len(comp_set) + 1)
                mpi_index: float = values[0][1] / aggregate_value if aggregate_value > 0 else 0
                values = get_data_point_values(values, len(comp_set), period)
                values[0].append(mpi_index)
        if report_attr.sheet == ReportAttribute.BAR_GRAPH:
            values = [value[:] for value in values]
            values.extend([[str(), str()]] * (9 - len(comp_set)))
        update_ranges.append(RangeValues(report_attr.range, values).to_dict())

    # Update Reader Board data
    def sort_events(data: List[Usage]) -> None:
        data.sort(key=lambda item: item.timing, reverse=True)
        data.sort(key=lambda item: (item.hotel, item.date))

    sorted_events: List[Usage] = data[ReportAttribute.FULL_DAY].my_prop[:]
    sort_events(sorted_events)
    sort_events(data[ReportAttribute.FULL_DAY].comp_set)
    sorted_events.extend(data[ReportAttribute.FULL_DAY].comp_set)
    rbd = [["Date", "Timings", "Company Name", "Event Type", "Hotel Name", "BTR", "Ballrooms"]]
    rbd.extend([[u.formatted_date, u.timing, u.client, u.event_type, u.hotel, u.event_description, u.formatted_ballroom,
                 ] for u in sorted_events])
    update_ranges.append(RangeValues(f"'{ReportAttribute.RBD}'!A1:G{len(sorted_events) + 1}", rbd).to_dict())

    # Update Top 5 clients
    top5_counts: dict = dict()
    counted: set = set()
    for u in data[ReportAttribute.CORPORATE].comp_set:
        key = f"{u.hotel}{u.client}"
        counted_key = f"{key}{u.date}"
        if key not in top5_counts:
            top5_counts[key] = [1, u]
            counted.add(counted_key)
            continue
        if counted_key in counted:
            continue
        top5_counts[key][0] += 1
    top5_list: List[list] = [top5_counts[key] for key in top5_counts if top5_counts[key][0] > 1]
    top5_list.sort(key=lambda item: (item[1].hotel, -item[0]))
    top5_report = [["Hotel Name", "Client Name", "No of Events in a Week", "Remarks"]]
    for hotel_name, top5_groups in groupby(top5_list, key=lambda item: item[1].hotel):
        clients = list(top5_groups)
        if not clients:
            update_top5_message(top5_report, hotel_name, "There are no clients with more than 1 event.")
            continue
        till_index: int = min(5, len(clients))
        for count, u in clients[:till_index]:
            top5_report.append([hotel_name, u.client, count, str()])
        if len(clients) < 5:
            message = f"There are only {len(clients)} clients with more than 1 event."
            update_top5_message(top5_report, hotel_name, message)
            continue
        if len(clients) > 5 and clients[4][0] == clients[5][0]:
            message = f"There are more clients with {clients[4][0]} events."
            update_top5_message(top5_report, hotel_name, message)
            continue
        top5_report.append([str(), str(), str(), str()])
    top5_range = f"'{ReportAttribute.TOP5}'!A1:D{len(top5_report)}"
    update_ranges.append(RangeValues(top5_range, top5_report).to_dict())

    # Update Ranges in the new copied sheet and download it
    new_sheet: File = sheet.await_copy()
    new_sheet.update_bulk_range(update_ranges)
    file_path = new_sheet.download_from_drive()
    new_sheet.delete_sheet()
    filename = f"BQT Analytics - {my_hotel.name} -  {compset_tag} Compset - {current_user.report_month} " \
               f"{current_user.report_year} - {short_title}.{new_sheet.extension}"
    return file_path, filename


def get_usages_from_query(action: QueryAttribute, comp_set: List[str]) -> List[Usage]:
    hotel_names: List[str] = comp_set[:]
    hotel_names.append(current_user.hotel)
    if action.period == QueryAttribute.WEEKLY:
        start_date, end_date = get_db_date_range_for_week(current_user.report_week)
    else:
        start_date, end_date = get_db_date_range_for_month(current_user.report_month, current_user.report_year)
    query = Usage.objects.filter_by(city=current_user.city, no_event=False)
    query = query.filter("hotel", query.IN, hotel_names)
    query = query.filter("date", query.GREATER_THAN_OR_EQUAL, start_date)
    query = query.filter("date", query.LESS_THAN_OR_EQUAL, end_date)
    usages: List[Usage] = query.get()
    if action.period == QueryAttribute.DAYS:
        date_list = get_db_date_list_for_days(current_user.report_days, current_user.report_month,
                                              current_user.report_year)
        usages = [u for u in usages if u.date in date_list]
    return usages


def get_occupancy_values(usages: List[Usage], hotel_name: str, timing_count: int, ballroom_count: int) -> list:
    occupied = sum(len(u.ballrooms) for u in usages if u.hotel == hotel_name)
    total = timing_count * ballroom_count
    occupancy: float = occupied / total
    return [hotel_name, occupancy]


def rank_values(values: List[list]) -> List[list]:
    sorted_values = sorted(values, key=itemgetter(1), reverse=True)
    previous_value = previous_rank = 0
    ranked_values = [value[:] for value in values]
    for index, value in enumerate(sorted_values):
        rank = previous_rank if value[1] == previous_value else index + 1
        previous_value, previous_rank = value[1], rank
        hotel_value = next(r for r in ranked_values if r[0] == value[0])
        hotel_value.append(rank)
    return ranked_values


def get_data_point_values(values: List[list], comp_set_count: int, period: str) -> list:
    my_prop_value: float = values[0][1]
    comp_set_value: float = sum(value[1] for value in values[1:]) / comp_set_count if comp_set_count > 0 else 0
    ranked_values = rank_values(values)
    my_rank = ranked_values[0][2]
    return [[period, my_prop_value, comp_set_value, my_rank]]


def get_days_from_period(period: str) -> Days:
    if period == QueryAttribute.WEEKLY:
        return Days(total_days=7, weekend_days=2, week_days=5)
    elif period == QueryAttribute.MONTHLY:
        return get_days_count_from_month(current_user.report_month, current_user.report_year)
    elif period == QueryAttribute.DAYS:
        return get_days_count_from_days(current_user.report_days, current_user.report_month, current_user.report_year)
    return Days()


def update_top5_message(top5_values: list, hotel_name: str, message: str) -> None:
    top5_values.append([hotel_name, str(), str(), message])
    top5_values.append([str(), str(), str(), str()])


class QueryTag:
    PRIMARY_WEEKLY = "primary_weekly"
    PRIMARY_MONTHLY = "primary_monthly"
    PRIMARY_DAYS = "primary_days"
    SECONDARY_WEEKLY = "secondary_weekly"
    SECONDARY_MONTHLY = "secondary_monthly"
    SECONDARY_DAYS = "secondary_days"
    NEXT_WEEK = "next_week"
    PREVIOUS_WEEK = "previous_week"
    NEXT_MONTH = "next_month"
    PREVIOUS_MONTH = "previous_month"
    NEXT_YEAR = "next_year"
    PREVIOUS_YEAR = "previous_year"
    DEFAULT_WEEK = "default_week"
    UPDATE_DAYS = "update_days"


def get_query_attribute(query_tag: str) -> QueryAttribute:
    _action_attributes: List[QueryAttribute] = [
        QueryAttribute(QueryTag.PRIMARY_WEEKLY, comp_set=QueryAttribute.PRIMARY, period=QueryAttribute.WEEKLY),
        QueryAttribute(QueryTag.SECONDARY_WEEKLY, comp_set=QueryAttribute.SECONDARY,
                       period=QueryAttribute.WEEKLY),
        QueryAttribute(QueryTag.PRIMARY_MONTHLY, comp_set=QueryAttribute.PRIMARY, period=QueryAttribute.MONTHLY),
        QueryAttribute(QueryTag.SECONDARY_MONTHLY, comp_set=QueryAttribute.SECONDARY,
                       period=QueryAttribute.MONTHLY),
        QueryAttribute(QueryTag.PRIMARY_DAYS, comp_set=QueryAttribute.PRIMARY, period=QueryAttribute.DAYS),
        QueryAttribute(QueryTag.SECONDARY_DAYS, comp_set=QueryAttribute.SECONDARY, period=QueryAttribute.DAYS),
        QueryAttribute(QueryTag.NEXT_WEEK, nav_method=current_user.next_report_week),
        QueryAttribute(QueryTag.PREVIOUS_WEEK, nav_method=current_user.previous_report_week),
        QueryAttribute(QueryTag.NEXT_MONTH, nav_method=current_user.next_report_month),
        QueryAttribute(QueryTag.PREVIOUS_MONTH, nav_method=current_user.previous_report_month),
        QueryAttribute(QueryTag.NEXT_YEAR, nav_method=current_user.next_report_year),
        QueryAttribute(QueryTag.PREVIOUS_YEAR, nav_method=current_user.previous_report_year),
        QueryAttribute(QueryTag.DEFAULT_WEEK, nav_method=current_user.default_report_week),
        QueryAttribute(QueryTag.UPDATE_DAYS, nav_method=current_user.update_report_days),
    ]
    return next(attribute for attribute in _action_attributes if attribute.name == query_tag)
