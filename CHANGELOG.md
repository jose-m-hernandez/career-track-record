# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.4] - 2026-11-17

### Changed

- The `ab` guide now warns that `claude --help` does not list connectors or MCP servers among what the `claude` fallback's flags turn off, and that no live run has been checked for connector tools. Docs only.

### Fixed

- `docs/specs/drafts.md` errata E1: the failure line `cannot run: cannot write output` follows any warnings already written. Docs only.
- `docs/specs/reader-ab.md` errata E2: a reader's name is a label, so an extension may name every reader anew. Docs only.
- `docs/specs/keyword-scan.md` errata E3: the verbatim guarantee is stated directly, without a pointer to a README promise that is not there. Docs only.
- `docs/specs/reader-ab.md` errata E4: the signed text's sentence that the README gives the effect each read count can detect is withdrawn, since no such table exists. Docs only.
- `docs/specs/reader-ab.md` errata E5: build interpretation 29 no longer says the README's example plans are checked by a test, since no such test exists. Docs only.
- Correction to 0.10.2: `--terms` errors for a file that cannot be read, is not valid UTF-8, or holds an invalid regular expression do not yet name the format and guide; the hint lands with the parse-error fix.

## [0.10.3] - 2026-11-17

### Changed

- `examples/readers/model_reader.py` now passes `--disable apps` to `codex exec` (one module constant, `CODEX_APPS_OFF`), which turns codex's apps and connectors feature off. The flag is the one `codex exec --help` lists as equivalent to `-c features.apps=false`. Whether a `codex exec` run then offers no connector tools has not been measured. The `claude` fallback is unchanged.
- The `ab` guide now says in brackets, at its first use of "A/A", that an A/A read gives the reader the same version twice, as a control.
- The `ab` guide has a worked example of `change-scope`: a pattern is a Python regular expression tried with `re.search` against every changed line, both the removed and the added text must match, `run` stops with exit 2 before any read when a changed line is outside the scope, and `freeze` does not check it.
- The `ab` guide's first test lists `--disable apps` in the Codex command, and says that the app-server check offered 0 tools with it and 431 without, that this was not a `codex exec` run, and that anyone with a mail app connected to the account they sign in to Codex with should use a reader of their own instead of the example.
- The `barred` guide's `--min-chars` section says what the joined form is: the text after the tool's folding, with every run of whitespace turned into one space and nothing trimmed, so a final line feed counts as one space.

## [0.10.2] - 2026-11-17

### Added

- `examples/readers/model_reader.py`, an example reader for `ab --live` that asks `codex exec` (read-only sandbox, no approval prompts) or, as the fallback, `claude -p` (built-in tools off) about one pair and prints the reply, with tests that use a fake CLI and never call a model.
- The `ab` guide's "Your first A/B test": a plain-words walk-through with a copy-paste plan at `examples/ab-first-plan.txt`, invented files under `examples/ab-first/`, and the `freeze`, `run` and `run --live` steps.
- The keywords guide's "A worked example": a headed posting, a posting with a `.meta.json` sidecar, how to get its hash, and a three-term `terms.tsv`, all invented, under `examples/keywords/`.
- `ab freeze` and `panel freeze` now warn on standard error, one line per reader, when a live reader's program is an absolute path that does not exist or cannot be executed, a bare name that is not on PATH, or a `python3 /abs/script.py` whose script does not exist. The freeze is still written and the exit status is still 0; the freeze file's contents and hash do not change. Before, a bad path showed only after a live run had spent its reads.

### Changed

- `keywords` errors for a missing, empty or malformed `--terms` file and a posting with no header or sidecar now name the format and point to the guide's worked example. `--terms` stays required, and its `--help` line names the format and the guide.
- The refusal "a freeze file already exists" now says why and what to do: one plan per folder, so put the plan in its own folder. The `ab` guide's first test states the rule.
- The README no longer says that no live reader ships: it says the package ships none, that the example reader under `examples/readers/` starts `codex` or `claude`, which reach the network and spend the user's own plan, and that the no-network test scans `src/` only.
- The README's front page now leads with the pointer to First run, the exit codes sit in their own "Exit codes" section instead of a tool-table column, the three things each check shows it was looking for are a list, and the credit line sits under Maintainer.

### Fixed

- A read number in a run's key file may have any number of digits on every supported Python; before, one of more than 4,300 digits crashed `ab score` and `panel score` on Python 3.11 and later.

