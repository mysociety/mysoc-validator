"""
Structure for handling a transcript file.
"""

from __future__ import annotations

import datetime
from typing import (
    Annotated,
    Any,
    Iterator,
    Literal,
    NamedTuple,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
    runtime_checkable,
)

from pydantic import AliasChoices, Discriminator, Field, Tag

from .xml_base import (
    AsAttr,
    AsAttrSingle,
    BaseXMLModel,
    Items,
    MixedContent,
    StrictBaseXMLModel,
    TextStr,
)

T = TypeVar("T", bound=BaseXMLModel)

gid_pattern = r"^uk\.org\.publicwhip\/[a-z]+\/\d{4}-\d{2}-\d{2}[a-z]?\.\d+\.\d+"
agreement_gid_pattern = (
    r"uk\.org\.publicwhip\/[a-z]+\/\d{4}-\d{2}-\d{2}[a-z]?\.\d+\.\d+\.a\.\d+"
)
person_id_pattern = r"uk\.org\.publicwhip/person/\d+$"
GIDPattern = Annotated[str, Field(pattern=gid_pattern)]


@runtime_checkable
class HasText(Protocol):
    def as_str(self) -> str: ...

    @property
    def id(self) -> str: ...


class GIDRedirect(StrictBaseXMLModel, tags=["gidredirect"]):
    oldgid: GIDPattern
    newgid: GIDPattern
    matchtype: str


class OralHeading(StrictBaseXMLModel, tags=["oral-heading"]):
    id: GIDPattern
    nospeaker: str
    colnum: str
    time: str
    url: str
    content: MixedContent

    def as_str(self):
        return self.content.text


class MajorHeading(StrictBaseXMLModel, tags=["major-heading"]):
    id: GIDPattern
    nospeaker: Optional[str] = None
    colnum: Optional[str] = None
    time: Optional[str] = None
    url: str = ""
    content: MixedContent

    def as_str(self):
        return self.content.text


class MinorHeading(StrictBaseXMLModel, tags=["minor-heading"]):
    id: GIDPattern
    nospeaker: Optional[str] = None
    colnum: Optional[str] = None
    time: Optional[str] = None
    url: Optional[str] = None
    content: MixedContent

    def as_str(self):
        return self.content.text


class SpeechItem(StrictBaseXMLModel, tags=["speech.*"]):
    pid: Optional[str] = None
    qnum: Optional[str] = None
    class_: Optional[str] = Field(
        validation_alias="class", serialization_alias="class", default=None
    )
    pwmotiontext: Optional[str] = None
    content: MixedContent

    def as_str(self):
        return self.content.text


class Speech(StrictBaseXMLModel, tags=["speech"]):
    id: GIDPattern
    type: str = ""
    nospeaker: Optional[str] = None
    speakername: Optional[str] = None
    speech_type: Optional[str] = Field(
        validation_alias="speech", serialization_alias="speech", default=None
    )
    person_id: Optional[str] = Field(
        pattern=r"uk\.org\.publicwhip/person/\d+$", default=None
    )
    colnum: Optional[str] = None
    time: Optional[str] = None
    url: Optional[str] = None
    oral_qnum: Optional[str] = Field(
        validation_alias="oral-qnum", serialization_alias="oral-qnum", default=None
    )
    items: Items[SpeechItem]


class DivisionCount(StrictBaseXMLModel, tags=["divisioncount"]):
    content: Optional[int] = None
    not_content: Optional[int] = Field(
        default=None, validation_alias="not-content", serialization_alias="not-content"
    )
    ayes: Optional[int] = None
    noes: Optional[int] = None
    neutral: Optional[int] = None
    absent: Optional[int] = None


class MSPName(StrictBaseXMLModel, tags=["mspname"]):
    person_id: str = Field(
        validation_alias=AliasChoices("person_id", "id"),
        serialization_alias="id",
        pattern=person_id_pattern,
    )  # scotland uses id rather than person_id
    vote: str
    proxy: Optional[str] = None
    name: TextStr


