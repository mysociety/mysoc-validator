from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional
from urllib.parse import urlparse

import click
import rich
import typer
from tqdm import tqdm
from trogon.trogon import Trogon  # type: ignore

from .models.interests import Register
from .models.popolo import Popolo
from .models.transcripts import Transcript


def init_tui(app: typer.Typer, name: Optional[str] = None):
    def wrapped_tui():
        Trogon(
            typer.main.get_group(app),
            app_name=name,
            click_context=click.get_current_context(),
        ).run()

    app.command("tui", help="Open Textual TUI.")(wrapped_tui)

    return app


OptionalDate = Annotated[Optional[date], typer.Option(parser=date.fromisoformat)]

app = typer.Typer()
init_tui(app)

transcript_app = typer.Typer(help="Commands for Transcript files")
interests_app = typer.Typer(help="Commands for Register of Interests files")
popolo_app = typer.Typer(help="Commands for Popolo files")
party_app = typer.Typer(help="Commands for party modifications in popolo files")

popolo_app.add_typer(party_app, name="party")
app.add_typer(popolo_app, name="popolo")
app.add_typer(transcript_app, name="transcript")
app.add_typer(interests_app, name="interests")


def is_url(url: str) -> bool:
    parsed = urlparse(url)

    # A valid URL will typically have a scheme (like http, https, ftp) and a netloc.
    if parsed.scheme in ["http", "https", "ftp"] and parsed.netloc:
        return True
    return False


@party_app.command()
def change__party(
    file: Path,
    person_id: str,
    new_party_id: str,
    change_date: OptionalDate = None,
    change_reason: str = "",
):
    """
    Change the party for a given person id
    """
    popolo = Popolo.from_path(file)
    popolo.change_party(
        person_id=person_id,
        new_party_id=new_party_id,
        change_date=change_date,
        change_reason=change_reason,
    )
    rich.print(f"[green]Changed party for {person_id} to {new_party_id}[/green]")
    popolo.to_path(file)


@party_app.command()
def remove_whip(
    file: Path,
    person_id: str,
    change_date: OptionalDate = None,
):
    """
    Remove the whip for a given person id
    """
    popolo = Popolo.from_path(file)
    popolo.remove_whip(
        person_id=person_id,
        change_date=change_date,
    )
    rich.print(f"[green]Removed whip for {person_id}[/green]")
    popolo.to_path(file)


@party_app.command()
def restore_whip(
    file: Path,
    person_id: str,
    change_date: OptionalDate = None,
):
    """
    Restore the whip for a given person id
    """
    popolo = Popolo.from_path(file)
    popolo.restore_whip(
        person_id=person_id,
        change_date=change_date,
    )
    rich.print(f"[green]Restored whip for {person_id}[/green]")
    popolo.to_path(file)


class ValidateOptions(str, Enum):
    POPOLO = "popolo"
    TRANSCRIPT = "transcript"
    INTERESTS = "interests"


@popolo_app.command(name="format")
def format_cmd(
    file: Path,
):
    """
    Validate and format a mysoc style Popolo file.
    """
    validate_popolo_file(file, format=True)


@popolo_app.command(name="validate")
def validate_popolo_cmd(
    loc: str,
    format: bool = False,
):
    """
    Validate and optionally format a mysoc style Popolo file.
    """

    if is_url(loc):
        validate_popolo_url_file(loc)
    else:
        p = Path(loc)
        validate_popolo_file(p, format=format)


@transcript_app.command(name="validate")
def validate_transcript_cmd(
    file: Path,
    glob: bool = False,
):
    if glob:
        files = list(file.parent.glob(file.name))
        for f in tqdm(files):
            validate_transcript(f, quiet_success=True)
    else:
        validate_transcript(file)


@interests_app.command()
def validate(
    file: Path,
    glob: bool = False,
):
    if glob:
        files = list(file.parent.glob(file.name))
        for f in tqdm(files):
            validate_interests(f, quiet_success=True)
    else:
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


def validate_transcript(file: Path, quiet_success: bool = False):
    """
    Validate a mysoc style Popolo file.
    Returns Exit 1 if a validation error.
    """
    try:
        Transcript.from_xml_path(file)
    except Exception as e:
        typer.echo(f"Error: {e}")
        rich.print(f"[red]Invalid Transcript file: {file}[/red]")
        raise typer.Exit(code=1)
    if not quiet_success:
        rich.print(f"[green]Valid Transcript file: {file}[/green]")


def validate_interests(file: Path, quiet_success: bool = False):
    """
    Validate a mysoc style Popolo file.
    Returns Exit 1 if a validation error.
    """
    try:
        Register.from_xml_path(file)
    except Exception as e:
        typer.echo(f"Error: {e}")
        rich.print(f"[red]Invalid Interests file: {file}[/red]")
        raise typer.Exit(code=1)
    if not quiet_success:
        rich.print(f"[green]Valid Interests file: {file}[/green]")


if __name__ == "__main__":
    app()
