from datetime import date, timedelta
from typing import Optional

from .dates import FixedDate
from .popolo import Chamber, Membership, Person, PersonRedirect, Popolo


def add_membership(
    popolo: Popolo,
    person_id: str | Person,
    organization_id: Chamber,
    role: str,
    start_date: date,
    end_date: date = FixedDate.FUTURE,
    post_id: str = "",
    on_behalf_of_id: str = "",
    start_reason: str = "",
    end_reason: str = "",
) -> Popolo:
    """
    Add a membership to a person.
    """
    if isinstance(person_id, Person):
        if person_id.parent is None:
            raise ValueError("Person has no parent Popolo object")
        person = person_id
    else:
        person = popolo.persons[person_id].self_or_redirect()

    membership = Membership(
        id=Membership.BLANK_ID,
        person_id=person.id,
        organization_id=organization_id,
        role=role,
        start_date=start_date,
        end_date=end_date,
        post_id=post_id,
        on_behalf_of_id=on_behalf_of_id,
        start_reason=start_reason,
        end_reason=end_reason,
    )
    popolo.memberships.append(membership)
    return popolo


def merge_people(popolo: Popolo, person1_id: str, person2_id: str) -> Popolo:
    """
    Merge two people into one - absorb memberships and names - remove person 2 id and add a PersonRedirect

    Need to create concept of person redirect
    """

    person1 = popolo.persons[person1_id]
    person2 = popolo.persons[person2_id]

    if person1 == person2:
        return popolo

    for n in person2.names:
        n.note = "Alternate"

    old_names = [str(x) for x in person1.names]
    person_2_names = [x for x in person2.names if str(x) not in old_names]

    person1.names.extend(person_2_names)

    old_identifiers = [str(x) for x in person1.identifiers]
    person_2_identifiers = [
        x for x in person2.identifiers if str(x) not in old_identifiers
    ]

    person2.identifiers.extend(person_2_identifiers)

    for m in person2.memberships():
        m.person_id = person1.id

    popolo.persons.pop(person2.id)
    popolo.persons.append(PersonRedirect(id=person2.id, redirect=person1.id))

    return popolo


def end_body(
    popolo: Popolo, body_id: Chamber, end_date: date, end_reason: str
) -> Popolo:
    """
    Close all open memberships for a body.
    """
    for membership in popolo.memberships.get_matching_values(
        "organization_id", body_id
    ):
        if isinstance(membership, Membership):
            if membership.end_date == FixedDate.FUTURE:
                membership.end_date = end_date
                membership.end_reason = end_reason
    return popolo


def end_with_reason(
    popolo: Popolo,
    person_id: str | Person,
    end_date: date,
    end_reason: str,
) -> Popolo:
    """
    End the most recent membership for a person - record reason.
    """
    if isinstance(person_id, Person):
        if person_id.parent is None:
            raise ValueError("Person has no parent Popolo object")
        person = person_id
    else:
        person = popolo.persons[person_id].self_or_redirect()
    last_membership = person.memberships()[-1]
    last_membership.end_date = end_date
    last_membership.end_reason = end_reason
    return popolo


def change_party(
    popolo: Popolo,
    person_id: str | Person,
    new_party_id: str,
    change_date: Optional[date] = None,
    change_reason: str = "",
) -> Popolo:
    """
    Change the party of a person - close old membership and create new one.
    """
    if change_date is None:
        change_date = date.today()

    if isinstance(person_id, Person):
        if person_id.parent is None:
            raise ValueError("Person has no parent Popolo object")
        person = person_id
    else:
        person = popolo.persons[person_id].self_or_redirect()
    last_membership = person.memberships()[-1]
    last_membership.end_date = change_date
    last_membership.end_reason = change_reason

    new_membership = Membership(
        id=Membership.BLANK_ID,
        person_id=person.id,
        start_date=change_date + timedelta(days=1),
        end_date=FixedDate.FUTURE,
        organization_id=last_membership.organization_id,
        on_behalf_of_id=new_party_id,
        post_id=last_membership.post_id,
        start_reason=change_reason,
    )
    popolo.memberships.append(new_membership)
    return popolo
