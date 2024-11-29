"""
Here we're trying to solve a problem that pydantic loads from json very fast - but not from xml.
We also have an issue that mySociety XML formats are slightly atypyical as 'data storage' XMLs,
because they contain mixed content (text and tags) in the same element.

This approach is designed to take a string and return a string as this might be replaced
with a faster rust implementation in the future.

So we need a way to convert XML to json - in a way that is lightly tailored to the kind of XML and
data structures we have.

We do this by taking as parameters:

 - tag_as_attr: a list of tags that should be converted to attributes.
 - mixed_content: a list of tags that should be treated as mixed content.

A json representation of the XML is then produced, with the following rules:

- the tag name is added to a key called "@tag"
- normal attributes are added as keys with the same name as the attribute
- tag_as_attr tags are added as as a list with the same name as the tag, prefixed with "@"
- mixed_content tags have their text content extracted and added as a key called "@content"
  and with a key called "@raw" that contains the raw content of the tag, and a key called
  "@text" that contains the text content of the tag.
- children (not listed as attributes) are added to a key called "@children".
- if serializing a dict without a @tag property - the dict is stored as a string in the @text property.
- and the reverse of this when importing - if a @text property is a valid json string it is converted to a dict.
- if there is a key: value, the value is a str - this is seen as equivilient to a child of {"@tag": key, "@text": value}
The @ approach is used to avoid conflicts with normal data.

e.g.
```
<headertag attr1="value1" attr2="value2">
<item person_id="10001">
    <foo>value1</foo>
    <bar>This has <b>mixed content<b></bar>
    <bar>This also has <i>mixed content<i></bar>
</item>
```

Is prompted with
tag_as_attr = ["item.foo"]
mixed_content = ["bar"]

And we get:

```
{
    "@tag": "headertag",
    "attr1": "value1",
    "attr2": "value2",
    "@children": [
        {
            "@tag": "item",
            "person_id": "10001",
            "@foo": [
                "value1"
            ],
            "@children": [
                {
                    "@tag": "bar",
                    "@content": {
                        "@raw": "This has <b>mixed content<b>",
                        "@text": "This has mixed content",
                    },
                },
                {
                    "@tag": "bar",
                    "@content": {
                        "@raw": "This also has <i>mixed content<i>",
                        "@text": "This also has mixed content",
                    },
                },
            ],
        }
    ],
}"""

import json
from typing import Annotated, Any, Dict, List

from lxml import etree

# Quick alias to avoid the private typing error
EtreeElement = Annotated[etree._Element, None]  # type: ignore


def transfer_mixed_content(source: EtreeElement, target: EtreeElement) -> EtreeElement:
    """
    Mixed content is so fiddly - this scoops out the content of one element and puts it in another
    """
    if source.text:
        target.text = source.text

    for child in source:
        new_child = etree.SubElement(target, child.tag)
        new_child.text = child.text
        new_child.tail = child.tail
        for attrib_key, attrib_value in child.attrib.items():
            new_child.attrib[attrib_key] = attrib_value
        transfer_mixed_content(child, new_child)

    if source.tail:
        target.tail = source.tail

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
    if element.tail:
        content.append(element.tail)
    return "".join(content)


def array_overlap(a: list[str], b: list[str]) -> bool:
    """
    Check if two lists have any common elements
    """
    return bool(set(a) & set(b))


def element_to_dict(
    element: EtreeElement,
    tag_as_attr: List[str],
    mixed_content: List[str],
    parent_tag: str = "",
) -> Dict[str, Any]:
    """
    converts an etree element to a dictionary following the rules of this approach.
    """

    data: dict[str, Any] = {}
    # Add the tag name
    data["@tag"] = element.tag

    # Add the attributes
    for key, value in element.attrib.items():
        if isinstance(key, bytes):
            key = key.decode()
        if isinstance(value, bytes):
            value = value.decode()
        data[key] = value  # type: ignore

    sub_content: list[dict[str, Any]] = []
    used_tag_as_attr: list[str] = []

    if (
        f"{parent_tag}.*" in mixed_content or element.tag in mixed_content
    ):  # handle mixed content
        data["@content"] = {
            "@raw": get_inner_content(element),
            "@text": get_inner_content_str(element),
        }
    else:
        if element.text and element.text.strip():
            # this shouldn't really happen because it can't be depended on
            # but adding as @text so that a strict validation will fail.
            data["@text"] = element.text
        # in our data a mixed set of data is the end of the line.
        for child in element:
            if (
                f"{element.tag}.*" in tag_as_attr
                or f"{element.tag}.{child.tag}" in tag_as_attr
            ):
                element_name = f"@{child.tag}"
                used_tag_as_attr.append(element_name)
                if element_name not in data:
                    data[element_name] = []
                element_data = element_to_dict(
                    child, tag_as_attr, mixed_content, parent_tag=element.tag
                )
                data[element_name].append(element_data)
            else:
                sub_content.append(
                    element_to_dict(
                        child, tag_as_attr, mixed_content, parent_tag=element.tag
                    )
                )

    # Add children if present
    if sub_content:
        data["@children"] = sub_content

    return data


def xml_to_json(
    text: str, tag_as_attr: List[str] = [], mixed_content: List[str] = []
) -> str:
    # remove all new lines and indents
    text = "".join([x.lstrip() for x in text.split("\n")])
    bytes_text = text.encode()
    root = etree.fromstring(bytes_text)
    data = element_to_dict(root, tag_as_attr, mixed_content)
    return json.dumps(data)


def dict_to_etree(
    data: dict[str, Any], tag_as_attr: List[str] = [], mixed_content: List[str] = []
) -> EtreeElement:
    element = etree.Element(data["@tag"])
    for key, value in data.items():
        if not key.startswith("@"):
            if isinstance(value, (int, bool)):
                value = str(value).lower()
            if isinstance(value, dict):
                value = json.dumps(value)
            element.attrib[key] = value
        else:
            if key == "@tag":
                pass
            elif key == "@content":
                # we use the raw value to create the content of this element
                if isinstance(value, dict):
                    # construct an element from the raw content
                    content_element = etree.fromstring(
                        f"<root>{value['@raw']}</root>", parser=None
                    )
                    transfer_mixed_content(content_element, element)
                else:
                    raise ValueError("Content should be a dictionary")
            elif key == "@children":
                for child in value:
                    element.append(dict_to_etree(child, tag_as_attr, mixed_content))
            elif key == "@text":
                if isinstance(value, str):
                    element.text = value
                else:
                    raise ValueError("Text should be a string")
            else:
                for item_data in value:
                    if isinstance(item_data, dict) and "@tag" not in item_data:
                        item_data = {"@tag": key[1:], "@text": json.dumps(item_data)}
                    elif isinstance(item_data, str):
                        item_data = {"@tag": key[1:], "@text": item_data}
                    element.append(dict_to_etree(item_data, tag_as_attr, mixed_content))  # type: ignore

    return element


def json_to_xml(text: str, tag_as_attr: list[str], mixed_content: list[str]) -> str:
    # need to do this manually because the lxml version uses single quotes with twfy doesn't like!
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'

    data = json.loads(text)
    root = dict_to_etree(data, tag_as_attr, mixed_content)
    text = etree.tostring(root, pretty_print=True).decode()
    return xml_declaration + text
