from datetime import date
from pathlib import Path

from mysoc_validator.models.transcripts import (
    MajorHeading,
    MinorHeading,
    Question,
    Reply,
    Source,
    Transcript,
)

SP_WRITTEN_ANSWERS_PATH = Path("data", "spwa1999-06-17.xml")
UK_WRITTEN_ANSWERS_PATH = Path("data", "answers2026-02-23.xml")


def test_transcript_load():
    t = Transcript.from_xml_path(Path("data", "debates2023-03-28d.xml"))

    assert len(t.items) > 0


def test_transcript_date():
    t = Transcript.from_parlparse(
        date(2015, 1, 20),
        chamber=Transcript.Chamber.COMMONS,
        transcript_type=Transcript.TranscriptType.DEBATES,
    )

    assert len(t.items) > 0


def test_transcript_round_trip():
    t = Transcript.from_xml_path(Path("data", "debates2023-03-28d.xml"))

    dumped_xml = t.model_dump_xml()

    t2 = Transcript.model_validate_xml(dumped_xml)

    dumped_xml_2 = t2.model_dump_xml()

    assert dumped_xml == dumped_xml_2


def test_sp_written_answers_load():
    t = Transcript.from_xml_path(SP_WRITTEN_ANSWERS_PATH)
    assert len(t.items) > 0


def test_sp_written_answers_item_types():
    t = Transcript.from_xml_path(SP_WRITTEN_ANSWERS_PATH)
    types = [type(item).__name__ for item in t.items[:9]]
    assert types == [
        "Source",
        "MajorHeading",
        "MajorHeading",
        "MajorHeading",
        "MinorHeading",
        "Question",
        "Reply",
        "MinorHeading",
        "Question",
    ]


def test_sp_written_answers_source():
    t = Transcript.from_xml_path(SP_WRITTEN_ANSWERS_PATH)
    source = t.items[0]
    assert isinstance(source, Source)
    assert (
        source.url == "http://www.scottish.parliament.uk/business/pqa/wa-99/wa0617.htm"
    )


def test_sp_written_answers_major_heading():
    t = Transcript.from_xml_path(SP_WRITTEN_ANSWERS_PATH)
    heading = t.items[1]
    assert isinstance(heading, MajorHeading)
    assert str(heading) == "Scottish Parliament"
    assert heading.id == "uk.org.publicwhip/spwa/1999-06-17.0.mh"
    assert heading.nospeaker == "True"


def test_sp_written_answers_minor_heading():
    t = Transcript.from_xml_path(SP_WRITTEN_ANSWERS_PATH)
    heading = t.items[4]
    assert isinstance(heading, MinorHeading)
    assert str(heading) == "Community Care"
    assert heading.id == "uk.org.publicwhip/spwa/1999-06-17.S1W-131.h"


def test_sp_written_answers_question():
    t = Transcript.from_xml_path(SP_WRITTEN_ANSWERS_PATH)
    ques = t.items[5]
    assert isinstance(ques, Question)
    assert ques.id == "uk.org.publicwhip/spwa/1999-06-17.S1W-131.q0"
    assert ques.member_id == "uk.org.publicwhip/member/80197"
    assert ques.speakername == "Michael Matheson (Central Scotland) (SNP)"
    assert ques.spid == "S1W-131"
    assert len(ques.items) == 1
    assert "mental incapacity" in str(ques)


def test_sp_written_answers_reply():
    t = Transcript.from_xml_path(SP_WRITTEN_ANSWERS_PATH)
    reply = t.items[6]
    assert isinstance(reply, Reply)
    assert reply.id == "uk.org.publicwhip/spwa/1999-06-17.S1W-131.r0"
    assert reply.member_id == "uk.org.publicwhip/member/80167"
    assert reply.speakername == "Iain Gray"
    assert len(reply.items) == 1
    assert "Incapable Adults Bill" in str(reply)


def test_sp_written_answers_round_trip():
    t = Transcript.from_xml_path(SP_WRITTEN_ANSWERS_PATH)
    dumped_xml = t.model_dump_xml()
    t2 = Transcript.model_validate_xml(dumped_xml)
    dumped_xml_2 = t2.model_dump_xml()
    assert dumped_xml == dumped_xml_2


def test_sp_written_answers_file_load():
    """Validate the full SP written answers file from data dir."""
    t = Transcript.from_xml_path(SP_WRITTEN_ANSWERS_PATH)
    assert len(t.items) > 0

    sources = [item for item in t.items if isinstance(item, Source)]
    assert len(sources) == 1

    questions = [item for item in t.items if isinstance(item, Question)]
    assert len(questions) > 0
    for q in questions:
        assert q.member_id is not None
        assert q.speakername is not None

    replies = [item for item in t.items if isinstance(item, Reply)]
    assert len(replies) > 0


def test_sp_written_answers_file_round_trip():
    """Round-trip the full SP written answers file."""
    t = Transcript.from_xml_path(SP_WRITTEN_ANSWERS_PATH)
    dumped_xml = t.model_dump_xml()
    t2 = Transcript.model_validate_xml(dumped_xml)
    dumped_xml_2 = t2.model_dump_xml()
    assert dumped_xml == dumped_xml_2


def test_uk_written_answers_file_load():
    """Validate the UK written answers file from data dir."""
    t = Transcript.from_xml_path(UK_WRITTEN_ANSWERS_PATH)
    assert len(t.items) > 0

    questions = [item for item in t.items if isinstance(item, Question)]
    assert len(questions) > 0
    for q in questions:
        assert q.person_id is not None
        assert q.speakername is not None

    replies = [item for item in t.items if isinstance(item, Reply)]
    assert len(replies) > 0


def test_uk_written_answers_file_round_trip():
    """Round-trip the UK written answers file."""
    t = Transcript.from_xml_path(UK_WRITTEN_ANSWERS_PATH)
    dumped_xml = t.model_dump_xml()
    t2 = Transcript.model_validate_xml(dumped_xml)
    dumped_xml_2 = t2.model_dump_xml()
    assert dumped_xml == dumped_xml_2
