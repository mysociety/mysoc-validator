# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[comment]: # (Template for updates)

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