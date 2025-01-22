from dataclasses import dataclass
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

from .models.dates import FixedDate
from .models.interests import RegmemRegister
from .models.popolo import Popolo
from .models.transcripts import Transcript
from .models.xml_interests import Register


@dataclass
class URLorPath:
    url: Optional[str] = None
    path: Optional[Path] = None

    def __str__(self):
        if self.url:
            return self.url
        else:
            return str(self.path)


def init_tui(app: typer.Typer, name: Optional[str] = None):
    """
    Here to fix the typing error for 3.9 in trogon.
    """

    def wrapped_tui():
        Trogon(
            typer.main.get_group(app),
            app_name=name,
            click_context=click.get_current_context(),
        ).run()

    app.command("tui", help="Open Textual TUI.")(wrapped_tui)

    return app


def find_people_json(root: Path = Path(".")) -> Optional[Path]:
    # if in the right folder
    in_folder = root / "people.json"

    # for root in parlparse
    member_folder = root / "members" / "people.json"

    for o in [in_folder, member_folder]:
        if o.exists():
            return o
    return None


def process_path(str_path: str) -> Path:
    p = Path(str_path)
    if p.is_dir():
        p = find_people_json(p)
    if p and p.exists():
        return p
    elif p:
        raise typer.BadParameter(f"File does not exist: {p}")
    else:
        raise typer.BadParameter(f"File does not exist or not specified: {str_path}")


def process_path_or_url(str_path: str) -> URLorPath:
    str_path = str(str_path)
    if is_url(str_path):
        return URLorPath(url=str_path)
    else:
        return URLorPath(path=process_path(str_path))


def enhance_person_id(person_id: str) -> str:
    if not person_id:
        raise typer.BadParameter("person_id is required")

    if "uk.org.publicwhip" in person_id:
        return person_id
    else:
        return f"uk.org.publicwhip/person/{person_id}"


PopoloPath = Annotated[
    Path,
    typer.Argument(
        parser=process_path,
        help="Path to the Popolo file, or folder containing people.json",
    ),
]
PopoloPathOrUrl = Annotated[
    URLorPath,
    typer.Argument(parser=process_path_or_url, help="Path or URL to the Popolo file"),
]
PersonID = Annotated[str, typer.Option(parser=enhance_person_id, help="Person ID")]
DescPath = Annotated[Path, typer.Argument(parser=Path, help="Path to a file or folder")]
XmlPath = Annotated[
    Path,
    typer.Argument(
        parser=Path, help="Path to the XML file, or folder containing XML files"
    ),
]
OptionalDate = Annotated[Optional[date], typer.Option(parser=date.fromisoformat)]

app = typer.Typer()
init_tui(app)

transcript_app = typer.Typer(help="Commands for Transcript files")
interests_app = typer.Typer(help="Commands for Register of Interests files")
popolo_app = typer.Typer(help="Commands for Popolo files")
party_app = typer.Typer(help="Commands for party modifications in popolo files")
name_app = typer.Typer(help="Commands for name modifications in popolo files")

popolo_app.add_typer(party_app, name="party")
popolo_app.add_typer(name_app, name="name")
app.add_typer(popolo_app, name="popolo")
app.add_typer(transcript_app, name="transcript")
app.add_typer(interests_app, name="interests")


def is_url(url: str) -> bool:
    parsed = urlparse(url)

    # A valid URL will typically have a scheme (like http, https, ftp) and a netloc.
    if parsed.scheme in ["http", "https", "ftp"] and parsed.netloc:
        return True
    return False


@name_app.command()
def add_alt_name(
    file: PopoloPath = Path("."),
    person_id: PersonID = "",
    one_name: str = "",
    given_name: str = "",
    family_name: str = "",
    start_date: OptionalDate = None,
    end_date: OptionalDate = None,
):
    """
    Add an alternative name to a given person id
    """
    if not start_date:
        start_date = FixedDate.PAST

    if not end_date:
        end_date = FixedDate.FUTURE

    popolo = Popolo.from_path(file)
    person = popolo.persons[person_id]
    person.add_alt_name(
        given_name=given_name,
        family_name=family_name,
        one_name=one_name,
        start_date=start_date,
        end_date=end_date,
    )

    if one_name:
        added_name = one_name
    else:
        added_name = f"{given_name} {family_name}"
    rich.print(f"[green]Added alternative name {added_name} for {person_id}[/green]")
    popolo.to_path(file)


@name_app.command()
def change_name(
    file: PopoloPath = Path("."),
    person_id: PersonID = "",
    given_name: str = "",
    family_name: str = "",
    change_date: OptionalDate = None,
):
    """
    Change the name for a given person id
    """
    if not (given_name and family_name):
        raise typer.BadParameter("Both given_name or family_name is required")

    if not change_date:
        change_date = date.today()

    popolo = Popolo.from_path(file)
    person = popolo.persons[person_id]
    person.change_main_name(
        given_name=given_name, family_name=family_name, change_date=change_date
    )
    rich.print(
        f"[green]Changed name for {person_id} to {given_name} {family_name}[/green]"
    )
    popolo.to_path(file)


