"""
Structure for handling the main Parlparse people.json file
Following the general shape of the popolo standard.

"""

from __future__ import annotations

import re
from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import groupby
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Literal,
    Match,
    NamedTuple,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

import requests
from mysoc_validator.models.dates import ApproxDate, FixedDate
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    PlainSerializer,
    PlainValidator,
    RootModel,
    Tag,
    ValidationInfo,
    WithJsonSchema,
    model_validator,
)
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Self

from .consts import Chamber as Chamber
from .consts import IdentifierScheme as IdentifierScheme


@dataclass
class MockValidate:
    context: Any = None
    config: None = None
    mode: Literal["python"] = "python"
    data: dict[str, Any] = field(default_factory=dict)
    field_name: Optional[str] = None


NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")


def escape_unicode_characters(text: str) -> str:
    """
    Currently people json uses escaped unicode characters
    Enforce this on outputs while preserviing escape
    sequences like newlines
    """

    def escape(match: Match[str]) -> str:
        char = match.group(0)
        return f"\\u{ord(char):04x}"

    return NON_ASCII_RE.sub(escape, text)


BLANK_ID = "BLANK_ID"


def BlankID(blank_id: str):
    def inner(v: Any) -> Optional[str]:
        if v == BLANK_ID:
            return blank_id
        return v

    return BeforeValidator(inner)


Url = Annotated[str, Field(pattern=r"^https?://.*$")]
MemberID = Annotated[
    str,
    BlankID("uk.org.publicwhip/member/0"),
    # Actually can't even assume this pattern - doesn't hold for the ministers file
    # Field(pattern=r"uk\.org\.publicwhip/(member|lord|royal)/-?\d+$"),
]
OrgID = Annotated[str, Field(pattern=r"^[a-z0-9-]+$")]
PersonID = Annotated[
    str,
    BlankID("uk.org.publicwhip/person/0"),
    Field(pattern=r"uk\.org\.publicwhip/person/\d+$"),
]
PostID = Annotated[
    str,
    Field(pattern=r"uk\.org\.publicwhip/cons/\d+(-NI)?$"),
    BlankID("uk.org.publicwhip/cons/0"),
]
OrgType = Literal["party", "chamber", "metro"]


def approx_date_or_default(default: Any = None):
    def inner(v: Union[str, date]) -> Optional[Union[ApproxDate, date]]:
        if v:
            if isinstance(v, date):
                return v
            try:
                return date.fromisoformat(v)
            except ValueError:
                return ApproxDate.fromisoformat(v)
        # the issue is this should get default rather than none
        return default

    return inner


def empty_string_if_none(obj: Any) -> str:
    # default values will *be* these values, not just match them
    if obj is FixedDate.PAST or obj is FixedDate.FUTURE:
        return ""
    return str(obj)


# Fall back to more flexible ApproxDate if it's not a full ISO
# comparisons still work
FlexiDatePast = Annotated[
    Union[ApproxDate, date],
    Field(default=FixedDate.PAST),
    PlainValidator(approx_date_or_default(FixedDate.PAST)),
    PlainSerializer(empty_string_if_none, return_type=str),
    WithJsonSchema({"type": "string", "pattern": r"^\d{4}(-\d{2})?(-\d{2})?$"}),
]

FlexiDateFuture = Annotated[
    Union[ApproxDate, date],
    Field(default=FixedDate.FUTURE),
    PlainValidator(approx_date_or_default(FixedDate.FUTURE)),
    PlainSerializer(empty_string_if_none, return_type=str),
    WithJsonSchema({"type": "string", "pattern": r"^\d{4}(-\d{2})?(-\d{2})?$"}),
]


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def reduce_to_slug(s: str) -> str:
    """
    make lower case and remove all punctuation
    """
    return "".join(c for c in s if c.isalpha()).lower()


class HasStartAndEndDate(Protocol):
    start_date: date
    end_date: date
    __pydantic_fields_set__: set[str]


class DateFormatMixin:
    @model_validator(mode="after")
    def default_values_are_unset(self: HasStartAndEndDate):
        """
        remove start_date or end_date from set list if they're the default and present in the set_list.
        This stops us unnecessarily serializing them.
        """
        if (
            self.start_date == FixedDate.PAST
            and "start_date" in self.__pydantic_fields_set__
        ):
            self.__pydantic_fields_set__.remove("start_date")
        if (
            self.end_date == FixedDate.FUTURE
            and "end_date" in self.__pydantic_fields_set__
        ):
            self.__pydantic_fields_set__.remove("end_date")
        return self

    @model_validator(mode="after")
    def correct_date_range_order(self: HasStartAndEndDate):
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                print(self.start_date, self.end_date)
                raise ValueError(
                    f"end date {self.end_date} is before start date {self.start_date}"
                )
        return self


