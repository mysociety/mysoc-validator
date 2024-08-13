from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Optional,
    Type,
    _AnnotatedAlias,  # type: ignore
    _UnionGenericAlias,  # type: ignore
    get_args,
    get_origin,
    get_type_hints,
)
from xml.dom import minidom

from lxml import etree
from pydantic import BaseModel
from typing_extensions import Self

NoneType = type(None)


class XmlTypeMetaData(Enum):
    ItemContents = "ItemContents"
    XMLItemContents = "XMLItemContents"
    XMLTag = "XMLTag"
    ReadOnly = "ReadOnly"


StrItemContents = Annotated[str, XmlTypeMetaData.ItemContents]
StrItemContentsReadOnly = Annotated[
    str, XmlTypeMetaData.ItemContents, XmlTypeMetaData.ReadOnly
]
XMLItemContents = Annotated[str, XmlTypeMetaData.XMLItemContents]
StrXMLTag = Annotated[str, XmlTypeMetaData.XMLTag]

# Quick alias to avoid the private typing error
EtreeElement = Annotated[etree._Element, None]  # type: ignore


def get_meta_data(item: Any) -> tuple[Any]:
    return get_args(item)[1:] if isinstance(item, _AnnotatedAlias) else tuple()


def transfer_mixed_content(source: EtreeElement, target: EtreeElement) -> EtreeElement:
    if source.text:
        target.text = source.text  # type: ignore

    for child in source:  # type: ignore
        new_child = etree.SubElement(target, child.tag)  # type: ignore
        new_child.text = child.text
        new_child.tail = child.tail

    if source.tail:
        target.tail = source.tail  # type: ignore

    return target


def get_inner_content(element: EtreeElement):
    """
    Get the mixed contents of an xml element as a string
    """
    element_string = etree.tostring(element)
    start = element_string.index(b">") + 1
    end = element_string.rindex(b"<")
    return element_string[start:end].decode()


def get_inner_content_str(element: EtreeElement):
    """
    Get the mixed contents of an xml element as a string - but extracting the contents of
    the children as strings
    """

    content: list[str] = []
    if element.text:
        content.append(element.text)
    for child in element.iterchildren(tag=None):
        content.append(get_inner_content_str(child))
        if child.tail:
            content.append(child.tail)
    return "".join(content)


