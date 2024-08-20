# mysoc-validator

A set of pydantic based validators for common mySociety democracy formats.

The long term goal is to consolidate different scripts behind a common validation system.

## Transcripts

Python validator and handler for 'publicwhip' style transcript format. 

Haven't ensured it can do round trips yet - but can read and write. Needs tests.

```python
from mysoc_validator import Transcript

transcript = Transcript.from_path(<path to xml file>)
```

```bash
python -m validate_transcript <path-to-transcript.xml>
```

## Popolo

A pydantic based validator for main mysociety people.json file (which mostly follows the popolo standard with a few extra bits).

Validates:

- Basic structure
- Unique IDs and ID Patterns
- Foreign key relationships between objects.

It also has support for looking up from name or indentifer to person (see tests), and new ID generation for membership. 

```python
from mysoc_validator import Popolo

popolo = Popolo.from_path(<path to people.json>)
```

```bash
python -m validate_popolo <path-to-people.json>
```

### People.json

The currently committed people.json is not the authoriative one - currently has some tweaks to pass validation. 

In the long run - do not store this in this repo, fetch the live one before running tests.

curl -o data/people.json https://raw.githubusercontent.com/mysociety/parlparse/master/members/people.json