class ModelInList(StrictBaseModel):
    BLANK_ID: ClassVar[str] = "BLANK_ID"
    _index_on: ClassVar[str] = "id"
    _int_style_id: ClassVar[bool] = True
    parent: Optional[IndexedList[Self]] = Field(default=None, exclude=True, repr=False)

    def __str__(self) -> str:
        return f"<Popolo.{self.__class__.__name__}: {getattr(self, self._index_on)}>"

    def is_blank_id(self) -> bool:
        id_str: str = getattr(self, self._index_on)
        try:
            return int(id_str.split("/")[-1]) == 0
        except ValueError:
            return False

    def replace_blank_id(self, new_id: int) -> None:
        current_id: str = getattr(self, self._index_on)
        new_id_str = current_id.rsplit("/", 1)[0] + f"/{new_id}"
        setattr(self, self._index_on, new_id_str)

    def get_unassigned_id(self) -> int:
        """
        This needs to be subclasses for any classes that have ranges based on
        other values
        """
        if not self.parent:
            raise ValueError("No parent set")

        return self.parent.get_unassigned_id()

    def check_and_replace_blank_id(self):
        if not self.is_blank_id():
            return

        if not self.get_is_int_style_id():
            raise ValueError(
                f"Can't replace blank id for model type {self.__class__} - ID style not predictable. "
            )

        new_id = self.get_unassigned_id()
        self.replace_blank_id(new_id)

    @classmethod
    def get_list_index_field(cls) -> str:
        return cls._index_on

    @classmethod
    def get_is_int_style_id(cls) -> bool:
        return cls._int_style_id

    def get_index_on_field(self) -> str:
        return getattr(self, self._index_on)

    def delete(self):
        if self.parent:
            own_id = getattr(self, self.get_index_on_field())
            self.parent.pop(own_id)

    def parent_compatibility_check(self, parent: IndexedList[Any]) -> None:
        raise NotImplementedError

    def set_parent(self, parent: IndexedList[Any], *, extra_checks: bool):
        if extra_checks:
            self.parent_compatibility_check(parent)
        self.parent = parent
        self.check_and_replace_blank_id()

    def __setattr__(self, name: str, value: Any):
        """
        Models are validated on creation.
        But because validate_assignment doesn't play well with how we're doing typing for list items
        need to do it manually
        """
        super().__setattr__(name, value)
        if name != "parent":
            self.__class__.model_validate(self.model_dump())
            if name == "id" or "_id" in name:
                if self.parent:
                    # if changing id field, check that the parent list is still valid
                    self.parent.revalidate(full=False)

    @property
    def parent_popolo(self):
        if self.parent:
            return self.parent.get_parent()


StrInt = Union[str, int]
T = TypeVar("T", bound=ModelInList)
IDConstructor = Callable[[Any], Optional[str]]
SpecifiedIDConstructor = Callable[[T], Optional[str]]


class SimpleIdentifier(StrictBaseModel):
    identifier: str
    scheme: str


class Name(StrictBaseModel):
    family_name: str
    given_name: str


class MembershipRedirect(ModelInList):
    id: str
    redirect: str

    def self_or_redirect(self) -> Membership:
        return self.get_redirect()

    def get_redirect(self) -> Membership:
        if self.parent_popolo:
            return self.parent_popolo.memberships[self.redirect]
        raise ValueError(
            f"MembershipRedirect {self.id} points to invalid membership {self.redirect}"
        )


class Membership(ModelInList, DateFormatMixin):
    """
    A timed connection between a person and a post.
    """

    end_date: FlexiDateFuture
    end_reason: Optional[str] = None
    id: MemberID
    identifiers: Optional[list[SimpleIdentifier]] = None
    label: Optional[str] = None
    name: Optional[Name] = None
    on_behalf_of_id: Optional[OrgID] = None
    organization_id: Optional[OrgID] = None
    person_id: PersonID
    post_id: Optional[PostID] = None
    role: Optional[str] = None
    source: Optional[str] = None
    start_date: FlexiDatePast
    start_reason: str = ""

    def self_or_redirect(self) -> Membership:
        return self

    def get_unassigned_id(self) -> int:
        """
        This needs to be subclasses for any classes that have ranges based on
        other values
        """
        if not self.parent:
            raise ValueError("No parent set")

        if post := self.post():
            if post.organization_id == "house-of-commons":
                return self.parent.get_unassigned_id(start=0, end=69999)
            elif post.organization_id == "welsh-parliament":
                return self.parent.get_unassigned_id(start=70000, end=79999)
            elif post.organization_id == "scottish-parliament":
                return self.parent.get_unassigned_id(start=80000, end=89999)
            elif post.organization_id == "northern-ireland-assembly":
                return self.parent.get_unassigned_id(start=90000, end=99999)
            elif post.organization_id == "house-of-lords":
                return self.parent.get_unassigned_id(start=100000, end=199999)
            elif post.organization_id == "london-assembly":
                return self.parent.get_unassigned_id(start=200000, end=299999)
            else:
                raise ValueError(f"Unknown organization id {post.organization_id}")
        else:
            raise ValueError("Post required for new membership to assign blank ID.")

    def parent_compatibility_check(self, parent: IndexedList[Any]):
        """
        Extra check on new memeberships to make sure they don't overlap with existing ones
        with same person_id and post_id
        """

        rel_memberships = [
            m
            for m in parent
            if isinstance(m, Membership)
            and m.person_id == self.person_id
            and m.post_id == self.post_id
        ]

        ## check that there are no overlaps in the date ranges
        for m in rel_memberships:
            if self.start_date <= m.end_date and self.end_date >= m.start_date:
                raise ValueError(
                    f"New Membership {self.id} overlaps with membership {m.id}"
                )

    def person(self) -> Optional[Person]:
        if self.parent_popolo and self.person_id:
            return self.parent_popolo.persons[self.person_id]

    def post(self) -> Optional[Post]:
        if self.parent_popolo and self.post_id:
            return self.parent_popolo.posts[self.post_id]

    def organization(self) -> Optional[Organization]:
        if self.parent_popolo and self.organization_id:
            return self.parent_popolo.organizations[self.organization_id]

    def on_behalf_of(self) -> Optional[Organization]:
        if self.parent_popolo and self.on_behalf_of_id:
            return self.parent_popolo.organizations[self.on_behalf_of_id]