class BaseXMLModel(BaseModel):
    @classmethod
    def __init_subclass__(cls, tag: Optional[str | list[str]] = None) -> None:
        if tag is None:
            tag = [cls.__name__.lower()]
        if isinstance(tag, str):
            tag = [tag]
        cls.__tag_alias = tag

    @classmethod
    def from_path(cls: Type[Self], path: Path) -> Self:
        return cls.from_xml(path.read_bytes())

    @classmethod
    def from_xml(cls: Type[Self], contents: bytes) -> Self:
        root = etree.fromstring(contents, parser=None)
        return cls.from_xml_tree(root)

    @classmethod
    def from_xml_tree(cls: Type[Self], etree_element: EtreeElement) -> Self:
        attrs = dict(etree_element.attrib)
        for field_name, annotation in get_type_hints(cls, include_extras=True).items():
            # Get the metadata item out
            meta_data = get_meta_data(annotation)
            if NoneType in get_args(annotation):
                # assume for the moment we're only using Optional for attributes
                # I think the approach would be go replace annotation
                # with the first type in get_args(annotation) if it's Optional
                continue

            if XmlTypeMetaData.ItemContents in meta_data:
                attrs[field_name] = get_inner_content_str(etree_element)
            elif XmlTypeMetaData.XMLItemContents in meta_data:
                attrs[field_name] = get_inner_content(etree_element)
            elif XmlTypeMetaData.XMLTag in meta_data:
                attrs[field_name] = etree_element.tag

            elif get_origin(annotation) is list:
                # if annotation is a list of a child of BaseXMLModel,
                # we want to iterate through all the children of that type, convert them, and add them to the attrs
                child_type = get_args(annotation)[0]
                if isinstance(child_type, type) and issubclass(
                    child_type, BaseXMLModel
                ):
                    attrs[field_name] = [  # type: ignore
                        child_type.from_xml_tree(child)
                        for child in etree_element.iterchildren(
                            tag=None,
                        )
                        if child.tag in child_type.__tag_alias
                        or "*" in child_type.__tag_alias
                    ]
                elif isinstance(child_type, _UnionGenericAlias):
                    lookup_class = {}
                    for x in get_args(child_type):
                        if issubclass(x, BaseXMLModel):
                            for tag in x.__tag_alias:
                                lookup_class[tag] = x
                    attrs[field_name] = [  # type: ignore
                        lookup_class[child.tag].from_xml_tree(child)  # type: ignore
                        for child in etree_element.iterchildren(tag=None)
                    ]
            elif isinstance(annotation, type) and issubclass(annotation, BaseXMLModel):
                # if annotation is one child of BaseXMLModel
                # we want to find the one instance of that type, convert it, and add it to the attrs
                for child in etree_element.iterchildren(tag=None):
                    if child.tag in annotation.__tag_alias:
                        attrs[field_name] = annotation.from_xml_tree(child)  # type: ignore
                        break

        return cls(**attrs)  # type: ignore

    @classmethod
    @lru_cache
    def to_xml_helper(cls):  # type: ignore
        field_lookup = {}

        def sub_element(element: EtreeElement, value: BaseXMLModel):
            element.append(value.to_xml())

        def text_element(element: EtreeElement, value: str):
            element.text = value  # type: ignore

        def tag_element(element: EtreeElement, value: str):
            element.tag = value  # type: ignore

        def null_element(element: EtreeElement, value: Any):
            pass

        def xml_element(element: EtreeElement, value: str):
            parsed = etree.fromstring(f"<root>{value}</root>", parser=None)
            transfer_mixed_content(parsed, element)

        def list_sub_element(element: EtreeElement, value: list[BaseXMLModel]):
            for item in value:
                if isinstance(item, BaseXMLModel):  # type: ignore
                    element.append(item.to_xml())
                else:
                    raise ValueError(
                        "Lists of non children of BaseXMLModel not supported"
                    )

        class AttribCall:
            def __init__(self, serial_name: str):
                self.serial_name = str(serial_name)

            def __call__(self, element: EtreeElement, value: Any):
                if value is True:
                    value = "true"
                elif value is False:
                    value = "false"
                elif isinstance(value, int):
                    value = str(value)
                elif value is None:
                    return
                element.attrib[self.serial_name] = value

        for field_name, annotation in get_type_hints(cls, include_extras=True).items():
            # Get the metadata item out
            annotation_metadata = get_meta_data(annotation)

            if XmlTypeMetaData.ReadOnly in annotation_metadata:
                field_lookup[field_name] = null_element
            elif XmlTypeMetaData.ItemContents in annotation_metadata:
                field_lookup[field_name] = text_element
            elif XmlTypeMetaData.XMLTag in annotation_metadata:
                field_lookup[field_name] = tag_element
            elif XmlTypeMetaData.XMLItemContents in annotation_metadata:
                field_lookup[field_name] = xml_element
            elif get_origin(annotation) is list:
                field_lookup[field_name] = list_sub_element
            elif (
                NoneType not in get_args(annotation)
                and isinstance(annotation, type)
                and issubclass(annotation, BaseXMLModel)
            ):
                field_lookup[field_name] = sub_element
            else:
                serial_name = (
                    cls.model_fields[field_name].serialization_alias or field_name
                )

                field_lookup[field_name] = AttribCall(serial_name)

        return field_lookup  # type: ignore

    def to_xml(self) -> EtreeElement:
        tag = None
        if len(self.__tag_alias) == 1 and "*" not in self.__tag_alias:
            tag = self.__tag_alias[0]
        else:
            tag = "temp"

        element = etree.Element(tag, attrib=None, nsmap=None)

        for field_name, func in self.__class__.to_xml_helper().items():  # type: ignore
            value = getattr(self, field_name)  # type: ignore
            func(element, value)

        return element

    def to_xml_path(self, path: Path) -> None:
        element = self.to_xml()
        text = etree.tostring(element)
        parsed_string = minidom.parseString(text)
        pretty_string = parsed_string.toprettyxml(indent="  ")
        path.write_text(pretty_string)
