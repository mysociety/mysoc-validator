from __future__ import annotations

import ast
import json
import sys
from enum import Enum
from pathlib import Path
from types import GenericAlias
from typing import (
    Annotated,
    Any,
    ClassVar,
    ForwardRef,
    Optional,
    TypeVar,
    cast,
    get_args,
    get_origin,
)
from typing import (
    Literal as Literal,
)
from typing import (
    Union as Union,
)

import requests
from pydantic import (
    AfterValidator,
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic._internal._generics import PydanticGenericMetadata
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.functional_serializers import WrapSerializer
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Self, dataclass_transform

from .xml_to_json import json_to_xml, xml_to_json


def str_from_xml_path(path: Path) -> str:
    """
    We need to pop open the file and get the first line to determine the encoding.
    e.g. <?xml version="1.0" encoding="UTF-8"?>
    Then read in as bytes and decode with the encoding.
    """
    with path.open("rb") as f:
        first_line = f.readline().decode()
        if "encoding=" not in first_line:
            encoding = "UTF-8"
        else:
            encoding = first_line.split("encoding=")[1].strip().strip('"')

    return path.read_text(encoding=encoding)


def extract_real_classes(annotation: Any) -> list[type]:
    """
    Extract all the real classes possible from a generic construct.
    e.g. Union[str, int] -> [str, int]
    Optional[list[dict[str, int]]] -> [str, int]
    """
    real_classes: list[type] = []

    # Check if the annotation is a generic type like Union, Optional, or list
    origin = get_origin(annotation)

    if origin is Union or origin is Optional or origin is list:
        # Recursively analyze the arguments inside the generic type
        for arg in get_args(annotation):
            real_classes.extend(extract_real_classes(arg))
    elif origin is Annotated:
        real_item = get_args(annotation)[0]
        real_classes.extend(extract_real_classes(real_item))
    else:
        # If it's not a generic type, it's a direct class
        real_classes.append(annotation)
    return real_classes


def convert_to_forward_refs(
    type_hint: str,
    local_scope: Optional[dict[str, Any]] = None,
    global_scope: Optional[dict[str, Any]] = None,
) -> Any:
    """
    Similar to pydantic behind the scenes, get
    objects from string typehints that fails to using forward refs.
    Allows access to global and local scope for resolving type hints.
    """
    if global_scope is None:
        global_scope = globals()
    if local_scope is None:
        local_scope = locals()

    def _convert_type(node: ast.AST) -> Any:
        if isinstance(node, ast.Subscript):
            value = _convert_type(node.value)
            slice_val = _convert_type(node.slice)
            return value[slice_val]
        elif isinstance(node, ast.Name):
            type_name = node.id
            try:
                return eval(type_name, global_scope, local_scope)
            except NameError:
                return ForwardRef(type_name)
        elif isinstance(node, ast.Attribute):
            value = _convert_type(node.value)
            return getattr(value, node.attr)
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Tuple):
            return tuple(_convert_type(elt) for elt in node.elts)
        elif isinstance(node, ast.List):
            return [_convert_type(elt) for elt in node.elts]
        elif isinstance(node, ast.Call):
            return None
        else:
            raise ValueError(f"Unsupported AST node type: {type(node)}")

    node: ast.AST = ast.parse(type_hint, mode="eval").body
    return _convert_type(node)


class XmlTypeMetaData(Enum):
    MIXED_CONTENT = "MIXED_CONTENT"
    XML_ATTR = "XML_ATTR"
    XML_TEXT = "XML_TEXT"
    XML_CHILDREN = "XML_CHILDREN"
    XML_TAG = "XML_TAG"


def xml_alias(field_name: str, xml_field: str):
    """
    Shortcut for creating a field with an alias for XML serialization and validation.
    """
    return Field(
        validation_alias=AliasChoices(field_name, xml_field),
        serialization_alias=xml_field,
    )


class MixedContentHolder(BaseModel):
    text: str = xml_alias("text", "@text")
    raw: str = xml_alias("raw", "@raw")


