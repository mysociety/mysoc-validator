from typing import Any, Generic, TypeVar
from typing import Literal as Literal

from pydantic import AliasChoices, ConfigDict, Field
from typing_extensions import dataclass_transform

from .xml_base import BaseXMLModel, Items, XMLModelMeta


@dataclass_transform(kw_only_default=True)
class DefaultExtraForbid(XMLModelMeta):
    """
    This is so subclassing the PersonInfo model
    will reset it to being a forbid extra model.
    """

    def __new__(
        mcs,
        cls_name: str,
        bases: tuple[type[Any], ...],
        namespace: dict[str, Any],
        abstract_level: int = 2,
        **kwargs: Any,
    ):
        if "model_config" not in namespace:
            namespace["model_config"] = ConfigDict(extra="forbid")

        return super().__new__(
            mcs, cls_name, bases, namespace, abstract_level=abstract_level, **kwargs
        )


class ConsInfo(BaseXMLModel, metaclass=DefaultExtraForbid, tags=["consinfo"]):
    model_config = ConfigDict(extra="allow")
    canonical: str  # Canonical name for this consitiuency


class PersonInfo(BaseXMLModel, metaclass=DefaultExtraForbid, tags=["personinfo"]):
    model_config = ConfigDict(extra="allow")

    person_id: str = Field(
        validation_alias=AliasChoices("person_id", "id"),
        serialization_alias="id",
        pattern=r"uk\.org\.publicwhip/person/\d+$",
    )


InfoModel = TypeVar("InfoModel", ConsInfo, PersonInfo)


class InfoCollection(BaseXMLModel, Generic[InfoModel], tags=["twfy", "publicwhip"]):
    items: Items[InfoModel]

    @classmethod
    def from_parlparse(cls, file_name: str, *, branch: str = "master"):
        if file_name.endswith(".xml") is False:
            file_name += ".xml"
        url = f"https://raw.githubusercontent.com/mysociety/parlparse/refs/heads/{branch}/members/{file_name}"
        return cls.from_xml_url(url)
