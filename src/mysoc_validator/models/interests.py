"""
Structure for handling a register of interests
"""

from __future__ import annotations

from datetime import date
from typing import Literal as Literal
from typing import Optional

from pydantic import AliasChoices, Field

from .xml_base import AsAttrSingle, Items, MixedContent, StrictBaseXMLModel


class Item(StrictBaseXMLModel, tags=["item"]):
    item_class: str = Field(validation_alias="class", serialization_alias="class")
    contents: MixedContent


class Record(StrictBaseXMLModel, tags=["record"]):
    item_class: Optional[str] = Field(
        validation_alias="class", serialization_alias="class", default=None
    )
    items: Items[Item]


class Category(StrictBaseXMLModel, tags=["category"]):
    type: str
    name: str
    records: Items[Record]


class PersonEntry(StrictBaseXMLModel, tags=["regmem"]):
    person_id: str = Field(
        validation_alias=AliasChoices("person_id", "personid"),
        serialization_alias="personid",
        pattern=r"uk\.org\.publicwhip/person/\d+$",
    )
    membername: str
    date: date
    record: AsAttrSingle[Optional[Record]] = Field(
        default=None,
        validation_alias=AliasChoices("record", "@record"),
        serialization_alias="@record",
    )
    categories: Items[Category] = Field(
        default_factory=list,
        validation_alias=AliasChoices("categories", "@children"),
        serialization_alias="@children",
    )


class Register(StrictBaseXMLModel, tags=["twfy", "publicwhip"]):
    person_entries: Items[PersonEntry]
