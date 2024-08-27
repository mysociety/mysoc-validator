from pathlib import Path

from mysoc_validator.models.interests import Register


def test_interests_load():
    Register.from_xml_path(Path("data", "regmem2024-05-28.xml"))


def test_interests_round_trip():
    t = Register.from_xml_path(Path("data", "regmem2024-05-28.xml"))

    dumped_xml = t.model_dump_xml()

    t2 = Register.model_validate_xml(dumped_xml)

    dumped_xml_2 = t2.model_dump_xml()

    assert dumped_xml == dumped_xml_2
