from mysoc_validator import (
    Popolo,
    RegmemRegister,
    XMLRegister,
    Transcript,
    InfoCollection,
)
import json
from pydantic import BaseModel
import jsonschema2md  # type: ignore
from pathlib import Path

schema_folder = Path(__file__).parents[2] / "schemas"

parser = jsonschema2md.Parser(examples_as_yaml=False)


def write_schemas(type: type[BaseModel]):
    schema = type.model_json_schema()
    markdown = "".join(parser.parse_schema(schema))  # type: ignore
    title = schema["title"]
    slug = title.lower().replace(" ", "_")

    with open(schema_folder / f"{slug}.md", "w") as f:
        f.write(markdown)

    with open(schema_folder / f"{slug}.json", "w") as f:
        json.dump(schema, f, indent=2)


def dump_models():
    write_schemas(Popolo)
    write_schemas(RegmemRegister)
    write_schemas(XMLRegister)
    write_schemas(Transcript)
    write_schemas(InfoCollection)


if __name__ == "__main__":
    dump_models()