class Organization(ModelInList):
    """
    May be a party or chamber
    """

    _int_style_id: ClassVar[bool] = False
    classification: Optional[OrgType] = None
    id: OrgID
    identifiers: Optional[list[SimpleIdentifier]] = None
    name: str

    def close_open_memberships(self, end_date: date, end_reason: str):
        """
        Close all open memberships for a body.
        """

        popolo = self.parent_popolo
        if not popolo:
            raise ValueError("Organization has no parent Popolo")

        for membership in popolo.memberships.get_matching_values(
            "organization_id", self.id
        ):
            if isinstance(membership, Membership):
                if membership.end_date == FixedDate.FUTURE:
                    membership.end_date = end_date
                    membership.end_reason = end_reason
        return self


class PersonIdentifier(ModelInList):
    """
    Alternative identifiers in other schemas for a person
    """

    _index_on: ClassVar[str] = "scheme"

    identifier: StrInt
    scheme: str

    def __str__(self) -> str:
        return f"{self.scheme}:{self.identifier}"

    def parent_compatibility_check(self, parent: IndexedList[PersonIdentifier]):
        # check there isn't already something for this identifer

        for identifer in parent:
            if identifer.scheme == self.scheme:
                raise ValueError(f"Duplicate identifier scheme {self.scheme}")


class AltName(StrictBaseModel, DateFormatMixin):
    end_date: FlexiDateFuture
    name: str
    note: Literal["Alternate"]
    organization_id: Optional[OrgID] = None
    start_date: FlexiDatePast

    def nice_name(self) -> str:
        return self.name


class BasicPersonName(StrictBaseModel, DateFormatMixin):
    """
    Basic name for for most elected persons
    """

    end_date: FlexiDateFuture
    family_name: str
    given_name: Optional[str] = None
    honorific_prefix: Optional[str] = None
    note: Literal["Main", "Alternate"]
    start_date: FlexiDatePast

    def nice_name(self) -> str:
        if self.given_name:
            return self.given_name + " " + self.family_name
        return self.family_name


class LordName(StrictBaseModel, DateFormatMixin):
    """
    A name - with all the lords options.
    There's so many optional fields here because of all the lords types.
    """

    additional_name: Optional[str] = None  # first name
    county: Optional[str] = None  # county
    end_date: FlexiDateFuture
    given_name: Optional[str] = None  # first name
    honorific_prefix: Optional[str] = None  # Viscount etc
    honorific_suffix: Optional[str] = None  # KCMG
    lordname: Optional[str] = None  # the styled lord name, when different from surname
    lordofname: Optional[str] = None  # of place
    lordofname_full: Optional[str] = None  # the second of place - of place, of place
    note: Literal["Main", "Alternate"]
    start_date: FlexiDatePast
    surname: Optional[str] = None  # The surname of the lord

    def nice_name(self) -> str:
        """
        Construct a basic name from the lord name
        """
        name = self.lordname or self.surname or self.lordofname
        if not name:
            return "Unknown"
        if self.honorific_prefix:
            name = self.honorific_prefix + " " + name
        if self.honorific_suffix:
            name = name + " " + self.honorific_suffix
        return name


class Shortcuts(StrictBaseModel):
    """
    Previously calculated shortcuts between a person
    and their current consitutency and party.
    This is out of date in people.json, and won't work for people
    in multiple chambers.
    """

    current_constituency: Optional[str] = None
    current_party: str


def name_discriminator(v: dict[str, Any]) -> str:
    if "name" in v or hasattr(v, "name"):
        return "alt"
    if "family_name" in v or hasattr(v, "family_name"):
        return "person_name"
    else:
        return "lord"


class PersonRedirect(ModelInList):
    id: PersonID
    redirect: PersonID

    def self_or_redirect(self) -> Person:
        return self.get_redirect()

    def get_redirect(self) -> Person:
        if self.parent_popolo:
            return self.parent_popolo.persons[self.redirect]
        raise ValueError(
            f"MembershipRedirect {self.id} points to invalid membership {self.redirect}"
        )


class Link(StrictBaseModel):
    note: Optional[str] = None
    url: Url


