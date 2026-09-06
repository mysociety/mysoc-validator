import datetime
from decimal import Decimal

import pytest

from mysoc_validator.models.consts import Chamber
from mysoc_validator.models.interests import (
    CommonKey,
    RegmemAnnotation,
    RegmemCategory,
    RegmemDetail,
    RegmemDetailContainer,
    RegmemDetailGroup,
    RegmemEntry,
    RegmemPerson,
    RegmemRegister,
    slugify,
)


def test_slugify_produces_stable_machine_keys():
    """Verify slugify produces stable machine keys."""
    assert slugify("  Company  Name! (UK) ") == "company_name_uk"


@pytest.mark.parametrize(
    ("value", "expected_type"),
    [
        ("text", "string"),
        (True, "boolean"),
        (3, "int"),
        (datetime.date(2024, 1, 2), "date"),
        (1.5, "float"),
        (Decimal("1.50"), "decimal"),
    ],
)
def test_detail_infers_metadata_from_python_value(value, expected_type):
    """Verify detail infers metadata from python value."""
    detail = RegmemDetail[type(value)](display_as="Display Name", value=value)

    assert detail.slug == "display_name"
    assert detail.type == expected_type


def test_detail_infers_display_name_and_exposes_plain_value():
    """Verify detail infers display name and exposes plain value."""
    detail = RegmemDetail[str](slug="registered_address", value="Cardiff")

    assert detail.display_as == "Registered Address"
    assert detail.dict_value() == "Cardiff"
    assert detail.sub_detail_groups == []
    assert list(detail.iter_sub_details()) == []


def test_container_details_flatten_and_iterate_nested_groups():
    """Verify container details flatten and iterate nested groups."""
    nested = RegmemDetailGroup(
        root=[
            RegmemDetail[str](slug="destination", value="Oslo"),
            RegmemDetail[Decimal](slug="cost", value=Decimal("12.50")),
        ]
    )
    container = RegmemDetailContainer(slug="trips", value=[nested])

    assert container.dict_value() == [{"destination": "Oslo", "cost": Decimal("12.50")}]
    assert [detail.slug for detail in container.iter_sub_details()] == [
        "destination",
        "cost",
    ]


def test_detail_group_append_extend_and_source_override():
    """Verify detail group append extend and source override."""
    group = RegmemDetailGroup()
    first = RegmemDetail[str](slug="one", value="1")
    second = RegmemDetail[int](slug="two", value=2)

    group.append(first, source="manual")
    group.extend([second], source="imported")

    assert len(group) == 2
    assert group[0].source == "manual"
    assert group[1].source == "imported"
    assert group.detail_dict() == {"one": "1", "two": 2}


def test_duplicate_detail_append_is_atomic():
    """Verify duplicate detail append is atomic."""
    group = RegmemDetailGroup(root=[RegmemDetail[str](slug="name", value="first")])

    with pytest.raises(ValueError, match="Duplicate detail names"):
        group.append(RegmemDetail[str](slug="name", value="second"))

    assert group.detail_dict() == {"name": "first"}


def test_parameterized_detail_lookup_supports_serialized_types():
    """Verify parameterized detail lookup supports serialized types."""
    assert (
        RegmemDetail.parameterized_class_from_str("date") == RegmemDetail[datetime.date]
    )
    assert (
        RegmemDetail.parameterized_class_from_str("container")
        == RegmemDetail[list[RegmemDetailGroup]]
    )


def test_entry_adds_scalar_details_without_optional_dataframe_dependency():
    """Verify entry adds scalar details without optional dataframe dependency."""
    entry = RegmemEntry(id="entry-1", content="Trip", date_registered="2024-01-02")
    entry.add_details(
        source="researcher",
        employer="Example Ltd",
        amount=Decimal("42.00"),
    )
    assert entry.get_detail_value("employer") == "Example Ltd"


