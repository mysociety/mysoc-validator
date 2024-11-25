import asyncio
import datetime
import re
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Optional

import httpx
import nest_asyncio  # type: ignore
from pydantic import BaseModel

from ...models.consts import TranscriptType
from ...models.popolo import Chamber
from .enum_helpers import MiniEnum

nest_asyncio.apply()  # type: ignore


def get_user_agent():
    from ... import __version__

    return f"mysoc_validator/{__version__}"


def persistent_download_path():
    return Path(tempfile.gettempdir()) / "parlparse_xmls"


@lru_cache
def get_xmls_from_index(index_url: str) -> list[str]:
    content = httpx.get(index_url).text
    xml_links = re.findall(r'<a href="([^"]+\.xml)">', content)
    return [link for link in xml_links]


def get_scot_debate_xmls(debate_date: datetime.date) -> Optional[str]:
    scot_debate_index = "https://www.theyworkforyou.com/pwdata/scrapedxml/sp-new/meeting-of-the-parliament/"
    links = get_xmls_from_index(scot_debate_index)
    debate_str = debate_date.isoformat()
    matches = [link for link in links if debate_str in link]
    matches.sort()
    if matches:
        return scot_debate_index + matches[-1]
    else:
        return None


class XMLManager(BaseModel):
    twfy_base_url: ClassVar[str] = "https://www.theyworkforyou.com/pwdata/"
    letter_options: ClassVar[list[str]] = [
        "",
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
    ]
    label: str
    relative_path: str
    file_structure_pre_date: str
    transcript_type: TranscriptType
    chamber_type: Chamber

    def construct_path(
        self,
        date: datetime.date,
        letter: str = "",
        download_path: Optional[Path] = None,
    ):
        if not download_path:
            download_path = persistent_download_path()
        download_path.mkdir(parents=True, exist_ok=True)
        file_name = f"{self.file_structure_pre_date}{date.isoformat()}{letter}.xml"
        return download_path / self.relative_path / file_name

    def construct_url(self, date: datetime.date, letter: str = ""):
        return f"{self.twfy_base_url}{self.relative_path}{self.file_structure_pre_date}{date.isoformat()}{letter}.xml"

    def download_for_date(
        self, date: datetime.date, download_path: Optional[Path] = None
    ) -> Path:
        if self.transcript_type != TranscriptType.DEBATES:
            raise ValueError("Only debates are supported at this time.")

        if not download_path:
            download_path = persistent_download_path()
        download_path.mkdir(parents=True, exist_ok=True)
        all_urls = [self.construct_url(date, letter) for letter in self.letter_options]
        valid_urls = check_urls_exist(all_urls)
        if not valid_urls:
            raise FileNotFoundError(f"No files found for {date}")
        valid_urls.sort()
        latest_url = valid_urls[-1]
        # download file to download_path
        base_path = self.construct_path(date, download_path=download_path)
        # need to figure out the file name of the url
        url_file_name = latest_url.split("/")[-1]
        file_path = base_path.parent / url_file_name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": get_user_agent()}
        response = httpx.get(latest_url, headers=headers)
        file_path.write_text(response.text)
        return file_path

    def get_latest_for_date_scot(
        self,
        date: datetime.date,
        download_path: Optional[Path] = None,
        *,
        force_download: bool = False,
    ) -> Path:
        if self.transcript_type != TranscriptType.DEBATES:
            raise ValueError("Only debates are supported for scottish parliament")

        date_iso = date.isoformat()

        download_path = download_path or persistent_download_path()
        existing = list(download_path.glob(f"*{date_iso}*.xml"))

        if existing and not force_download:
            existing.sort()
            return existing[-1]

        url = get_scot_debate_xmls(date)
        if not url:
            raise FileNotFoundError(f"No files found for {date}")

        # get the file name from the url
        file_name = url.split("/")[-1]

        if not download_path:
            download_path = persistent_download_path()

        file_path = download_path / file_name

        headers = {"User-Agent": get_user_agent()}
        response = httpx.get(url, headers=headers)
        file_path.write_text(response.text)
        return file_path

    def get_latest_for_date(
        self,
        date: datetime.date,
        download_path: Optional[Path] = None,
        *,
        force_download: bool = False,
    ) -> Path:
        if self.chamber_type == Chamber.SCOTLAND:
            return self.get_latest_for_date_scot(
                date, download_path=download_path, force_download=force_download
            )
        get_local = [
            self.construct_path(date, letter, download_path)
            for letter in self.letter_options
        ]
        # limit down to just those that exist
        existing = [x for x in get_local if x.exists()]
        if existing and not force_download:
            # sort and return the latest
            existing.sort()
            return existing[-1]
        else:
            return self.download_for_date(date, download_path=download_path)


