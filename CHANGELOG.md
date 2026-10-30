# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `track-record ab`, Reader A/B: it compares two versions of your copy by asking test readers which reads better, under a plan you freeze by hash before the first read. Every run includes an A/A control (the same version in both slots), checks that the two versions differ only where the plan says, and scores the replies against the frozen rules. The subcommands are `freeze`, `run` and `score`. A live reader is a command you name, and it runs only when you add `--live`. Spec: docs/specs/reader-ab.md.
- A decision record, `docs/decisions/2026-10-29-a-reader-command-is-the-one-outside-program-a-user-names.md`, and a matching CONTRIBUTING line explain why a reader command a user names may start an outside program.

### Changed

- The no-network test now lets a second module, `ab_reader_command.py`, import `subprocess`, and checks that it makes exactly one `subprocess.run` call, with an argument list and no shell. The only keyword it adds to `pdf_text.py`'s call is `cwd`.
- CI installs `poppler-utils`, so the test that reads a PDF version with the real `pdftotext` runs there.
- The command-line spec, docs/specs/cli.md, is revision 2: it names `ab` and its fixed help text.
- The README's statement that the tools cannot send anything now names the reader command as the one exception.

### Fixed

- An offline install on a stock Python 3.9 failed with `invalid command 'bdist_wheel'`. The package now asks for setuptools 70.1 or later to build, and the README says how to install offline.
- The packaging test failed, rather than skipping, on a Python without `bdist_wheel`.

## [0.2.2] - 2026-10-27

### Added

- `track-record barred` and `track-record tone` accept `-h` and `--help`: each prints its fixed help text and exits 0, without reading any file. The new command spec, docs/specs/cli.md, states the help rule that `track-record keywords`, `barred` and `tone` share.

### Changed

- The barred-wording check's behaviour spec, revision 6.1, lists exactly which characters count as whitespace and adds a third way of comparing text, one that keeps a plain hyphen at the end of a line. It describes how a hyphenated entry wrapped at its hyphen is caught, and states a known limit: inside a PDF page, that wrap is still missed. This change is documentation only.
- The test sources write invisible characters and the no-break space as escapes, and a test fails if one appears raw in any Python file under `tests/`. More tests pin rules of the voice and tone check that its spec states.
- More tests pin how the PDF reader behaves: the time-limit test now runs a program that really waits, so it fails unless the limit stops it, and new tests check that the voice and tone check prints an unreadable PDF's name escaped and that `pdftotext` is started with no standard input. Tests only.
- The no-network test now also fails if a tool starts a program through `os.exec*`, `os.spawn*`, `os.fork` or a similar call (the one `pdftotext` call in `pdf_text.py` stays allowed), imports another network module (`_socket`, `_ssl`, `socketserver`, `wsgiref`, `nntplib`), imports `email`, or imports `runpy` or `code`, which run code from a string or file, or looks up names by string through `globals`, `vars`, `locals`, `__dict__` or `sys.modules`. It still checks names as written, not aliases, chains of lookups or names built from strings.
- A new decision record says `AGENTS.md` is the only instruction file and the repository has no `CLAUDE.md`. It supersedes the 2026-10-19 record that kept a one-line `CLAUDE.md`, which was removed in 0.2.1. Documentation only.
- CONTRIBUTING.md states four more rules, each with its decision record: known limits, starting an outside program, UTF-8 files, and where a test module's main guard goes.

### Fixed

- `track-record barred` now catches an entry with a plain hyphen, wrapped at that hyphen, such as `zebra-word` written as `zebra-` at the end of one line and `word` at the start of the next, in a text file, in a file name and across a PDF page break. Inside a PDF page it is still missed, because `pdftotext` removes the hyphen there.

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
