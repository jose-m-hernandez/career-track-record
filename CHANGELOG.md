# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- In CI, the maintainer barred-strings scan prints only the number of hits, and a malformed list fails without naming the entry. Local runs still print each hit's entry number and where it was found, and name the malformed entry.

## [0.2.0] - 2026-10-21

### Added

- `track-record barred`: reports where a file's text or name uses wording from your own barred list, by entry number only, and refuses to call a file clean when it could not read it in full. A file name hyphenated across a line break still matches, and the paths it prints are escaped, so no file name can forge an output line.
- The barred-wording check's behaviour spec, `docs/specs/barred.md`.
- The no-network test now lets one module start one program: `pdf_text.py` may run `pdftotext`, and nothing else.
- `track-record tone`: flags hype, hedges and filler in résumé and profile copy, names the sentence and the reason, and fails only on rules you set as errors.
- A default rule set for the voice and tone check, each rule proven against its own examples before any file is checked.
- The voice and tone check's behaviour spec, `docs/specs/tone-and-tells.md`.
- METHOD.md: the six rules these tools are being built to.

### Changed

- README and AGENTS.md now name the three tools that ship. The README also covers how to install them and what's coming. AGENTS.md says the repository serves anyone managing their own career, not only a job search.
- The keyword scan's spec now names its releases in words: the parity release, which ships, and the citation release, which comes next.

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