@name_app.command()
def ennoble(
    file: PopoloPath = Path("."),
    person_id: PersonID = "",
    given_name: str = "",
    county: str = "",
    honorific_prefix: str = "",
    lordname: str = "",
    lordofname_full: str = "",
    change_date: OptionalDate = None,
):
    """
    Set a new lord name for a given person id
    """
    if not person_id:
        raise typer.BadParameter("person_id is required")

    if not change_date:
        change_date = date.today()

    popolo = Popolo.from_path(file)
    person = popolo.persons[person_id]
    person.change_main_name_to_lord(
        given_name=given_name,
        county=county,
        honorific_prefix=honorific_prefix,
        lordname=lordname,
        lordofname_full=lordofname_full,
        change_date=change_date,
    )
    rich.print(f"[green]Ennobled {person_id}[/green]")
    popolo.to_path(file)


@party_app.command()
def change_party(
    file: PopoloPath = Path("."),
    person_id: PersonID = "",
    new_party_id: str = "",
    change_date: OptionalDate = None,
    change_reason: str = "",
):
    """
    Change the party for a given person id
    """

    if not new_party_id:
        raise typer.BadParameter("new_party_id is required")

    popolo = Popolo.from_path(file)
    person = popolo.persons[person_id]
    org = popolo.organizations[new_party_id]
    person.change_party(
        new_party=org,
        change_date=change_date,
        change_reason=change_reason,
    )
    rich.print(f"[green]Changed party for {person_id} to {new_party_id}[/green]")
    popolo.to_path(file)


@party_app.command()
def remove_whip(
    file: PopoloPath = Path("."),
    person_id: PersonID = "",
    change_date: OptionalDate = None,
):
    """
    Remove the whip for a given person id
    """
    popolo = Popolo.from_path(file)
    person = popolo.persons[person_id]
    person.remove_whip(
        change_date=change_date,
    )
    rich.print(f"[green]Removed whip for {person_id}[/green]")
    popolo.to_path(file)


@party_app.command()
def restore_whip(
    file: PopoloPath = Path("."),
    person_id: PersonID = "",
    change_date: OptionalDate = None,
):
    """
    Restore the whip for a given person id
    """
    popolo = Popolo.from_path(file)
    person = popolo.persons[person_id]
    person.restore_whip(
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
    file: PopoloPath = Path("."),
):
    """
    Validate and format a mysoc style Popolo file.
    """
    validate_popolo_file(file, format=True)


@popolo_app.command(name="download")
def download(file: Path = Path("people.json"), branch: str = "master"):
    pop = Popolo.from_parlparse(branch=branch)
    pop.to_path(file)
    rich.print(f"[green]Popolo file saved to {file}[/green]")


@popolo_app.command(name="validate")
def validate_popolo_cmd(
    loc: PopoloPathOrUrl = URLorPath(path=Path(".")),
    format: bool = False,
):
    """
    Validate and optionally format a mysoc style Popolo file.
    """

    if loc.url:
        validate_popolo_url_file(loc.url)
    if loc.path:
        validate_popolo_file(loc.path, format=format)


@transcript_app.command(name="validate")
def validate_transcript_cmd(
    file: XmlPath,
    glob: bool = False,
):
    if file.is_dir():
        files = list(file.glob("*.xml"))
        for f in tqdm(files):
            validate_transcript(f, quiet_success=True)
    if glob:
        files = list(file.parent.glob(file.name))
        for f in tqdm(files):
            validate_transcript(f, quiet_success=True)
    else:
        validate_transcript(file)


@interests_app.command()
def validate(
    file: DescPath,
    glob: bool = False,
):
    if file.is_dir():
        files = list(file.glob("*.xml")) + list(file.glob("*.json"))
        for f in tqdm(files):
            validate_interests_xml_or_json(f, quiet_success=True)
    if glob:
        files = list(file.parent.glob(file.name))
        for f in tqdm(files):
            validate_interests_xml_or_json(f, quiet_success=True)
    else:
        validate_interests_xml_or_json(file)


def validate_popolo_file(file: PopoloPath, format: bool = False):
    """
    Validate a mysoc style Popolo file.
    Returns Exit 1 if a validation error.
    """
    try:
        people = Popolo.from_path(file)
    except Exception as e:
        typer.echo(f"Error: {e}")
        rich.print(f"[red]Invalid Popolo file {file}[/red]")
        raise typer.Exit(code=1)
    print(
        f"Loaded {len(people.organizations)} organizations, {len(people.posts)} posts, {len(people.persons)} people, and {len(people.memberships)} memberships."
    )
    rich.print(f"[green]Valid Popolo file {file}[/green]")
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


def validate_interests_json(file: Path, quiet_success: bool = False):
    """
    Validate a mysoc style Popolo file.
    Returns Exit 1 if a validation error.
    """
    try:
        RegmemRegister.from_path(file)
    except Exception as e:
        typer.echo(f"Error: {e}")
        rich.print(f"[red]Invalid Interests file: {file}[/red]")
        raise typer.Exit(code=1)
    if not quiet_success:
        rich.print(f"[green]Valid Interests file: {file}[/green]")


def validate_interests_xml_or_json(file: Path, quiet_success: bool = False):
    # if file extention is xml or json
    if file.suffix == ".xml":
        validate_interests_xml(file, quiet_success)
    elif file.suffix == ".json":
        validate_interests_json(file, quiet_success)
    else:
        raise typer.BadParameter("File must be either XML or JSON")


def validate_interests_xml(file: Path, quiet_success: bool = False):
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
