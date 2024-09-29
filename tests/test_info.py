import pytest
from mysoc_validator import ConsInfo, InfoCollection, PersonInfo
from pydantic import ValidationError


class SocialInfo(PersonInfo):
    facebook_page: str | None = None
    twitter_username: str | None = None


class SocialInfoMissingField(PersonInfo):
    twitter_username: str | None = None


def test_person_info_validates():
    info = InfoCollection[PersonInfo].from_parlparse("social-media-commons")
    assert len(info.items) > 0


def test_subclassed_info_validates():
    info = InfoCollection[SocialInfo].from_parlparse("social-media-commons")
    assert len(info.items) > 0


def test_subclassed_info_missing_field():
    with pytest.raises(ValidationError):
        InfoCollection[SocialInfoMissingField].from_parlparse("social-media-commons")


def test_cons_info_validates():
    info = InfoCollection[ConsInfo].from_parlparse("constituency-links")
    assert len(info.items) > 0