class Person(ModelInList):
    """
    A person who has held an office.
    """

    biography: Optional[str] = None
    birth_date: Optional[FlexiDatePast] = None
    death_date: Optional[FlexiDateFuture] = None
    gender: Optional[str] = None
    id: PersonID
    identifiers: IndexedPersonIdentifierList = Field(
        default_factory=lambda: IndexedPersonIdentifierList(root=[])
    )
    image: Optional[Url] = None
    links: list[Link] = Field(default_factory=list)
    names: list[
        Annotated[
            Union[
                Annotated[BasicPersonName, Tag("person_name")],
                Annotated[LordName, Tag("lord")],
                Annotated[AltName, Tag("alt")],
            ],
            Discriminator(name_discriminator),
        ]
    ] = Field(
        default_factory=list,
        serialization_alias="other_names",
        validation_alias=AliasChoices("names", "other_names"),
    )
    national_identity: Optional[str] = None
    summary: Optional[str] = None
    shortcuts: Optional[Shortcuts] = Field(
        deprecated="Shortcuts is not maintained - and should be blank in current versions of the database",
        default=None,
    )

    @model_validator(mode="after")
    def add_parent_ids(self):
        self.identifiers.set_parent(self)  # type: ignore
        return self

    def add_identifer(self, *, scheme: str, identifier: str, if_missing: bool = False):
        """
        Add an identifier to the person.
        """
        if if_missing:
            existing = self.identifiers.get(scheme)
            if existing and existing.identifier == identifier:
                return False

        self.identifiers.root = [x for x in self.identifiers.root if x.scheme != scheme]

        self.identifiers.append(PersonIdentifier(scheme=scheme, identifier=identifier))
        return True

    def reduced_id(self) -> str:
        return self.id.split("/")[-1]

    def self_or_redirect(self) -> Person:
        return self

    def names_on_date(self, date: date) -> list[str]:
        return [x.nice_name() for x in self.names if x.start_date <= date <= x.end_date]

    def get_main_name(
        self, date: date = FixedDate.FUTURE
    ) -> Optional[Union[BasicPersonName, LordName]]:
        names = [
            x
            for x in self.names
            if x.note == "Main" and x.start_date <= date <= x.end_date
        ]
        if len(names) > 1:
            raise ValueError(f"Multiple main names for person {self.id}")
        if names:
            return names[0]
        return None

    def get_identifier(self, scheme: str):
        rel = [x for x in self.identifiers if x.scheme == scheme]
        if rel:
            return rel[0].identifier

    def memberships(self) -> list[Membership]:
        if not self.parent_popolo:
            raise ValueError("Person has no parent Popolo")

        members = self.parent_popolo.memberships.get_matching_values(
            "person_id", self.id
        )
        return [m for m in members if not isinstance(m, MembershipRedirect)]

    def membership_on_date(
        self, date: date, *, chamber: Chamber
    ) -> Optional[Membership]:
        memberships = self.memberships()
        if memberships:
            for m in memberships:
                post = m.post()
                if post and post.organization_id == chamber:
                    if m.start_date <= date <= m.end_date:
                        return m

    def latest_membership(self, chamber: Chamber) -> Optional[Membership]:
        chamber_memberships: list[Membership] = []
        for m in self.memberships():
            post = m.post()
            if post and post.organization_id == chamber:
                chamber_memberships.append(m)
        if chamber_memberships:
            return max(chamber_memberships, key=lambda m: m.start_date)

    def add_membership(
        self,
        organization_id: Chamber,
        role: str,
        start_date: date,
        end_date: date = FixedDate.FUTURE,
        post_id: str = "",
        on_behalf_of_id: str = "",
        start_reason: str = "",
        end_reason: str = "",
    ):
        """
        Add a membership to a person.
        """

        if not self.parent_popolo:
            raise ValueError("Person has no parent Popolo object")

        popolo = self.parent_popolo

        membership = Membership(
            id=Membership.BLANK_ID,
            person_id=self.id,
            organization_id=organization_id,
            role=role,
            start_date=start_date,
            end_date=end_date,
            post_id=post_id,
            on_behalf_of_id=on_behalf_of_id,
            start_reason=start_reason,
            end_reason=end_reason,
        )
        popolo.memberships.append(membership)

    def end_membership_with_reason(
        self,
        end_date: date,
        end_reason: str,
    ):
        """
        End the most recent membership for a person - record reason.
        """
        last_membership = self.memberships()[-1]
        last_membership.end_date = end_date
        last_membership.end_reason = end_reason

    def change_party(
        self,
        new_party: Organization,
        change_date: Optional[date] = None,
        change_reason: str = "",
    ):
        """
        Change the party of a person - close open membership and create new one.
        """
        if change_date is None:
            change_date = date.today()

        if not self.parent_popolo:
            raise ValueError("Person has no parent Popolo object")

        popolo = self.parent_popolo

        last_membership = self.memberships()[-1]
        last_membership.end_date = change_date
        last_membership.end_reason = change_reason

        new_membership = Membership(
            id=Membership.BLANK_ID,
            person_id=self.id,
            start_date=change_date + timedelta(days=1),
            end_date=FixedDate.FUTURE,
            organization_id=last_membership.organization_id,
            on_behalf_of_id=new_party.id,
            post_id=last_membership.post_id,
            start_reason=change_reason,
        )
        popolo.memberships.append(new_membership)

    def restore_whip(self, change_date: Optional[date] = None):
        """
        Restore the whip role to a person.
        """

        # get the last party that wasn't 'independent'

        previous_party = None
        for membership in reversed(self.memberships()):
            if membership.on_behalf_of_id != "independent":
                previous_party = membership.on_behalf_of()
                break

        if previous_party is None:
            raise ValueError("No previous party found")

        self.change_party(
            new_party=previous_party,
            change_reason="changed_party",
            change_date=change_date,
        )

    def remove_whip(self, change_date: Optional[date] = None):
        """
        Remove the whip role from a person.
        """

        if not self.parent_popolo:
            raise ValueError("Person has no parent Popolo object")

        popolo = self.parent_popolo
        inde_party = popolo.organizations["independent"]

        self.change_party(
            change_date=change_date,
            new_party=inde_party,
            change_reason="changed_party",
        )

    def add_alt_name(
        self,
        given_name: Optional[str] = "",
        family_name: Optional[str] = "",
        one_name: Optional[str] = "",
        start_date: date = FixedDate.PAST,
        end_date: date = FixedDate.FUTURE,
    ):
        """
        Add an alternate name to a person.
        """

        alt_name = None

        if given_name and family_name:
            alt_name = BasicPersonName(
                family_name=family_name,
                given_name=given_name,
                note="Alternate",
                start_date=start_date,
                end_date=end_date,
            )

        else:
            if given_name or family_name:
                raise ValueError("Both given and last name must be provided")
            if one_name:
                alt_name = AltName(
                    name=one_name,
                    start_date=start_date,
                    note="Alternate",
                    end_date=end_date,
                )
                self.names.append(alt_name)
            else:
                raise ValueError(
                    "Either one_name or given and last name must be provided"
                )

        self.names.append(alt_name)

    def change_main_name_to_lord(
        self,
        given_name: str,
        county: str,
        honorific_prefix: str,
        lordname: str,
        lordofname_full: str,
        change_date: date,
    ):
        existing_name = self.get_main_name(change_date)

        if existing_name:
            existing_name.end_date = change_date - timedelta(days=1)

        new_name = LordName(
            start_date=change_date,
            end_date=FixedDate.FUTURE,
            note="Main",
            given_name=given_name,
            county=county,
            honorific_prefix=honorific_prefix,
            lordname=lordname,
            lordofname_full=lordofname_full,
        )

        self.names.append(new_name)

    def change_main_name(self, given_name: str, family_name: str, change_date: date):
        """
        Add a new main name.
        """
        existing_name = self.get_main_name(change_date)

        if existing_name:
            existing_name.end_date = change_date - timedelta(days=1)

        new_name = BasicPersonName(
            family_name=family_name,
            given_name=given_name,
            note="Main",
            start_date=change_date,
            end_date=FixedDate.FUTURE,
        )
        self.names.append(new_name)