## [0.10.1] - 2026-11-16

### Added

- A test pins that an extension which renames every reader still counts the first run's pairs from each model family when it checks that a version a model drafted wins with another family's readers.
- The barred guide documents `--min-chars`.

### Changed

- METHOD.md's status line no longer says that Reader A/B's reads have no control that must be found. It says that every read carries the self-read control, that a plan may add a control that must be found (a copy of a draft weakened on purpose), and that a run without that second control that finds no difference does not show the readers could have found one. It also says that `--check-sources` checks the quotes of approved and proposed entries, not refused ones.
- The README's tool reference moved word for word into one guide per tool under docs/guides/; the README now links to each.
- The README's exit-code cells for `ab`, `claims` and `record`, and the `ab` guide, now match the guides and the code: `ab freeze` exits 0 when it writes the freeze file, `claims` exits 1 for an approved entry no file uses (with `--stale-check`) or an approved quote not found (with `--check-sources`), and `record --report-only` exits 0 unless a check is DEAD.
- The README is cut to a front page: a table of each tool's question, exit codes and guide, three reasons to trust a result, the install and first-run steps, and links.

### Fixed

- An extension's `A/A slightly rate` line counts only the extension's own A/A reads; the first run's reads still count in the A/A gate.
- `keywords` `coverage` and `report` refuse a run with no copy file (exit 2) instead of printing an empty table or calling every term a gap.
- A reader command that contains a NUL byte is a failed read, not a crash.
- A posting's `.meta.json` that is nested too deeply to read is reported as not valid JSON (exit 2), not a traceback.
- A reader's score may be any whole number of any size on every supported Python; before, a score of more than 4,300 digits crashed `ab` and `panel` on Python 3.11 and later, and a score of more than about 300 digits crashed them on every Python when the result printed a mean. A mean that a float could hold prints as before.
- A whole number in an `ab` or `panel` plan may have any number of digits on every supported Python; before, a score threshold, a lens's `max` or a rule's count of more than 4,300 digits crashed `freeze` and `run` on Python 3.11 and later, as did a reads-per-reader, noise threshold, `alpha`, mechanism count or fake-reader read number of that size in `ab`.
- A spend ceiling, a live reader's cost or a fake reader's random seed of more than 4,300 digits no longer crashes `ab run` or `panel run` on Python 3.11 and later.
- The built-in fake reader no longer fails on a score of more than 4,300 digits on Python 3.11 and later, in a rule's score or in the reply it writes, in `ab` and in `panel`.
- A usage error exits 2, with the usage line on standard error where it can be written, even when standard error is closed or cannot be written. In 0.10.0, when standard error could not be written the exit status was 120, and when it was closed the usage line went to standard output and the exit status was 1 on Python 3.9 and 2 on Python 3.14.
- The record check's CSV reader no longer stops at a field of two billion characters; it asks for the largest field size the platform allows.

### Security

- The setuptools that CI builds the package with is raised to 84.2.1 on Python 3.10 and later, which has the fix for two reported weaknesses in that build tool (GHSA-xmj3-9gf7-h52w and GHSA-h35f-9h28-mq5c). On Python 3.9 it stays at 82.0.1, because no fixed setuptools supports Python 3.9. The weaknesses are in the tool that builds the package, not in the package, and nothing that `pip install` puts on your machine changes.

## [0.10.0] - 2026-11-15

### Added

- `track-record drafts` checks the file that holds a document's versions, and reports each break by file and line: a section that breaks the form, ids out of order, a parent or a named version that does not exist, an empty change note, dates that run backwards, a second send entry, a `sha256:` line that does not match, a run folder that does not exist, and an earlier copy that is no longer the start of the file. `track-record drafts extract` checks the file and writes one version's text to a new file. It never writes to the draft file and never prints a version's text, a change note or a result note; it runs a self-test of every rule first, reports a check that looked at nothing as DEAD (exit 2), and exits 1 for a fault.
- The drafts spec, docs/specs/drafts.md, is revision 1, signed by its owner.

### Changed

