# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[comment]: # (Template for updates)

## [1.4.1] - 2026-08-24

### Fixed

- Avoided a Pydantic 2.11 deprecation warning in `ListModel.get_list_container_type` by reading `model_fields` from the class instead of the instance.

## [1.4.0] - 2026-08-24

### Added

- Added typed Welsh and English localised values: `get_localised_value`/`set_localised_value` helpers on `Organization`/`Area` (`name`), `Post`/`Membership` (`label`, `role`), and `Person` (`biography`, `summary`), stored under `extra.localised_values` with canonical-value fallback.
- Added a forward-compatible `extra` container to `Membership`, `Organization`, `Person`, `Area`, and `Post` so unknown keys round-trip instead of being rejected, with `getitem`/`setitem` access.
- Expanded supported Popolo organisation classifications to include `committee`, `cross_party_group`, `local_authority`, `combined_authority`, and `other`.
- Added `description` and `parent_id` fields to organisations from the Popolo spec, with cross-checking that `parent_id` refers to a valid organisation.
- Added `name_variants` and `original_full_name` to `LordName` to generate the range of styles (e.g. "The Earl of Erroll", "The Lord Bishop of Norwich") transcripts use to refer to a Lord.
- Added `include_historical_names` to `IndexedPeopleList.from_name`, so a person can be looked up by any name they've ever held (e.g. a later peerage title) while still gating eligibility by chamber and date.

### Changed

- Allowed supplemental (non-constituency) `Post` IDs and made `Post.area` optional, to support posts such as committee memberships.
- Improved Lords name construction: `nice_name` now builds "Bishop of Norwich"/"Earl of Arran" style names when there's no `lordname`, and `LordName` now validates that a `surname` is paired with a `lordname`, or a `lordofname` and `honorific_prefix`.
- `honorific_prefix` is now always required on `LordName` rather than optional.
- `NameIndex` now looks up current Lords by their membership's organisation directly, since Lords memberships have no associated post.
- The membership overlap check now only compares postless memberships (e.g. Lords) within the same organisation, so a person can hold a committee membership and a Lords membership at the same time.
- `NameIndex` now tracks name collisions as entries are added; `get_id_reduced` raises on an ambiguous name instead of silently resolving to whichever person was indexed last.

## [1.3.3] - 2026-08-15

### Fixed

- Made transcript `Speech.items` optional.
- Added `data/sp-debates2026-03-13.xml` and accompanying tests covering Holyrood divisions preceded by these stub speeches.

## [1.3.2] - 2026-08-05

### Fixed

- Relaxed transcript `GIDPattern` chamber matching to allow hyphenated lower-case segments (for example `london-mayors-questions`).


## [1.3.1] - 2026-04-30

### Fixed

- Added `parent_compatibility_check` implementations to `Person`, `Post`, `Organization`, `PersonRedirect`, `MembershipRedirect`, and `Area` so that `append` correctly rejects duplicate entries in `IndexedList`.
- Added tests covering duplicate-rejection for each of the above types.

## [1.3.0] - 2026-02-27

### Added

- Added `Question`, `Reply`, and `Source` models to transcript schema.

### Changed

- Relaxed GID pattern to allow alphanumeric and hyphenated segments.
- Added missing `instagram_username` and `threads_username` to test fixtures for live data compatibility.

## [1.2.0] - 2025-09-18

### Added

- Added fixed start and end reasons to match TWFY database restrictions.
- Add source_url capture options to party change CLI functions.

## [1.1.5] - 2025-07-01

### Changed

- Expand allowed versions of httpx
- Add missing bluesky_handle to allow tests off live data.


## [1.1.4] - 2025-03-24

### Changed

- Need to manually add items to __pydantic_set so is exported correctly.

## [1.1.3] - 2025-03-24

### Changed

- Added Senedd, ScotParl identifer schemes
- Added default empty list for InfoCollection.

