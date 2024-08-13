from __future__ import annotations

from typing import (
    Annotated,
    Iterator,
    Literal,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
    runtime_checkable,
)

from pydantic import AliasChoices, Field

from .xml_base import BaseXMLModel, XmlTypeMetaData

T = TypeVar("T", bound=BaseXMLModel)
StrItemContents = Annotated[str, XmlTypeMetaData.ItemContents]
StrItemContentsReadOnly = Annotated[
    str, XmlTypeMetaData.ItemContents, XmlTypeMetaData.ReadOnly
]
XMLItemContents = Annotated[str, XmlTypeMetaData.XMLItemContents]
StrXMLTag = Annotated[str, XmlTypeMetaData.XMLTag]


@runtime_checkable
class HasText(Protocol):
    def as_str(self) -> str: ...

    @property
    def id(self) -> str: ...


class GIDRedirect(BaseXMLModel, tag="gidredirect"):
    oldgid: str
    newgid: str
    matchtype: str


class OralHeading(BaseXMLModel, tag="oral-heading"):
    id: str
    nospeaker: str
    colnum: str
    time: str
    url: str
    text: StrItemContents

    def as_str(self):
        return self.text


class MajorHeading(BaseXMLModel, tag="major-heading"):
    id: str
    nospeaker: Optional[str] = None
    colnum: Optional[str] = None
    time: Optional[str] = None
    url: str = ""
    text: StrItemContents

    def as_str(self):
        return self.text


class MinorHeading(BaseXMLModel, tag="minor-heading"):
    id: str
    nospeaker: Optional[str] = None
    colnum: Optional[str] = None
    time: Optional[str] = None
    url: Optional[str] = None
    text: StrItemContents

    def as_str(self):
        return self.text


class SpeechItem(BaseXMLModel, tag="*"):
    tag: StrXMLTag
    pid: Optional[str] = None
    qnum: Optional[str] = None
    contents_xml: XMLItemContents
    contents_text: StrItemContentsReadOnly
    class_: Optional[str] = Field(
        validation_alias="class", serialization_alias="class", default=None
    )
    pwmotiontext: Optional[str] = None


class Speech(BaseXMLModel, tag="speech"):
    id: str
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
    items: list[SpeechItem]

    def as_str(self):
        return "\n".join(item.contents_text for item in self.items)


class DivisionCount(BaseXMLModel, tag="divisioncount"):
    content: Optional[int] = None
    not_content: Optional[int] = Field(
        default=None, validation_alias="not-content", serialization_alias="not-content"
    )
    ayes: Optional[int] = None
    noes: Optional[int] = None
    neutral: Optional[int] = None
    absent: Optional[int] = None


class RepName(BaseXMLModel, tag=["mpname", "mspname", "msname", "mlaname", "lord"]):
    tag: StrXMLTag
    person_id: str = Field(
        validation_alias=AliasChoices("person_id", "id")
    )  # scotland uses id rather than person_id
    vote: str
    proxy: Optional[str] = None
    name: StrItemContents


class RepList(BaseXMLModel, tag=["mplist", "msplist", "mslist", "mlalist", "lordlist"]):
    tag: StrXMLTag
    vote: Literal[
        "aye",
        "no",
        "absent",
        "neutral",
        "content",
        "not-content",
        "for",
        "against",
        "abstentions",
        "spoiledvotes",
        "abstain",
        "didnotvote",
    ]
    items: list[RepName]


class Motion(BaseXMLModel, tag="motion"):
    speech_id: str
    text: StrItemContents


class Agreement(BaseXMLModel, tag="agreement"):
    speech_id: str
    nospeaker: Optional[bool] = True
    motion: Optional[Motion] = None


class Division(BaseXMLModel, tag="division"):
    nospeaker: Optional[bool] = None
    divdate: str
    divnumber: int
    colnum: Optional[int] = None
    time: Optional[str] = None
    count: DivisionCount
    motion: Optional[Motion] = None
    items: list[RepList]


class Transcript(BaseXMLModel, tag="publicwhip"):
    scraper_version: Optional[str] = Field(
        default=None, validation_alias="scraperversion"
    )
    latest: Optional[str] = Field(default=None, validation_alias="latest")
    items: list[
        Union[
            Speech,
            Division,
            GIDRedirect,
            OralHeading,
            MajorHeading,
            MinorHeading,
            Agreement,
        ]
    ]

    def __iter__(self):  # type: ignore
        return iter(self.items)

    def iter_type(self, type: Type[T]) -> Iterator[T]:
        return (item for item in self.items if isinstance(item, type))

    def iter_speeches(self):
        return self.iter_type(Speech)

    def iter_has_text(self) -> Iterator[HasText]:
        return (item for item in self.items if isinstance(item, HasText))

    def iter_headings_and_paragraphs(self) -> Iterator[tuple[str, str]]:
        for speech in self.iter_has_text():
            if isinstance(speech, Speech):
                for paragraph in speech.items:
                    s_id = speech.id
                    if paragraph.pid:
                        s_id += f"#{paragraph.pid}"
                    yield (
                        s_id,
                        paragraph.contents_text.strip(),
                    )
            else:
                yield speech.id, speech.as_str()
