"""
This contains the pydantic schema for a generic register of members interests format.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from enum import Enum
from hashlib import md5
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Generic,
    Iterator,
    Literal,
    NamedTuple,
    Optional,
    TypeVar,
    Union,
    cast,
)

from mysoc_validator.models.consts import Chamber
from pydantic import (
    BaseModel,
    Discriminator,
    Field,
    RootModel,
    Tag,
    computed_field,
    model_validator,
)

if TYPE_CHECKING:
    import pandas as pd

ContentType = Literal["string", "markdown", "xml"]
ValidDetailTypes = Union[
    int, str, Decimal, datetime.date, float, bool, list["RegmemDetailGroup"]
]

T = TypeVar(
    "T",
    bound=ValidDetailTypes,
)


def slugify(s: str) -> str:
    """
    lowercase, space with _, only otherwise alphanumeric, no double __
    """
    # remove non-alphanumeric
    s = "".join([c for c in s if c.isalnum() or c == " "]).strip()
    # replace spaces with _
    s = s.replace(" ", "_")
    # lowercase
    s = s.lower()
    # remove double __
    s = s.replace("__", "_")
    return s


def df_to_details_group(df: pd.DataFrame) -> list[RegmemDetailGroup]:
    groups: list[RegmemDetailGroup] = []
    for row in df.to_dict(orient="records"):  # type: ignore
        row_group = RegmemDetailGroup()

        for k, v in row.items():
            row_group.append(RegmemDetail[type(v)](display_as=str(k), value=v))  # type: ignore

        groups.append(row_group)

    return groups


class CommonKey(str, Enum):
    COMPANIES_HOUSE = "companies_house"
    URL = "url"
    STANDARDISED_NAME = "standardised_name"
    SIC_CODE = "sic_code"


class RegmemDetail(BaseModel, Generic[T]):
    """
    Flexible model for storing key-value information about an interest.

    This is mostly expressing the complexity of the Commons register.

    Details can also have sub_detail_groups - these are grouped so values can relate to each other.

    This is used for:
    'declaring interest of trip' (entry)
    'leg of journey' (detail)
    'details about leg' (detail in detail)

    The discriminator union applies the correct type validator to the input.

    It's not strictly required for adding new entries, but add correct type information.
    e.g.
    RegmemDetail[datetime.date](slug="date", value=datetime.date(2021, 1, 1))
    """

    source: str = Field(
        default="official",
        description="The source of the information, for flagging when info is added by third parties",
    )
    slug: Optional[str] = None
    display_as: Optional[str] = None
    common_key: Optional[CommonKey] = Field(
        default=None,
        description="For adding a key against standardised list without changing the slug",
    )
    description: Optional[str] = Field(
        default=None, description="A description of the field - rather than the value"
    )
    type: Optional[str] = Field(default=None, description="The type of the value")
    value: Optional[T] = Field(
        default=None, description="Might be a direct value or a list of DetailGroups"
    )
    annotations: list[RegmemAnnotation] = Field(default_factory=list)

    @property
    def sub_detail_groups(self) -> list[RegmemDetailGroup]:
        """
        Shortcut for accessing details of containers
        """
        if isinstance(self.value, list):
            return self.value
        return []

    @model_validator(mode="after")
    def infer_slug(self):
        """
        if slug is missing, infer from display_as and vice versa.
        """
        if not self.slug and self.display_as:
            self.slug = slugify(self.display_as)
        if not self.display_as and self.slug:
            self.display_as = self.slug.replace("_", " ").title()
        return self

    @classmethod
    def parameterized_class_from_str(
        cls, type_str: str
    ) -> type[RegmemDetail[ValidDetailTypes]]:
        lookup: dict[str, type] = {
            "decimal": Decimal,
            "date": datetime.date,
            "int": int,
            "boolean": bool,
            "string": str,
            "container": list[RegmemDetailGroup],
        }
        return cls[lookup[type_str]]  # type: ignore

    def dict_value(self):
        if self.sub_detail_groups:
            return [x.detail_dict() for x in self.sub_detail_groups]
        else:
            return self.value

    def iter_sub_details(self) -> Iterator[RegmemDetail[Any]]:
        for group in self.sub_detail_groups:
            for detail in group:
                yield detail

    @model_validator(mode="after")
    def infer_type(self):
        """
        if type information is missing, infer from value.
        """
        if not self.type:
            if isinstance(self.value, str):
                self.type = "string"
            elif isinstance(self.value, bool):
                self.type = "boolean"
            elif isinstance(self.value, int):
                self.type = "int"
            elif isinstance(self.value, datetime.date):
                self.type = "date"
            elif isinstance(self.value, float):
                self.type = "float"
            elif isinstance(self.value, Decimal):
                self.type = "decimal"
            elif isinstance(self.value, list):
                self.type = "container"
        return self


def get_tag(v: Any) -> str:
    if isinstance(v, dict):
        v = cast(dict[str, str], v)
        item_type = v.get("type")
        item_value = v.get("value")
    else:
        item_type = getattr(v, "type", None)
        item_value = getattr(v, "value", None)

    if item_type:
        return item_type

    if isinstance(item_value, int):
        return "int"
    elif isinstance(item_value, str):
        return "string"
    elif isinstance(item_value, Decimal):
        return "decimal"
    elif isinstance(item_value, datetime.date):
        return "date"
    elif isinstance(item_value, float):
        return "float"
    elif isinstance(item_value, bool):
        return "boolean"
    elif item_value is None:
        return "string"
    else:
        return "string"


class RegmemDetailGroup(RootModel[Any]):
    """
    This is a container object for groups of details.
    The discriminator union applies the correct type validator
    logic depending on the type property.
    """

    root: list[
        Annotated[
            Union[
                Annotated[RegmemDetail[int], Tag("int")],
                Annotated[RegmemDetail[str], Tag("string")],
                Annotated[RegmemDetail[Decimal], Tag("decimal")],
                Annotated[RegmemDetail[datetime.date], Tag("date")],
                Annotated[RegmemDetail[float], Tag("float")],
                Annotated[RegmemDetail[bool], Tag("boolean")],
                Annotated[
                    RegmemDetail[list[RegmemDetailGroup]],
                    Tag("container"),
                ],
            ],
            Discriminator(get_tag),
        ]
    ] = Field(default_factory=list)

    def detail_dict(self) -> dict[str, ValidDetailTypes]:
        """
        Condense a group of details into a dictionary of keys and values.
        """
        return {x.slug: x.dict_value() for x in self.root}  # type: ignore

    def __iter__(self):  # type: ignore
        return iter(self.root)

    def __getitem__(self, index: slice):
        return self.root[index]

    def __len__(self):
        return len(self.root)

    def append(self, item: RegmemDetail[Any], *, source: Optional[str] = None):
        if source:
            item.source = source
        self.root.append(item)
        self.check_unique_detail_names()

    def extend(self, items: list[RegmemDetail[Any]], *, source: Optional[str] = None):
        if source:
            for item in items:
                item.source = source
        self.root.extend(items)
        self.check_unique_detail_names()

    def check_unique_detail_names(self):
        names = [x.slug for x in self.root]
        if len(names) != len(set(names)):
            duplicate_names = set([x for x in names if names.count(x) > 1])
            raise ValueError(f"Duplicate detail names in entry: {duplicate_names}")


RegmemDetailContainer = RegmemDetail[list[RegmemDetailGroup]]


class RegmemAnnotation(BaseModel):
    """
    A simple Annotation for a register entry.
    """

    author: str
    type: str = "note"
    content: str
    date_added: Optional[datetime.date] = None
    content_format: ContentType = Field(
        default="string", description="The format of the content"
    )

    @model_validator(mode="after")
    def date_is_today(self):
        if not self.date_added:
            self.date_added = datetime.date.today()
        return self


class RegmemInfoBase(BaseModel):
    """
    The core entry where the actual details are.

    The complexity here mostly reflects the Commons register.
    There are concepts of child interests and details.

    Details are a set of key-value pairs (ish - see RegmemDetail).
    Child interests will represent multiple payments from a single source.
    The content for the Commons will be the 'summary' of the interest.
    The Senedd register also uses Details to store information - but does not have a summary.
    When this is storing XML from the legacy format, the description_format is set to 'xml'.

    """

    id: Optional[str] = Field(
        default=None,
        description="A identifier for the entry (may not be unique, and reflect id in original system). If blank a hash is used.",
    )
    content: str = Field(default="", description="The main content of the entry")
    content_format: ContentType = Field(
        default="string", description="The format of the content"
    )
    date_registered: Optional[datetime.date] = None  # or lodged
    date_published: Optional[datetime.date] = None
    date_updated: Optional[datetime.date] = None
    date_received: Optional[datetime.date] = None
    null_entry: bool = Field(
        default=False,
        description="If the entry is saying 'no entries declared' or similar.",
    )
    annotations: list[RegmemAnnotation] = Field(default_factory=list)
    details: RegmemDetailGroup = Field(default_factory=RegmemDetailGroup)
    sub_entries: list[RegmemEntry] = Field(
        default_factory=list,
        description="Sub-entries - for instance multiple payments to this person.",
    )

    def add_details(
        self,
        *,
        source: Optional[str] = None,
        **values: Union[ValidDetailTypes, pd.DataFrame],
    ):
        import pandas as pd

        for k, v in values.items():
            if isinstance(v, pd.DataFrame):
                self.details.append(
                    RegmemDetailContainer(value=df_to_details_group(v), slug=k),
                    source=source,
                )
            else:
                self.details.append(
                    RegmemDetail[type(v)](value=v, slug=k), source=source
                )

    def details_dict(self, reduce: Optional[dict[str, list[str]]] = None):
        """
        Condense the details into a dictionary of keys and values.
        """
        data: dict[str, Any] = {"id": self.comparable_id, "content": self.content}
        if self.date_registered:
            data["date_registered"] = self.date_registered.isoformat()
        if self.date_published:
            data["date_published"] = self.date_published.isoformat()
        data |= self.details.detail_dict()

        def extract_discription(
            list_of_groups: list[RegmemDetailGroup], slug: str
        ) -> list[str]:
            values = []
            for group in list_of_groups:
                for item in group:
                    if item.slug == slug:
                        values.append(item.value)  # type: ignore
            return values  # type: ignore

        if reduce:
            for key, slugs in reduce.items():
                if key in data:
                    for slug in slugs:
                        value = data[key]
                        if isinstance(value, list):
                            data[slug] = extract_discription(value, slug)  # type: ignore
                    # remove the original key
                    del data[key]
        return data

    def get_detail(self, name: Union[str, CommonKey]) -> Optional[RegmemDetail[Any]]:
        for detail in self.details:
            if (
                detail.slug == name
                or detail.display_as == name
                or detail.common_key == name
            ):
                return detail
        return None

    def get_detail_value(self, name: Union[str, CommonKey]) -> Optional[Any]:
        detail = self.get_detail(name)
        if detail:
            return detail.value
        return None

    @computed_field
    @property
    def comparable_id(self) -> str:
        if self.id:
            return self.id
        return self.item_hash

    @computed_field
    @property
    def item_hash(self) -> str:
        hash_cols = [
            "content",
            "date_registered",
            "date_published",
            "date_updated",
            "date_received",
            "id",
            "details",
        ]
        data = self.model_dump(include=set(hash_cols))
        data["sub_items"] = [x.item_hash for x in self.sub_entries]
        return md5(str(data).encode()).hexdigest()[:10]


class RegmemEntry(RegmemInfoBase):
    info_type: Literal["entry", "subentry"] = "entry"


class RegmemSummary(RegmemInfoBase):
    info_type: Literal["summary"] = "summary"


class RegmemCategory(BaseModel):
    """
    Across all registers there are different categories of interests.
    We mostly use these to structure the output - they vary by chamber.

    *Ideally* category_id is a number, or at least sortable.

    """

    category_id: str = Field(
        default="", description="The unique identifier for the category"
    )
    category_name: str
    category_description: Optional[str] = None
    legislation_or_rule_name: Optional[str] = None
    legislation_or_rule_url: Optional[str] = None
    summaries: list[RegmemSummary] = Field(default_factory=list)
    entries: list[RegmemEntry] = Field(default_factory=list)

    def entries_and_subentries(self) -> Iterator[RegmemEntry]:
        for entry in self.entries:
            yield entry
            for subentry in entry.sub_entries:
                yield subentry


class RegmemPerson(BaseModel):
    """
    All registered interests for a person.
    Duplicate published_date here with overall register because sometimes
    we know the individual date of publication.
    """

    person_id: str
    person_name: str
    published_date: datetime.date
    chamber: Chamber
    language: Literal["en", "cy"] = "en"
    categories: list[RegmemCategory] = Field(default_factory=list)

    def get_category_from_id(self, category_id: str) -> RegmemCategory:
        for category in self.categories:
            if category.category_id == category_id:
                return category
        raise ValueError(f"Category {category_id} not found in register")


class EntryIterator(NamedTuple):
    person: RegmemPerson
    category: RegmemCategory
    entry: RegmemEntry
    parent_entry: Optional[RegmemEntry]


class RegmemRegister(BaseModel):
    """
    General container for a specific release of a register in a chamber.
    This may in practice be "the public information as of date" rather
    than an explicitly released register.
    """

    chamber: Optional[Chamber] = None
    language: Optional[Literal["en", "cy"]] = "en"
    published_date: Optional[datetime.date] = None
    annotations: list[RegmemAnnotation] = Field(default_factory=list)
    summaries: list[RegmemSummary] = Field(default_factory=list)
    persons: list[RegmemPerson] = Field(default_factory=list)

    @model_validator(mode="after")
    def either_global_or_person_chambers(self):
        """
        We want to make sure either all persons have a chamber and language value,
        or that there is a global one set.

        This is so in principle you could use the format to contain registers from
        multiple chambers.
        """
        if self.chamber is None:
            for person in self.persons:
                if person.chamber is None:
                    raise ValueError("Either global or per-person chamber must be set")
        else:
            # confirm all persons have the same chamber
            for person in self.persons:
                if person.chamber != self.chamber:
                    raise ValueError(
                        "All persons must have the same chamber as the register"
                    )
        if self.language is not None:
            # confirm all persons have the same language
            for person in self.persons:
                if person.language != self.language:
                    raise ValueError(
                        "All persons must have the same language as the register"
                    )
        if self.published_date is None:
            for person in self.persons:
                if person.published_date is None:
                    raise ValueError("Published date must be set")
        return self

    def iter_entries(self) -> Iterator[EntryIterator]:
        for person in self.persons:
            for category in person.categories:
                for entry in category.entries:
                    yield EntryIterator(person, category, entry, None)
                    for subentry in entry.sub_entries:
                        yield EntryIterator(person, category, subentry, entry)

    def get_person_from_id(self, person_id: str) -> RegmemPerson:
        for person in self.persons:
            if person.person_id == person_id:
                return person
        raise ValueError(f"Person {person_id} not found in register")

    @classmethod
    def from_path(cls, path: Path) -> RegmemRegister:
        data = path.read_text()
        return cls.model_validate_json(data)

    def to_path(self, path: Path, full: bool = False):
        if full:
            data = self.model_dump_json(indent=2)
        else:
            data = self.model_dump_json(
                indent=2, exclude_none=True, exclude_defaults=True
            )
        path.write_text(data)
