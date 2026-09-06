import json
from enum import auto

import pytest
from lxml import etree

from mysoc_validator.models.info import ConsInfo, InfoCollection, PersonInfo
from mysoc_validator.models.transcripts import (
    MajorHeading,
    MinorHeading,
    Speech,
    Transcript,
    extract_tag,
    seperate_out_msp,
)
from mysoc_validator.models.xml_base.xml_base import (
    extract_real_classes,
    str_from_xml_path,
)
from mysoc_validator.models.xml_base.xml_to_json import (
    array_overlap,
    dict_to_etree,
    get_inner_content,
    get_inner_content_str,
    json_to_xml,
    transfer_mixed_content,
    xml_to_json,
)
from mysoc_validator.utils.parlparse.enum_helpers import MiniEnum, StrEnum


def test_xml_conversion_preserves_attributes_children_and_mixed_content():
    """Verify xml conversion preserves attributes children and mixed content."""
    xml = '<root enabled="true"><item><name>A</name><body>Hello <b>x</b>!</body></item></root>'

    data = json.loads(
        xml_to_json(xml, tag_as_attr=["item.name"], mixed_content=["body"])
    )

    item = data["@children"][0]
    assert data["enabled"] == "true"
    assert item["@name"][0]["@text"] == "A"
    assert item["@children"][0]["@content"] == {
        "@raw": "Hello <b>x</b>!",
        "@text": "Hello x!",
    }
    rebuilt = json_to_xml(
        json.dumps(data), tag_as_attr=["item.name"], mixed_content=["body"]
    )
    assert (
        json.loads(
            xml_to_json(rebuilt, tag_as_attr=["item.name"], mixed_content=["body"])
        )
        == data
    )


def test_xml_helpers_handle_nested_content_and_tails():
    """Verify xml helpers handle nested content and tails."""
    source = etree.fromstring(
        b"<source>one <b role='x'>two <i>three</i></b> four</source>"
    )
    target = etree.Element("target")

    transfer_mixed_content(source, target)

    assert get_inner_content(source) == 'one <b role="x">two <i>three</i></b> four'
    assert get_inner_content_str(source) == "one two three four"
    assert get_inner_content_str(target) == "one two three four"
    assert array_overlap(["a", "b"], ["b", "c"])
    assert not array_overlap(["a"], ["c"])


def test_dict_to_etree_serializes_scalar_and_json_attributes():
    """Verify dict to etree serializes scalar and json attributes."""
    element = dict_to_etree(
        {
            "@tag": "item",
            "count": 2,
            "enabled": True,
            "metadata": {"a": 1},
            "@children": [{"@tag": "child", "@text": "value"}],
        }
    )

    assert element.attrib == {
        "count": "2",
        "enabled": "true",
        "metadata": '{"a": 1}',
    }
    assert element[0].text == "value"

    with pytest.raises(ValueError, match="Content should be a dictionary"):
        dict_to_etree({"@tag": "item", "@content": "bad"})
    with pytest.raises(ValueError, match="Text should be a string"):
        dict_to_etree({"@tag": "item", "@text": 3})


def test_xml_path_reader_defaults_to_utf8_without_encoding_declaration(tmp_path):
    """Verify xml path reader defaults to utf8 without encoding declaration."""
    path = tmp_path / "value.xml"
    path.write_text("<root>café</root>")
    assert str_from_xml_path(path) == "<root>café</root>"


def test_extract_real_classes_flattens_nested_annotations():
    """Verify extract real classes flattens nested annotations."""
    from typing import Annotated, Optional, Union

    assert extract_real_classes(Optional[list[Union[str, int]]]) == [
        str,
        int,
        type(None),
    ]
    assert extract_real_classes(Annotated[list[str], "metadata"]) == [str]


def test_generic_person_info_promotes_text_and_json_children():
    """Verify generic person info promotes text and json children."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<twfy><personinfo id="uk.org.publicwhip/person/1"><label>Ada</label><meta>{"active": true}</meta></personinfo></twfy>"""

    collection = InfoCollection[PersonInfo].model_validate_xml(xml).promote_children()
    person = collection.items[0]

    assert person.label == "Ada"  # type: ignore[attr-defined]
    assert person.meta == {"active": True}  # type: ignore[attr-defined]
    assert not hasattr(person, "@children")


