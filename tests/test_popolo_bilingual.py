import json
from pathlib import Path
from typing import Literal, get_args

import pytest
from mysoc_validator.models.popolo import (
    Area,
    Membership,
    Organization,
    Person,
    Popolo,
    Post,
)
from mysoc_validator.models.popolo_extras import LocalisedLabelsExtra

SUPPLEMENTAL_POPOLO = {
    "organizations": [
        {
            "id": "senedd-committee-210781",
            "name": "Y Pwyllgor Cyllid / Finance Committee",
            "extra": {
                "localised_values": {
                    "name": {"en": "Finance Committee", "cy": "Y Pwyllgor Cyllid"}
                }
            },
            "classification": "committee",
        }
    ],
    "posts": [
        {
            "id": "senedd-committee-210781-chair",
            "organization_id": "senedd-committee-210781",
            "label": ("Cadeirydd y Pwyllgor Cyllid / Chair of the Finance Committee"),
            "role": "chair",
            "extra": {"localised_values": {"role": {"cy": "cadeirydd"}}},
        }
    ],
    "persons": [
        {
            "id": "uk.org.publicwhip/person/123",
            "other_names": [
                {"given_name": "Jane", "family_name": "Doe", "note": "Main"}
            ],
        }
    ],
    "memberships": [
        {
            "id": "senedd.wales/Committee/210781/Chair/123",
            "person_id": "uk.org.publicwhip/person/123",
            "post_id": "senedd-committee-210781-chair",
            "label": "Cadeirydd pwyllgor / Committee chair",
            "extra": {
                "localised_values": {
                    "label": {"en": "Committee chair", "cy": "Cadeirydd pwyllgor"}
                }
            },
        }
    ],
}


@pytest.mark.parametrize("model_type", [Membership, Organization, Person, Area, Post])
def test_extra_class_matches_extra_annotation(model_type):
    # Each concrete owner must declare its own `_extra_class`. Checking __dict__
    # specifically guards against accidentally relying on a mixin default, or
    # copy-pasting another model's declaration, where the wrong value would
    # still resolve via inheritance instead of failing loudly.
    assert "_extra_class" in model_type.__dict__

    # `ensure_extra` constructs `_extra_class` directly, so it must describe the
    # same type as the owner's declared Pydantic field.
    extra_annotation = model_type.model_fields["extra"].annotation
    concrete_extra_types = [
        candidate
        for candidate in get_args(extra_annotation)
        if candidate is not type(None)
    ]

    assert concrete_extra_types == [model_type._extra_class]


def test_supplemental_popolo_round_trips_without_changes(tmp_path: Path):
    # The complete bilingual fixture must retain its exact JSON representation.
    popolo = Popolo.model_validate(SUPPLEMENTAL_POPOLO)
    organization = popolo.organizations["senedd-committee-210781"]
    post = popolo.posts["senedd-committee-210781-chair"]
    membership = popolo.memberships["senedd.wales/Committee/210781/Chair/123"]

    assert organization.get_localised_value("name", "en") == "Finance Committee"
    assert organization.get_localised_value("name", "cy") == "Y Pwyllgor Cyllid"
    assert organization.classification == "committee"
    assert post.area is None
    assert post.role == "chair"
    assert post.get_localised_value("label", "en") == post.label
    assert post.get_localised_value("label", "cy") == post.label
    assert post.get_localised_value("role", "en") == post.role
    assert post.get_localised_value("role", "cy") == "cadeirydd"
    assert membership.organization_id is None
    assert membership.post_id == post.id
    assert membership.get_localised_value("label", "en") == "Committee chair"
    assert membership.get_localised_value("label", "cy") == "Cadeirydd pwyllgor"

    dumped = popolo.to_json_str()
    assert json.loads(dumped) == SUPPLEMENTAL_POPOLO
    assert Popolo.model_validate_json(dumped).to_json_str() == dumped

    path = tmp_path / "supplemental.json"
    popolo.to_path(path)
    assert Popolo.from_path(path).to_json_str() == dumped


