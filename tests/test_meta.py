"""
Run meta tests on package (apply to muliple packages)

"""

from pathlib import Path
from typing import Literal

import mysoc_validator as package
import toml
from mysoc_validator.models.xml_base import AttrStr, BaseXMLModel, TextStr
from mysoc_validator.utils.parlparse.enum_helpers import StrEnum


class AnnotationRegressionModel(BaseXMLModel, tags=["annotation-regression"]):
    attribute: AttrStr
    text: TextStr
    literal: Literal["literal"] = "literal"


class AnnotationRegressionEnum(StrEnum):
    VALUE: str


def test_xml_model_meta_reads_deferred_annotations():
    """Verify xml model meta reads deferred annotations."""
    model = AnnotationRegressionModel.model_validate(
        {"@attribute": "attribute value", "@text": "text value"}
    )
    assert model.attribute == "attribute value"
    assert model.text == "text value"
    assert model.tag == "annotation-regression"


def test_typed_enum_meta_reads_deferred_annotations():
    """Verify typed enum meta reads deferred annotations."""
    assert AnnotationRegressionEnum.VALUE.value == "value"


def test_version_in_workflow():
    """
    Check if the current version is mentioned in the changelog
    """
    package_init_version = package.__version__
    path = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
    change_log = path.read_text()
    format = f"## [{package_init_version}]"
    assert format in change_log


def test_versions_are_in_sync():
    """Checks if the pyproject.toml and package.__init__.py __version__ are in sync."""

    path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = toml.loads(open(str(path), encoding="utf-8").read())
    pyproject_version = pyproject["tool"]["poetry"]["version"]

    package_init_version = package.__version__

    assert package_init_version == pyproject_version
