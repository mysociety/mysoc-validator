import json
from typing import Any, Generic, TypeVar, Union
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

    def promote_children(self):
        for child in getattr(self, "@children", []):
            setattr(self, child["@tag"], child["@text"])


class PersonInfo(BaseXMLModel, metaclass=DefaultExtraForbid, tags=["personinfo"]):
    model_config = ConfigDict(extra="allow")

    person_id: str = Field(
        validation_alias=AliasChoices("person_id", "id"),
        serialization_alias="id",
        pattern=r"uk\.org\.publicwhip/person/\d+$",
    )

    def promote_children(self):
        for child in getattr(self, "@children", []):
            if child["@text"].strip()[0] in ["[", "{"]:
                content = json.loads(child["@text"])
            else:
                content = child["@text"]
            setattr(self, child["@tag"], content)
        # if set, remove @children
        if hasattr(self, "@children"):
            delattr(self, "@children")


InfoModel = TypeVar("InfoModel", bound=Union[ConsInfo, PersonInfo])


class InfoCollection(BaseXMLModel, Generic[InfoModel], tags=["twfy", "publicwhip"]):
    items: Items[InfoModel] = Field(
        validation_alias=AliasChoices("items", "@children"),
        serialization_alias="@children",
        default_factory=list,
    )

    def append(self, item: InfoModel):
        self.items.append(item)
        self.__pydantic_fields_set__.add("items")

    def extend(self, items: list[InfoModel]):
        self.items.extend(items)
        self.__pydantic_fields_set__.add("items")

    def __iter__(self):  # type: ignore
        return iter(self.items)

    def promote_children(self):
        """
        When run this will no longer roundtrip.

        Use to access using the generic PersonInfo reader
        """
        for item in self.items:
            item.promote_children()

        return self

    def to_records(self) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []

        for item in self.items:
            if isinstance(item, ConsInfo):
                base = {"canonical": item.canonical}
            else:
                base = {"person_id": item.person_id}
            for k, v in item.model_dump():
                records.append({**base, "key": k, "value": str(v)})

        return records

    @classmethod
    def from_parlparse(cls, file_name: str, *, branch: str = "master"):
        if file_name.endswith(".xml") is False:
            file_name += ".xml"
        url = f"https://raw.githubusercontent.com/mysociety/parlparse/refs/heads/{branch}/members/{file_name}"
        return cls.from_xml_url(url)
