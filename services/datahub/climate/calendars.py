"""CF 일 단위 날짜를 Gregorian datetime으로 강제 변환하지 않고 검증한다."""

import re

ALIASES = {
    "standard": "standard",
    "gregorian": "standard",
    "proleptic_gregorian": "proleptic_gregorian",
    "360_day": "360_day",
    "noleap": "noleap",
    "365_day": "noleap",
    "all_leap": "all_leap",
    "366_day": "all_leap",
    "julian": "julian",
}


def normalize_calendar(value: str) -> str:
    if not isinstance(value, str) or value.lower() not in ALIASES:
        raise ValueError("UNSUPPORTED_CF_CALENDAR")
    return ALIASES[value.lower()]


def date_parts(value: str, calendar: str) -> tuple[int, int, int]:
    calendar = normalize_calendar(calendar)
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("CF_DATE_REQUIRES_YYYY_MM_DD")
    year, month, day = map(int, value.split("-"))
    if not 1 <= year <= 9999 or not 1 <= month <= 12:
        raise ValueError("INVALID_CF_DATE")
    # mixed Julian/Gregorian 전환과 연도0은 현재 일 단위 서비스 범위 밖이다.
    if calendar == "standard" and year < 1583:
        raise ValueError("STANDARD_PRE_1583_NOT_SUPPORTED")
    leap = (
        calendar == "all_leap"
        or calendar == "julian"
        and year % 4 == 0
        or calendar in {"standard", "proleptic_gregorian"}
        and year % 4 == 0
        and (year % 100 != 0 or year % 400 == 0)
    )
    lengths = (
        [30] * 12
        if calendar == "360_day"
        else [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    )
    if not 1 <= day <= lengths[month - 1]:
        raise ValueError("INVALID_DAY_FOR_CF_CALENDAR")
    return year, month, day


def ordinal(value: str, calendar: str) -> int:
    calendar = normalize_calendar(calendar)
    year, month, day = date_parts(value, calendar)
    previous = year - 1
    if calendar == "360_day":
        return previous * 360 + (month - 1) * 30 + day
    if calendar in {"noleap", "all_leap"}:
        base = previous * (365 if calendar == "noleap" else 366)
    elif calendar == "julian":
        base = previous * 365 + previous // 4
    else:
        base = previous * 365 + previous // 4 - previous // 100 + previous // 400
    # 같은 달력의 실제 월말을 이용하므로 noleap/360_day가 섞이지 않는다.
    days = 0
    for candidate in range(1, month):
        for last in (31, 30, 29, 28):
            try:
                date_parts(f"{year:04}-{candidate:02}-{last:02}", calendar)
                days += last
                break
            except ValueError:
                continue
    return base + days + day


def period_days(start: str, end: str, calendar: str) -> int:
    days = ordinal(end, calendar) - ordinal(start, calendar) + 1
    if days <= 0:
        raise ValueError("REVERSED_CF_TIME_COVERAGE")
    return days


def validate_time_units(value: str, calendar: str) -> None:
    # months/years since 및 sub-day 해석은 별도 CF decoder가 필요하므로 추정하지 않는다.
    match = re.fullmatch(r"(days|hours|seconds) since (\d{4}-\d{2}-\d{2})(?: 00:00:00)?", value)
    if not match:
        raise ValueError("UNSUPPORTED_CF_TIME_UNITS")
    date_parts(match.group(2), calendar)
