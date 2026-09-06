import json
from datetime import date
from types import SimpleNamespace

import pytest

from mysoc_validator.models.consts import Chamber, MembershipReason
from mysoc_validator.models.dates import FixedDate
from mysoc_validator.models.popolo import (
    AltName,
    BasicPersonName,
    IndexedList,
    LordName,
    Membership,
    Organization,
    Person,
    Popolo,
    Post,
    escape_unicode_characters,
    reduce_to_slug,
)


def _minimal_popolo():
    return Popolo.model_validate(
        {
            "organizations": [
                {"id": "house-of-commons", "name": "Commons"},
                {"id": "labour", "name": "Labour", "classification": "party"},
                {
                    "id": "independent",
                    "name": "Independent",
                    "classification": "party",
                },
            ],
            "posts": [
                {
                    "id": "uk.org.publicwhip/cons/1",
                    "label": "Example",
                    "organization_id": "house-of-commons",
                    "role": "MP",
                }
            ],
            "persons": [
                {
                    "id": "uk.org.publicwhip/person/1",
                    "identifiers": [{"scheme": "external", "identifier": "old"}],
                    "other_names": [
                        {
                            "given_name": "Ada",
                            "family_name": "Example",
                            "note": "Main",
                            "start_date": "2020-01-01",
                        }
                    ],
                }
            ],
            "memberships": [
                {
                    "id": "uk.org.publicwhip/member/1",
                    "person_id": "uk.org.publicwhip/person/1",
                    "organization_id": "house-of-commons",
                    "on_behalf_of_id": "labour",
                    "post_id": "uk.org.publicwhip/cons/1",
                    "role": "MP",
                    "start_date": "2020-01-01",
                }
            ],
        }
    )


def test_text_helpers_make_expected_output_forms():
    """Verify text helpers make expected output forms."""
    assert reduce_to_slug("D'Arcy-McGee") == "darcymcgee"
    assert escape_unicode_characters("café\n") == "caf\\u00e9\n"


def test_name_models_expose_human_and_matching_variants():
    """Verify name models expose human and matching variants."""
    basic = BasicPersonName(family_name="Example", given_name="Ada", note="Main")
    alt = AltName(name="A. Example", note="Alternate")
    bishop = LordName(
        honorific_prefix="Bishop",
        lordofname="Norwich",
        surname="Smith",
        given_name="Ada",
        note="Main",
    )

    assert basic.nice_name() == "Ada Example"
    assert alt.nice_name() == "A. Example"
    assert bishop.nice_name() == "Bishop of Norwich"
    assert bishop.original_full_name() == "Ada Smith"
    assert bishop.name_variants(include_original_name=True) == [
        "Bishop of Norwich",
        "The Bishop of Norwich",
        "The Lord Bishop of Norwich",
        "Ada Smith",
    ]


def test_person_identifier_add_replace_and_if_missing_semantics():
    """Verify person identifier add replace and if missing semantics."""
    person = _minimal_popolo().persons["uk.org.publicwhip/person/1"]

    assert person.get_identifier("external") == "old"
    assert (
        person.add_identifer(scheme="external", identifier="old", if_missing=True)
        is False
    )
    assert person.add_identifer(scheme="external", identifier="new") is True
    assert person.get_identifier("external") == "new"
    assert str(person.identifiers.first()) == "external:new"


def test_person_navigation_resolves_membership_post_and_organizations():
    """Verify person navigation resolves membership post and organizations."""
    popolo = _minimal_popolo()
    person = popolo.persons["uk.org.publicwhip/person/1"]
    membership = person.memberships()[0]

    assert person.reduced_id() == "1"
    assert membership.person() is person
    assert membership.post() is popolo.posts["uk.org.publicwhip/cons/1"]
    assert membership.organization() is popolo.organizations["house-of-commons"]
    assert membership.on_behalf_of() is popolo.organizations["labour"]
    assert membership.post().organization() is popolo.organizations["house-of-commons"]  # type: ignore[union-attr]
    assert (
        person.membership_on_date(date(2022, 1, 1), chamber=Chamber.COMMONS)
        is membership
    )
    assert person.latest_membership(Chamber.COMMONS) is membership