def test_get_localised_value_rejects_field_not_on_model():
    # Getter calls must target a real field on the model.
    organization = Organization(id="body", name="Body")

    # A typo or unsupported field should fail instead of silently returning None.
    with pytest.raises(ValueError, match="Field label not found on Organization"):
        organization.get_localised_value("label", "en")  # type: ignore


def test_set_localised_value_creates_extra_when_missing():
    # Setter calls should safely create extra data when there is no extra to start
    organization = Organization(id="body", name="Corff / Body")

    assert organization.extra is None

    organization.set_localised_value("name", "cy", "Corff")

    assert organization.get_localised_value("name", "cy") == "Corff"
    assert organization.extra is not None
    assert organization.extra.localised_values == {"name": {"cy": "Corff"}}


def test_set_localised_value_uses_concrete_type_and_serializes_unset_defaults():
    # Start without extra to create  it through the values
    organization = Organization(id="body", name="Corff / Body")

    organization.set_localised_value("name", "cy", "Corff")
    organization.set_localised_value("name", "en", "Body")

    # Check we have the right concrete type for the generic LocalisedLabelsExtra.
    assert organization.extra is not None
    assert (
        type(organization.extra)
        is LocalisedLabelsExtra[Literal["name", "abstract", "description"]]
    )
    # Reassigning the updated dict must mark the field as explicitly set.
    # Otherwise excluded from to_path later on
    assert organization.extra.model_fields_set == {"localised_values"}
    assert organization.model_dump(exclude_unset=True)["extra"] == {
        "localised_values": {"name": {"cy": "Corff", "en": "Body"}}
    }


def test_set_localised_value_preserves_unknown_extra_and_replaces_value():
    # Setter calls should safely create and update one translation entry leaving any unknown extras in place.
    organization = Organization.model_validate(
        {
            "id": "body",
            "name": "Corff / Body",
            "extra": {"future_property": True},
        }
    )

    # Creating a translation must not overwrite the canonical value or unknown extras.
    organization.set_localised_value("name", "cy", "Corff")

    assert organization.get_localised_value("name", "cy") == "Corff"
    assert organization.name == "Corff / Body"
    assert organization.extra is not None
    assert organization.extra.model_extra == {"future_property": True}

    # Setting the same field and language again replaces it rather than duplicating it.
    organization.set_localised_value("name", "cy", "Y Corff")

    assert organization.get_localised_value("name", "cy") == "Y Corff"
    assert organization.extra.localised_values == {"name": {"cy": "Y Corff"}}


def test_set_localised_value_rejects_field_not_on_model():
    # Invalid setter calls must fail before changing the model.
    organization = Organization(id="body", name="Body")

    # The setter applies the same field guard as the getter.
    with pytest.raises(ValueError, match="Field label not found on Organization"):
        organization.set_localised_value("label", "cy", "Label")  # type: ignore

    # Validation happens before mutation, so a failed set does not create extra data.
    assert organization.extra is None


def test_localised_values_are_independent_per_field():
    # One language may translate multiple fields, each keeping its own entry.
    post = Post.model_validate(
        {
            "id": "bilingual-post",
            "organization_id": "bilingual-body",
            "label": "Cadeirydd / Chair",
            "role": "chair",
            "extra": {
                "localised_values": {
                    "label": {"en": "Chair"},
                    "role": {"en": "chairperson"},
                }
            },
        }
    )

    assert post.get_localised_value("label", "en") == "Chair"
    assert post.get_localised_value("role", "en") == "chairperson"
    assert post.get_localised_value("label", "cy") == post.label


def test_organization_abstract_and_description_are_localisable():
    organization = Organization.model_validate(
        {
            "id": "finance-committee",
            "name": "Y Pwyllgor Cyllid / Finance Committee",
            "abstract": "Pwyllgor ariannol / A finance committee",
            "description": "Disgrifiad hir / A longer description",
            "extra": {
                "localised_values": {
                    "abstract": {"en": "A finance committee"},
                    "description": {"cy": "Disgrifiad hir"},
                }
            },
        }
    )

    assert organization.get_localised_value("abstract", "en") == "A finance committee"
    assert organization.get_localised_value("abstract", "cy") == organization.abstract
    assert organization.get_localised_value("description", "cy") == "Disgrifiad hir"
