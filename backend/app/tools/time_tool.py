import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_DEFAULT_TZ = "UTC"
_CITY_TIMEZONES = {
    "karachi": "Asia/Karachi",
    "lahore": "Asia/Karachi",
    "islamabad": "Asia/Karachi",
    "pakistan": "Asia/Karachi",
    "london": "Europe/London",
    "new york": "America/New_York",
    "dubai": "Asia/Dubai",
    "mumbai": "Asia/Kolkata",
    "india": "Asia/Kolkata",
    "tokyo": "Asia/Tokyo",
    "utc": "UTC",
    "gmt": "UTC",
}


def _detect_timezone(query: str) -> str:
    lowered = query.lower()
    for name, tz in sorted(_CITY_TIMEZONES.items(), key=lambda x: -len(x[0])):
        if name in lowered:
            return tz
    match = re.search(r"\b([A-Za-z]+/[A-Za-z_]+)\b", query)
    return match.group(1) if match else _DEFAULT_TZ


def _wants_date_only(query: str) -> bool:
    lowered = query.lower()
    if any(k in lowered for k in ("time", "baj", "clock", "hour")):
        return False
    return any(k in lowered for k in ("date", "tareekh", "din", "day"))


def handle(query: str = "", timezone: str | None = None) -> str:
    tz_name = timezone or _detect_timezone(query)
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo(_DEFAULT_TZ)
        tz_name = _DEFAULT_TZ

    now = datetime.now(tz)
    date_str = now.strftime("%A, %d %B %Y")
    time_str = now.strftime("%I:%M %p").lstrip("0")

    if _wants_date_only(query):
        return f"Today's date in {tz_name} is {date_str}."
    return (
        f"Current time in {tz_name} is {time_str} on {date_str} "
        f"({now.strftime('%Y-%m-%d %H:%M:%S %Z')})."
    )
