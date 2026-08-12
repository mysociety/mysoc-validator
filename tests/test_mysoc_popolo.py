import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests
from mysoc_validator.models.dates import FixedDate
from mysoc_validator.models.popolo import (
    Chamber,
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


def test_non_spec_extra_accessors_round_trip():
    popolo = Popolo.model_validate(
        {
            "organizations": [
                {
                    "id": "body",
                    "name": "Body",
                    "extra": {"upstream_reference": "external/body/1"},
                }
            ]
        }
    )
    organization = popolo.organizations["body"]
    assert organization.extra is not None

    assert organization.extra["upstream_reference"] == "external/body/1"

    organization.extra["sync_metadata"] = {
        "source": "example",
        "revision": 2,
    }
    assert organization.extra["sync_metadata"] == {
        "source": "example",
        "revision": 2,
    }

    dumped = popolo.to_json_str()
    restored = Popolo.model_validate_json(dumped)
    restored_extra = restored.organizations["body"].extra

    assert restored_extra is not None
    assert restored_extra["upstream_reference"] == "external/body/1"
    assert restored_extra["sync_metadata"] == {"source": "example", "revision": 2}
    assert restored.to_json_str() == dumped


def test_organization_supports_supplemental_details():
    organization_data = {
        "id": "finance-committee",
        "name": "Finance Committee",
        "abstract": "A finance committee",
        "description": "A longer description",
        "founding_date": "2021-05",
        "dissolution_date": "2026-04-06",
        "links": ["https://example.com/finance-committee"],
        "parent_id": "welsh-parliament",
    }

    organization = Organization.model_validate(organization_data)

    assert organization.model_dump(mode="json", exclude_unset=True) == organization_data


def test_organization_supplemental_details_are_optional():
    organization = Organization(id="body", name="Body")

    assert organization.abstract is None
    assert organization.description is None
    assert organization.founding_date is None
    assert organization.dissolution_date is None
    assert organization.links == []
    assert organization.parent_id is None
    assert organization.model_dump(exclude_unset=True) == {"id": "body", "name": "Body"}


def test_organization_parent_id_is_cross_checked():
    valid = Popolo.model_validate(
        {
            "organizations": [
                {"id": "parent", "name": "Parent"},
                {"id": "child", "name": "Child", "parent_id": "parent"},
            ]
        }
    )
    assert valid.organizations["child"].parent_id == "parent"

    missing_parent_data = {
        "organizations": [
            {"id": "child", "name": "Child", "parent_id": "missing-parent"}
        ]
    }
    with pytest.raises(
        ValueError,
        match=(
            "Organization child refers to invalid parent organization missing-parent"
        ),
    ):
        Popolo.model_validate(missing_parent_data)

    # check that we can skip cross-checks if we want to
    partial = Popolo.model_validate(
        missing_parent_data, context={"skip_cross_checks": True}
    )
    assert partial.organizations["child"].parent_id == "missing-parent"


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
