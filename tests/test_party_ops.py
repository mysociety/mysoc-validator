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

    popolo.change_party(person, "conservative", change_date=today)
    last_membership = person.memberships()[-1]
    assert last_membership.on_behalf_of_id == "conservative"

    popolo.remove_whip(person, change_date=today + timedelta(days=1))
    last_membership = person.memberships()[-1]
    assert last_membership.on_behalf_of_id == "independent"

    popolo.restore_whip(person, change_date=today + timedelta(days=2))
    last_membership = person.memberships()[-1]
    assert last_membership.on_behalf_of_id == "conservative"


