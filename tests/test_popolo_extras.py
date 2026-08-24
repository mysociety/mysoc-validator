from datetime import date

import pytest
from mysoc_validator.models.popolo import (
    Area,
    Membership,
    MembershipExtra,
    Organization,
    Person,
    Post,
)

iso = date.fromisoformat

MINIMAL_KWARGS = {
    Membership: {
        "id": Membership.BLANK_ID,
        "person_id": "uk.org.publicwhip/person/1",
        "start_date": iso("2020-01-01"),
        "end_date": iso("2020-12-31"),
    },
    Organization: {"id": "body", "name": "Body"},
    Person: {"id": "uk.org.publicwhip/person/1"},
    Area: {"name": "Area"},
    Post: {"id": "post", "label": "Label", "organization_id": "body", "role": "role"},
}


@pytest.fixture(params=[Membership, Organization, Person, Area, Post])
def blank_model(request):
    # Every model with an ``extra`` field should support get_extra/set_extra
    # the same way, so exercise the operators across all of them from a
    # freshly constructed instance with no extra data set yet.
    model_type = request.param
    return model_type(**MINIMAL_KWARGS[model_type])


def test_get_extra_is_none_when_extra_unset(blank_model):
    assert blank_model.extra is None
    assert blank_model.get_extra("anything") is None


def test_set_extra_creates_extra_and_is_retrievable(blank_model):
    assert blank_model.extra is None

    blank_model.set_extra("note", "flagged")

    assert blank_model.extra is not None
    assert blank_model.get_extra("note") == "flagged"


def test_get_extra_returns_none_for_unset_key_on_existing_extra(blank_model):
    # extra being populated shouldn't make an unrelated key raise or fall back
    # to something other than None.
    blank_model.set_extra("note", "flagged")

    assert blank_model.get_extra("other") is None


def test_set_extra_is_chainable(blank_model):
    # set_extra returns self so callers can chain several assignments.
    result = blank_model.set_extra("a", 1).set_extra("b", 2)

    assert result is blank_model
    assert blank_model.get_extra("a") == 1
    assert blank_model.get_extra("b") == 2


class TaggedMembershipExtra(MembershipExtra):
    """
    A project-specific Extra subtype adding its own typed field, to
    demonstrate that consumers can subclass the named ``XExtra`` alias for
    consistent typing while still using the generic get_extra/set_extra
    operators.
    """

    tag: str = ""


def test_get_extra_reads_a_field_declared_on_a_membershipextra_subclass():
    membership = Membership(
        id=Membership.BLANK_ID,
        person_id="uk.org.publicwhip/person/1",
        start_date=iso("2020-01-01"),
        end_date=iso("2020-12-31"),
        extra=TaggedMembershipExtra(tag="whip-removed"),
    )

    assert membership.get_extra("tag") == "whip-removed"


def test_set_extra_updates_a_field_declared_on_a_membershipextra_subclass_in_place():
    membership = Membership(
        id=Membership.BLANK_ID,
        person_id="uk.org.publicwhip/person/1",
        start_date=iso("2020-01-01"),
        end_date=iso("2020-12-31"),
        extra=TaggedMembershipExtra(tag="whip-removed"),
    )

    membership.set_extra("tag", "whip-restored")

    assert membership.get_extra("tag") == "whip-restored"
    # set_extra mutates the existing instance rather than replacing it with a
    # plain MembershipExtra, so the concrete subclass - and any other fields
    # it declares - survive.
    assert isinstance(membership.extra, TaggedMembershipExtra)


def test_get_extra_as_reads_extra_data_into_a_project_specific_model():
    # extra was set generically (as it would be after parsing untyped JSON),
    # not constructed as a TaggedMembershipExtra directly - get_extra_as is
    # what lets a caller reinterpret it as one.
    membership = Membership(
        id=Membership.BLANK_ID,
        person_id="uk.org.publicwhip/person/1",
        start_date=iso("2020-01-01"),
        end_date=iso("2020-12-31"),
    )
    membership.set_extra("tag", "whip-removed")

    tagged = membership.get_extra_as(TaggedMembershipExtra)

    assert isinstance(tagged, TaggedMembershipExtra)
    assert tagged.tag == "whip-removed"


def test_get_extra_as_is_none_when_extra_unset(blank_model):
    assert blank_model.get_extra_as(TaggedMembershipExtra) is None
