import datetime

from mysoc_validator import Transcript


def test_downloader_works():
    """Verify downloader works."""
    date = datetime.date(2024, 9, 5)
    t = Transcript.from_parlparse(date, chamber=Transcript.Chamber.COMMONS)
    assert t.items[0].tag == "oral-heading"


def test_downloader_scot():
    """Verify downloader scot."""
    date = datetime.date(2021, 9, 7)
    t = Transcript.from_parlparse(date, chamber=Transcript.Chamber.SCOTLAND)
    assert t.items[0].tag == "major-heading"


def test_downloader_senedd():
    """Verify downloader senedd."""
    date = datetime.date(2016, 5, 11)
    t = Transcript.from_parlparse(date, chamber=Transcript.Chamber.SENEDD)
    assert t.items[0].tag == "speech"


def test_downloader_ni():
    """Verify downloader ni."""
    date = datetime.date(2024, 6, 24)
    t = Transcript.from_parlparse(date, chamber=Transcript.Chamber.NORTHERN_IRELAND)
    assert t.items[0].tag == "speech"


def test_downloader_lords():
    """Verify downloader lords."""
    date = datetime.date(2024, 9, 5)
    t = Transcript.from_parlparse(date, chamber=Transcript.Chamber.LORDS)
    assert t.items[0].tag == "major-heading"
