from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Any, Optional, Union

from typing_extensions import Self

ISO8601_DATE_REGEX_YYYY_MM_DD = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$"
)
ISO8601_DATE_REGEX_YYYY_MM = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})$")
ISO8601_DATE_REGEX_YYYY = re.compile(r"^(?P<year>\d{4})$")


class ImmutableDate(date):
    def __setattr__(self, name: str, value: Any):
        raise AttributeError("Cannot modify immutable instance")

    def __delattr__(self, name: str):
        raise AttributeError("Cannot delete attribute from immutable instance")

    # Overriding methods that could potentially modify the date
    def replace(self, *args: Any, **kwargs: Any):
        raise AttributeError("Cannot modify immutable instance")


class FixedDateMeta(type):
    def __setattr__(self, name: str, value: Any):
        raise AttributeError("Cannot modify immutable instance")


class FixedDate(metaclass=FixedDateMeta):
    PAST: date = ImmutableDate(1, 1, 1)
    FUTURE: date = ImmutableDate(9999, 12, 31)


class ApproxDate:
    def __init__(
        self,
        earliest_date: date,
        latest_date: date,
        source_string: Optional[str] = None,
    ):
        self.earliest_date = earliest_date
        self.latest_date = latest_date
        self.source_string = source_string

    def is_partial_just_year(self):
        """
        Are our dates the start and end of a year?
        """
        ed = self.earliest_date
        ld = self.latest_date
        if ed.year == ld.year:
            if ed.month == 1 and ed.day == 1:
                return ld.month == 12 and ld.day == 31

    def is_partial_just_year_and_month(self):
        """
        Are the dates the start and end of a month?
        """
        ed = self.earliest_date
        ld = self.latest_date
        if ed.month == ld.month and ed.year == ld.year:
            days_in_month = calendar.monthrange(ed.year, ed.month)[1]
            return ed.day == 1 and ld.day == days_in_month

    def isoformat(self):
        """
        Convert the date range into the most compact
        iso8601 possible
        """
        if self.earliest_date == self.latest_date:
            return self.earliest_date.isoformat()
        else:
            if self.is_partial_just_year_and_month():
                return self.latest_date.strftime("%Y-%m")
            if self.is_partial_just_year():
                return "{0}".format(self.earliest_date.year)
        # if none of these - return a date range
        return "{0}/{1}".format(
            self.earliest_date.isoformat(), self.latest_date.isoformat()
        )

    @classmethod
    def fromisoformat(cls, iso8601_date_string: str) -> Self:
        if "/" in iso8601_date_string:  # extract double date
            start, end = iso8601_date_string.split("/")
            start_date = cls.fromisoformat(start)
            end_date = cls.fromisoformat(end)
            combined = cls(
                start_date.earliest_date, end_date.latest_date, iso8601_date_string
            )
            return combined

        full_match = ISO8601_DATE_REGEX_YYYY_MM_DD.search(iso8601_date_string)
        if full_match:
            d = date(*(int(p, 10) for p in full_match.groups()))
            return cls(d, d, iso8601_date_string)
        no_day_match = ISO8601_DATE_REGEX_YYYY_MM.search(iso8601_date_string)
        if no_day_match:
            year = int(no_day_match.group("year"), 10)
            month = int(no_day_match.group("month"), 10)
            days_in_month = calendar.monthrange(year, month)[1]
            earliest = date(year, month, 1)
            latest = date(year, month, days_in_month)
            return cls(earliest, latest, iso8601_date_string)
        only_year_match = ISO8601_DATE_REGEX_YYYY.search(iso8601_date_string)
        if only_year_match:
            earliest = date(int(only_year_match.group("year"), 10), 1, 1)
            latest = date(int(only_year_match.group("year"), 10), 12, 31)
            return cls(earliest, latest, iso8601_date_string)
        msg = "Couldn't parse the ISO 8601 partial date '{0}'"
        raise ValueError(msg.format(iso8601_date_string))

    @property
    def midpoint_date(self):
        delta = self.latest_date - self.earliest_date
        return self.earliest_date + delta / 2

    def __str__(self):
        return self.isoformat()

    def __add__(self, other: Any) -> ApproxDate:
        if isinstance(other, timedelta):
            return ApproxDate(self.earliest_date + other, self.latest_date + other)
        else:
            raise NotImplementedError(f"Can't add {type(other)} to ApproxDate")

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, date):
            # if the date is the same as the earliest and latest date
            return (
                self.earliest_date == self.latest_date and self.earliest_date == other
            )
        elif isinstance(other, ApproxDate):
            return (
                self.earliest_date == self.latest_date
                and self.earliest_date == other.latest_date
            )
        elif isinstance(other, str):
            return self.isoformat() == other
        else:
            return False

    def __ne__(self, other: Any):
        return not (self == other)

    def __gt__(self, other: Any):
        if isinstance(other, date):
            return self.earliest_date > other
        elif isinstance(other, ApproxDate):
            return self.earliest_date > other.latest_date
        else:
            raise NotImplementedError(f"Can't compare ApproxDate to {type(other)}")

    def __lt__(self, other: Any):
        if isinstance(other, date):
            return self.latest_date < other
        if isinstance(other, ApproxDate):
            return self.latest_date < other.earliest_date
        else:
            raise NotImplementedError(f"Can't compare ApproxDate to {type(other)}")

    def __le__(self, other: Any):
        return self < other or self == other

    def __ge__(self, other: Any):
        return self > other or self == other

    def __repr__(self):
        return f"ApproxDate.fromisoformat({self.isoformat()})"

    @classmethod
    def possibly_between(
        cls,
        start_date: Union[ApproxDate, date],
        d: Union[ApproxDate, date],
        end_date: Union[ApproxDate, date],
    ) -> bool:
        """
        Is the date d possibly between start_date and end_date?
        """

        earliest_bound = (
            start_date.earliest_date
            if isinstance(start_date, ApproxDate)
            else start_date
        )
        latest_bound = (
            end_date.latest_date if isinstance(end_date, ApproxDate) else end_date
        )
        return earliest_bound <= d <= latest_bound
