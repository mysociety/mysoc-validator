import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests
from mysoc_validator.models.dates import FixedDate
from mysoc_validator.models.popolo import (
    Chamber,
    LordName,
    Membership,
    MembershipRedirect,
    Organization,
    Person,
    PersonRedirect,
    Popolo,
    Post,
)

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


def test_lookup_lord_full_title(popolo_data: Popolo):
    # Lord Allan of Hallam — full peerage title lookup
    person = popolo_data.persons.from_name(
        "Lord Allan of Hallam", chamber_id=Chamber.LORDS, date=iso("2024-01-01")
    )
    assert person is not None
    assert person.id == "uk.org.publicwhip/person/10007"


def test_lookup_lord_no_lordname(popolo_data: Popolo):
    # Bishops have no lordname; transcripts use several forms inconsistently
    for name in [
        "Bishop of Norwich",  # simple form seen in some transcripts
        "The Bishop of Norwich",  # with "The" prefix
        "The Lord Bishop of Norwich",  # formal Lords chamber style
    ]:
        person = popolo_data.persons.from_name(
            name, chamber_id=Chamber.LORDS, date=iso("2010-01-01")
        )
        assert person is not None, f"Failed to find person for {name!r}"
        assert person.id == "uk.org.publicwhip/person/12844"

    # Earls without a lordname also appear with and without "The"
    for name in ["Earl of Sandwich", "The Earl of Sandwich"]:
        person = popolo_data.persons.from_name(
            name, chamber_id=Chamber.LORDS, date=iso("2010-01-01")
        )
        assert person is not None, f"Failed to find person for {name!r}"
        assert person.id == "uk.org.publicwhip/person/13633"


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


def test_round_trip():
    branch = "master"
    parlparse_url = f"https://raw.githubusercontent.com/mysociety/parlparse/{branch}/members/people.json"

    # don't need to be consistent on final whitespace
    original_text = requests.get(parlparse_url).text.strip()
    popolo = Popolo.model_validate_json(original_text)
    dumped_text = popolo.to_json_str()
    popolo2 = Popolo.model_validate_json(dumped_text)
    dumped_text2 = popolo2.to_json_str()
    assert dumped_text == dumped_text2, "Internal round trip failed"
    assert original_text == dumped_text, "External round trip failed"


def test_write_popolo(popolo_data: Popolo):
    with tempfile.TemporaryDirectory() as temp_dir:
        data_dir = Path(temp_dir, "data")
        data_dir.mkdir()
        dest = Path(data_dir, "people_test_dump.json")
        popolo_data.to_path(dest)
        assert dest.exists()
        Popolo.from_path(dest)  # test reimport parses ok
        dest.unlink()
        data_dir.rmdir()


def test_lord_name_surname_without_lord_style_rejected():
    """A bare surname isn't a valid Lords name - it needs a lordname, or a
    lordofname paired with an honorific_prefix, to build a peerage-style name."""
    with pytest.raises(ValueError, match="also needs a lordname"):
        LordName(note="Main", surname="Smith", honorific_prefix="Baron")

    # surname with lordofname but no honorific_prefix is still not enough
    with pytest.raises(ValueError, match="also needs a lordname"):
        LordName(
            note="Main", surname="Smith", lordofname="Somewhere", honorific_prefix=""
        )


def test_lord_name_surname_with_lord_style_accepted():
    """A surname is fine alongside a lordname, or alongside a lordofname and
    honorific_prefix."""
    LordName(
        note="Main",
        surname="Smith",
        lordname="Smith of Somewhere",
        honorific_prefix="Baron",
    )
    LordName(
        note="Main",
        surname="Smith",
        lordofname="Somewhere",
        honorific_prefix="Baron",
    )


def test_duplicate_person_rejected(popolo_data: Popolo):
    """Appending a Person with an already-existing ID should raise ValueError."""
    dup = Person(id="uk.org.publicwhip/person/10001")
    with pytest.raises(ValueError, match="Duplicate Person id"):
        popolo_data.persons.append(dup)


def test_duplicate_person_redirect_rejected(popolo_data: Popolo):
    """Appending a PersonRedirect whose ID already exists in the list should raise ValueError."""
    # person/10001 already exists as a Person entry
    dup = PersonRedirect(
        id="uk.org.publicwhip/person/10001",
        redirect="uk.org.publicwhip/person/10002",
    )
    with pytest.raises(ValueError, match="Duplicate PersonRedirect id"):
        popolo_data.persons.append(dup)


def test_duplicate_post_rejected(popolo_data: Popolo):
    """Appending a Post with an already-existing ID should raise ValueError."""
    existing: Post = popolo_data.posts.root[0]
    dup = existing.model_copy()
    with pytest.raises(ValueError, match="Duplicate Post id"):
        popolo_data.posts.append(dup)


def test_duplicate_organization_rejected(popolo_data: Popolo):
    """Appending an Organization with an already-existing ID should raise ValueError."""
    dup = Organization(id="house-of-commons", name="Duplicate")
    with pytest.raises(ValueError, match="Duplicate Organization id"):
        popolo_data.organizations.append(dup)


def test_duplicate_membership_redirect_rejected(popolo_data: Popolo):
    """Appending a MembershipRedirect whose ID already exists should raise ValueError."""
    redirects = popolo_data.memberships.redirects()
    if not redirects:
        pytest.skip("No membership redirects in data")
    existing = redirects[0]
    dup = MembershipRedirect(id=existing.id, redirect=existing.redirect)
    with pytest.raises(ValueError, match="Duplicate MembershipRedirect id"):
        popolo_data.memberships.append(dup)