class Area(ModelInList):
    """
    Constituency name
    """

    _index_on: ClassVar[str] = "name"
    _int_style_id: ClassVar[bool] = False

    name: str
    other_names: list[str] = Field(default_factory=list)


class PostIdentifier(StrictBaseModel):
    """
    ID for post (e.g. MP of constituency) in other schemas
    """

    identifier: str
    scheme: str


class Post(ModelInList, DateFormatMixin):
    _int_style_id: ClassVar[bool] = False

    area: Area
    end_date: Optional[FlexiDateFuture] = None
    id: PostID
    identifiers: Optional[list[PostIdentifier]] = None
    label: str
    organization_id: OrgID
    role: str
    start_date: Optional[FlexiDatePast] = None

    def organization(self) -> Organization:
        if not self.parent_popolo:
            raise ValueError("Post has no parent Popolo")

        return self.parent_popolo.organizations[self.organization_id]


class IDIndex:
    """
    Basic index holding class.
    """

    def __init__(self, *, id_constructor: IDConstructor, items: list[Any] = []):
        self.id_constructor = id_constructor
        self.index: dict[str, list[int]] = {}
        self.construct_index(items)

    def __getitem__(self, key: str) -> list[int]:
        return self.index[key]

    def get(self, key: str, default: Optional[list[int]] = None) -> Optional[list[int]]:
        return self.index.get(key, default)

    def construct_index(self, items: list[Any]):
        """
        Construct a dictionary mapping unique values in items[]."id_field" to a list of the index positions
        of the items in items.
        """
        self.index = {}
        for i, item in enumerate(items):
            id_value = self.id_constructor(item)
            if id_value:
                if id_value not in self.index:
                    self.index[id_value] = []
                self.index[id_value].append(i)


