from datetime import date, timedelta
from pathlib import Path

import pytest
from mysoc_validator.models.dates import FixedDate
from mysoc_validator.models.popolo import Chamber, Membership, Popolo

iso = date.fromisoformat


@pytest.fixture(scope="session")
def popolo_data():
    return Popolo.from_parlparse()


def test_lookup_from_id(popolo_data: Popolo):
    person = popolo_data.persons["uk.org.publicwhip/person/10001"]
    assert "Diane Abbott" in person.names_on_date(date=iso("2024-07-31"))


def test_lookup_from_identifer(popolo_data: Popolo):
    person = popolo_data.persons.from_identifier("172", scheme="datadotparl_id")
    assert "Diane Abbott" in person.names_on_date(date=iso("2024-07-31"))


def test_lookup_from_name(popolo_data: Popolo):
    person = popolo_data.persons.from_name(
        "Elizabeth Truss", chamber_id=Chamber.COMMONS, date=iso("2022-07-31")
    )
    assert person is not None
    assert person.id == "uk.org.publicwhip/person/24941"


def test_valid_addition(popolo_data: Popolo):
    person = popolo_data.persons["uk.org.publicwhip/person/10001"]
    last_membership = person.memberships()[-1]
    if last_membership.end_date == FixedDate.FUTURE:
        # cap membership
        last_membership.end_date = last_membership.start_date + timedelta(days=1)
    new_start_date = last_membership.end_date + timedelta(days=1)
    new_end_date = new_start_date + timedelta(days=365)
    new_membership = Membership(
        id="uk.org.publicwhip/member/122323232",
        person_id=person.id,
        start_date=new_start_date,
        end_date=new_end_date,
        organization_id="labour",
        post_id=last_membership.post_id,
    )
    popolo_data.memberships.extend([new_membership])
    assert popolo_data.memberships.root[-1].id == "uk.org.publicwhip/member/122323232"


def test_invalid_overlapping_memberhsip(popolo_data: Popolo):
    person = popolo_data.persons["uk.org.publicwhip/person/10001"]
    last_membership = person.memberships()[-1]
    new_membership = Membership(
        id="uk.org.publicwhip/member/122323232",
        person_id=person.id,
        start_date=last_membership.start_date,
        end_date=last_membership.end_date,
        organization_id="labour",
        post_id=last_membership.post_id,
    )
    with pytest.raises(ValueError):
        popolo_data.memberships.extend([new_membership])


def add_invalid_membership_duplicate_id(popolo_data: Popolo):
    person = popolo_data.persons["uk.org.publicwhip/person/10001"]
    new_membership = Membership(
        id="uk.org.publicwhip/member/10001",
        person_id=person.id,
        start_date=iso("2022-01-01"),
        end_date=iso("2024-01-01"),
        organization_id="conservative",
    )
    with pytest.raises(ValueError):
        popolo_data.memberships.extend([new_membership])


def add_invalid_membership_bad_id_format(popolo_data: Popolo):
    new_membership = Membership(
        id="uk.org.publicwhip/personmembership/10001",
        person_id="uk.org.publicwhip/person/34343243",
        start_date=iso("2022-01-01"),
        end_date=iso("2024-01-01"),
        organization_id="conservative",
    )
    with pytest.raises(ValueError):
        popolo_data.memberships.extend([new_membership])


def add_invalid_membership_not_a_person(popolo_data: Popolo):
    new_membership = Membership(
        id="uk.org.publicwhip/member/10001",
        person_id="uk.org.publicwhip/person/34343243",
        start_date=iso("2022-01-01"),
        end_date=iso("2024-01-01"),
        organization_id="conservative",
    )
    with pytest.raises(ValueError):
        popolo_data.memberships.extend([new_membership])


def test_write_popolo(popolo_data: Popolo):
    dest = Path("data", "people_test_dump.json")
    popolo_data.to_path(dest)
    assert dest.exists()
    Popolo.from_path(dest)  # test reimport parses ok
    dest.unlink()


def test_true_is_true():
    assert True is True
