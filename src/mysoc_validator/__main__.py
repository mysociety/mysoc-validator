from enum import Enum
from pathlib import Path
from typing import Optional

import rich
import typer

from .models.interests import Register
from .models.popolo import Popolo
from .models.transcripts import Transcript

app = typer.Typer()


class ValidateOptions(str, Enum):
    POPOLO = "popolo"
    TRANSCRIPT = "transcript"
    INTERESTS = "interests"


@app.command()
def blank():
    """
    Holding command to make 'validate' not the default.
    """
    pass


@app.command()
def format(
    file: Path,
    type: ValidateOptions = ValidateOptions.POPOLO,
):
    if type != ValidateOptions.POPOLO:
        typer.echo("Format option is only valid for Popolo files.")
        raise typer.Exit(code=1)
    validate_popolo_file(file, format=True)


@app.command()
def validate(
    file: Optional[Path] = None,
    url: Optional[str] = None,
    type: ValidateOptions = ValidateOptions.POPOLO,
    format: bool = False,
):
    if format and type != ValidateOptions.POPOLO:
        typer.echo("Format option is only valid for Popolo files.")
        raise typer.Exit(code=1)
    # must be at least one of file or url, but not both
    if not file and not url:
        typer.echo("Must provide either a file or a URL.")
        raise typer.Exit(code=1)
    if file and url:
        typer.echo("Must provide either a file or a URL, not both.")
        raise typer.Exit(code=1)
    if type == ValidateOptions.POPOLO:
        if file:
            validate_popolo_file(file, format=format)
        if url:
            validate_popolo_url_file(url)
    elif type == ValidateOptions.TRANSCRIPT:
        if not file:
            typer.echo("Must provide a local file for a transcript.")
            raise typer.Exit(code=1)
        validate_transcript(file)
    elif type == ValidateOptions.INTERESTS:
        if not file:
            typer.echo("Must provide a local file for interests.")
            raise typer.Exit(code=1)
        validate_interests(file)


def validate_popolo_file(file: Path, format: bool = False):
    """
    Validate a mysoc style Popolo file.
    Returns Exit 1 if a validation error.
    """
    try:
        people = Popolo.from_path(file)
    except Exception as e:
        typer.echo(f"Error: {e}")
        rich.print("[red]Invalid Popolo file[/red]")
        raise typer.Exit(code=1)
    print(
        f"Loaded {len(people.organizations)} organizations, {len(people.posts)} posts, {len(people.persons)} people, and {len(people.memberships)} memberships."
    )
    rich.print("[green]Valid Popolo file[/green]")
    if format:
        people.to_path(file)
        rich.print(f"[green]Formatted Popolo file saved to {file}[/green]")


def validate_popolo_url_file(url: str):
    """
    Validate a mysoc style Popolo file.
    Returns Exit 1 if a validation error.
    """
    try:
        people = Popolo.from_url(url)
    except Exception as e:
        typer.echo(f"Error: {e}")
        rich.print("[red]Invalid Popolo file[/red]")
        raise typer.Exit(code=1)
    print(
        f"Loaded {len(people.organizations)} organizations, {len(people.posts)} posts, {len(people.persons)} people, and {len(people.memberships)} memberships."
    )
    rich.print("[green]Valid Popolo file[/green]")


def validate_transcript(file: Path):
    """
    Validate a mysoc style Popolo file.
    Returns Exit 1 if a validation error.
    """
    try:
        Transcript.from_xml_path(file)
    except Exception as e:
        typer.echo(f"Error: {e}")
        rich.print("[red]Invalid Transcript file[/red]")
        raise typer.Exit(code=1)
    rich.print("[green]Valid Transcript file[/green]")


def validate_interests(file: Path):
    """
    Validate a mysoc style Popolo file.
    Returns Exit 1 if a validation error.
    """
    try:
        Register.from_xml_path(file)
    except Exception as e:
        typer.echo(f"Error: {e}")
        rich.print("[red]Invalid Interests file[/red]")
        raise typer.Exit(code=1)
    rich.print("[green]Valid Interests file[/green]")


if __name__ == "__main__":
    app()
