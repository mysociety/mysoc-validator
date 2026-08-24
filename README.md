# mysoc-validator

A set of pydantic-based validators and classes for common mySociety democracy formats.

Currently supports:

- Popolo database
- Transcript format (old-style XML and new json format)
- Interests format

XML based formats are tested to round-trip with themselves, but not to be string identical with the original source.

Can be installed with `pip install mysoc-validator`

To use as a cli validator:

```bash
python -m mysoc_validator popolo validate path-to-people.json
python -m mysoc_validator transcript validate path-to-transcript.xml
python -m mysoc_validator transcript validate transcripts/
python -m mysoc_validator transcript validate path-to-*.xml --glob
python -m mysoc_validator interests validate path-to-interests.xml
```

To see all options use `python -m mysoc_validator --help` or `python -m mysoc_validator popolo tui`.

Or if using uvx (don't need to install first):

```bash
uvx mysoc-validator popolo validate path-to-people.json
```

To validate and consistently format:

```bash
uvx mysoc-validator format people.json
```

# Modification functions

See `python -m mysoc_validator popolo --help` for functions to change parties/whip and add alt names.


## Popolo

A pydantic based validator for main mySociety people.json file (which mostly follows the popolo standard with a few extra bits).

Validates:

- Basic structure
- Unique IDs and ID Patterns
- Foreign key relationships between objects.

It also has support for looking up from name or identifying to person, and new ID generation for membership. 

### Extra popolo fields

The validator is strict on the fields that should be present everywhere except the extra field - where we have some specified values, but the validator itself is more tolerant of things it doesn't recognise there (better backwards compatibility for new data outside the normal schema). 

### Localised Popolo fields

For some Senedd related items we want to record bilingual labels - but the Popolo standard doesn't support this.

We're using an extension in the 'extra' field to record when a string value in a model has a localised value. 

When using this, set both en and cy fields as localised values, and the 'main' version of the field should be 'cy / en'. 

e.g. 

```json
        {
            "id": "senedd-committee-210781",
            "name": "Y Pwyllgor Cyllid / Finance Committee",
            "extra": {
                "localised_values": {
                    "name": {"en": "Finance Committee", "cy": "Y Pwyllgor Cyllid"}
                }
            },
            "classification": "committee"
        }
```

These can be read and set through `.get_localised_value(field, lang)` and `.set_localised_value(field, lang, value)`. Getting a field with no localised value for that language falls back to the model's canonical field value.

Only specific fields on specific models are localisable:

- `Organization`: `name`, `abstract`, `description`
- `Post`: `label`, `role`
- `Membership`: `label`, `role`
- `Person`: `biography`, `summary`
- `Area`: `name`

### Extra fields in external projects

`Membership`, `Organization`, `Person`, `Area` and `Post` all share `get_extra`/`set_extra` helpers for reading and writing arbitrary keys on the `extra` field, so a downstream project can attach its own data without needing changes to this library.

```python
from mysoc_validator.models.popolo import Membership

membership = Membership(
    id=Membership.BLANK_ID,
    person_id="uk.org.publicwhip/person/1",
    start_date="2020-01-01",
    end_date="2020-12-31",
)
membership.set_extra("tag", "whip-removed")

membership.get_extra("tag")  # "whip-removed"
membership.get_extra("nope")  # None - missing keys don't raise
```

`set_extra` returns the model, so calls can be chained: `membership.set_extra("a", 1).set_extra("b", 2)`.

For a typed field with its own validation, subclass the model's named `XExtra` alias (e.g. `MembershipExtra`, `OrganizationExtra`) and construct the model with an instance of it:

```python
from mysoc_validator.models.popolo import Membership, MembershipExtra

class TaggedMembershipExtra(MembershipExtra):
    tag: str = ""

membership = Membership(
    id=Membership.BLANK_ID,
    person_id="uk.org.publicwhip/person/1",
    start_date="2020-01-01",
    end_date="2020-12-31",
    extra=TaggedMembershipExtra(tag="whip-removed"),
)

membership.get_extra("tag")  # "whip-removed" - still works through the generic accessor
membership.extra.tag  # "whip-removed" - and through your own typed field
```

If a model was instead loaded generically (e.g. straight from JSON, so `extra` only knows about the fields this library defines), use `get_extra_as` to reinterpret it as your project-specific type:

```python
from mysoc_validator.models.popolo import Membership, MembershipExtra

class TaggedMembershipExtra(MembershipExtra):
    tag: str = ""

membership = Membership(
    id=Membership.BLANK_ID,
    person_id="uk.org.publicwhip/person/1",
    start_date="2020-01-01",
    end_date="2020-12-31",
)
membership.set_extra("tag", "whip-removed")

tagged = membership.get_extra_as(TaggedMembershipExtra)
tagged.tag  # "whip-removed"
```

`get_extra_as` returns `None` if `extra` isn't set at all, and raises a Pydantic `ValidationError` if the existing data doesn't satisfy your model.

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

For new style generic json format.  

```python
from mysoc_validator import RegmemRegister
from pathlib import Path

register_file = Path("data", "commons-regmem-2025-01-20.json")
interests = RegmemRegister.from_path(register_file)
```

```python
from mysoc_validator import XMLRegister
from pathlib import Path

register_file = Path("data", "regmem2024-05-28.xml")
interests = XMLRegister.from_xml_path(register_file)
```

## Info fields

We have various XML files in [parlparse](https://github.com/mysociety/parlparse/tree/master/members) that are loaded into TWFY as extra info for people or constituencies.

This library has two approaches for this - a general permissive model that can load any file, and tools to create models to add validation for particular files if needed.

### Load any file

```python 
from mysoc_validator.models.info import InfoCollection, PersonInfo, ConsInfo

social_media_links = InfoCollection[PersonInfo].from_parlparse("social-media-commons")
constituency_links = InfoCollection[ConsInfo].from_parlparse("constituency-links")
```

And this is an example of creating a more bespoke model for a particular file. 
Subclassing `PersonInfo` switches the 'extras' setting from 'allow' to 'forbid'. 

```python 
from typing import Optional

from mysoc_validator.models.info import InfoCollection, PersonInfo, ConsInfo

class SocialInfo(PersonInfo):
    facebook_page: Optional[str] = None
    twitter_username: Optional[str]= None
    bluesky_handle: Optional[str]= None
    instagram_username: Optional[str] = None
    threads_username: Optional[str] = None

social_media_links = InfoCollection[SocialInfo].from_parlparse("social-media-commons")
```

If needing to pass dicts across the XML boundary (although this implies a change to how things are imported), do the following:

```python
from mysoc_validator.models.info import InfoCollection, PersonInfo
from mysoc_validator.models.xml_base import XMLDict, AsAttrStr

class DemoDataModel(PersonInfo):
    regmem_info: XMLDict
    random_string: AsAttrStr


item = DemoDataModel(
    person_id="uk.org.publicwhip/person/10001",
    regmem_info={"hello": ["yes", "no"]},
    random_string="banana",
)

items = InfoCollection[DemoDataModel](items=[item])

xml_data = items.model_dump_xml()

# Which looks like
"""
<twfy>
  <personinfo id="uk.org.publicwhip/person/10001">
    <regmem_info>{"hello": ["yes", "no"]}</regmem_info>
    <random_string>banana</random_string>
  </personinfo>
</twfy>
"""

# which can either be round-triped in the same model - or read by the generic model like this

generic_read = (
    InfoCollection[PersonInfo].model_validate_xml(xml_data).promote_children()
)

```
