from mysoc_validator.__main__ import app
from typer.testing import CliRunner

runner = CliRunner()


def test_validate_popolo():
    result = runner.invoke(
        app,
        [
            "popolo",
            "validate",
            "https://raw.githubusercontent.com/mysociety/parlparse/master/members/people.json",
        ],
    )
    assert result.exit_code == 0
    assert "Valid Popolo file" in result.stdout


def test_validate_transcript():
    result = runner.invoke(
        app,
        ["transcript", "validate", "data/debates2023-03-28d.xml"],
    )
    assert result.exit_code == 0
    assert "Valid Transcript file" in result.stdout


def test_validate_transcript_glob():
    result = runner.invoke(
        app,
        ["transcript", "validate", "data/debates*.xml", "--glob"],
    )
    assert result.exit_code == 0


def test_validate_interests():
    result = runner.invoke(app, ["interests", "validate", "data/regmem2024-05-28.xml"])
    assert result.exit_code == 0
    assert "Valid Interests file" in result.stdout


def test_validate_interests_glob():
    result = runner.invoke(app, ["interests", "validate", "data/regmem*.xml", "--glob"])
    assert result.exit_code == 0
