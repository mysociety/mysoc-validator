from typing import Optional

import pytest
from mysoc_validator import ConsInfo, InfoCollection, PersonInfo
from mysoc_validator.models.xml_base import AsAttrStr, XMLDict
from pydantic import ValidationError


class SocialInfo(PersonInfo):
    facebook_page: Optional[str] = None
    twitter_username: Optional[str] = None
    bluesky_handle: Optional[str] = None


class SocialInfoMissingField(PersonInfo):
    twitter_username: Optional[str] = None


class DemoDataModel(PersonInfo):
    regmem_info: XMLDict
    random_string: AsAttrStr


def test_person_info_validates():
    info = InfoCollection[PersonInfo].from_parlparse("social-media-commons")
    assert len(info.items) > 0


def test_subclassed_info_validates():
    info = InfoCollection[SocialInfo].from_parlparse("social-media-commons")
    assert len(info.items) > 0


def test_subclassed_info_missing_field():
    with pytest.raises(ValidationError):
        InfoCollection[SocialInfoMissingField].from_parlparse("social-media-commons")


def test_cons_info_validates():
    info = InfoCollection[ConsInfo].from_parlparse("constituency-links")
    assert len(info.items) > 0


example_xml_data = """
<?xml version="1.0" encoding="UTF-8"?>
<twfy>
  <personinfo id="uk.org.publicwhip/person/10001">
    <regmem_info>{"hello": ["yes", "no"]}</regmem_info>
    <random_string>banana</random_string>
  </personinfo>
</twfy>
"""


def test_attr_xml():
    item = DemoDataModel(
        person_id="uk.org.publicwhip/person/10001",
        regmem_info={"hello": ["yes", "no"]},
        random_string="banana",
    )

    items = InfoCollection[DemoDataModel](items=[item])

    xml_data = items.model_dump_xml()
    json_data = items.model_dump_json()

    # Which looks like

    assert xml_data.strip() == example_xml_data.strip()

    reread = InfoCollection[DemoDataModel].model_validate_xml(xml_data)
    new_json_data = reread.model_dump_json()
    assert json_data == new_json_data

    # which can either be round-triped in the same model - or read by the generic model like this

    generic_read = (
        InfoCollection[PersonInfo].model_validate_xml(xml_data).promote_children()
    )

    assert generic_read.items[0].random_string == "banana"  # type: ignore
