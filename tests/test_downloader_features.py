import datetime
from types import SimpleNamespace

import httpx
import pytest

from mysoc_validator.models.consts import Chamber, TranscriptType
from mysoc_validator.utils.parlparse import downloader


DAY = datetime.date(2024, 9, 5)


def _manager(**overrides):
    values = {
        "label": "test",
        "relative_path": "debates/",
        "file_structure_pre_date": "debates",
        "transcript_type": TranscriptType.DEBATES,
        "chamber_type": Chamber.COMMONS,
    }
    values.update(overrides)
    return downloader.XMLManager(**values)


def test_retry_recovers_from_transient_transport_errors(monkeypatch):
    """Verify retry recovers from transient transport errors."""
    attempts = []
    sleeps = []

    def fake_get(url, **kwargs):
        attempts.append((url, kwargs))
        if len(attempts) < 3:
            raise httpx.ReadTimeout("temporary")
        return SimpleNamespace(text="ok")

    monkeypatch.setattr(downloader.httpx, "get", fake_get)
    monkeypatch.setattr(downloader.time, "sleep", sleeps.append)

    response = downloader.get_with_retry(
        "https://example.test/file", retries=3, backoff=0.25
    )

    assert response.text == "ok"
    assert len(attempts) == 3
    assert sleeps == [0.25, 0.5]


def test_retry_reraises_the_final_transport_error(monkeypatch):
    """Verify retry reraises the final transport error."""
    error = httpx.ConnectTimeout("still unavailable")
    monkeypatch.setattr(
        downloader.httpx, "get", lambda *args, **kwargs: (_ for _ in ()).throw(error)
    )
    monkeypatch.setattr(downloader.time, "sleep", lambda seconds: None)

    with pytest.raises(httpx.ConnectTimeout) as caught:
        downloader.get_with_retry("https://example.test/file", retries=2, backoff=0)

    assert caught.value is error


def test_index_parser_and_scottish_latest_selection(monkeypatch):
    """Verify index parser and scottish latest selection."""
    downloader.get_xmls_from_index.cache_clear()
    monkeypatch.setattr(
        downloader,
        "get_with_retry",
        lambda url: SimpleNamespace(
            text='<a href="2024-09-05a.xml">a</a><a href="ignore.txt">x</a><a href="2024-09-05b.xml">b</a>'
        ),
    )

    assert downloader.get_xmls_from_index("https://example.test/") == [
        "2024-09-05a.xml",
        "2024-09-05b.xml",
    ]
    assert downloader.get_scot_debate_xmls(DAY).endswith("2024-09-05b.xml")
    assert downloader.get_scot_debate_xmls(datetime.date(2020, 1, 1)) is None


def test_manager_constructs_paths_and_urls(tmp_path):
    """Verify manager constructs paths and urls."""
    manager = _manager()

    assert manager.construct_path(DAY, "b", tmp_path) == (
        tmp_path / "debates" / "debates2024-09-05b.xml"
    )
    assert manager.construct_url(DAY, "b") == (
        "https://www.theyworkforyou.com/pwdata/debates/debates2024-09-05b.xml"
    )


def test_download_selects_latest_available_variant_and_writes_it(monkeypatch, tmp_path):
    """Verify download selects latest available variant and writes it."""
    manager = _manager()
    monkeypatch.setattr(
        downloader,
        "check_urls_exist",
        lambda urls: [url for url in urls if url.endswith(("a.xml", "c.xml"))],
    )
    monkeypatch.setattr(
        downloader,
        "get_with_retry",
        lambda url, headers=None: SimpleNamespace(text=f"downloaded {url}"),
    )

    result = manager.download_for_date(DAY, tmp_path)

    assert result.name == "debates2024-09-05c.xml"
    assert result.read_text().endswith("debates2024-09-05c.xml")


def test_download_rejects_unsupported_type_and_missing_files(monkeypatch, tmp_path):
    """Verify download rejects unsupported type and missing files."""
    unsupported = _manager(transcript_type=TranscriptType.WRITTEN_QUESTIONS)
    with pytest.raises(ValueError, match="Only debates"):
        unsupported.download_for_date(DAY, tmp_path)

    monkeypatch.setattr(downloader, "check_urls_exist", lambda urls: [])
    with pytest.raises(FileNotFoundError, match="No files found"):
        _manager().download_for_date(DAY, tmp_path)


