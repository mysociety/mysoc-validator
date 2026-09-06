from datetime import date
from unittest.mock import Mock

import pytest
import typer

import mysoc_validator.__main__ as cli
from mysoc_validator.models.consts import MembershipReason


def test_path_and_url_parsers_resolve_supported_inputs(tmp_path):
    """Verify path and url parsers resolve supported inputs."""
    direct = tmp_path / "people.json"
    direct.write_text("{}")
    nested_root = tmp_path / "checkout"
    (nested_root / "members").mkdir(parents=True)
    nested = nested_root / "members" / "people.json"
    nested.write_text("{}")

    assert cli.find_people_json(tmp_path) == direct
    assert cli.find_people_json(nested_root) == nested
    assert cli.process_path(str(nested_root)) == nested
    assert cli.process_path_or_url("https://example.test/people.json").url == (
        "https://example.test/people.json"
    )
    assert cli.process_path_or_url(str(direct)).path == direct


def test_path_and_person_id_parsers_reject_or_expand_values(tmp_path):
    """Verify path and person id parsers reject or expand values."""
    with pytest.raises(typer.BadParameter, match="File does not exist"):
        cli.process_path(str(tmp_path / "missing.json"))
    with pytest.raises(typer.BadParameter, match="person_id is required"):
        cli.enhance_person_id("")

    assert cli.enhance_person_id("123") == "uk.org.publicwhip/person/123"
    assert (
        cli.enhance_person_id("uk.org.publicwhip/person/123")
        == "uk.org.publicwhip/person/123"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://example.test/a", True),
        ("http://example.test", True),
        ("ftp://example.test/a", True),
        ("file:///tmp/a", False),
        ("example.test/a", False),
    ],
)
def test_url_detection(value, expected):
    """Verify url detection."""
    assert cli.is_url(value) is expected


def _mock_popolo(monkeypatch):
    person = Mock()
    organization = Mock(id="new-party")
    popolo = Mock()
    popolo.persons = {"uk.org.publicwhip/person/1": person}
    popolo.organizations = {"new-party": organization}
    monkeypatch.setattr(cli.Popolo, "from_path", lambda path: popolo)
    return popolo, person, organization


def test_name_commands_delegate_mutations_and_save(monkeypatch, tmp_path):
    """Verify name commands delegate mutations and save."""
    popolo, person, _ = _mock_popolo(monkeypatch)
    path = tmp_path / "people.json"

    cli.add_alt_name(path, "uk.org.publicwhip/person/1", one_name="Ada")
    person.add_alt_name.assert_called_once_with(
        given_name="",
        family_name="",
        one_name="Ada",
        start_date=cli.FixedDate.PAST,
        end_date=cli.FixedDate.FUTURE,
    )
    cli.change_name(
        path,
        "uk.org.publicwhip/person/1",
        given_name="Ada",
        family_name="Lovelace",
        change_date=date(2024, 1, 2),
    )
    person.change_main_name.assert_called_once_with(
        given_name="Ada", family_name="Lovelace", change_date=date(2024, 1, 2)
    )
    cli.ennoble(
        path,
        "uk.org.publicwhip/person/1",
        given_name="Ada",
        county="London",
        honorific_prefix="Baroness",
        lordname="Lovelace",
        lordofname_full="of London",
        change_date=date(2024, 1, 3),
    )
    person.change_main_name_to_lord.assert_called_once()
    assert popolo.to_path.call_count == 3


def test_name_commands_reject_incomplete_requests(tmp_path):
    """Verify name commands reject incomplete requests."""
    with pytest.raises(typer.BadParameter, match="Both given_name"):
        cli.change_name(tmp_path / "people.json", "person", given_name="Ada")
    with pytest.raises(typer.BadParameter, match="person_id is required"):
        cli.ennoble(tmp_path / "people.json", "")


