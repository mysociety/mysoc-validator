import json

from pydantic import BaseModel

import mysoc_validator.generate_model_descriptions as descriptions


class ExampleSchema(BaseModel):
    name: str


def test_write_schemas_emits_matching_markdown_and_json(monkeypatch, tmp_path):
    """Verify write schemas emits matching markdown and json."""
    monkeypatch.setattr(descriptions, "schema_folder", tmp_path)

    descriptions.write_schemas(ExampleSchema)

    schema = json.loads((tmp_path / "exampleschema.json").read_text())
    markdown = (tmp_path / "exampleschema.md").read_text()
    assert schema == ExampleSchema.model_json_schema()
    assert "ExampleSchema" in markdown
    assert "name" in markdown


def test_dump_models_includes_every_documented_top_level_format(monkeypatch):
    """Verify dump models includes every documented top level format."""
    calls = []
    monkeypatch.setattr(descriptions, "write_schemas", calls.append)

    descriptions.dump_models()

    assert calls == [
        descriptions.Popolo,
        descriptions.RegmemRegister,
        descriptions.XMLRegister,
        descriptions.Transcript,
        descriptions.InfoCollection,
    ]
