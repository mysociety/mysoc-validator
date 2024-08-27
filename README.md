# mysoc-validator

A set of pydantic-based validators and classes for common mySociety democracy formats.

Currently supports:

- Popolo database
- Transcript format
- Interests format

XML based formats are tested to round-trip with themselves, but not to be string identical with the original source.

To use as a cli validator:

```bash
python -m mysoc_validator validate --path <path-to-people.json> --type popolo
python -m mysoc_validator validate --path <path-to-transcript.xml> --type transcript
python -m mysoc_validator validate --path <path-to-interests.xml> --type interests

```

## Popolo

A pydantic based validator for main mySociety people.json file (which mostly follows the popolo standard with a few extra bits).

Validates:

- Basic structure
- Unique IDs and ID Patterns
- Foreign key relationships between objects.

It also has support for looking up from name or identifying to person, and new ID generation for membership. 

### Using name or ID lookup

After first use, there is some caching behind the scenes to speed this up.

```python
from mysoc_validator import Popolo
from mysoc_validator.models.popolo import Chamber, IdentifierScheme
from datetime import date

popolo = Popolo.from_parlparse()

keir_starmer_parl_id = popolo.persons.from_identifier(
    "4514", scheme=IdentifierScheme.MNIS
)
keir_starmer_name = popolo.persons.from_name(
    "keir starmer", chamber_id=Chamber.COMMONS, date=date.fromisoformat("2022-07-31")
)

keir_starmer_parl_id.id == keir_starmer_name.id

```


## Transcripts

Python validator and handler for 'publicwhip' style transcript format. 

```python
from mysoc_validator import Transcript
from pathlib import Path

transcript_file = Path("data", "debates2023-03-28d.xml")

transcript = Transcript.from_xml_path(transcript_file)
```

## Register of Interests

Python validator and handler for 'publicwhip' style interests format. 

```python
from mysoc_validator import Register
from pathlib import Path

register_file = Path("data", "regmem2024-05-28.xml")
interests = Register.from_xml_path(register_file)

```

