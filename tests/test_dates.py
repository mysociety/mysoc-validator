from datetime import date

import pytest
from mysoc_validator.models.dates import ApproxDate, FixedDate


def test_create_from_full_iso_8601():
    """Verify create from full iso 8601."""
    d = ApproxDate.fromisoformat("1964-06-26")
    assert isinstance(d, ApproxDate)
    assert d.earliest_date == date(1964, 6, 26)
    assert d.latest_date == date(1964, 6, 26)
    assert d == "1964-06-26"


def test_create_from_partial_iso_8601_only_year():
    """Verify create from partial iso 8601 only year."""
    d = ApproxDate.fromisoformat("1964")
    assert isinstance(d, ApproxDate)
    assert d.earliest_date == date(1964, 1, 1)
    assert d.latest_date == date(1964, 12, 31)
    assert d == "1964"


def test_create_from_partial_iso_8601_only_year_and_month():
    """Verify create from partial iso 8601 only year and month."""
    d = ApproxDate.fromisoformat("1964-06")
    assert isinstance(d, ApproxDate)
    assert d.earliest_date == date(1964, 6, 1)
    assert d.latest_date == date(1964, 6, 30)
    assert d == "1964-06"


def test_malformed_iso_8601_date():
    """Verify malformed iso 8601 date."""
    with pytest.raises(ValueError):
        ApproxDate.fromisoformat("next Tuesday-ish")


def test_midpoint_for_precise_date():
    """Verify midpoint for precise date."""
    d = ApproxDate.fromisoformat("1977-12-27")
    assert d.midpoint_date == date(1977, 12, 27)


def test_midpoint_for_missing_day():
    """Verify midpoint for missing day."""
    d = ApproxDate.fromisoformat("1999-12")
    assert d.midpoint_date == date(1999, 12, 16)


def test_midpoint_for_year():
    """Verify midpoint for year."""
    d = ApproxDate.fromisoformat("2016")
    assert d.midpoint_date == date(2016, 7, 1)


def test_arbitrary_date_range():
    """Verify arbitrary date range."""
    d = ApproxDate(date(1926, 1, 3), date(2016, 3, 8))
    assert d == "1926-01-03/2016-03-08"


def test_equality_true_to_other_approxdate():
    """Verify equality true to other approxdate."""
    d1 = ApproxDate.fromisoformat("1964-06-26")
    d2 = ApproxDate.fromisoformat("1964-06-26")
    assert d1 == d2


def test_equality_false_to_other_approxdate():
    """Verify equality false to other approxdate."""
    d1 = ApproxDate.fromisoformat("1964-06-26")
    d2 = ApproxDate.fromisoformat("1977-12-27")
    assert d1 != d2


def test_inequality_true_to_other_approxdate():
    """Verify inequality true to other approxdate."""
    d1 = ApproxDate.fromisoformat("1964-06-26")
    d2 = ApproxDate.fromisoformat("1977-12-27")
    assert d1 != d2


def test_inequality_false_to_other_approxdate():
    """Verify inequality false to other approxdate."""
    d1 = ApproxDate.fromisoformat("1964-06-26")
    d2 = ApproxDate.fromisoformat("1964-06-26")
    assert d1 == d2


def test_equality_false_to_different_precision():
    """Verify equality false to different precision."""
    d1 = ApproxDate.fromisoformat("1964-06-26")
    d2 = ApproxDate.fromisoformat("1964-06")
    assert d1 != d2


def test_inequality_true_to_different_precision():
    """Verify inequality true to different precision."""
    d1 = ApproxDate.fromisoformat("1964-06-26")
    d2 = ApproxDate.fromisoformat("1964-06")
    assert d1 != d2


def test_equality_false_between_precise_and_date():
    """Verify equality false between precise and date."""
    approx_date = ApproxDate.fromisoformat("1964-06-26")
    datetime_date = date(1964, 6, 26)
    assert approx_date == datetime_date


def test_equality_false_between_precise_and_different_date():
    """Verify equality false between precise and different date."""
    approx_date = ApproxDate.fromisoformat("1964-06-26")
    datetime_date = date(1964, 6, 10)
    assert approx_date != datetime_date


def test_equality_false_between_imprecise_and_date_in_range():
    """Verify equality false between imprecise and date in range."""
    approx_date = ApproxDate.fromisoformat("1964-06")
    datetime_date = date(1964, 6, 26)
    assert approx_date != datetime_date


def test_equality_false_between_imprecise_and_date_out_of_range():
    """Verify equality false between imprecise and date out of range."""
    approx_date = ApproxDate.fromisoformat("1999")
    datetime_date = date(1964, 6, 26)
    assert approx_date != datetime_date


def test_fixed_date():
    """Verify fixed date."""
    assert FixedDate.PAST < FixedDate.FUTURE


def test_fixed_date_values():
    """Verify fixed date values."""
    assert FixedDate.PAST == date(1, 1, 1)
    assert FixedDate.FUTURE == date(9999, 12, 31)


def test_assert_fix_date_immutable():
    """Verify assert fix date immutable."""
    with pytest.raises(AttributeError):
        FixedDate.PAST = date(1, 1, 2)
    with pytest.raises(AttributeError):
        FixedDate.FUTURE = date(9999, 12, 30)