def test_entry_details_can_be_found_by_each_public_key():
    """Verify entry details can be found by each public key."""
    entry = RegmemEntry(id="entry-1", content="Trip", date_registered="2024-01-02")
    entry.details.extend(
        [
            RegmemDetail[str](
                slug="employer", value="Example Ltd", source="researcher"
            ),
            RegmemDetail[Decimal](
                slug="amount", value=Decimal("42.00"), source="researcher"
            ),
            RegmemDetail[str](
                slug="company_number",
                display_as="Company number",
                common_key=CommonKey.COMPANIES_HOUSE,
                value="1234",
            ),
        ]
    )

    assert entry.get_detail("employer").source == "researcher"  # type: ignore[union-attr]
    assert entry.get_detail("Company number").value == "1234"  # type: ignore[union-attr]
    assert entry.get_detail(CommonKey.COMPANIES_HOUSE).slug == "company_number"  # type: ignore[union-attr]
    assert entry.get_detail_value("amount") == Decimal("42.00")
    assert entry.get_detail_value("missing") is None
    assert entry.details_dict() == {
        "id": "entry-1",
        "content": "Trip",
        "date_registered": "2024-01-02",
        "employer": "Example Ltd",
        "amount": Decimal("42.00"),
        "company_number": "1234",
    }


def test_entry_reduces_nested_detail_columns():
    """Verify entry reduces nested detail columns."""
    rows = [
        RegmemDetailGroup(
            root=[
                RegmemDetail[str](slug="name", value="A"),
                RegmemDetail[int](slug="amount", value=1),
            ]
        ),
        RegmemDetailGroup(
            root=[
                RegmemDetail[str](slug="name", value="B"),
                RegmemDetail[int](slug="amount", value=2),
            ]
        ),
    ]
    entry = RegmemEntry(
        content="Payments",
        details=RegmemDetailGroup(
            root=[RegmemDetailContainer(slug="payments", value=rows)]
        ),
    )

    details = entry.details_dict(reduce={"payments": ["name", "amount"]})

    assert details["name"] == ["A", "B"]
    assert details["amount"] == [1, 2]
    assert "payments" not in details


def test_hash_id_is_stable_and_tracks_nested_content():
    """Verify hash id is stable and tracks nested content."""
    entry = RegmemEntry(content="Parent", sub_entries=[RegmemEntry(content="Child")])
    original = entry.comparable_id

    assert original == entry.item_hash
    assert len(original) == 10
    entry.sub_entries[0].content = "Changed"
    assert entry.comparable_id != original


def _register():
    child = RegmemEntry(id="child", info_type="subentry", content="Child")
    entry = RegmemEntry(id="parent", content="Parent", sub_entries=[child])
    category = RegmemCategory(
        category_id="1", category_name="Employment", entries=[entry]
    )
    person = RegmemPerson(
        person_id="uk.org.publicwhip/person/1",
        person_name="Ada Example",
        published_date=datetime.date(2024, 1, 1),
        chamber=Chamber.COMMONS,
        categories=[category],
    )
    return RegmemRegister(
        chamber=Chamber.COMMONS,
        published_date=datetime.date(2024, 1, 1),
        persons=[person],
    )


def test_register_navigation_preserves_parent_context():
    """Verify register navigation preserves parent context."""
    register = _register()
    person = register.get_person_from_id("uk.org.publicwhip/person/1")
    category = person.get_category_from_id("1")

    assert [entry.id for entry in category.entries_and_subentries()] == [
        "parent",
        "child",
    ]
    rows = list(register.iter_entries())
    assert rows[0].parent_entry is None
    assert rows[1].parent_entry is rows[0].entry

    with pytest.raises(ValueError, match="Category missing not found"):
        person.get_category_from_id("missing")
    with pytest.raises(ValueError, match="Person missing not found"):
        register.get_person_from_id("missing")


def test_register_compact_and_full_file_round_trips(tmp_path):
    """Verify register compact and full file round trips."""
    register = _register()
    compact = tmp_path / "compact.json"
    full = tmp_path / "full.json"

    register.to_path(compact)
    register.to_path(full, full=True)

    assert RegmemRegister.from_path(compact) == register
    assert RegmemRegister.from_path(full) == register
    assert len(full.read_text()) > len(compact.read_text())


def test_annotation_defaults_to_creation_date():
    """Verify annotation defaults to creation date."""
    annotation = RegmemAnnotation(author="editor", content="Checked")
    assert annotation.date_added == datetime.date.today()
