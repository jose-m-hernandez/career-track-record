# career-track-record

Six checks for the career copy you send. Open the repository in your own AI agent and ask in plain words:

- **Did any wording I ruled out get into this file?** The barred-wording check (`track-record barred`) finds it, whatever the case, ligature or invisible character around it, and reports which entry it was, never the wording itself.
- **What do the postings I saved ask for that my copy never says?** The keyword scan (`track-record keywords`) lists the gaps. It never rewrites your copy or sets a score to chase.
- **Does this sound like hype?** The voice and tone check (`track-record tone`) flags hype, hedges and filler, names the sentence and says why. It never edits.
- **Which of these two drafts reads better?** Reader A/B (`track-record ab`) asks test readers, under a plan you freeze first. A control that reads one draft against itself shows how often a reader picks a side when the drafts are the same. Each comparison ends SUPPORTED, REFUTED or INCONCLUSIVE, by the rule you wrote.
- **Is every sentence in this file one I approved?** The claim gate (`track-record claims`) fails on any sentence your claims list has not approved. A sentence you change is a new sentence, so it fails until you approve it again. It never decides whether a claim is true.
- **How does this one draft read to a recruiter, and to the hiring manager?** The reader panel (`track-record panel`) reads one draft blind through lenses you name, each a reader in a role. Every lens also reads two planted anchors, one strong and one weak; a lens that cannot tell them apart is not counted. Each rule you wrote ends PASS, FAIL or INCONCLUSIVE.

Your agent runs the tools and tells you what they returned. Each tool proves it was looking before you trust a clean result: a control phrase that must be found, a term that must be found in the postings, rules tested against their own examples, a control read. It needs only Python 3.9 or later (reading a PDF also needs `pdftotext`), and it is under the AGPL.

Designed and directed by José Miguel Hernandez, built with AI coding agents. Where it was recorded, [docs/provenance.md](docs/provenance.md) names the harness and model that wrote each file.

