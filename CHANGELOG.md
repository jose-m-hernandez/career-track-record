# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The Reader A/B spec, docs/specs/reader-ab.md, is revision 3, a draft its owner has not signed yet, built on revision 2, also unsigned. Revision 2 puts an exact p-value, an interval and the missing reads beside each verdict, and corrects what section 1 claims for the A/A control. Revision 3 adds an optional sensitivity arm (a version against a copy weakened on purpose), replicate runs and an optional read floor, and lets a settled completion lift an INCONCLUSIVE when the plan sets a floor. **It changes verdicts:** reads from a reader marked `not-blind` are no longer counted in any verdict.
- The reader panel spec, docs/specs/reader-panel.md, is revision 3, a draft its owner has not signed yet, built on revision 2, also unsigned. Revision 2 puts an interval beside each clause count, an exact p-value when a rule names a share to test against, and the missing reads beside each verdict, and its inner status line and decisions now read as signed. Revision 3 adds replicate runs and an optional read floor, and the same lift. **It changes verdicts:** reads from a reader marked `not-blind` are no longer counted in any rule or gate.

## [0.7.0] - 2026-11-06

### Added

- `career_track_record/stats.py`: the exact binomial p-value and the 95% Wilson interval the reader commands will print beside their verdicts, with the spec's rounding (p half up to 4 places; the interval's ends rounded outward to 3).
- `track-record ab` plans take two optional keys from the Reader A/B spec revision 2: `sidedness` (`two`, `greater` or `less`; default `two`) and `alpha` (written `0.` and digits, not all zero; default `0.05`). `freeze` refuses any other form, naming the plan line.
- `track-record ab` results put the evidence of the Reader A/B spec revision 2 beside each verdict: the exact sign-test p-value and the 95% Wilson interval for the second-listed version's share of non-TIE picks, a flag when that evidence disagrees with the verdict (or a line saying a one-sided test did not look at the verdict's direction), the A/A gate's own interval, the count of not-blind reads on every verdict line, and one validity line. No verdict or exit status changes.
- `track-record ab` results count each arm's missing reads (failed, and not run), say for each hypothesis whether its verdict would hold whatever the missing reads had said, with the range of the p-value, and print a `DEAD` line when no read is valid. These lines never change a verdict, and a dead run still exits 1.
- `track-record ab` results say, for each arm, how many valid reads scored both slots at 10 or more and how many gave both the same score, and say when every read is at the ceiling, so that preference is the only measure there.
- `track-record panel` plans take three optional items from the reader panel spec revision 2: `max <n>` on a lens (the top of its own scale, at or above `anchor-strong-at-least`), `null-share <n>/<d>` on a rule (the share of reads expected to pass each test by chance, strictly between 0 and 1), and `sidedness` (`two`, `greater` or `less`). `freeze` refuses any other form, naming the plan line.
- `track-record panel` results put the evidence of the reader panel spec revision 2 beside each verdict: a 95% Wilson interval for each clause count, an exact p-value against the rule's `null-share` when it declares one, the count of not-blind reads on every rule verdict line, and one validity line, the same as `ab`'s. No verdict or exit status changes.
- `track-record panel` results count each lens's missing version reads (failed, and not run), say for each rule whether its verdict would hold whatever the missing reads had said, and print a `DEAD` line when no read is valid. These lines never change a verdict, and a dead run still exits 1.
- `track-record panel` results give, for each lens, the version's lowest score beside the strong anchor's highest and the version's spread, say when the lens cannot rank the version above the strong anchor or gives every read the same score, and, when the lens names `max`, the room between the strong anchor and the top of its scale.

### Changed

- The Reader A/B spec, docs/specs/reader-ab.md, is revision 2, signed by its owner: it puts an exact p-value, an interval and the missing reads beside each verdict, says when a one-sided test did not look at a verdict's direction, and corrects what section 1 claims for the A/A control. It changes no verdict, exit status or prompt.
- The reader panel spec, docs/specs/reader-panel.md, is revision 2, signed by its owner: it puts an interval beside each clause count, an exact p-value when a rule names a share to test against, and the missing reads beside each verdict, and its inner status line and decisions now read as signed. It changes no verdict, exit status or prompt.
- The README says what a reader result means and what the reader tools' controls show, and METHOD.md's status line says how Reader A/B relates to rule 6.
- The Reader A/B and reader panel specs are revision 2.1: each adds the maintainer's build interpretations of revision 2 after its signed text (no flag beside an A/A-gate or position reason line; where the new lines go; how the completions are tried; the panel's rule labels, its room line with no strong-anchor read, and no p when a rule counts no read). The signed text is unchanged.

### Fixed

- 0.6.0's package reported its version as 0.5.0; 0.7.0 corrects the version string.

## [0.6.0] - 2026-11-05

### Added

