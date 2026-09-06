from datetime import date, timedelta

import pytest

from mysoc_validator.models.dates import ApproxDate, FixedDate


def test_date_ranges_parse_and_round_trip_their_source_precision():
    """Verify date ranges parse and round trip their source precision."""
    value = ApproxDate.fromisoformat("2020-02/2021")

    assert value.earliest_date == date(2020, 2, 1)
    assert value.latest_date == date(2021, 12, 31)
    assert value.isoformat() == "2020-02-01/2021-12-31"
    assert str(value) == value.isoformat()
    assert repr(value) == "ApproxDate.fromisoformat(2020-02-01/2021-12-31)"


def test_approx_date_arithmetic_shifts_both_bounds():
    """Verify approx date arithmetic shifts both bounds."""
    original = ApproxDate.fromisoformat("2020-02")
    shifted = original + timedelta(days=2)

    assert shifted.earliest_date == date(2020, 2, 3)
    assert shifted.latest_date == date(2020, 3, 2)
    with pytest.raises(NotImplementedError):
        original + 1


def test_approx_date_ordering_only_succeeds_for_non_overlapping_ranges():
    """Verify approx date ordering only succeeds for non overlapping ranges."""
    january = ApproxDate.fromisoformat("2020-01")
    february = ApproxDate.fromisoformat("2020-02")

    assert january < february
    assert february > january
    assert january <= date(2020, 2, 1)
    assert february >= date(2020, 1, 31)
    with pytest.raises(NotImplementedError):
        january < "2020-02"
    with pytest.raises(NotImplementedError):
        january > "2020-02"


def test_possibly_between_uses_uncertain_outer_bounds():
    """Verify possibly between uses uncertain outer bounds."""
    assert ApproxDate.possibly_between(
        ApproxDate.fromisoformat("2020"),
        date(2020, 6, 1),
        ApproxDate.fromisoformat("2021"),
    )
    assert not ApproxDate.possibly_between(
        date(2020, 1, 1), date(2019, 12, 31), date(2020, 12, 31)
    )


def test_fixed_dates_reject_instance_mutation_apis():
    """Verify fixed dates reject instance mutation apis."""
    with pytest.raises(AttributeError, match="Cannot modify"):
        FixedDate.PAST.extra = 1
    with pytest.raises(AttributeError, match="Cannot delete"):
        del FixedDate.PAST.extra
    with pytest.raises(AttributeError, match="Cannot modify"):
        FixedDate.PAST.replace(year=2)