@dataclass_transform(kw_only_default=True)
class XMLModelMeta(ModelMetaclass):
    __register__: dict[str, dict[str, Any]] = {}

    def __new__(
        mcs,
        cls_name: str,
        bases: tuple[type[Any], ...],
        namespace: dict[str, Any],
        __pydantic_generic_metadata__: PydanticGenericMetadata | None = None,
        __pydantic_reset_parent_namespace__: bool = True,
        _create_model_module: str | None = None,
        tags: Optional[list[str]] = None,
        abstract_level: int = 1,
        **kwargs: Any,
    ) -> type:
        # from where the class is being defined
        caller_globals = sys._getframe(abstract_level).f_globals  # type: ignore
        # merge caller_globals with current globals
        caller_globals = {**caller_globals, **globals()}

        # add tag field based on class attribute
        if "tag" in namespace and tags:
            raise AttributeError("Cannot have both tag field and tags attributes")
        if "__annotations__" not in namespace:
            namespace["__annotations__"] = {}
        namespace["__as_attr__"] = []
        namespace["__mixed_content__"] = []
        if tags:
            namespace["__xml_tags__"] = tags
            if any(["*" in x for x in tags]):
                namespace["tag"] = Field(
                    validation_alias=AliasChoices("tag", "@tag"),
                    serialization_alias="@tag",
                )
                namespace["__annotations__"]["tag"] = str
            else:
                namespace["tag"] = Field(
                    default=tags[0],
                    validation_alias=AliasChoices("tag", "@tag"),
                    serialization_alias="@tag",
                )
                namespace["__annotations__"]["tag"] = (
                    f'Literal[{", ".join([f"{tag!r}" for tag in tags])}]'
                )

        # add special XML fields based on metadata
        for key, value in namespace.get("__annotations__", {}).items():
            if isinstance(value, str):
                local_scope = {**locals(), **caller_globals}
                value = convert_to_forward_refs(value, local_scope=local_scope)
            if key not in namespace and get_origin(value) is Annotated:
                item, *metadata = get_args(value)
                if XmlTypeMetaData.XML_ATTR in metadata:
                    real_classes = [
                        x for x in extract_real_classes(item) if x is not type(None)
                    ]
                    if len(real_classes) == 1 and hasattr(
                        real_classes[0], "__xml_tags__"
                    ):
                        eval_subclass_tag = real_classes[0].__xml_tags__[0]  # type: ignore
                    else:
                        eval_subclass_tag = key
                    if key in namespace:
                        raise AttributeError(
                            f"Cannot have both {key} field and XML_ATTR metadata"
                        )
                    namespace[key] = Field(
                        validation_alias=AliasChoices(key, f"@{eval_subclass_tag}"),
                        serialization_alias=f"@{eval_subclass_tag}",
                    )
                if XmlTypeMetaData.MIXED_CONTENT in metadata:
                    namespace[key] = Field(
                        validation_alias=AliasChoices(key, "@content"),
                        serialization_alias="@content",
                    )
                if XmlTypeMetaData.XML_CHILDREN in metadata:
                    namespace[key] = Field(
                        validation_alias=AliasChoices(key, "@children"),
                        serialization_alias="@children",
                    )
                if XmlTypeMetaData.XML_TEXT in metadata:
                    namespace[key] = Field(
                        validation_alias=AliasChoices(key, "@text"),
                        serialization_alias="@text",
                    )
        new_cls = super().__new__(
            mcs,
            cls_name,
            bases,
            namespace,
            __pydantic_generic_metadata__,
            __pydantic_reset_parent_namespace__,
            _create_model_module,
            **kwargs,
        )
        new_cls.set_xml_options()  # type: ignore
        return new_cls