class IndexedList(RootModel[list[T]]):
    """
    A list model with additional indexing and caching of the indexing.
    """

    root: list[T] = Field(default_factory=list)

    def check_unique_id(self) -> Self:
        """
        Check that all items in the list have a unique id
        """
        id_column = self.get_index_field()
        if id_column != "id":
            return self
        ids = [getattr(x, id_column) for x in self.root]
        if len(set(ids)) != len(ids):
            # if there's actual duplicate ids we need to
            # we figure out which ones for the error message
            id_counts: dict[Any, int] = {}
            for i in ids:
                if i not in id_counts:
                    id_counts[i] = 0
                id_counts[i] += 1
            duplicates = [k for k, v in id_counts.items() if v > 1]
            raise ValueError(f"Duplicate ids found: {duplicates}")
        return self

    pydantic_validate_unique_id = model_validator(mode="after")(check_unique_id)

    def model_post_init(self, __context: dict[str, Any]):
        for item in self.root:
            item.parent = self
        self._id_lookups: dict[str, IDIndex] = {}
        self._parent: Optional[Popolo] = None
        self._max_id: Optional[int] = None
        self._id_int: list[int] = []
        self.refresh_id_int()

    def refresh_id_int(self):
        get_index_field = self.get_index_field()
        is_int_style = self.get_is_int_style_id()
        if get_index_field != "id" or not is_int_style:
            self._id_int = []
            return

        if len(self.root) == 0:
            self._id_int = []
            return

        if hasattr(self.root[0], "id") and isinstance(self.root[0].id, str):  # type: ignore
            self._id_int_list = sorted([int(x.id.split("/")[-1]) for x in self.root])  # type: ignore

    def get_unassigned_id(self, *, start: int = 0, end: int = 999999) -> int:
        """
        Get the first unassigned id in the range
        """

        # if we have no items, just return the start
        if not self._id_int_list:
            return start + 1

        # find the value that is the highest in the list before the specified end point
        highest_allowed_value = bisect_left(self._id_int_list, end) - 1

        if highest_allowed_value == -1:
            return start + 1

        return self._id_int_list[highest_allowed_value] + 1

    def get_list_container_type(self) -> list[Type[T]]:
        """
        What real classes are being stored in this list.
        Need to break open unions and annotated in some instasnces
        """

        def remove_annotation(t: Any) -> Type[T]:
            if get_origin(t):
                return get_args(t)[0]
            return t

        list_contents = get_args(self.model_fields["root"].annotation)[0]
        # if it's annotated, we want the true value
        if get_origin(list_contents):
            list_contents = remove_annotation(list_contents)

        # if union, get rid of annotated types
        if container_types := get_args(list_contents):
            list_contents = [remove_annotation(x) for x in container_types]
            return list_contents
        else:
            return [list_contents]

    def get_parent(self) -> Popolo:
        if not self._parent:
            raise ValueError("No parent set")
        return self._parent

    def set_parent(self, parent: Popolo):
        self._parent = parent

    def invalidate_indexes(self):
        """
        If anything changes in a list, we need to invalidate the indexes
        If they're then used they're just regenerated anyway.
        """
        self._id_lookups = {}

    def get_matching_indexes(
        self,
        *,
        field: str,
        value: str,
        value_to_id_func: Optional[SpecifiedIDConstructor[T]] = None,
    ) -> list[int]:
        """
        Get the matching index positions in the list for items whose field == value.
        """

        def field_to_id(item: T) -> Optional[str]:
            if not hasattr(item, field):
                return None
            return getattr(item, field)

        if value_to_id_func is None:
            value_to_id_func = field_to_id

        if field not in self._id_lookups:
            self._id_lookups[field] = IDIndex(
                id_constructor=value_to_id_func, items=self.root
            )
        return self._id_lookups[field].get(value) or []

    def get_matching_index(
        self,
        field: str,
        value: str,
        value_to_id_func: Optional[SpecifiedIDConstructor[T]] = None,
    ) -> int:
        """
        Same as get_matching_indexes - but allows only a single index result
        """
        matches = self.get_matching_indexes(
            field=field, value=value, value_to_id_func=value_to_id_func
        )
        if len(matches) == 0:
            raise ValueError(f"No item with {field} == {value}")
        if len(matches) > 1:
            raise ValueError(f"Multiple items with {field} == {value}")
        return matches[0]

    def get_matching_values(
        self,
        field: str,
        value: str,
        value_to_id_func: Optional[SpecifiedIDConstructor[T]] = None,
    ) -> list[T]:
        """
        Get the actual values that where the value is the same as the field
        list[].field == value
        """
        return [
            self.root[i]
            for i in self.get_matching_indexes(
                field=field, value=value, value_to_id_func=value_to_id_func
            )
        ]

    def get_single_from_index(
        self,
        field: str,
        value: str,
        value_to_id_func: Optional[SpecifiedIDConstructor[T]] = None,
    ) -> T:
        """
        Get a single item from the index where field == value
        """
        matches = self.get_matching_values(field, value, value_to_id_func)
        if len(matches) == 0:
            raise ValueError(f"No item with {field} == {value}")
        if len(matches) > 1:
            raise ValueError(f"Multiple items with {field} == {value}")
        return matches[0]

    def __getitem__(self, key: str) -> T:
        """
        Getitem will behave normally for a list if an int
        But a string will be treated as an id lookup
        """
        try:
            return self.get_single_from_index(self.get_index_field(), key)
        except ValueError:
            raise KeyError(f"Couldn't find an entry for {key}")

    def __contains__(self, key: str) -> bool:
        try:
            self[key]
            return True
        except (ValueError, IndexError):
            return False

    def get(self, key: str, default: Optional[Any] = None) -> Optional[T]:
        try:
            return self[key]
        except KeyError:
            return default

    def get_index_field(self) -> str:
        possible_index_types = self.get_list_container_type()
        index_fields = [x.get_list_index_field() for x in possible_index_types]
        # reduce to unique values and error if more than one
        index_fields = list(set(index_fields))
        if len(index_fields) > 1:
            raise ValueError(f"Multiple index_on fields found {index_fields}")
        return index_fields[0]

    def get_is_int_style_id(self) -> bool:
        possible_index_types = self.get_list_container_type()
        index_fields = [x.get_is_int_style_id() for x in possible_index_types]
        # reduce to unique values and error if more than one
        index_fields = list(set(index_fields))
        if len(index_fields) > 1:
            raise ValueError(f"Multiple index_on fields found {index_fields}")
        return index_fields[0]

    def pop(self, key: int | str) -> T:
        """
        Can remove by index position or by passing the ID
        """
        if isinstance(key, int):
            return self.root.pop(key)
        else:
            index = self.get_matching_index(self.get_index_field(), key)
            return self.root.pop(index)

    def __len__(self) -> int:
        return len(self.root)

    def __iter__(self):  # type: ignore
        return iter(self.root)

    def first(self) -> T:
        return self.root[0]

    def revalidate(self, *, full: bool):
        """
        Revalidate unique and valid id rules
        """
        self.check_unique_id()

        mock_validate = MockValidate()

        self.get_parent().check_valid_ids_used(mock_validate)
        if full:
            # Don't rerun this as role date range should be enforced
            # quicker on append or extend
            self.get_parent().check_role_date_ranges(mock_validate)
        self.refresh_id_int()

    def append(self, item: T):
        valid_types = tuple(self.get_list_container_type())

        try:
            item.set_parent(self, extra_checks=True)
        except AttributeError:
            raise ValueError(f"Item {item} does not have a parent attribute")
        if not isinstance(item, valid_types):
            raise ValueError(f"Item must be of type {valid_types}, not {type(item)}")

        self.root.append(item)

        self.invalidate_indexes()
        self.revalidate(full=False)

    def extend(self, items: list[T]):
        valid_types = tuple(self.get_list_container_type())

        for item in items:
            try:
                item.set_parent(self, extra_checks=True)
            except AttributeError:
                raise ValueError(f"Item {item} does not have a parent attribute")
            if not isinstance(item, valid_types):
                raise ValueError(
                    f"Item must be of type {valid_types}, not {type(item)}"
                )

        self.root.extend(items)

        self.invalidate_indexes()
        self.revalidate(full=False)


class NameIndex(dict[str, str]):
    """
    Store a reduced name index for a repeated lookups
    in a given chamber in a given day.
    """

    def get_id_reduced(self, key: str) -> Optional[str]:
        return self.get(reduce_to_slug(key))

    @classmethod
    def from_people(cls, people: list[Person], date: date) -> NameIndex:
        ni = NameIndex()

        for p in people:
            for name in p.names_on_date(date):
                ni[reduce_to_slug(name)] = p.id

        return ni

    @classmethod
    def from_memberships(cls, popolo: Popolo, chamber_id: str, date: date) -> NameIndex:
        # get posts associated with the chamber
        rel_posts = popolo.posts.get_matching_values("organization_id", chamber_id)
        post_ids = set([p.id for p in rel_posts])
        # get memberships for this post
        rel_memberships = [x for x in popolo.memberships if x.post_id in post_ids]

        # filter out memberships that are not current - date needs to be between start and end date
        rel_people = [
            m.person() for m in rel_memberships if m.start_date <= date <= m.end_date
        ]
        rel_people = [p for p in rel_people if p]

        return cls.from_people(rel_people, date)


