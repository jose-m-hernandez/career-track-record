# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `track-record barred`: reports where a file's text or name uses wording from your own barred list, by entry number only, and refuses to call a file clean when it could not read it in full.
- The barred-wording check's behaviour spec, `docs/specs/barred.md`.
- The no-network test now excuses one module, by exact problem, to run `pdftotext`.
- `track-record barred` checks file names in both forms, so a name hyphenated across a line break still matches, and escapes control and format characters in the paths it prints, so no file name can forge an output line.
- METHOD.md: the six rules these tools are being built to.

### Changed

- README now covers what ships today, how to install it, and what's coming.
- AGENTS.md now says which tools ship, and that the repository serves anyone managing their own career, not only a job search.

## [0.1.0] - 2026-10-20

### Added

- README, AGENTS.md (the instructions your AI agent reads) and this changelog.
- The AGPL-3.0 licence text.
- Contributing and security policies, code owners and a pull request template.
- The first two decision records: the CLAUDE.md bridge and this changelog's format.
- A CI scan that fails a push or pull request if any entry from a private list appears in its history, author or committer names and emails, or branch name. It never prints the match.
- Package metadata in setup.cfg, and a test that the package builds offline on Python 3.9.
- CI installs setuptools from a hash-pinned requirement on both test legs, and the offline build test fails in CI instead of skipping when setuptools is missing.
- A placeholder commercial-licence notice.
- A decision record of the one read of career-ops's source and how its findings reached this project.
- `track-record keywords`: a keyword scan of saved job postings, with three modes (`demand`, `coverage`, `report`), that shows which terms the postings ask for and your own copy never uses.
- A reader and writer for the saved-posting file format, which checks each posting against its recorded SHA-256 and refuses one that does not match.
- The keyword scan's behaviour spec, `docs/specs/keyword-scan.md`.
- A test that no tool module imports a network or mail capability.

### Changed

- SECURITY.md now promises a best-effort reply to a private report, not a guaranteed one.
- CONTRIBUTING.md now states that every change is reviewed independently before it lands.
