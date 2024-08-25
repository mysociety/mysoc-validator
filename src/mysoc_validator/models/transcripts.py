from __future__ import annotations

from typing import (
    Annotated,
    Any,
    Iterator,
    Literal,
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
    BaseXMLModel,
    Items,
    MixedContent,
    StrictBaseXMLModel,
    TextStr,
)

T = TypeVar("T", bound=BaseXMLModel)


@runtime_checkable
class HasText(Protocol):
    def as_str(self) -> str: ...

    @property
    def id(self) -> str: ...


class GIDRedirect(StrictBaseXMLModel, tags=["gidredirect"]):
    oldgid: str
    newgid: str
    matchtype: str


class OralHeading(StrictBaseXMLModel, tags=["oral-heading"]):
    id: str
    nospeaker: str
    colnum: str
    time: str
    url: str
    content: MixedContent

    def as_str(self):
        return self.content.text


class MajorHeading(StrictBaseXMLModel, tags=["major-heading"]):
    id: str
    nospeaker: Optional[str] = None
    colnum: Optional[str] = None
    time: Optional[str] = None
    url: str = ""
    content: MixedContent

    def as_str(self):
        return self.content.text


class MinorHeading(StrictBaseXMLModel, tags=["minor-heading"]):
    id: str
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
    id: str
    type: str = ""
    nospeaker: Optional[str] = None
    speakername: Optional[str] = None
    speech_type: Optional[str] = Field(
        validation_alias="speech", serialization_alias="speech", default=None
    )
    person_id: Optional[str] = None
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
        validation_alias=AliasChoices("person_id", "id"), serialization_alias="id"
    )  # scotland uses id rather than person_id
    vote: str
    proxy: Optional[str] = None
    name: TextStr


class RepName(
    StrictBaseXMLModel, tags=["repname", "mpname", "msname", "mlaname", "lord"]
):
    person_id: str
    vote: str
    teller: Optional[str] = None
    proxy: Optional[str] = None
    name: TextStr


class RepList(
    StrictBaseXMLModel,
    tags=["replist", "mplist", "msplist", "mslist", "mlalist", "lordlist"],
):
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
    speech_id: str
    content: MixedContent


class Agreement(StrictBaseXMLModel, tags=["agreement"]):
    speech_id: str
    nospeaker: Optional[bool] = True
    motion: Optional[Motion] = None


class Division(StrictBaseXMLModel, tags=["division"]):
    id: str = Field(validation_alias=AliasChoices("id", "division_id"))
    nospeaker: Optional[bool] = None
    divdate: str
    divnumber: int
    colnum: Optional[int] = None
    time: Optional[str] = None
    count: AsAttr[Optional[DivisionCount]]
    motion: Optional[Motion] = None
    items: Items[RepList]


def extract_tag(v: Any) -> str:
    return v["@tag"]


class Transcript(StrictBaseXMLModel, tags=["publicwhip"]):
    scraper_version: Optional[str] = Field(
        default=None, validation_alias="scraperversion"
    )
    latest: Optional[str] = Field(default=None, validation_alias="latest")
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

    def iter_has_text(self) -> Iterator[HasText]:
        return (item for item in self.items if isinstance(item, HasText))