- The barred-check spec, docs/specs/barred.md, is revision 7.1, signed by the maintainer: its status line now states where the layout check came from and how it was specified and built. This corrects a clause of revision 7, which said that nothing in it comes from any private tool or record. No behaviour changes.
- The claim gate spec, docs/specs/claims.md, is revision 2.1, signed by the maintainer: its status line now states where the quote check came from and how it was specified and built. This corrects a clause of revision 2, which said that nothing in the quote check came from any private tool or record. No behaviour changes.
- The barred-wording spec, docs/specs/barred.md, is revision 8, signed by its owner. Every input file that is not a PDF, and every file name, is now also compared after a line-end soft hyphen that follows a word character becomes a hyphen, as a PDF's layout text already was; the text as read is still compared, so nothing matched before is missed. **It changes results:** a text or file name that wraps a word at a line-end soft hyphen now fails an entry for the whole word that it passed before, and the run exits 1 where it exited 0.
- A plan frozen with an earlier release is refused: `run` and `score` exit 2 and say to score it with the release that froze it or write it again as a new plan. A new plan must name each reader's model `family` and who drafted each version (`drafted-by`).
- The default is now 12 reads per arm, up from 6, because each reader reads every pair in both orders. `reads-per-reader` must be an even number.
- A reader's pick counts only when both orders agree. `slightly` picks now count in the A/A gate. If a model drafted or edited the winning version and a blind reader is of that model's family, blind readers of another family must agree too, or the verdict is INCONCLUSIVE.
- The Reader A/B spec, docs/specs/reader-ab.md, is revision 4, signed by its owner. Each reader reads every pair of versions in both orders, and a pick counts only when both orders agree. **It changes verdicts:** rules count paired picks, `slightly` A/A picks count toward the noise gate, a read floor counts valid pairs, a mechanism needs a margin over its A/A floor, and a version drafted by a model of a reader's family needs readers of another family to agree. The default run makes twice the reads it did: 12 per arm, was 6. `freeze` now refuses, with exit 2, an odd `reads-per-reader`, a version without `drafted-by`, a reader without `family`, or an amendment that changes a threshold. `run` and `score` refuse a plan frozen under an earlier revision, exit 2. An optional `document` key (`résumé`, the default, `cover letter`, `essay` or `profile`) names the kind of document in the reader prompt. Without it, the prompt and its hash are unchanged.
- The command line spec, docs/specs/cli.md, is revision 7: it names `track-record drafts` among the eight commands and lists it with those whose fixed help text is in their own spec.
- The README names eight checks and has a `track-record drafts` section. AGENTS.md names eight tools.

## [0.9.0] - 2026-11-14

### Added

- `track-record record` checks the tables of your record against rules you declare, and reports each break by file and line: references that point at nothing (dangling references), repeated keys, empty or disallowed cells, bad dates, corrections that point the wrong way, and an old file that is no longer the start of the file now. It never prints a cell value, runs a self-test of every check first, calls a check that looked at nothing DEAD, and exits 1 for a finding (0 with `--report-only`) and 2 for a DEAD check. The drafter of this design had read the specification of a private tool that does a similar job for the maintainer's own records. No code or data from that tool is in the command's spec. Its wording was checked against that tool's specification and redrafted where it echoed it; the plain-English terms the check left in common, such as the flag name `--report-only`, keep their ordinary meaning.
- The record check spec, docs/specs/record-check.md, is revision 1, signed by its owner.
- The record-model document, docs/record-model.md: a record as a graph of nodes and references, what the record check covers and what it does not.
- A test, tests/test_placeholders.py, that fails while any file holds the placeholder marker for a sentence its owner has not yet worded, in any case and with any run of non-letter, non-digit characters between its two words, and the decision record behind it.
- A rule in CONTRIBUTING.md, and its decision record, that every date a change writes is the UTC day it is written.

### Changed

- The command line spec, docs/specs/cli.md, is revision 6: it names `track-record record` among the seven commands and lists it with those whose fixed help text is in their own spec.
- The decision record on the shared reader harness gains an Updated line: `track-record record` reads its declaration with the harness's plan-file syntax.
- The README names seven checks and has a `track-record record` section. AGENTS.md names seven tools. METHOD.md says the record check covers rules 1 to 4 as far as a table can show them, and points to docs/record-model.md.
- The README says that no desktop AI agent app has been tested yet.

## [0.8.0] - 2026-11-10

### Added