class TranscriptXMl(MiniEnum[XMLManager]):
    UK_COMMONS_DEBATES = XMLManager(
        label="uk_commons_debates",
        relative_path="scrapedxml/debates/",
        file_structure_pre_date="debates",
        transcript_type=TranscriptType.DEBATES,
        chamber_type=Chamber.COMMONS,
    )
    UK_LORDS_DEBATES = XMLManager(
        label="uk_lords_debates",
        relative_path="scrapedxml/lordspages/",
        file_structure_pre_date="daylord",
        transcript_type=TranscriptType.DEBATES,
        chamber_type=Chamber.LORDS,
    )
    SCOTTISH_PARLIAMENT_DEBATES = XMLManager(
        label="scottish_parliament_debates",
        relative_path="scrapedxml/sp-new/meeting-of-the-parliament/",
        file_structure_pre_date="",
        transcript_type=TranscriptType.DEBATES,
        chamber_type=Chamber.SCOTLAND,
    )
    WELSH_SENEDD_DEBATES = XMLManager(
        label="welsh_senedd_debates",
        relative_path="scrapedxml/senedd/en/",
        file_structure_pre_date="senedd",
        transcript_type=TranscriptType.DEBATES,
        chamber_type=Chamber.SENEDD,
    )
    NI_ASSEMBLY_DEBATES = XMLManager(
        label="ni_assembly_debates",
        relative_path="scrapedxml/ni/",
        file_structure_pre_date="ni",
        transcript_type=TranscriptType.DEBATES,
        chamber_type=Chamber.NORTHERN_IRELAND,
    )

    @classmethod
    def get_transcript_manager(
        cls,
        chamber: Chamber,
        transcript: TranscriptType,
    ):
        for option in cls.options():
            if option.chamber_type == chamber and option.transcript_type == transcript:
                return option
        raise ValueError(
            f"No option found for chamber {chamber} and transcript {transcript}"
        )


async def async_check_file_existence(client: httpx.AsyncClient, url: str):
    try:
        headers = {"User-Agent": get_user_agent()}
        response = await client.head(url, headers=headers)
        return url, response.status_code
    except httpx.RequestError:
        return url, None


async def async_check_urls_exist(urls: list[str]) -> list[str]:
    valid_urls: list[str] = []
    async with httpx.AsyncClient() as client:
        tasks = [async_check_file_existence(client, url) for url in urls]
        results = await asyncio.gather(*tasks)
        for url, status_code in results:
            if status_code == 200:
                valid_urls.append(url)
    return valid_urls


def check_urls_exist(urls: list[str]) -> list[str]:
    return asyncio.run(async_check_urls_exist(urls))


def get_latest_for_date(
    date: datetime.date,
    *,
    chamber: Chamber = Chamber.COMMONS,
    transcript_type: TranscriptType = TranscriptType.DEBATES,
    download_path: Optional[Path] = None,
    force_download: bool = False,
):
    transcript_manager = TranscriptXMl.get_transcript_manager(
        chamber=chamber, transcript=transcript_type
    )
    return transcript_manager.get_latest_for_date(
        date, download_path, force_download=force_download
    )