class OrgDate(NamedTuple):
    organization_id: str
    date: date


def person_descriminator(v: dict[str, Any]) -> str:
    if "redirect" in v or hasattr(v, "redirect"):
        return "redirect"
    return "person"


class IndexedPeopleList(
    IndexedList[
        Annotated[
            Union[
                Annotated[Person, Tag("person")],
                Annotated[PersonRedirect, Tag("redirect")],
            ],
            Discriminator(person_descriminator),
        ]
    ]
):
    """
    Indexed list with extra options for people
    with a name index and identifier index.
    """

    def model_post_init(self, __context: dict[str, Any]):
        super().model_post_init(__context)
        self._name_to_id_lookups: dict[OrgDate, NameIndex] = {}

    def __iter__(self):
        return iter([x for x in self.root if isinstance(x, Person)])

    def redirects(self):
        return [x for x in self.root if isinstance(x, PersonRedirect)]

    def invalidate_indexes(self):
        super().invalidate_indexes()
        self._name_to_id_lookups = {}

    def from_identifier(self, identifer: str, *, scheme: str) -> Person:
        def lookup_identifier(person: Union[Person, PersonRedirect]) -> Optional[str]:
            if isinstance(person, PersonRedirect):
                return None
            identifer = person.identifiers.get(scheme)
            if identifer:
                return str(identifer.identifier)
            else:
                return None

        item = self.get_single_from_index(
            f"identifier_{scheme}", identifer, lookup_identifier
        )

        if isinstance(item, PersonRedirect):
            raise ValueError(f"Person {item.id} is a redirect")

        return item

    def __getitem__(self, key: str) -> Person:
        """
        Getitem will behave normally for a list if an int
        But a string will be treated as an id lookup
        """
        return super().__getitem__(key).self_or_redirect()

    def from_name(self, name: str, *, chamber_id: str, date: date) -> Optional[Person]:
        org_date = OrgDate(organization_id=chamber_id, date=date)
        if org_date not in self._name_to_id_lookups:
            self._name_to_id_lookups[org_date] = NameIndex.from_memberships(
                popolo=self.get_parent(), chamber_id=chamber_id, date=date
            )

        id = self._name_to_id_lookups[org_date].get_id_reduced(name)
        item = self.get(id) if id else None

        if isinstance(item, PersonRedirect):
            raise ValueError(f"Person {item.id} is a redirect")

        return item

    def merge_people(self, person1_id: str, person2_id: str):
        """
        Merge two people into one.

        Absorb memberships and names.
        Remove person 2 id and add a PersonRedirect
        """

        person1 = self[person1_id]
        person2 = self[person2_id]

        if person1 == person2:
            return self

        for n in person2.names:
            n.note = "Alternate"

        old_names = [str(x) for x in person1.names]
        person_2_names = [x for x in person2.names if str(x) not in old_names]

        person1.names.extend(person_2_names)

        old_identifiers = [str(x) for x in person1.identifiers]
        person_2_identifiers = [
            x for x in person2.identifiers if str(x) not in old_identifiers
        ]

        person2.identifiers.extend(person_2_identifiers)

        for m in person2.memberships():
            m.person_id = person1.id

        self.pop(person2.id)
        self.append(PersonRedirect(id=person2.id, redirect=person1.id))

        return self


def membership_discriminator(v: dict[str, Any]) -> str:
    if "redirect" in v or hasattr(v, "redirect"):
        return "redirect"
    return "membership"


class IndexedPersonIdentifierList(IndexedList[PersonIdentifier]):
    def revalidate(self, *, full: bool):
        """
        Revalidate unique and valid id rules
        """
        self.check_unique_id()

        # this is because we don't export not set
        # but things set on a list this far deep
        # don't get seen as set further up
        if self._parent:
            for field in self._parent.model_fields.keys():
                if getattr(self._parent, field) == self:
                    self._parent.__pydantic_fields_set__.add(field)


class IndexedMembershipList(
    IndexedList[
        Annotated[
            Union[
                Annotated[Membership, Tag("membership")],
                Annotated[MembershipRedirect, Tag("redirect")],
            ],
            Discriminator(membership_discriminator),
        ]
    ]
):
    def __getitem__(self, key: str) -> Membership:
        return super().__getitem__(key).self_or_redirect()

    def __iter__(self):
        return iter([x for x in self.root if isinstance(x, Membership)])

    def redirects(self):
        return [x for x in self.root if isinstance(x, MembershipRedirect)]