def test_add_membership_assigns_chamber_range_id_and_is_queryable():
    """Verify add membership assigns chamber range id and is queryable."""
    popolo = _minimal_popolo()
    person = popolo.persons["uk.org.publicwhip/person/1"]
    current = person.memberships()[0]
    current.end_date = date(2022, 1, 1)

    person.add_membership(
        Chamber.COMMONS,
        "MP",
        date(2022, 1, 2),
        post_id="uk.org.publicwhip/cons/1",
        on_behalf_of_id="labour",
        start_reason=MembershipReason.ELECTION,
    )

    added = person.memberships()[-1]
    assert added.id == "uk.org.publicwhip/member/2"
    assert added.start_reason == MembershipReason.ELECTION


def test_organization_closes_only_open_memberships():
    """Verify organization closes only open memberships."""
    popolo = _minimal_popolo()
    organization = popolo.organizations["house-of-commons"]

    assert (
        organization.close_open_memberships(
            date(2024, 5, 30), MembershipReason.DISSOLUTION
        )
        is organization
    )
    membership = popolo.memberships.first()
    assert membership.end_date == date(2024, 5, 30)
    assert membership.end_reason == MembershipReason.DISSOLUTION

    with pytest.raises(ValueError, match="no parent Popolo"):
        Organization(id="orphan", name="Orphan").close_open_memberships(
            date.today(), "closed"
        )


def test_person_name_change_closes_previous_name_the_day_before():
    """Verify person name change closes previous name the day before."""
    person = _minimal_popolo().persons["uk.org.publicwhip/person/1"]
    person.change_main_name("Augusta", "King", date(2024, 1, 10))

    assert person.get_main_name(date(2024, 1, 9)).nice_name() == "Ada Example"  # type: ignore[union-attr]
    assert person.get_main_name(date(2024, 1, 10)).nice_name() == "Augusta King"  # type: ignore[union-attr]


def test_end_membership_records_date_and_reason():
    """Verify end membership records date and reason."""
    person = _minimal_popolo().persons["uk.org.publicwhip/person/1"]
    person.end_membership_with_reason(date(2024, 5, 30), MembershipReason.DISSOLUTION)
    membership = person.memberships()[-1]
    assert membership.end_date == date(2024, 5, 30)
    assert membership.end_reason == MembershipReason.DISSOLUTION


def test_indexed_list_lookups_and_custom_indexes_are_cached_and_invalidated():
    """Verify indexed list lookups and custom indexes are cached and invalidated."""
    popolo = _minimal_popolo()
    organizations = popolo.organizations

    assert organizations.get_matching_index("id", "labour") == 1
    assert organizations.get_matching_values("name", "Labour") == [
        organizations["labour"]
    ]
    assert organizations.get("missing") is None
    with pytest.raises(ValueError, match="No item"):
        organizations.get_matching_index("name", "Missing")
    with pytest.raises(ValueError, match="Multiple items"):
        organizations.get_matching_index("classification", "party")

    organizations.append(Organization(id="green", name="Green"))
    assert organizations["green"].parent_popolo is popolo
    assert str(organizations["green"]) == "<Popolo.Organization: green>"


def test_indexed_list_contains_returns_false_for_missing_ids():
    """Verify indexed list contains returns false for missing ids."""
    assert "missing" not in _minimal_popolo().organizations


def test_indexed_list_pop_keeps_lookup_indexes_consistent():
    """Verify indexed list pop keeps lookup indexes consistent."""
    organizations = _minimal_popolo().organizations
    assert organizations["labour"].name == "Labour"  # populate id cache
    removed = organizations.pop("house-of-commons")
    assert removed.id == "house-of-commons"
    assert organizations["labour"].name == "Labour"


@pytest.mark.xfail(
    strict=True,
    reason="SNAGGING: ModelInList.delete uses the identifier value as an attribute name",
)
def test_model_delete_removes_itself_from_parent_collection():
    """Verify model delete removes itself from parent collection."""
    popolo = _minimal_popolo()
    popolo.organizations["labour"].delete()
    assert popolo.organizations.get("labour") is None


