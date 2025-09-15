from datetime import date, timedelta

from mysoc_validator import Popolo
from mysoc_validator.models.popolo import Chamber
from mysoc_validator.models.consts import MembershipReason

iso = date.fromisoformat

# this needs to be a current labour person
test_person = "uk.org.publicwhip/person/10001"
today = date.today()


def test_add_alt_name():
    popolo = Popolo.from_parlparse()
    person = popolo.persons["uk.org.publicwhip/person/10001"]
    person.add_alt_name(one_name="D Abbott")
    found_person = popolo.persons.from_name(
        "D Abbott", chamber_id=Chamber.COMMONS, date=iso("2022-07-31")
    )
    assert found_person and found_person.id == "uk.org.publicwhip/person/10001"


def test_change_name():
    popolo = Popolo.from_parlparse()
    person = popolo.persons["uk.org.publicwhip/person/10001"]
    person.change_main_name(
        given_name="Diane", family_name="Test Abbott", change_date=iso("2022-07-31")
    )
    new_name = person.get_main_name()
    assert new_name is not None
    assert new_name.family_name == "Test Abbott"  # type: ignore
    found_person = popolo.persons.from_name(
        "Diane Test Abbott", chamber_id=Chamber.COMMONS, date=iso("2022-07-31")
    )
    assert found_person and found_person.id == "uk.org.publicwhip/person/10001"


def test_change_party():
    popolo = Popolo.from_parlparse()

    person = popolo.persons["uk.org.publicwhip/person/25034"]
    last_membership = person.memberships()[-1]
    assert last_membership.on_behalf_of_id == "labour"

    person.change_party(
        popolo.organizations["conservative"],
        change_date=today,
        source_url="http://example.com",
    )
    last_membership = person.memberships()[-1]
    assert last_membership.on_behalf_of_id == "conservative"
    assert last_membership.start_reason == MembershipReason.CHANGED_PARTY
    assert last_membership.source == "http://example.com"

    person.remove_whip(
        change_date=today + timedelta(days=1), source_url="http://example.com/remove"
    )
    last_membership = person.memberships()[-1]
    assert last_membership.on_behalf_of_id == "independent"
    assert last_membership.start_reason == MembershipReason.WHIP_REMOVED
    assert last_membership.source == "http://example.com/remove"

    person.restore_whip(
        change_date=today + timedelta(days=2), source_url="http://example.com/restore"
    )
    last_membership = person.memberships()[-1]
    assert last_membership.on_behalf_of_id == "conservative"
    assert last_membership.start_reason == MembershipReason.WHIP_RESTORED
    assert last_membership.source == "http://example.com/restore"
