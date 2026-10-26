# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The barred-wording check's behaviour spec, revision 6.1, lists exactly which characters count as whitespace and adds a third way of comparing text, one that keeps a plain hyphen at the end of a line. It describes how a hyphenated entry wrapped at its hyphen is caught, and states a known limit: inside a PDF page, that wrap is still missed. This change is documentation only.

## [0.2.1] - 2026-10-26

### Added

- The maintainer barred-strings scan can accept an intentional use of a barred entry, in one file's contents or one commit, that the maintainer has approved privately; every other use still fails, and a file or branch name is never accepted.
- `track-record tone` reads PDFs: a file whose name ends in `.pdf` (any case) is checked as the text `pdftotext` extracts from it, the same extraction `track-record barred` uses. Tone checks that text as written, without folding, so case-sensitive rules still apply.

### Changed

- In CI, the maintainer barred-strings scan prints only the number of hits, and a malformed list fails without naming the entry. Local runs still print each hit's entry number and where it was found, and name the malformed entry.
- The documentation calls the tone check the voice and tone check. The command is still `track-record tone`.
- The behaviour specs for the barred-wording check, the keyword scan and the voice and tone check now say what happens when output can't be written or standard error is closed. The voice and tone check's spec also says how it prints file names and which options may be repeated. This entry changes documentation only.
- In CI, the maintainer barred-strings scan's messages for a repository state it can't scan (a submodule, or a file or commit that isn't UTF-8 text) no longer print the ID of the commit or file involved; run the scan locally to see which.
- CONTRIBUTING.md now says how to name the maintainer barred-strings scan and a barred entry.

### Fixed

- The test suite no longer hangs when it runs with standard input left open.
- Every `track-record` command exits 2 with one line, `cannot run: cannot write output`, when its output cannot be written (a closed or broken pipe, or a full disk), instead of a traceback; a closed standard error no longer changes the exit status.
- `track-record keywords` treats a term pattern too large or too deeply nested to compile as an invalid pattern (exit 2, one line), instead of a traceback.
- `track-record tone` escapes control and format characters in the file names it prints, as `barred` does, so a file name can no longer forge an output line.
- `track-record tone` stops at the first stage of a run that fails (for example, the rule file is read and its rules proven against their own examples before any input file is opened) and reports every problem in that stage.
- The maintainer barred-strings scan now refuses a list or allow file inside the repository even when its path is spelled with different letter case, as on a case-insensitive disk.
- The maintainer barred-strings scan now refuses a list or allow file that has more than one hard link, because a link outside the repository could point at a file inside it.

## [0.2.0] - 2026-10-21

### Added

- `track-record barred`: reports where a file's text or name uses wording from your own barred list, by entry number only, and refuses to call a file clean when it could not read it in full. A file name hyphenated across a line break still matches, and the paths it prints are escaped, so no file name can forge an output line.
- The barred-wording check's behaviour spec, `docs/specs/barred.md`.
- The no-network test now lets one module start one program: `pdf_text.py` may run `pdftotext`, and nothing else.
- `track-record tone`: flags hype, hedges and filler in résumé and profile copy, names the sentence and the reason, and fails only on rules you set as errors.
- A default rule set for the tone check, each rule proven against its own examples before any file is checked.
- The tone check's behaviour spec, `docs/specs/tone-and-tells.md`.
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
