from datetime import date
from pathlib import Path

from mysoc_validator.models.transcripts import Transcript


def test_transcript_load():
    Transcript.from_xml_path(Path("data", "debates2023-03-28d.xml"))


def test_transcript_date():
    Transcript.from_parlparse(
        date(2015, 1, 20),
        chamber=Transcript.Chamber.COMMONS,
        transcript_type=Transcript.TranscriptType.DEBATES,
    )


def test_transcript_round_trip():
    t = Transcript.from_xml_path(Path("data", "debates2023-03-28d.xml"))

    dumped_xml = t.model_dump_xml()

    t2 = Transcript.model_validate_xml(dumped_xml)

    dumped_xml_2 = t2.model_dump_xml()

    assert dumped_xml == dumped_xml_2