## [1.1.2] - 2025-03-23

### Changed

- Fixed typing on InfoCollection for better support of subclasses.

## [1.1.1] - 2025-03-20

### Changed

- Removed incorrect sub_details_group value in favour of proxy property.

## [1.1.0] - 2025-03-11

### Added

- Details addition functions to Regmem.

### Changed

- Better slugify function for regmem entries.
- Added 'full' save option for regmem (include default values etc).


## [1.0.0] - 2025-01-23

### Added

- RegmemRegister model structure.
- Add schema jsons and mardkwons.

### Changed

- Rename older XML Register to new location.

## [0.10.0] - 2024-12-09

### Changed
- Mark shortcuts as deprecated.
- Make record optional for regmem (new format doesn't create them).
- Enable time range overlap checks for popolo.
- Bring LordName into consistent date approach.
- Remove rogue reason rather than end_reason.

## [0.9.3] - 2024-12-09

### Changed
- Correct 'person_entires' to 'person_entries'.

## [0.9.2] - 2024-12-09

### Changed
- Extend not saving start_date when default to memberships (for whip removal).

## [0.9.1] - 2024-12-09

### Changed
- Update minimum required click to 8.1

## [0.9.0] - 2024-12-09

### Added
- Added cli options for adding parties, removing whip, and adding name.

## Changed
- CLI interface now uses more sub-menus for consistent formatting.
- Doesn't require a people.json path is one is in an expected location. 

## [0.8.0] - 2024-12-04

### Added
- Improved helpers for adding person identifiers.
- New `person.add_identifer` method works as a shortcut.

## [0.7.0] - 2024-12-03

### Added
- SCOTPARL identifer shortcut added.

## [0.6.5] - 2024-11-29

### Changed
- Include XML declaration by default when writing XML files.

## [0.6.4] - 2024-11-29

### Changed
- Allow twfy as valid wrapper for register of interests format. 

## [0.6.3] - 2024-11-29

### Changed
- Mixed content writer handles wider range of valid xml. 


## [0.6.2] - 2024-11-28

### Changed
- Wider lxml requirement range.

## [0.6.1] - 2024-11-25

### Changed
- Allow more transcript revisions.


## [0.6.0] - 2024-10-08

### Added
- Support for devolved transcripts through downloader.
- Added format option for CLI.

### Changed
- Roundtrip test is less sensitive to whitespace at the start and end.

## [0.5.0] - 2024-09-30

### Added
- Added InfoCollection approach and related tests.
- A few more fields from the popolo standard  
- Approach to loading add-on popolo files. 

### Change
- Popolo membership and people iterators will not return the redirect objects. These are accessed seperately through `.redirects()`.
- Popolo date range validator improved and disabled until upstream data change. 


## [0.4.0] - 2024-09-23

### Added
- 'validate' option for from_xml_path. 

### Fixed 
- Expanded transcript validation options for Scottish Transcripts.


## [0.3.2] - 2024-09-23

### Fixed 
- Expanded transcript validation options for pre-2015 transcripts.

## [0.3.1] - 2024-09-11

### Fixed 
- Removed unnecessary tag discriminators that were causing problems loading the interests model in later pydantic versions.

## [0.3.0] - 2024-09-08

### Add
- Download handler for Transcripts

### Change
- Consistently re-export relevant enum collections under models.

## [0.2.1] - 2024-09-03

### Change
- Less restrictive rich versioning for better cross compatibility.

## [0.2.0] - 2024-08-27
### Added
- New iter `iter_headed_speeches` for Transcripts.
### Change
- `__str__` used for consistent external API when a Transcript related object is stringable.


## [0.1.1] - 2024-08-27
### Change
- Package description.

## [0.1.0] - 2024-08-27
### Added
- Initial release.

## [x.x.x] - YYYY-MM-DD
### Added
- Anything added since last version
### Changed
- Anything changed from last version