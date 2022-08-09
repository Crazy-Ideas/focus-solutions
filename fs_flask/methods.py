import datetime as dt
from typing import List, Tuple

from pytz import timezone

YEARS = [str(year) for year in range(2018, 2040)]
MONTHS = [dt.datetime(2022, month, 1).strftime("%b") for month in range(1, 13)]
www_dd_mmm_yyyy = "%a,%d-%b-%Y"
WEEK_TAG = "Week "
WEEK_SEPARATOR = ": "
DATE_SEPARATOR = " to "


def format_www_dd_mmm_yyyy(date: dt.datetime) -> str:
    return date.strftime(www_dd_mmm_yyyy)


def unpack_www_dd_mmm_yyyy(date_str: str) -> dt.datetime:
    return dt.datetime.strptime(date_str, www_dd_mmm_yyyy)


def format_week_range(week_number: int, start_date: dt.datetime, end_date: dt.datetime) -> str:
    return f"{WEEK_TAG}{week_number}{WEEK_SEPARATOR}{format_www_dd_mmm_yyyy(start_date)}" \
           f"{DATE_SEPARATOR}{format_www_dd_mmm_yyyy(end_date)}"


def unpack_week_range(week_range: str) -> Tuple[int, dt.datetime, dt.datetime]:
    week_index: int = len(WEEK_TAG)
    week: str = week_range[week_index]
    www_dd_mmm_yyyy_len = len(format_www_dd_mmm_yyyy(dt.datetime.utcnow()))
    start_date_index = week_index + 1 + len(WEEK_SEPARATOR)
    start_date: str = week_range[start_date_index: start_date_index + www_dd_mmm_yyyy_len]
    end_date_index: int = start_date_index + www_dd_mmm_yyyy_len + len(DATE_SEPARATOR)
    end_date: str = week_range[end_date_index: end_date_index + www_dd_mmm_yyyy_len]
    return int(week), unpack_www_dd_mmm_yyyy(start_date), unpack_www_dd_mmm_yyyy(end_date)


def get_weeks_from_month(month: str, year: str) -> List[Tuple[dt.datetime, dt.datetime]]:
    week_number: int = 1
    first_date: dt.datetime = dt.datetime.strptime(f"1-{month}-{year}", "%d-%b-%Y")
    start_monday: dt.datetime = first_date if first_date.isoweekday() == 1 else \
        first_date + dt.timedelta(days=8 - first_date.isoweekday())
    weeks: list = list()
    while start_monday.month == first_date.month:
        end_sunday: dt.datetime = start_monday + dt.timedelta(days=6)
        weeks.append((start_monday, end_sunday))
        start_monday += dt.timedelta(days=7)
        week_number += 1
    return weeks


def format_weeks_from_month(month: str, year: str) -> List[str]:
    return [format_week_range(index + 1, start_date, end_date)
            for index, (start_date, end_date) in enumerate(get_weeks_from_month(month, year))]


def get_default_week_month(test_date=None) -> Tuple[str, str, str]:
    today: dt.datetime = test_date or dt.datetime.combine(dt.datetime.now(tz=timezone("Asia/Kolkata")).date(),
                                                          dt.datetime.min.time())
    previous_monday: dt.datetime = today - dt.timedelta(days=today.isoweekday() + 6)
    month = previous_monday.strftime("%b")
    year = str(previous_monday.year)
    weeks: List[tuple] = get_weeks_from_month(month, year)
    date_range: tuple = next(week for week in weeks if week[0] == previous_monday)
    format_week: str = format_week_range(weeks.index(date_range) + 1, date_range[0], date_range[1])
    return format_week, month, year
