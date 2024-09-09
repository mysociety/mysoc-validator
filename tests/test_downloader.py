import datetime

from mysoc_validator import Transcript


def test_downloader_works():
    date = datetime.date(2024, 9, 5)
    t = Transcript.from_parlparse(date, chamber=Transcript.Chamber.COMMONS)
    assert t.items[0].tag == "oral-heading"
