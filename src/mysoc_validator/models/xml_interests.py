"""
Structure for handling the old-style XML register of interests
"""

from __future__ import annotations

from datetime import date
from typing import Literal as Literal
from typing import Optional

from pydantic import AliasChoices, Field

from .xml_base import AsAttrSingle, BaseXMLModel, Items, MixedContent


class Item(BaseXMLModel, tags=["item"]):
    item_class: Optional[str] = Field(
        validation_alias="class", serialization_alias="class", default=None
    )
    contents: MixedContent


class Record(BaseXMLModel, tags=["record"]):
    item_class: Optional[str] = Field(
        validation_alias="class", serialization_alias="class", default=None
    )
    items: Items[Item]


class Category(BaseXMLModel, tags=["category"]):
    type: str
    name: str
    records: Items[Record]


class PersonEntry(BaseXMLModel, tags=["regmem"]):
    person_id: str = Field(
        validation_alias=AliasChoices("person_id", "personid"),
        serialization_alias="personid",
        pattern=r"uk\.org\.publicwhip/person/\d+$",
    )
    memberid: Optional[str] = None
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


class Register(BaseXMLModel, tags=["twfy", "publicwhip"]):
    person_entries: Items[PersonEntry]