The method behind the tools, and which parts are built so far, is in [METHOD.md](METHOD.md). To try one now, go to [First run](#first-run).

## Install

Python 3.9 or later, with no other dependencies. Reading a PDF also needs `pdftotext` (from Poppler) on your `PATH`.

    git clone https://github.com/jose-m-hernandez/career-track-record.git
    cd career-track-record
    python3 -m pip install .

To install with no network, first make sure setuptools 70.1 or later is already installed. Then run:

    python3 -m pip install --no-build-isolation .

This installs the `track-record` command. If your shell can't find it, or you haven't installed it, run `PYTHONPATH=src python3 -m career_track_record` from the clone's top folder instead. To check it works:

    track-record --help

## First run

The repository ships invented files to try the tools on. From the top folder of your clone:

    cd tests/fixtures/barred
    track-record barred --list list-l1.txt --control Example\ Corp clean.txt two.txt nocontrol.txt

You should see this:

    OK    clean.txt: 0 of 5 entries (control found; 1209 chars)
    FAIL  two.txt: 2 entries
    two.txt:13: entry #1 (2 x)
    two.txt:13: entry #2 (1 x)
    DEAD  nocontrol.txt: control not found

`clean.txt` passes. `two.txt` uses two of the five entries on the list, so it fails. `nocontrol.txt` lacks the control phrase, so the check says DEAD and does not vouch for it: a file read as blank or garbled cannot pass as clean. The run exits 2 because of that one DEAD file. If `track-record` is not found, see Install.

Then point it at your own files: `track-record barred --list your-list.txt --control "Your Name" your-file.md`. The other five tools are under [The tools](#the-tools).

## Why you can trust a result

- **No network library.** No tool imports a network or mail library, and a [test](tests/test_no_network.py) fails if one does.
- **A check that finds nothing shows it was looking.** Every barred-wording run names a control phrase that must be in each file. A file too short or lacking it is DEAD, never OK. Every claim-gate run also names a control phrase, and a file without it, or with no sentence to check, is DEAD. The voice and tone check tests each rule against its own examples before it reads any file. Reader A/B reads one version against itself in every run. The reader panel reads a strong and a weak anchor through every lens in every run.
- **The rules are fixed before the answer.** A Reader A/B or reader panel plan is frozen by hash before the first read, and a run refuses anything that has changed since.

The tools start only two kinds of outside program: `pdftotext`, to read a PDF, and, in `track-record ab` and `track-record panel` only, a reader command you name yourself. That command runs only when you add `--live`, and no live reader ships with the tool (the built-in `fake` reader only tests a plan). A reader command can do whatever its program does, including reaching the network, so choose it with care. Apart from that command, the tools can't submit an application, publish a post or send a message for you. None of this covers what your AI agent does on its own or what you share with your AI provider.

## The tools

Each tool below has its own spec in `docs/specs/`. The commands and options here are the full reference; start with First run above.

### `track-record barred`

Keep a private list of wording that must never appear in what you send: a UTF-8 text file with one entry per line, where a line starting with `#` is a comment. To have an entry match only as a whole word, put a tab character after it and then exactly `word`, in any case, so that a letter or digit directly before or after it rules the match out. For each file that uses an entry, the check reports only the entry's number, so the wording itself never shows up in its output or your logs. Case, ligatures, invisible characters and a word split across a line break can't hide a match. One exception is in PDFs. When a hyphenated word such as `zebra-word` wraps at its hyphen inside a page, `pdftotext` removes the hyphen and the line break before the check reads the text, so the check sees `zebraword` (measured with poppler 26.07.0). An entry `zebra-word` is then not caught, and neither is a `word`-flagged entry for one half of it, `zebra` or `word`. Across a page break, and in text files, both are caught.

Every run names a control phrase, such as your own name, that must appear in each file, so a file read as blank or garbled can't pass as clean. A file that is too short, or that lacks the control, is reported DEAD, never OK.

    track-record barred --list barred.txt --control "Your Name" resume.pdf letter.md

From a clone, in the repository's own test fixtures (`tests/fixtures/barred/`), the check gives:

    cd tests/fixtures/barred
    track-record barred --list list-l1.txt --control Example\ Corp clean.txt two.txt nocontrol.txt
    OK    clean.txt: 0 of 5 entries (control found; 1209 chars)
    FAIL  two.txt: 2 entries
    two.txt:13: entry #1 (2 x)
    two.txt:13: entry #2 (1 x)
    DEAD  nocontrol.txt: control not found

The run exits 2 because one file is DEAD: it has no control phrase, so the check cannot vouch for it.

Exit 0 means every file is OK, 1 means a match, and 2 means the check couldn't vouch for a file, or couldn't run. Spec: [docs/specs/barred.md](docs/specs/barred.md).

### `track-record keywords`

Keep a folder of job postings you've saved yourself, and a table of the terms you care about. The scan shows which terms the postings ask for that your copy never uses. It has three modes: `demand` shows which terms the postings ask for, `coverage` shows which terms your copy uses, and `report` puts the two together and lists the gaps.

Each posting is a `.txt` file whose short header, or `.meta.json` sidecar, records its SHA-256; a posting that no longer matches is refused. [keyword-scan.md § 4](docs/specs/keyword-scan.md) shows both formats. The term table is a tab-separated file with the columns `family`, `pattern` and `note`. In `demand` and `report`, mark at least one family `must-find` in its note, so a run that can't see the postings stops instead of reporting zeros. Mark a term `chosen` when it's your own choice of word.

    track-record keywords demand   --postings postings/ --terms terms.tsv
    track-record keywords coverage --terms terms.tsv resume.md
    track-record keywords report   --postings postings/ --terms terms.tsv --copy resume.md

It reports gaps and never rewrites your copy or sets a keyword-score target. A `chosen` term is labelled as yours in the report, and the scan never suggests dropping or replacing one your copy uses. Spec: [docs/specs/keyword-scan.md](docs/specs/keyword-scan.md).

### `track-record tone`

Run the voice and tone check over your copy to find hype, hedges and filler:

    track-record tone resume.md letter.md

It checks each file against a rule file of phrasings to avoid, each set as an `error` or a `warn`; without `--rules`, the shipped default rules run. Every finding names the sentence and the rule's reason, and only `error` rules fail a run. The check never edits a file or suggests a replacement. A file whose name ends in `.pdf` (any case) is checked as the text `pdftotext` extracts from it, as written, so case-sensitive rules still apply.

To make your own rules, start from the defaults:

    track-record tone --print-defaults > tone-rules.json
    track-record tone --rules tone-rules.json resume.md letter.md

Before any file is read, each rule is tested against its own examples, so a broken rule stops the run instead of passing everything. An exemption lets one `error` rule pass a piece of wording you quote exactly, and the same wording anywhere else still fails.

Add `--warn-only` to run only the `warn` rules, and `--stale-check` to report exemptions whose wording appears in none of the files you name; a stale exemption counts as an error. Exit 0 means no errors (warnings allowed), 1 means at least one error, and 2 means the check couldn't run. Spec: [docs/specs/tone-and-tells.md](docs/specs/tone-and-tells.md).

### `track-record ab`

Compare two versions of a résumé, or any career document, by asking test readers which reads better. A reader is a command you name, such as one that calls a language model, or the built-in `fake`, which tests a plan. You write a plan first: the posting, the versions, where they may differ and what counts as a win. The tool hashes the plan and every file it names, and a run refuses anything that has changed since, so the rules can't quietly move after you see the answer. Every run also reads one version against itself, as a control, so you can see how often a reader picks a side when there is no difference. Each comparison ends SUPPORTED, REFUTED or INCONCLUSIVE, by the rule you wrote. This plan is invented:

```
posting: posting.txt
versions:
  base | resume-base.txt
  skills-top | resume-skills-top.txt
comparisons:
  base vs skills-top
readers:
  reader-1 | fake
  reader-2 | /path/to/my-reader.sh | not-blind | cost 3
reads-per-reader: 3
hypotheses:
  SUPPORTED if skills-top preferred in 6 of 6; REFUTED if base preferred in 4 or more; otherwise INCONCLUSIVE
change-scope:
  ^Skills$
  ^At a glance$
  ^(Languages|Tools|Practices):
fake-reader:
  prefer containing "At a glance"
```

A reader's program is an absolute path, as here, or a program name found on your `PATH`. `freeze` refuses a relative path such as `./my-reader.sh`, because each read runs inside a folder of its own. `not-blind` marks a reader you know gets your identity from its own setup, so its reads are also reported separately. `cost 3` is what one read costs, in a unit you choose; it feeds the spend estimate. Two readers with three reads each make six reads per comparison, which is what `6 of 6` counts. This plan has a live reader, so without `--live` it prints the commands and runs nothing, the fake reader included.

The tool has three subcommands:

    track-record ab freeze plan.txt
    track-record ab run plan.txt [--live]
    track-record ab score plan.txt

`freeze` finds every problem in the plan and writes a freeze file beside it. `run` checks the hashes and that the versions differ only where the plan says, runs the readers and writes a result. `score` scores the replies again into a new result and never overwrites an earlier one. The `fake` reader answers by the rules in the plan's `fake-reader` block, so it tests the plan and says nothing about your copy. A live reader is a command you name, run without a shell in a folder holding the two versions, the posting and the prompt; it inherits your whole environment, API keys included. A plan with a live reader prints its commands and a spend estimate, and starts nothing, until you add `--live`. What a live reader does with your files is up to that reader.

Exit 0 means the run completed and was scored, whatever the verdicts, or it only printed the commands because `--live` was absent. Exit 1 means it finished but a read failed, or the spend ceiling cut it short. Exit 2 means it couldn't run: a plan error, a changed file, a failed check on the versions, or an interrupt. Spec: [docs/specs/reader-ab.md](docs/specs/reader-ab.md).

### `track-record claims`

Keep a claims list: the sentences you have approved for your copy. The claim gate reads each file you name and fails on any sentence the list has not approved. A sentence you change is a new sentence, so it fails until you approve it again. The gate never decides whether a claim is true. Approving it is yours.

The list is a UTF-8 text file with one entry per line. Each entry has tab-separated fields: a status, the sentence, and, if you like, a source. The status is `approved`, `proposed` or `refused`. `proposed` lists a sentence you have not decided on, and it does not pass. `refused` records a claim you turned down, so the sentence fails with that reason if it comes back. A source can be anything you like: a file path, a URL or a record id. It is never printed, and only `--check-sources` reads it, as a file path relative to the folder that holds the list. Anything after a third tab is a note, which is never matched or printed. A line starting with `#` is a comment. This list is invented, with a tab between fields:

```text
# invented list
approved	Led a team of six engineers at Example Corp.	notes/offer-letter.txt
approved	Shipped the Example importer in 2021.
approved	Joined Example Corp. in 2019.	notes/start.txt	invented note
approved	Built an end-to-end import pipeline.
proposed	Cut build times by forty percent.	notes/draft.txt
refused	Increased revenue tenfold.
```

Every sentence is checked, short ones and contact lines included, because a short sentence can carry a claim. Each bullet and each heading starts a new sentence, with or without a final full stop. Matching is exact after folding, so case, ligatures, invisible characters, curly quotes, the hyphens U+2010 and U+2011 and one final full stop make no difference. An entry never matches part of a sentence, and a sentence that holds an entry plus more words is not covered by it.

Every run names a control phrase that must appear in each file. Give `--control` more than once and any one counts. A file without the control, or with no sentence to check, is reported DEAD, never OK. If a file you name is the list itself (a pattern such as `*.txt` can pick it up), it is also reported DEAD: the list is never checked as text, and the line names it by its position, such as `file #2`, never by its path.

    track-record claims --list claims.txt --control "Your Name" profile.md letter.md

Add `--stale-check` to also report approved entries that no file uses.

Add `--check-sources` to check your evidence too. Under an entry that has a source, write a `quote` line: `quote`, a tab, then a phrase that should appear word for word in that source. This check is a port of an evidence-check method in which a quote must appear in the source it cites. With the flag, each `approved` and `proposed` entry that has a quote is checked against its source, whether or not a file used it; `refused` entries are never checked. The quote is matched after the same folding as a sentence, and must start and end on word boundaries; a quote that ends in a number is not found inside a longer number, so `Version 2.` is not found in `Version 2.5`. Only UTF-8 text files and PDFs (through `pdftotext`) are read. A source that is not a local file at all, such as a URL, a record id or a missing path, is reported unverified and nothing is read. This invented entry has a quote, with a tab between fields:

```text
approved	Led a team of six engineers at Example Corp.	evidence/offer.txt
quote	will lead a group of six engineers
```

After the file lines and any stale lines, the gate prints one line for each checked quote that is not found (`approved, entry #1: quote not found`), whose source cannot be read (`source unreadable (not UTF-8)`, with the reason), or that is unverified (`source unverified`), then two count lines, one for approved entries and one for proposed ones, such as `quotes, approved: 1 found, 0 not found, 0 unreadable, 0 unverified`. These lines name an entry only by its number and status: they never print a quote, a source, its path or its text. An approved quote not found makes the run exit at least 1, and an approved source that cannot be read makes it exit 2. An unverified quote is printed and counted but does not change the exit code, and a proposed entry never changes it.

For each file the gate prints one line, OK, FAIL or DEAD. After a FAIL line comes one line for each unapproved sentence, or each run of sentences that one entry covers: the file, the line number, the reason (`unlisted`, or `proposed` or `refused` with the entry number) and the sentence as it stands in the file. A stale entry prints as `stale entry #N`. The output prints only text from the file you check. It never prints a source, a note, the path of your list or the sentence of an entry your files never used, and it names an entry only by its number. The gate knows your list by the file itself, not by what it holds: a copy of the list under another name is checked like any file, and its findings can print the sources and notes it holds.

Take the list above and a file `copy.txt` that holds one line, `Led a team of seven engineers at Example Corp.`:

    track-record claims --list claims.txt --control example copy.txt
    FAIL  copy.txt: 1 of 1 sentences not approved
    copy.txt:1: unlisted: Led a team of seven engineers at Example Corp.

The list approves a team of six, so the changed sentence is a new one and fails. The run exits 1.

Markdown marks such as `**` count as ordinary text. A word that layout split with a hyphen at a line end fails until you fix it or approve it with the hyphen.

Exit 0 means every file is OK. Exit 1 means a sentence is not approved, with `--stale-check` an approved entry no file uses, or with `--check-sources` an approved quote not found. Exit 2 means a file is DEAD, with `--check-sources` an approved entry's source cannot be read, or the gate couldn't run, for example because no file or control was named, or the list has an unknown status, two entries for one sentence, or a quote line it can't use (before the first entry, a second one for an entry, under an entry with no source, or with no quote). Spec: [docs/specs/claims.md](docs/specs/claims.md).

### `track-record panel`

Read one version of a résumé, or any career document, through several lenses: each a reader in a role you name, such as a recruiter or the hiring manager, given as a plain-text prompt file you write. Readers are the same as in `track-record ab`: a command you name, or the built-in `fake`. The plan is frozen by hash before the first read, lens files included.

Every lens also reads two anchors you supply: a document you wrote to be plainly strong for the posting, and one you wrote to be plainly weak. If a lens does not score the strong anchor at or above `anchor-strong-at-least` and the weak anchor at or below `anchor-weak-at-most`, on every anchor read, that lens's reads of your version are reported INCONCLUSIVE and not counted. The anchors do for the panel what the control read does for `ab`: a lens that shows nothing also shows whether it could see anything. This plan is invented:

```
posting: posting.txt
version: resume.txt
anchors:
  strong | anchor-strong.txt
  weak | anchor-weak.txt
lenses:
  recruiter | recruiter.lens.txt
  hiring-manager | hiring-manager.lens.txt
readers:
  reader-1 | fake
  reader-2 | /path/to/my-reader.sh | not-blind | cost 3
anchor-strong-at-least: 7
anchor-weak-at-most: 4
rules:
  recruiter | PASS if score at least 7 in 5 of 6; FAIL if score at most 4 in 2 or more; otherwise INCONCLUSIVE
  hiring-manager | FAIL if DOUBTS flagged in 3 or more; PASS if score at least 7 in 5 of 6; otherwise INCONCLUSIVE
  overall | PASS if score at least 7 in 10 or more; otherwise INCONCLUSIVE
fake-reader:
  strong | score 9
  weak | score 2
  version | score 7
```

Each reader reads the version three times per lens and each anchor once, unless the plan says otherwise. A rule names its lens, or `overall` for every counted lens, and tests scores or flagged fields: a field such as `DOUBTS` is flagged when the reader wrote anything there but `none`. The reader sees the posting, the lens and one document, and nothing says whether that document is an anchor or your version.

The tool has the same three subcommands as `ab`:

    track-record panel freeze plan.txt
    track-record panel run plan.txt [--live]
    track-record panel score plan.txt

The `--live` rule, the spend ceiling, the `fake` reader and the exit codes are those of `ab`. The spec is signed (revision 1). Spec: [docs/specs/reader-panel.md](docs/specs/reader-panel.md).

## Coming

Later: more default rules for the voice and tone check, building and reviewing a résumé from one source file, tracking applications and contacts, and keeping a dated record of what you did each week. Each arrives with its own spec and tests.

## Maintainer

Maintainer: José Miguel Hernandez (@jose-m-hernandez) · https://jose.io

Designed and directed by José Miguel Hernandez, built with AI coding agents.

## Licence

Copyright (c) 2026 José Miguel Hernandez.

GNU Affero General Public License v3.0 or later; see [LICENSE](LICENSE).
A commercial licence is also available from the copyright holder.

## Development

Run the tests from the repository root:

    python3 -m unittest discover -s tests -t . -v

The barred-strings scan, `ci/barred_strings.py` (a maintainer check on this repository's history, not the `barred` tool), runs in CI on every push and pull request against a private list held in a repository secret. It checks committed history, not uncommitted edits. To run it locally, keep a list file outside the repository and run:

    BARRED_STRINGS_PATH=/path/to/list python3 ci/barred_strings.py

The first entry in the list must be a canary: `barred-strings-canary-` followed by at least 8 letters or digits. Run locally, the scan prints each hit's entry number and where it was found; in CI it prints only the number of hits. It never prints the matched text. Exit 0 means clean, 1 a hit, 2 the scan could not run.

An intentional use of a barred entry in one file's contents or one commit (a commit that quotes a barred string on purpose, say) can be approved privately by the maintainer; the scan then accepts that entry there and still fails everywhere else. A file name or branch name is never approved.