class Popolo(StrictBaseModel):
    """
    The overall Popolo object - connecting the common political data objects.
    """

    Chamber: ClassVar[Type[Chamber]] = Chamber
    IdentifierScheme: ClassVar[Type[IdentifierScheme]] = IdentifierScheme
    memberships: IndexedMembershipList = Field(default_factory=IndexedMembershipList)
    organizations: IndexedList[Organization] = Field(
        default_factory=IndexedList[Organization]
    )
    persons: IndexedPeopleList = Field(default_factory=IndexedPeopleList)
    posts: IndexedList[Post] = Field(default_factory=IndexedList[Post])

    def check_role_date_ranges(self, info: ValidationInfo) -> Popolo:
        """
        Within memberships, there should be no overlap between any instances that share a post_id
        e.g. seperated by post_id, sorted by start_date the end_date
        of one should be before the start_date of the next
        """

        if info and info.context:
            if info.context.get("skip_cross_checks") is True:
                return self

        errors: list[str] = []

        just_memberships = [
            m
            for m in self.memberships
            if (m.post_id or m.organization_id == Chamber.LORDS)
            and m.start_date > date.fromisoformat("1900-01-01")
        ]

        for _, group in groupby(
            sorted(
                just_memberships,
                key=lambda x: (
                    x.post_id or Chamber.LORDS,
                    x.person_id,
                    str(x.start_date),
                ),
            ),
            key=lambda x: (x.post_id or Chamber.LORDS, x.person_id),
        ):
            group = list(group)
            for i in range(1, len(group)):
                prev_date = group[i - 1].end_date
                this_date = group[i].start_date
                # only really care if both are real dates, if either approxdate
                # continue
                if isinstance(prev_date, ApproxDate) or isinstance(
                    this_date, ApproxDate
                ):
                    continue
                if prev_date >= this_date:
                    errors.append(
                        f"Membership {group[i-1].id} overlaps with {group[i].id}"
                    )

        if errors:
            raise ValueError(errors)

        return self

    pydantic_check_role_date_ranges = model_validator(mode="after")(
        check_role_date_ranges
    )

    def check_valid_ids_used(self, info: ValidationInfo) -> Popolo:
        """
        Check that references between different types of models refer to valid ids
        """

        if info and info.context:
            if info.context.get("skip_cross_checks") is True:
                return self

        person_ids = {p.id for p in self.persons}
        org_ids = {o.id for o in self.organizations}
        post_ids = {p.id for p in self.posts}

        just_memberships = [m for m in self.memberships]
        member_person_ids = {m.person_id for m in just_memberships if m.person_id}
        member_org_ids = {
            m.organization_id for m in just_memberships if m.organization_id
        }
        member_post_ids = {m.post_id for m in just_memberships if m.post_id}

        errors: list[str] = []

        # Check for invalid person IDs
        invalid_person_ids = member_person_ids - person_ids
        for invalid_id in invalid_person_ids:
            for member in just_memberships:
                if member.person_id == invalid_id:
                    errors.append(
                        f"Membership {member.id} refers to invalid person {invalid_id}"
                    )

        # Check for invalid organization IDs
        invalid_org_ids = member_org_ids - org_ids
        for invalid_id in invalid_org_ids:
            for member in just_memberships:
                if member.organization_id == invalid_id:
                    errors.append(
                        f"Membership {member.id} refers to invalid organization {invalid_id}"
                    )

        # Check for invalid post IDs
        invalid_post_ids = member_post_ids - post_ids
        for invalid_id in invalid_post_ids:
            for member in just_memberships:
                if member.post_id == invalid_id:
                    errors.append(
                        f"Membership {member.id} refers to invalid post {invalid_id}"
                    )

        # Check posts for invalid organization IDs
        invalid_post_orgs = {
            post.id: post.organization_id
            for post in self.posts
            if post.organization_id and post.organization_id not in org_ids
        }
        for post_id, org_id in invalid_post_orgs.items():
            errors.append(f"Post {post_id} refers to invalid organization {org_id}")

        if errors:
            raise ValueError("\n".join(errors))

        return self

    pydantic_check_unique_ids_used = model_validator(mode="after")(check_valid_ids_used)

    def model_post_init(self, __context: Any) -> None:
        self.memberships.set_parent(self)
        self.organizations.set_parent(self)
        self.persons.set_parent(self)
        self.posts.set_parent(self)

    @classmethod
    def from_json_str(cls, json_str: str, *, cross_validate: bool = True) -> Self:
        if cross_validate:
            return cls.model_validate_json(json_str)
        else:
            return cls.model_validate_json(
                json_str, context={"skip_cross_checks": True}
            )

    @classmethod
    def from_path(
        cls, json_path: Union[Path, list[Path]], cross_validate: bool = True
    ) -> Self:
        if isinstance(json_path, Path):
            json_path = [json_path]

        base = cls.from_json_str(
            json_path[0].read_text(), cross_validate=cross_validate
        )

        # Assume these are updates that may not be complete in themselves
        for u in json_path[1:]:
            base.update(cls.from_json_str(u.read_text(), cross_validate=False))

        return base

    @classmethod
    def from_url(
        cls, url: Union[str, list[str]], cross_validate: bool = True
    ) -> Popolo:
        if isinstance(url, str):
            url = [url]

        base = cls.from_json_str(
            requests.get(url[0]).text, cross_validate=cross_validate
        )

        # Assume these are updates that may not be complete in themselves
        for u in url[1:]:
            base.update(cls.from_json_str(requests.get(u).text, cross_validate=False))

        return base

    def update(self, other: Popolo) -> Popolo:
        """
        Add new items from another Popolo object to this one
        """
        self.organizations.extend(other.organizations.root)
        self.posts.extend(other.posts.root)
        self.persons.extend(other.persons.root)
        self.memberships.extend(other.memberships.root)

        return self

    @classmethod
    def from_parlparse(
        cls, *, extras: Optional[list[str]] = None, branch: str = "master"
    ) -> Popolo:
        url_format = "https://raw.githubusercontent.com/mysociety/parlparse/{branch}/members/{file}"

        urls = [url_format.format(branch=branch, file="people.json")]

        if extras:
            extras = [x + ".json" if not x.endswith(".json") else x for x in extras]
            urls.extend([url_format.format(branch=branch, file=f) for f in extras])

        return cls.from_url(urls)

    def to_json_str(self) -> str:
        txt = self.model_dump_json(
            indent=2,
            exclude_unset=True,
            exclude_defaults=False,
            exclude_none=True,
            by_alias=True,
        )
        return escape_unicode_characters(txt)

    def to_path(self, json_path: Path) -> None:
        data = self.to_json_str()
        json_path.write_text(data)