class BaseXMLModel(BaseModel, metaclass=XMLModelMeta):
    __xml_tags__: ClassVar[list[str]]
    __as_attr__: ClassVar[list[str]]
    __mixed_content__: ClassVar[list[str]]
    __as_children__: ClassVar[list[str]] = []
    tag: str = ""

    @model_validator(mode="after")
    def set_tag_if_default(self):
        self.tag = self.tag
        return self

    @field_validator("tag")
    @classmethod
    def check_tag(cls, value: Optional[str]):
        if not isinstance(value, str):
            literal_list = cls.model_fields["name"].annotation
            options = list(get_args(literal_list))
            return options[0]
        return value

    @classmethod
    def set_xml_options(cls):
        for field, data in cls.model_fields.items():
            if XmlTypeMetaData.MIXED_CONTENT in data.metadata:
                cls.__mixed_content__.extend(cls.__xml_tags__)
            elif XmlTypeMetaData.XML_ATTR in data.metadata:
                for real_class in extract_real_classes(data.annotation):
                    if isinstance(real_class, GenericAlias):
                        # this is so dictionaries can just be injected as content
                        for our_tag in cls.__xml_tags__:
                            cls.__as_attr__.append(f"{our_tag}.{field}")
                    elif isinstance(real_class, type) and issubclass(
                        real_class, BaseXMLModel
                    ):
                        listed_tags = real_class.__xml_tags__
                        # for all of our tags and all of listed tags, construct a.b strings.
                        for our_tag in cls.__xml_tags__:
                            for listed_tag in listed_tags:
                                if "." not in listed_tag:
                                    cls.__as_attr__.append(f"{our_tag}.{listed_tag}")
                                else:
                                    cls.__as_attr__.append(listed_tag)
                    elif real_class is type(None):
                        pass
                    else:
                        for our_tag in cls.__xml_tags__:
                            cls.__as_attr__.append(f"{our_tag}.{field}")
            elif XmlTypeMetaData.XML_CHILDREN in data.metadata:
                cls.__as_children__.append(field)

            # recursively get the tags from the sub classes
            for sub_class in extract_real_classes(data.annotation):
                if hasattr(sub_class, "__as_attr__"):
                    cls.__as_attr__.extend(sub_class.__as_attr__)  # type: ignore
                    cls.__mixed_content__.extend(sub_class.__mixed_content__)  # type: ignore
        # remove duplicates
        cls.__as_attr__ = list(set(cls.__as_attr__))
        cls.__mixed_content__ = list(set(cls.__mixed_content__))

    @classmethod
    def model_validate_xml(cls, text: str):
        json_str = xml_to_json(text, cls.__as_attr__, cls.__mixed_content__)
        return cls.model_validate_json(json_str)

    @classmethod
    def model_construct_xml(cls, text: str):
        json_str = xml_to_json(text, cls.__as_attr__, cls.__mixed_content__)
        return cls.model_construct_json(json_str)

    @classmethod
    def model_construct_json(cls, json_str: str):
        objs = json.loads(json_str)
        return cls.model_construct(objs)

    @classmethod
    def from_xml_url(cls, url: str):
        content = requests.get(url).text
        return cls.model_validate_xml(content)

    @classmethod
    def from_xml_path(
        cls, path: Path, extra: Optional[Literal["forbid", "allow", "ignore"]] = None
    ) -> Self:
        if extra is None:
            return cls.model_validate_xml(str_from_xml_path(path))

        class LessValidatedXMLModel(cls):
            model_config = ConfigDict(extra=extra)

        LessValidatedXMLModel.__name__ = cls.__name__
        model = LessValidatedXMLModel.model_validate_xml(str_from_xml_path(path))
        model = cast(cls, model)
        return model

    def model_dump_xml(self):
        return json_to_xml(
            self.model_dump_json(
                by_alias=True,
                exclude_unset=True,
                exclude_defaults=False,
                exclude_none=True,
            ),
            self.__class__.__as_attr__,
            self.__class__.__mixed_content__,
        )

    def to_xml_path(self, path: Path):
        path.write_text(self.model_dump_xml())


class StrictBaseXMLModel(BaseXMLModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


T = TypeVar("T", bound=BaseXMLModel)
A = TypeVar("A")

Tag = Annotated[
    A,
    xml_alias("tag", "@tag"),
    XmlTypeMetaData.XML_TAG,
]


def single_item_list(items: Union[list[T], T]) -> T:
    if not isinstance(items, list):
        return items

    if len(items) != 1:
        raise ValidationError("Expected a single item list")
    return items[0]


def convert_to_single_item_list(value: Any, handler: Any, info: Any):
    return [handler(value, info)]


def escape_stored_dict(v: dict[Any, Any]) -> dict[Any, Any]:
    if "@text" in v:
        return json.loads(v["@text"])
    return v


def escape_stored_dict_str(v: Union[dict[Any, Any], str]) -> str:
    if isinstance(v, list):
        if len(v) > 1:
            raise ValueError("Expected a single item list")
        v = v[0]
    if isinstance(v, dict):
        if "@text" in v:
            return str(v["@text"])
    if isinstance(v, str):
        return v
    else:
        raise ValueError("Expected a dictionary or string")


AttrStr = Annotated[str, XmlTypeMetaData.XML_ATTR]
MixedContent = Annotated[
    MixedContentHolder,
    XmlTypeMetaData.MIXED_CONTENT,
]
TextStr = Annotated[
    str,
    XmlTypeMetaData.XML_TEXT,
]
AsAttrSingle = Annotated[
    A,
    BeforeValidator(single_item_list),
    WrapSerializer(convert_to_single_item_list),
    XmlTypeMetaData.XML_ATTR,
]
XMLDict = Annotated[
    dict[Any, Any],
    BeforeValidator(single_item_list),
    WrapSerializer(convert_to_single_item_list),
    AfterValidator(escape_stored_dict),
    XmlTypeMetaData.XML_ATTR,
]
AsAttrStr = Annotated[
    str,
    XmlTypeMetaData.XML_ATTR,
    BeforeValidator(single_item_list),
    BeforeValidator(escape_stored_dict_str),
    WrapSerializer(convert_to_single_item_list),
]
AsAttr = Annotated[
    A,
    XmlTypeMetaData.XML_ATTR,
]
Items = Annotated[
    list[T],
    XmlTypeMetaData.XML_CHILDREN,
]