- `career_track_record/stats.py` gains the two-sided Fisher exact p-value, computed exactly, that a replicate run prints beside each count it compares with its first run.
- `track-record ab` and `track-record panel` readers can name a reader group (`reader-group <name>`), for readers that are alike, such as one model behind two commands. The result counts each group's valid reads; a group changes no verdict.
- `track-record ab` plans can name a sensitivity pair (`sensitivity: X vs W`, with `sensitivity-scope` and an optional `sensitivity-threshold`, default 5/6): a version against a copy of it weakened on purpose. It runs as its own arm, `s`, after the A/A arm and before the comparisons, and gets the isolation check against `sensitivity-scope`. Fake-reader rules reach it only when they name `s`.
- `track-record ab` results judge a sensitivity pair: when fewer than `sensitivity-threshold` of the valid sensitivity reads prefer the version over its weakened copy, or the arm has fewer valid reads than planned, every comparison and mechanism is INCONCLUSIVE, with the reason. The gate's line gives its count, a one-sided p-value and an interval, and each reader's score gap between the two. Without a pair, every result says `sensitivity gate: not tested`.
- `track-record ab` plans can set a read floor (`min-valid-reads`). A comparison with fewer valid reads from blind readers is INCONCLUSIVE "below the read floor". With a floor set and met, a verdict that is INCONCLUSIVE only because reads are missing, and that every completion of those reads settles the same way, takes the settled verdict, and the result says it was lifted.
- `track-record ab` plans can name a first run's freeze file (`replicate-of`), to run the same frozen plan again in a new folder. `freeze` refuses a replicate whose plan differs from the first in any other line, or whose inputs have changed since the first freeze. `run` and `score` refuse a replicate until the first run has been run, and never write to its folder. Each hypothesis's result compares the two runs' counts with a two-sided Fisher exact p-value.
- `track-record panel` plans can set a read floor (`min-valid-reads`). A rule that counts fewer valid reads from blind readers is INCONCLUSIVE "below the read floor". With a floor set and met, a rule that is INCONCLUSIVE only because reads are missing, and that every completion of those reads settles the same way, takes the settled verdict, and the result says it was lifted.
- `track-record panel` plans can name a first run's freeze file (`replicate-of`), under the same freeze rules as `track-record ab`, with the lens files among the inputs that must be unchanged. Each rule's result compares each clause's counted reads in the two runs with a two-sided Fisher exact p-value.

### Changed

- The Reader A/B spec, docs/specs/reader-ab.md, is revision 3, signed by its owner. It adds an optional sensitivity arm (a version against a copy weakened on purpose), replicate runs and an optional read floor, and lets a settled completion lift an INCONCLUSIVE when the plan sets a floor. **It changes verdicts:** reads from a reader marked `not-blind` are no longer counted in any verdict.
- The reader panel spec, docs/specs/reader-panel.md, is revision 3, signed by its owner. It adds replicate runs and an optional read floor, and the same lift. **It changes verdicts:** reads from a reader marked `not-blind` are no longer counted in any rule or gate.
- 0.8.0 changes verdicts: reads that weren't blind no longer count toward a verdict, and each verdict line shows how many were left out. Plans frozen under 0.7.0 still run, and a verdict that used not-blind reads can come out differently.
- `track-record ab` counts only blind readers' reads: reads from a reader marked `not-blind` are left out of every verdict, gate, mechanism count, score and missing-read line, and each verdict line ends with how many it left out (`[not blind: <b> reads left out]`). In a plan with a not-blind reader, the per-arm count line reads `reads blind readers`.
- `track-record panel` counts only blind readers' reads: reads from a reader marked `not-blind` are left out of every rule, anchor gate, score, flag count and missing-read line, and each rule's verdict line ends with how many it left out (`[not blind: <b> reads left out]`). In a plan with a not-blind reader, the per-lens count lines begin `reads blind readers`.
- The Reader A/B and reader panel specs are revision 3.1: each adds the maintainer's build interpretations of revision 3 after its signed text and carries forward revision 2.1's, amended where revision 3 changes them (what counts as blind, where the lines go, the sensitivity pair, the read floor and the lift, replicates, reader groups). The signed text is unchanged. A hypothesis may name the original version of a sensitivity pair; only its weakened copy is refused.
- The README's example plans no longer mark a reader `not-blind`, so every rule they show can be met under 0.8.0. The README says a not-blind reader's reads are never counted toward a verdict, its panel section names revision 3, and it lists the plan keys added in 0.8.0.
- The `track-record panel` version count line now names the readers first, as `track-record ab` does: `reads all readers <lens> version: …`.

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
