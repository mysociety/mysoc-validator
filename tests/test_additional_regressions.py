from datetime import date

import pytest

from mysoc_validator.models.interests import RegmemDetailGroup
from mysoc_validator.models.popolo import (
    LordName,
    Membership,
    Person,
    Popolo,
)


def test_untyped_boolean_interest_detail_preserves_boolean_type():
    """Verify untyped boolean interest detail preserves boolean type."""
    group = RegmemDetailGroup.model_validate([{"slug": "flag", "value": True}])
    detail = group.root[0]
    assert detail.value is True
    assert detail.type == "boolean"


def test_merge_people_moves_names_and_identifiers_and_installs_redirect():
    """Verify merge people moves names and identifiers and installs redirect."""
    popolo = Popolo.model_validate(
        {
            "persons": [
                {
                    "id": "uk.org.publicwhip/person/1",
                    "identifiers": [{"scheme": "one", "identifier": "1"}],
                },
                {
                    "id": "uk.org.publicwhip/person/2",
                    "identifiers": [{"scheme": "two", "identifier": "2"}],
                    "other_names": [
                        {
                            "given_name": "Second",
                            "family_name": "Person",
                            "note": "Main",
                        }
                    ],
                },
            ]
        }
    )

    popolo.persons.merge_people(
        "uk.org.publicwhip/person/1", "uk.org.publicwhip/person/2"
    )

    merged = popolo.persons["uk.org.publicwhip/person/1"]
    assert merged.get_identifier("two") == "2"
    assert "Second Person" in merged.all_name_variants()
    assert popolo.persons["uk.org.publicwhip/person/2"] is merged


def test_person_can_transition_from_common_name_to_peerage_name():
    """Verify person can transition from common name to peerage name."""
    person = Person.model_validate(
        {
            "id": "uk.org.publicwhip/person/1",
            "other_names": [
                {
                    "given_name": "Ada",
                    "family_name": "Example",
                    "note": "Main",
                    "start_date": "2020-01-01",
                }
            ],
        }
    )

    person.change_main_name_to_lord(
        given_name="Ada",
        county="Example",
        honorific_prefix="Baroness",
        lordname="Example",
        lordofname_full="of Example in the County of Example",
        change_date=date(2024, 1, 10),
    )

    assert person.get_main_name(date(2024, 1, 9)).nice_name() == "Ada Example"  # type: ignore[union-attr]
    peerage = person.get_main_name(date(2024, 1, 10))
    assert isinstance(peerage, LordName)
    assert peerage.nice_name() == "Baroness Example"


def test_alt_name_requires_either_complete_parts_or_one_name():
    """Verify alt name requires either complete parts or one name."""
    person = Person(id="uk.org.publicwhip/person/1")
    with pytest.raises(ValueError, match="Both given and last"):
        person.add_alt_name(given_name="Ada")
    with pytest.raises(ValueError, match="Either one_name"):
        person.add_alt_name()


def test_person_and_membership_redirects_resolve_transparently():
    """Verify person and membership redirects resolve transparently."""
    popolo = Popolo.model_validate(
        {
            "persons": [
                {"id": "uk.org.publicwhip/person/1"},
                {
                    "id": "uk.org.publicwhip/person/2",
                    "redirect": "uk.org.publicwhip/person/1",
                },
            ],
            "memberships": [
                {
                    "id": "uk.org.publicwhip/member/1",
                    "person_id": "uk.org.publicwhip/person/1",
                    "start_date": "2020-01-01",
                },
                {
                    "id": "uk.org.publicwhip/member/2",
                    "redirect": "uk.org.publicwhip/member/1",
                },
            ],
        }
    )

    assert (
        popolo.persons["uk.org.publicwhip/person/2"]
        is popolo.persons["uk.org.publicwhip/person/1"]
    )
    assert (
        popolo.memberships["uk.org.publicwhip/member/2"]
        is popolo.memberships["uk.org.publicwhip/member/1"]
    )
    assert len(popolo.persons.redirects()) == 1
    assert len(popolo.memberships.redirects()) == 1


def test_blank_membership_requires_a_post_to_choose_an_id_range():
    """Verify blank membership requires a post to choose an id range."""
    membership = Membership(
        id=Membership.BLANK_ID,
        person_id="uk.org.publicwhip/person/1",
        start_date=date(2020, 1, 1),
    )
    with pytest.raises(ValueError, match="No parent set"):
        membership.get_unassigned_id()