def test_party_commands_delegate_reason_source_and_save(monkeypatch, tmp_path):
    """Verify party commands delegate reason source and save."""
    popolo, person, organization = _mock_popolo(monkeypatch)
    path = tmp_path / "people.json"

    cli.change_party(
        path,
        "uk.org.publicwhip/person/1",
        "new-party",
        change_date=date(2024, 1, 2),
        source_url="https://example.test/source",
    )
    person.change_party.assert_called_once_with(
        new_party=organization,
        change_date=date(2024, 1, 2),
        change_reason=MembershipReason.CHANGED_PARTY,
        source_url="https://example.test/source",
    )
    cli.remove_whip(path, "uk.org.publicwhip/person/1", date(2024, 1, 3), "remove")
    cli.restore_whip(path, "uk.org.publicwhip/person/1", date(2024, 1, 4), "restore")
    person.remove_whip.assert_called_once_with(
        change_date=date(2024, 1, 3), source_url="remove"
    )
    person.restore_whip.assert_called_once_with(
        change_date=date(2024, 1, 4), source_url="restore"
    )
    assert popolo.to_path.call_count == 3


def test_change_party_requires_target_party(tmp_path):
    """Verify change party requires target party."""
    with pytest.raises(typer.BadParameter, match="new_party_id is required"):
        cli.change_party(tmp_path / "people.json", "person", "")


def test_popolo_command_dispatches_path_url_format_and_download(monkeypatch, tmp_path):
    """Verify popolo command dispatches path url format and download."""
    calls = []
    monkeypatch.setattr(
        cli,
        "validate_popolo_file",
        lambda path, format=False: calls.append((path, format)),
    )
    monkeypatch.setattr(cli, "validate_popolo_url_file", lambda url: calls.append(url))

    path = tmp_path / "people.json"
    cli.validate_popolo_cmd(cli.URLorPath(path=path), format=True)
    cli.validate_popolo_cmd(cli.URLorPath(url="https://example.test/people.json"))
    cli.format_cmd(path)

    assert calls == [
        (path, True),
        "https://example.test/people.json",
        (path, True),
    ]

    popolo = Mock()
    monkeypatch.setattr(cli.Popolo, "from_parlparse", lambda branch: popolo)
    destination = tmp_path / "download.json"
    cli.download(destination, branch="feature")
    popolo.to_path.assert_called_once_with(destination)


def test_transcript_directory_mode_only_validates_xml_children(monkeypatch, tmp_path):
    """Verify transcript directory mode only validates xml children."""
    one = tmp_path / "one.xml"
    two = tmp_path / "two.xml"
    one.write_text("<publicwhip/>")
    two.write_text("<publicwhip/>")
    calls = []
    monkeypatch.setattr(
        cli, "validate_transcript", lambda path, quiet_success=False: calls.append(path)
    )

    cli.validate_transcript_cmd(tmp_path)

    assert set(calls) == {one, two}


def test_interests_directory_mode_only_validates_supported_children(
    monkeypatch, tmp_path
):
    """Verify interests directory mode only validates supported children."""
    xml = tmp_path / "one.xml"
    json_path = tmp_path / "two.json"
    ignored = tmp_path / "three.txt"
    for path in (xml, json_path, ignored):
        path.write_text("")
    calls = []
    monkeypatch.setattr(
        cli,
        "validate_interests_xml_or_json",
        lambda path, quiet_success=False: calls.append(path),
    )

    cli.validate(tmp_path)

    assert calls == [xml, json_path]


def test_interest_dispatch_rejects_unknown_extensions(tmp_path):
    """Verify interest dispatch rejects unknown extensions."""
    with pytest.raises(typer.BadParameter, match="either XML or JSON"):
        cli.validate_interests_xml_or_json(tmp_path / "register.csv")


@pytest.mark.parametrize(
    ("validator_name", "loader"),
    [
        ("validate_popolo_file", (cli.Popolo, "from_path")),
        ("validate_popolo_url_file", (cli.Popolo, "from_url")),
        ("validate_transcript", (cli.Transcript, "from_xml_path")),
        ("validate_interests_json", (cli.RegmemRegister, "from_path")),
        ("validate_interests_xml", (cli.Register, "from_xml_path")),
    ],
)
def test_validation_helpers_translate_loader_errors_to_exit_one(
    monkeypatch, tmp_path, validator_name, loader
):
    """Verify validation helpers translate loader errors to exit one."""
    owner, method = loader

    def fail(*args, **kwargs):
        raise ValueError("broken input")

    monkeypatch.setattr(owner, method, fail)
    argument = "https://example.test/people.json" if method == "from_url" else tmp_path

    with pytest.raises(typer.Exit) as error:
        getattr(cli, validator_name)(argument)

    assert error.value.exit_code == 1