- `track-record panel`, the reader panel: it reads one version of your copy blind through lenses you name, each a reader role given as a plain-text prompt file frozen with the plan. Every lens also reads a planted strong anchor and a planted weak anchor; a lens that does not rank them is not counted. Rules per lens and overall end PASS, FAIL or INCONCLUSIVE. The plan format, freeze, `--live` rule, spend ceiling and fake reader are those of `ab`. A lens defines its own scale (the built-in prompt states none, and a score of 0 is valid), and the built-in prompt tells the reader to write exactly `none` for a free-text field with nothing material. `freeze` refuses a PASS clause `score at least <n>` above `anchor-strong-at-least`. Its spec, docs/specs/reader-panel.md, is revision 1, signed by its owner.
- A decision record, `docs/decisions/2026-11-05-the-reader-commands-share-one-harness.md`: what `ab` and `panel` share lives in one module, `reader_harness.py`, which starts no program.
- `track-record claims --check-sources`, the quote check, a port of an evidence-check method in which a quote must appear in the source it cites. Under an entry that has a source, a claims list can now hold a `quote` line: `quote`, a tab, then a phrase. With the flag, the quote of each `approved` and `proposed` entry is looked for, word for word after folding and on word boundaries, in the local file its source names, as a path relative to the list's folder; `refused` entries are never checked. Only regular files are read, as UTF-8 text or as PDFs through `pdftotext`, and a source that is not a regular file is never opened. An approved quote that is not found makes the run exit at least 1. An approved source that cannot be read makes it exit 2: a directory, a FIFO or a device, a dangling link, a path the gate has no permission to look up, a file that isn't UTF-8 text, or a PDF whose `pdftotext` is missing or fails. A source that is not a local file (a URL, a record id, a missing path, or a name no file can have) is reported unverified: it is printed and counted, and does not change the exit code. A proposed entry never changes the exit code. Each result prints as one line naming only the entry's status and number, followed by two count lines; no quote, source, path or source text is printed. A quote that ends in a number is not found inside a longer number (`Version 2.` is not found in `Version 2.5`). The search lives in `career_track_record/quote_check.py`. Without the flag, every run's output and exit code are as before, except that a list with a `quote` line, which was refused as an unknown status, is now accepted.

### Changed

- The parts of `ab` that `panel` also needs (the plan-file syntax, the freeze and its checks, the run folder, live reads, the read loop and the result's tail) moved from `ab.py` into `reader_harness.py`. `ab`'s behaviour, output and tests are unchanged.
- The command-line spec, docs/specs/cli.md, is revision 4: it names `panel` and its fixed help text.
- The README opens with six checks and adds a `track-record panel` section. AGENTS.md names six tools. METHOD.md lists the reader panel as running rule 6.
- The claims spec, docs/specs/claims.md, is revision 2, signed by its owner: it adds the quote line, `--check-sources` and the number boundary. The build readings of revision 1 still apply.
- The command-line spec, docs/specs/cli.md, is revision 5: it notes that `claims` takes `--check-sources` and lists it in its fixed help text.
- The README's `track-record claims` section describes quote lines and `--check-sources`, and its Coming section no longer promises the quote check. METHOD.md's status line says the claim gate checks quotes on request, and does not yet flag a claim with no source.
- The barred-check spec, docs/specs/barred.md, is revision 7, signed by its owner: it reads each PDF in layout mode too, and replaces the known limit for wraps inside a page with one for pages set in columns.

### Fixed

- `track-record barred --min-chars` with thousands of leading zeros (for example 5000 zeros then `5`) crashed with a traceback on Python 3.14; it now reads as its value, 5, and a value with more than 18 significant digits still gives the usage error.
- `track-record barred` also reads each PDF in `pdftotext`'s layout mode (a port of a wrapped-compound check method that reads `pdftotext -layout` output), so a hyphenated entry wrapped at its hyphen inside a page is caught, and so is a `word`-flagged half of it. The default-mode read still sets the length, the control and line numbers, so nothing caught before is missed. A soft hyphen that ends a line in the layout text counts as a hyphen. A wrap beside another column's text is still missed.

## [0.5.0] - 2026-11-04

### Fixed

- `track-record claims` was slow on a long file when the claims list held one long entry (about 2,400 characters): its run time grew roughly with the cube of the number of sentences, so 200 short sentences took about 2.4 s, 400 took about 18 s, and a 14 KB file ran past 60 s. For each sentence the gate now tries only runs of at most as many sentences as the most any entry could cover, counted from the full stops, exclamation marks and question marks inside the entries, and the same file now finishes in well under a second (0.03 s measured). The output is byte for byte the same as before, and the command line and the list format are unchanged. Known limit: a list entry that is itself made of hundreds of short sentences can still make the gate slow, even on a short file (an entry of 800 sentences took about two minutes on a 3 KB file).

## [0.4.0] - 2026-11-02

### Added

- `docs/provenance.md`, a ledger with one row per file in the repository: the harness and model recorded writing to it, and the day of the latest recorded write. A test fails if a file has no row or a row has no file.
- `track-record claims`, the claim gate: it fails on any sentence in your copy that your claims list has not approved. A sentence you change is a new sentence and fails until you approve it again. Every run names a control phrase that each file must hold, or the file is DEAD. Output prints only text from the file you check. `--stale-check` also reports approved entries that no file uses. Spec: docs/specs/claims.md.

### Changed

- The README now opens with what each tool does for you, adds a First run section that tries the barred-wording check on the shipped test fixtures and a section on why you can trust a result, and names the maintainer and the copyright holder.
- The Reader A/B spec is revision 1.2: its status line now records that the owner settled decision 6 on 2026-10-29, and the owner re-signed it.
- The command-line spec, docs/specs/cli.md, is revision 3: it names `claims` and its fixed help text.
- The README now opens with five checks, adds a `track-record claims` section, and plans 0.5.0 where it planned 0.4.0. AGENTS.md now names five tools. METHOD.md now lists the claim gate as running rule 6, and says it stores a source for each claim without checking it.
- Two test docstrings no longer carry an internal label. Tests only.

## [0.3.0] - 2026-10-30

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
