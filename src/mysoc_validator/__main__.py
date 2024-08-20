from pathlib import Path

import rich
import typer

from .models.popolo import Popolo
from .models.transcripts import Transcript

app = typer.Typer()


@app.command()
def validate_popolo(file: Path):
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


@app.command()
def validate_popolo_url(url: str):
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


@app.command()
def validate_transcript(file: Path):
    """
    Validate a mysoc style Popolo file.
    Returns Exit 1 if a validation error.
    """
    try:
        Transcript.from_path(file)
    except Exception as e:
        typer.echo(f"Error: {e}")
        rich.print("[red]Invalid Transcript file[/red]")
        raise typer.Exit(code=1)
    rich.print("[green]Valid Transcript file[/green]")


if __name__ == "__main__":
    app()
