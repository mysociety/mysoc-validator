from mysoc_validator.__main__ import app
from typer.testing import CliRunner

runner = CliRunner()


def test_validate_popolo():
    result = runner.invoke(
        app,
        [
            "validate",
            "--url",
            "https://raw.githubusercontent.com/mysociety/parlparse/master/members/people.json",
            "--type",
            "popolo",
        ],
    )
    assert result.exit_code == 0
    assert "Valid Popolo file" in result.stdout


def test_validate_transcript():
    result = runner.invoke(
        app,
        ["validate", "--file", "data/debates2023-03-28d.xml", "--type", "transcript"],
    )
    assert result.exit_code == 0
    assert "Valid Transcript file" in result.stdout


def test_validate_interests():
    result = runner.invoke(
        app, ["validate", "--file", "data/regmem2024-05-28.xml", "--type", "interests"]
    )
    assert result.exit_code == 0
    assert "Valid Interests file" in result.stdout