def test_info_collection_mutation_iteration_and_parlparse_url(monkeypatch):
    """Verify info collection mutation iteration and parlparse url."""
    collection = InfoCollection[PersonInfo]()
    first = PersonInfo(person_id="uk.org.publicwhip/person/1")
    second = PersonInfo(person_id="uk.org.publicwhip/person/2")

    collection.append(first)
    collection.extend([second])

    assert list(collection) == [first, second]
    assert "items" in collection.model_fields_set

    captured = {}

    def fake_from_xml_url(cls, url):
        captured["url"] = url
        return collection

    monkeypatch.setattr(
        InfoCollection[PersonInfo], "from_xml_url", classmethod(fake_from_xml_url)
    )
    assert (
        InfoCollection[PersonInfo].from_parlparse("people", branch="feature")
        is collection
    )
    assert captured["url"].endswith("/feature/members/people.xml")


@pytest.mark.xfail(
    strict=True,
    reason="SNAGGING: InfoCollection.to_records iterates dict keys as key/value pairs",
)
def test_info_collection_exports_long_form_records():
    """Verify info collection exports long form records."""
    collection = InfoCollection[PersonInfo](
        items=[PersonInfo(person_id="uk.org.publicwhip/person/1", twitter="ada")]
    )
    assert collection.to_records() == [
        {
            "person_id": "uk.org.publicwhip/person/1",
            "key": "twitter",
            "value": "ada",
        }
    ]


def test_constituency_info_promotes_generic_children():
    """Verify constituency info promotes generic children."""
    item = ConsInfo.model_validate(
        {
            "canonical": "Example",
            "@children": [{"@tag": "url", "@text": "https://example.test"}],
        }
    )
    item.promote_children()
    assert item.url == "https://example.test"  # type: ignore[attr-defined]


def test_transcript_iterators_return_typed_and_heading_context():
    """Verify transcript iterators return typed and heading context."""
    transcript = Transcript(
        items=[
            MajorHeading(
                id="uk.org.publicwhip/debates/2020-01-01.1.h",
                content={"text": "Major", "raw": "Major"},
            ),
            MinorHeading(
                id="uk.org.publicwhip/debates/2020-01-01.2.h",
                content={"text": "Minor", "raw": "Minor"},
            ),
            Speech(id="uk.org.publicwhip/debates/2020-01-01.3.1", items=[]),
        ]
    )

    speeches = list(transcript.iter_speeches())
    typed = list(transcript.iter_type(MinorHeading))
    headed = list(transcript.iter_headed_speeches())

    assert all(isinstance(item, Speech) for item in speeches)
    assert typed and all(isinstance(item, MinorHeading) for item in typed)
    assert headed
    assert all(item.speech_index >= 0 for item in headed)
    assert any(isinstance(item, MajorHeading) for item in transcript.iter_has_text())


def test_transcript_discriminators_accept_dicts_and_models():
    """Verify transcript discriminators accept dicts and models."""
    heading = MajorHeading(
        id="uk.org.publicwhip/spwa/2020-01-01.1.h",
        content={"text": "Heading", "raw": "Heading"},
    )
    assert extract_tag({"@tag": "speech"}) == "speech"
    assert extract_tag(heading) == "major-heading"
    with pytest.raises(ValueError, match="Cannot extract tag"):
        extract_tag("speech")
    assert seperate_out_msp({"@tag": "mspname"}) == "msp"
    assert seperate_out_msp({"@tag": "mpname"}) == "rep"


class Colour(StrEnum):
    RED: str
    BLUE = auto()
    GREEN = "green"


class Numbers(MiniEnum[int]):
    ONE = 1
    TWO = 2
    LABEL = "ignored"


def test_typed_string_enum_and_minienum_behave_like_public_values():
    """Verify typed string enum and minienum behave like public values."""
    assert Colour.RED.value == "red"
    assert Colour.BLUE.value == "blue"
    assert str(Colour.GREEN) == "green"
    assert repr(Colour.GREEN) == "green".__repr__()
    assert list(Numbers.options()) == [1, 2]


def test_typed_string_enum_rejects_miscased_explicit_value():
    """Verify typed string enum rejects miscased explicit value."""
    with pytest.raises(ValueError, match="not lowercase version"):

        class Invalid(StrEnum):
            CAMEL = "Camel"
