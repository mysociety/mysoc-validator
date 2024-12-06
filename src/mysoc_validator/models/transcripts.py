"""
Structure for handling a transcript file.
"""

from __future__ import annotations

import datetime
from typing import (
    Annotated,
    Any,
    ClassVar,
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

from ..utils.parlparse.downloader import get_latest_for_date
from .consts import TranscriptType as TranscriptType
from .popolo import Chamber as Chamber
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

gid_pattern = (
    r"^uk\.org\.publicwhip\/[a-z]+(\/(en|cy))?\/\d{4}-\d{2}-\d{2}[a-z]?\.\d+\.\d+"
)
agreement_gid_pattern = (
    r"uk\.org\.publicwhip\/[a-z]+\/\d{4}-\d{2}-\d{2}[a-z]?\.\d+\.\d+\.a\.\d+"
)
person_or_member_id_pattern = r"(uk\.org\.publicwhip/(person|member)/\d+$|unknown$)"
member_id_pattern = r"(uk\.org\.publicwhip/member/\d+$|unknown$)"
GIDPattern = Annotated[str, Field(pattern=gid_pattern)]


@runtime_checkable
class HasText(Protocol):
    def __str__(self) -> str: ...

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

    def __str__(self):
        return self.content.text


class MajorHeading(StrictBaseXMLModel, tags=["major-heading"]):
    id: GIDPattern
    nospeaker: Optional[str] = None
    colnum: Optional[str] = None
    time: Optional[str] = None
    url: str = ""
    content: MixedContent

    def __str__(self):
        return self.content.text


class MinorHeading(StrictBaseXMLModel, tags=["minor-heading"]):
    id: GIDPattern
    nospeaker: Optional[str] = None
    colnum: Optional[str] = None
    time: Optional[str] = None
    url: Optional[str] = None
    content: MixedContent

    def __str__(self):
        return self.content.text


class SpeechItem(StrictBaseXMLModel, tags=["speech.*"]):
    pid: Optional[str] = None
    qnum: Optional[str] = None
    class_: Optional[str] = Field(
        validation_alias="class", serialization_alias="class", default=None
    )
    pwmotiontext: Optional[str] = None
    content: MixedContent

    def __str__(self):
        return self.content.text


class Speech(StrictBaseXMLModel, tags=["speech"]):
    id: GIDPattern
    type: str = ""
    nospeaker: Optional[str] = None
    speakername: Optional[str] = None
    speakeroffice: Optional[str] = None
    error: Optional[str] = None
    speech_type: Optional[str] = Field(
        validation_alias="speech", serialization_alias="speech", default=None
    )
    person_id: Optional[str] = Field(pattern=person_or_member_id_pattern, default=None)
    member_id: Optional[Annotated[str, Field(pattern=member_id_pattern)]] = Field(
        validation_alias=AliasChoices("speakerid"),
        serialization_alias="speakerid",
        pattern=member_id_pattern,
        default=None,
    )
    colnum: Optional[str] = None
    time: Optional[str] = None
    url: Optional[str] = None
    oral_qnum: Optional[str] = Field(
        validation_alias="oral-qnum", serialization_alias="oral-qnum", default=None
    )
    original_lang: Optional[str] = None
    items: Items[SpeechItem]


class DivisionCount(StrictBaseXMLModel, tags=["divisioncount"]):
    content: Optional[int] = None
    not_content: Optional[int] = Field(
        default=None, validation_alias="not-content", serialization_alias="not-content"
    )
    ayes: Optional[int] = Field(
        validation_alias=AliasChoices("ayes", "for"), default=None
    )
    noes: Optional[int] = Field(
        validation_alias=AliasChoices("noes", "against"), default=None
    )
    neutral: Optional[int] = Field(
        validation_alias=AliasChoices("neutral", "abstentions"), default=None
    )
    absent: Optional[int] = Field(validation_alias=AliasChoices("absent"), default=None)
    spoiled: Optional[int] = Field(
        validation_alias=AliasChoices("spoiledvotes"),
        serialization_alias="spoiledvotes",
        default=None,
    )
    tellerayes: Optional[int] = None
    tellernoes: Optional[int] = None


class MSPName(StrictBaseXMLModel, tags=["mspname"]):
    person_id: str = Field(
        validation_alias=AliasChoices("person_id", "id"),
        serialization_alias="id",
        pattern=person_or_member_id_pattern,
    )  # scotland uses id rather than person_id
    vote: str
    proxy: Optional[str] = None
    name: TextStr


class RepName(
    StrictBaseXMLModel, tags=["repname", "mpname", "msname", "mlaname", "lord"]
):
    person_id: Optional[str] = Field(pattern=person_or_member_id_pattern, default=None)
    member_id: Optional[str] = Field(
        validation_alias=AliasChoices("id"),
        serialization_alias="id",
        pattern=member_id_pattern,
        default=None,
    )
    vote: str
    teller: Optional[str] = None
    proxy: Optional[str] = None
    name: TextStr


def seperate_out_msp(value: Any) -> str:
    if value["@tag"] == "mspname":
        return "msp"
    return "rep"


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
    items: Items[
        Annotated[
            Union[Annotated[MSPName, Tag("msp")], Annotated[RepName, Tag("rep")]],
            Discriminator(seperate_out_msp),
        ]
    ] = Field(
        validation_alias=AliasChoices("items", "@children"),
        serialization_alias="@children",
        default_factory=list,
    )


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
    id: str = Field(validation_alias=AliasChoices("id", "division_id"))
    nospeaker: Optional[bool] = None
    date: str = Field(
        validation_alias=AliasChoices("divdate", "date"), serialization_alias="divdate"
    )
    divnumber: int
    colnum: Optional[int] = None
    time: Optional[str] = None
    url: Optional[str] = None
    count: AsAttrSingle[Optional[DivisionCount]]
    rel_motions: AsAttr[list[Motion]] = []
    representatives: Items[RepList]


def extract_tag(v: Any) -> str:
    if isinstance(v, dict):
        return v["@tag"]  # type: ignore
    elif hasattr(v, "tag"):
        return v.tag
    else:
        raise ValueError(f"Cannot extract tag from {v}")


class HeaderSpeechTuple(NamedTuple):
    major_heading: Optional[MajorHeading]
    minor_heading: Optional[MinorHeading]
    speech: Speech
    speech_index: int


class Transcript(StrictBaseXMLModel, tags=["publicwhip"]):
    Chamber: ClassVar[Type[Chamber]] = Chamber
    TranscriptType: ClassVar[Type[TranscriptType]] = TranscriptType
    scraper_version: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "scraper_version", "scraperversion", "scrapeversion"
        ),
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

    @classmethod
    def from_parlparse(
        cls,
        date: datetime.date,
        chamber: Chamber = Chamber.COMMONS,
        transcript_type: TranscriptType = TranscriptType.DEBATES,
    ) -> Transcript:
        file_path = get_latest_for_date(
            date, chamber=chamber, transcript_type=transcript_type
        )
        return cls.from_xml_path(file_path)

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
