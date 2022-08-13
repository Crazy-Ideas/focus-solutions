import datetime as dt
from calendar import monthrange
from typing import List, Tuple

from pytz import timezone

www_dd_mmm_yyyy = "%a,%d-%b-%Y"
yyyy_mm_dd = "%Y-%m-%d"
WEEK_TAG = "Week "
SAAYA_TAG = "Saaya Days for "
WEEK_SEPARATOR = ": "
DATE_SEPARATOR = " to "


class Days:

    def __init__(self, total_days: int = 0, week_days: int = 0, weekend_days: int = 0):
        self.total_days: int = total_days
        self.week_days: int = week_days
        self.weekend_days: int = weekend_days


def format_www_dd_mmm_yyyy(date: dt.date) -> str:
    return date.strftime(www_dd_mmm_yyyy)


def unpack_www_dd_mmm_yyyy(date_str: str) -> dt.date:
    return dt.datetime.strptime(date_str, www_dd_mmm_yyyy).date()


def format_week_range(week_number: int, start_date: dt.date, end_date: dt.date) -> str:
    return f"{WEEK_TAG}{week_number}{WEEK_SEPARATOR}{format_www_dd_mmm_yyyy(start_date)}" \
           f"{DATE_SEPARATOR}{format_www_dd_mmm_yyyy(end_date)}"


def format_month_range(month: str, year: int, start_date: dt.date, end_date: dt.date) -> str:
    return f"{month}-{year}{WEEK_SEPARATOR}{format_www_dd_mmm_yyyy(start_date)}" \
           f"{DATE_SEPARATOR}{format_www_dd_mmm_yyyy(end_date)}"


def format_days(month: str, year: int, days: List[str]) -> str:
    return f"{SAAYA_TAG}{month}-{year}{WEEK_SEPARATOR}{' '.join(days)}"


def unpack_week_range(week_range: str) -> Tuple[int, dt.date, dt.date]:
    week_index: int = len(WEEK_TAG)
    week: str = week_range[week_index]
    www_dd_mmm_yyyy_len = len(format_www_dd_mmm_yyyy(dt.date.today()))
    start_date_index = week_index + 1 + len(WEEK_SEPARATOR)
    start_date: str = week_range[start_date_index: start_date_index + www_dd_mmm_yyyy_len]
    end_date_index: int = start_date_index + www_dd_mmm_yyyy_len + len(DATE_SEPARATOR)
    end_date: str = week_range[end_date_index: end_date_index + www_dd_mmm_yyyy_len]
    return int(week), unpack_www_dd_mmm_yyyy(start_date), unpack_www_dd_mmm_yyyy(end_date)


def get_date_from_month(day: int, month: str, year: int):
    return dt.datetime.strptime(f"{day}-{month}-{year}", "%d-%b-%Y").date()


def get_weeks_from_month(month: str, year: int) -> List[Tuple[dt.date, dt.date]]:
    week_number: int = 1
    first_date: dt.date = get_date_from_month(1, month, year)
    start_monday: dt.date = first_date if first_date.isoweekday() == 1 else \
        first_date + dt.timedelta(days=8 - first_date.isoweekday())
    weeks: list = list()
    while start_monday.month == first_date.month:
        end_sunday: dt.date = start_monday + dt.timedelta(days=6)
        weeks.append((start_monday, end_sunday))
        start_monday += dt.timedelta(days=7)
        week_number += 1
    return weeks


def format_weeks_from_month(month: str, year: int) -> List[str]:
    return [format_week_range(index + 1, start_date, end_date)
            for index, (start_date, end_date) in enumerate(get_weeks_from_month(month, year))]


def get_default_week_month(test_date=None) -> Tuple[str, str, int]:
    today: dt.date = test_date or dt.datetime.now(tz=timezone("Asia/Kolkata")).date()
    previous_monday: dt.date = today - dt.timedelta(days=today.isoweekday() + 6)
    month = previous_monday.strftime("%b")
    year = previous_monday.year
    weeks: List[tuple] = get_weeks_from_month(month, previous_monday.year)
    date_range: tuple = next(week for week in weeks if week[0] == previous_monday)
    format_week: str = format_week_range(weeks.index(date_range) + 1, date_range[0], date_range[1])
    return format_week, month, year


def next_year(current_year: int) -> int:
    return min(current_year + 1, 2100)


def previous_year(current_year: int) -> int:
    return max(current_year - 1, 1900)


def next_month(current_month: str, current_year: int) -> Tuple[str, int]:
    current_date: dt.date = get_date_from_month(1, current_month, current_year)
    next_month_date: dt.date = current_date + dt.timedelta(days=31)
    return next_month_date.strftime("%b"), next_month_date.year


def previous_month(current_month: str, current_year: int) -> Tuple[str, int]:
    current_date: dt.date = get_date_from_month(1, current_month, current_year)
    previous_month_date: dt.date = current_date - dt.timedelta(days=1)
    return previous_month_date.strftime("%b"), previous_month_date.year


def next_week(current_week: str, current_month: str, current_year: int) -> Tuple[str, str, int]:
    weeks: List[str] = format_weeks_from_month(current_month, current_year)
    next_week_index: int = weeks.index(current_week) + 1
    if next_week_index < len(weeks):
        return weeks[next_week_index], current_month, current_year
    month, year = next_month(current_month, current_year)
    return format_weeks_from_month(month, year)[0], month, year


def previous_week(current_week: str, current_month: str, current_year: int) -> Tuple[str, str, int]:
    weeks: List[str] = format_weeks_from_month(current_month, current_year)
    previous_week_index: int = weeks.index(current_week) - 1
    if previous_week_index >= 0:
        return weeks[previous_week_index], current_month, current_year
    month, year = previous_month(current_month, current_year)
    return format_weeks_from_month(month, year)[-1], month, year


def get_days_from_month(month: str, year: int) -> List[str]:
    month_number: int = get_date_from_month(1, month, year).month
    return [str(day) for day in range(1, monthrange(month=month_number, year=year)[1] + 1)]


def get_start_end_date_from_month(month: str, year: int) -> Tuple[dt.date, dt.date]:
    start_date: dt.date = get_date_from_month(1, month, year)
    end_date: dt.date = get_date_from_month(monthrange(month=start_date.month, year=year)[1], month, year)
    return start_date, end_date


def format_start_end_date_from_month(month: str, year: int) -> str:
    start_date, end_date = get_start_end_date_from_month(month, year)
    return format_month_range(month, year, start_date, end_date)


def get_db_date(date: dt.date) -> str:
    return date.strftime(yyyy_mm_dd)


def get_db_date_range_for_month(month: str, year: int) -> Tuple[str, str]:
    start_date, end_date = get_start_end_date_from_month(month, year)
    return get_db_date(start_date), get_db_date(end_date)


def get_db_date_range_for_week(week_range: str) -> Tuple[str, str]:
    week, start_date, end_date = unpack_week_range(week_range)
    return get_db_date(start_date), get_db_date(end_date)


def get_db_date_list_for_days(days: List[str], month, year) -> List[str]:
    return [get_db_date(get_date_from_month(int(day), month, year)) for day in days]


def get_days_count_from_month(month: str, year: int) -> Days:
    list_of_days = get_days_from_month(month, year)
    return get_days_count_from_days(list_of_days, month, year)


def get_days_count_from_days(list_of_days: List[str], month: str, year: int) -> Days:
    days = Days()
    days.total_days = len(list_of_days)
    days.week_days = sum(1 for day in list_of_days if get_date_from_month(int(day), month, year).isoweekday() <= 5)
    days.weekend_days = days.total_days - days.week_days
    return days