def test_latest_uses_cache_unless_force_downloaded(monkeypatch, tmp_path):
    """Verify latest uses cache unless force downloaded."""
    manager = _manager()
    cached = manager.construct_path(DAY, "b", tmp_path)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text("cached")
    download = MockDownload(tmp_path / "fresh.xml")
    monkeypatch.setattr(
        downloader.XMLManager,
        "download_for_date",
        lambda self, day, download_path=None: download(day, download_path),
    )

    assert manager.get_latest_for_date(DAY, tmp_path) == cached
    assert not download.calls
    assert (
        manager.get_latest_for_date(DAY, tmp_path, force_download=True) == download.path
    )
    assert download.calls == [(DAY, tmp_path)]


class MockDownload:
    def __init__(self, path):
        self.path = path
        self.calls = []

    def __call__(self, day, download_path=None):
        self.calls.append((day, download_path))
        return self.path


def test_scottish_latest_uses_cache_and_downloads_index_result(monkeypatch, tmp_path):
    """Verify scottish latest uses cache and downloads index result."""
    manager = _manager(chamber_type=Chamber.SCOTLAND)
    cached = tmp_path / "meeting2024-09-05a.xml"
    cached.write_text("cached")
    assert manager.get_latest_for_date_scot(DAY, tmp_path) == cached

    monkeypatch.setattr(
        downloader,
        "get_scot_debate_xmls",
        lambda day: "https://example.test/meeting2024-09-05b.xml",
    )
    monkeypatch.setattr(
        downloader,
        "get_with_retry",
        lambda url, headers=None: SimpleNamespace(text="fresh"),
    )
    result = manager.get_latest_for_date_scot(DAY, tmp_path, force_download=True)
    assert result.name == "meeting2024-09-05b.xml"
    assert result.read_text() == "fresh"


def test_scottish_latest_reports_missing_index_result(monkeypatch, tmp_path):
    """Verify scottish latest reports missing index result."""
    manager = _manager(chamber_type=Chamber.SCOTLAND)
    monkeypatch.setattr(downloader, "get_scot_debate_xmls", lambda day: None)
    with pytest.raises(FileNotFoundError, match="No files found"):
        manager.get_latest_for_date_scot(DAY, tmp_path)


def test_manager_lookup_and_module_level_delegation(monkeypatch, tmp_path):
    """Verify manager lookup and module level delegation."""
    manager = downloader.TranscriptXMl.get_transcript_manager(
        Chamber.COMMONS, TranscriptType.DEBATES
    )
    assert manager.label == "uk_commons_debates"
    with pytest.raises(ValueError, match="No option found"):
        downloader.TranscriptXMl.get_transcript_manager(
            Chamber.COMMONS, TranscriptType.WRITTEN_STATEMENTS
        )

    monkeypatch.setattr(
        downloader.XMLManager,
        "get_latest_for_date",
        lambda self, day, path, force_download=False: (day, path, force_download),
    )
    assert downloader.get_latest_for_date(
        DAY,
        chamber=Chamber.COMMONS,
        download_path=tmp_path,
        force_download=True,
    ) == (DAY, tmp_path, True)


def test_async_head_retry_returns_status_or_none(monkeypatch):
    """Verify async head retry returns status or none."""
    import asyncio

    monkeypatch.setattr(downloader, "DEFAULT_RETRIES", 2)
    monkeypatch.setattr(downloader.asyncio, "sleep", lambda seconds: AsyncNoop())
    client = AsyncHeadClient([httpx.ReadTimeout("temporary"), 200])
    assert asyncio.run(downloader.async_check_file_existence(client, "https://ok")) == (
        "https://ok",
        200,
    )

    client = AsyncHeadClient([httpx.ReadTimeout("one"), httpx.ReadTimeout("two")])
    assert asyncio.run(
        downloader.async_check_file_existence(client, "https://bad")
    ) == (
        "https://bad",
        None,
    )


class AsyncNoop:
    def __await__(self):
        if False:
            yield None
        return None


class AsyncHeadClient:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)

    async def head(self, url, headers=None):
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(status_code=outcome)