@pytest.mark.xfail(
    strict=True,
    reason="SNAGGING: one-part alternate names are appended twice",
)
def test_one_part_alt_name_is_added_once():
    """Verify one part alt name is added once."""
    person = Person(id="uk.org.publicwhip/person/2")
    person.add_alt_name(one_name="Banksy")
    assert [name.nice_name() for name in person.names] == ["Banksy"]


@pytest.mark.xfail(
    strict=True,
    reason="SNAGGING: empty integer-indexed collections do not initialize ID state",
)
def test_empty_integer_indexed_list_can_allocate_first_id():
    """Verify empty integer indexed list can allocate first id."""
    items = IndexedList[Membership]()
    assert items.get_unassigned_id(start=10, end=20) == 11


def test_popolo_update_and_multi_file_load_merge_fragments(tmp_path):
    """Verify popolo update and multi file load merge fragments."""
    base = _minimal_popolo()
    extra = Popolo.model_validate({"organizations": [{"id": "green", "name": "Green"}]})
    assert base.update(extra) is base
    assert base.organizations["green"].name == "Green"

    base_path = tmp_path / "base.json"
    extra_path = tmp_path / "extra.json"
    _minimal_popolo().to_path(base_path)
    extra.to_path(extra_path)
    loaded = Popolo.from_path([base_path, extra_path])
    assert loaded.organizations["green"].name == "Green"


def test_popolo_url_and_parlparse_loaders_merge_and_construct_urls(monkeypatch):
    """Verify popolo url and parlparse loaders merge and construct urls."""
    base = _minimal_popolo().to_json_str()
    extra = Popolo.model_validate(
        {"organizations": [{"id": "green", "name": "Green"}]}
    ).to_json_str()
    responses = iter([SimpleNamespace(text=base), SimpleNamespace(text=extra)])
    monkeypatch.setattr(
        "mysoc_validator.models.popolo.requests.get", lambda url: next(responses)
    )
    assert Popolo.from_url(["base", "extra"]).organizations["green"].name == "Green"

    captured = {}

    def fake_from_url(cls, urls, cross_validate=True):
        captured["urls"] = urls
        return _minimal_popolo()

    monkeypatch.setattr(Popolo, "from_url", classmethod(fake_from_url))
    Popolo.from_parlparse(extras=["ministers", "special.json"], branch="feature")
    assert captured["urls"] == [
        "https://raw.githubusercontent.com/mysociety/parlparse/feature/members/people.json",
        "https://raw.githubusercontent.com/mysociety/parlparse/feature/members/ministers.json",
        "https://raw.githubusercontent.com/mysociety/parlparse/feature/members/special.json",
    ]


def test_popolo_json_output_omits_default_dates_and_escapes_unicode():
    """Verify popolo json output omits default dates and escapes unicode."""
    popolo = _minimal_popolo()
    output = popolo.to_json_str()
    parsed = json.loads(output)

    name = parsed["persons"][0]["other_names"][0]
    membership = parsed["memberships"][0]
    assert "end_date" not in name
    assert "end_date" not in membership
    assert Popolo.from_json_str(output).to_json_str() == output


def test_orphan_relationship_helpers_report_missing_parent():
    """Verify orphan relationship helpers report missing parent."""
    person = Person(id="uk.org.publicwhip/person/9")
    post = Post(id="post", label="Post", organization_id="house-of-commons", role="MP")
    membership = Membership(
        id="uk.org.publicwhip/member/9",
        person_id=person.id,
        start_date=date(2020, 1, 1),
    )

    with pytest.raises(ValueError, match="no parent Popolo"):
        person.memberships()
    with pytest.raises(ValueError, match="no parent Popolo"):
        post.organization()
    assert membership.person() is None
    assert membership.post() is None
    assert membership.organization() is None
    assert membership.on_behalf_of() is None
    assert membership.end_date == FixedDate.FUTURE
