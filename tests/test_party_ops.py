from datetime import date, timedelta

from mysoc_validator import Popolo

iso = date.fromisoformat

# this needs to be a current labour person
test_person = "uk.org.publicwhip/person/10001"
today = date.today()


def test_change_party():
    popolo = Popolo.from_parlparse()

    person = popolo.persons["uk.org.publicwhip/person/10001"]
    last_membership = person.memberships()[-1]
    assert last_membership.on_behalf_of_id == "labour"

    person.change_party(popolo.organizations["conservative"], change_date=today)
    last_membership = person.memberships()[-1]
    assert last_membership.on_behalf_of_id == "conservative"

    person.remove_whip(change_date=today + timedelta(days=1))
    last_membership = person.memberships()[-1]
    assert last_membership.on_behalf_of_id == "independent"

    person.restore_whip(change_date=today + timedelta(days=2))
    last_membership = person.memberships()[-1]
    assert last_membership.on_behalf_of_id == "conservative"