class RepName(
    StrictBaseXMLModel, tags=["repname", "mpname", "msname", "mlaname", "lord"]
):
    person_id: str = Field(pattern=person_id_pattern)
    vote: str
    teller: Optional[str] = None
    proxy: Optional[str] = None
    name: TextStr


class RepList(
    StrictBaseXMLModel,
    tags=["replist", "mplist", "msplist", "mslist", "mlalist", "lordlist"],
):
    # this duplication is in the sources - twfy internally converts to
    # aye, no, both, absent
    vote: Literal[
        "aye",
        "no",
        "neutral",
        "content",
        "not-content",
        "for",
        "against",
        "spoiledvotes",
        "abstain",
        "absent",
        "abstentions",
        "didnotvote",
    ]
    items: Items[Union[MSPName, RepName]]


class Motion(StrictBaseXMLModel, tags=["motion"]):
    speech_id: GIDPattern
    motion_status: str
    content: MixedContent


class Agreement(StrictBaseXMLModel, tags=["agreement"]):
    agreement_id: str = Field(pattern=agreement_gid_pattern)
    speech_id: GIDPattern
    date: datetime.date
    agreementnumber: int
    nospeaker: bool = True
    rel_motions: AsAttr[list[Motion]] = []


class Division(StrictBaseXMLModel, tags=["division"]):
    id: str = Field(
        validation_alias=AliasChoices("id", "division_id"), pattern=gid_pattern
    )
    nospeaker: Optional[bool] = None
    date: str = Field(
        validation_alias=AliasChoices("divdate", "date"), serialization_alias="divdate"
    )
    divnumber: int
    colnum: Optional[int] = None
    time: Optional[str] = None
    count: AsAttrSingle[Optional[DivisionCount]]
    rel_motions: AsAttr[list[Motion]] = []
    representatives: Items[RepList]


def extract_tag(v: Any) -> str:
    return v["@tag"]


class HeaderSpeechTuple(NamedTuple):
    major_heading: Optional[MajorHeading]
    minor_heading: Optional[MinorHeading]
    speech: Speech
    speech_index: int


class Transcript(StrictBaseXMLModel, tags=["publicwhip"]):
    scraper_version: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("scraper_version", "scraperversion"),
        serialization_alias="scraperversion",
    )
    latest: Optional[str] = Field(default=None)
    items: Items[
        Annotated[
            Union[
                Annotated[Speech, Tag("speech")],
                Annotated[Division, Tag("division")],
                Annotated[GIDRedirect, Tag("gidredirect")],
                Annotated[OralHeading, Tag("oral-heading")],
                Annotated[MajorHeading, Tag("major-heading")],
                Annotated[MinorHeading, Tag("minor-heading")],
                Annotated[Agreement, Tag("agreement")],
            ],
            Discriminator(extract_tag),
        ]
    ]

    def iter_type(self, type: Type[T]) -> Iterator[T]:
        return (item for item in self.items if isinstance(item, type))

    def iter_speeches(self):
        return self.iter_type(Speech)

    def iter_headed_speeches(self) -> Iterator[HeaderSpeechTuple]:
        """
        Return a tuple covering the major heading, minor heading, speech
        and the speeches index within the current minor heading.
        """
        major_heading = None
        minor_heading = None
        speech_index = -1

        for item in self.items:
            if isinstance(item, MajorHeading):
                major_heading = item
                minor_heading = None
            elif isinstance(item, MinorHeading):
                minor_heading = item
                speech_index = -1
            elif isinstance(item, Speech):
                speech_index += 1
                yield HeaderSpeechTuple(
                    major_heading, minor_heading, item, speech_index
                )

    def iter_has_text(self) -> Iterator[HasText]:
        return (item for item in self.items if isinstance(item, HasText))
