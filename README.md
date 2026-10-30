# career-track-record

Tools for people managing their own career. Four ship:

- **The barred-wording check** finds wording you've barred in files you're about to send.
- **The keyword scan** shows what job postings ask for that your own copy (a résumé, a cover letter, a profile) never says.
- **The voice and tone check** flags hype, hedges and filler in that copy.
- **Reader A/B** compares two versions of your copy by asking test readers which reads better, under a plan you freeze first.

No tool imports a network or mail library, and a [test](tests/test_no_network.py) fails if one does. The tools start only two kinds of outside program: `pdftotext`, to read a PDF, and, in `track-record ab` only, a reader command you name yourself. That command runs only when you add `--live`, and none ships with the tool. A reader command can do whatever its program does, including reaching the network, so choose it with care. Apart from that command, the tools can't apply for a job, publish a post or send a message for you. None of this covers what your AI agent does on its own or what you share with your AI provider.

The method behind them, and which parts are built so far, is in [METHOD.md](METHOD.md).

## Install

Python 3.9 or later, with no other dependencies. Reading a PDF also needs `pdftotext` (from Poppler) on your `PATH`.

    git clone https://github.com/jose-m-hernandez/career-track-record.git
    cd career-track-record
    python3 -m pip install .

To install with no network, first make sure setuptools 70.1 or later is already installed. Then run:

    python3 -m pip install --no-build-isolation .

This installs the `track-record` command. If your shell can't find it, or you haven't installed it, run `PYTHONPATH=src python3 -m career_track_record` from the clone's top folder instead. To check it works:

    track-record --help

## The tools

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

## Coming

Planned for 0.4.0: a claim gate, a check that fails when a sentence in your career copy has no matching entry in a claims list you approve.

Later: building and reviewing a résumé from one source file, tracking applications and contacts, and keeping a dated record of what you did each week. Each arrives with its own spec and tests.

## Licence

GNU Affero General Public License v3.0 or later; see [LICENSE](LICENSE).
A commercial licence is also available from the copyright holder.

## Development

Run the tests from the repository root:

    python3 -m unittest discover -s tests -t . -v

The barred-strings scan, `ci/barred_strings.py` (a maintainer check on this repository's history, not the `barred` tool), runs in CI on every push and pull request against a private list held in a repository secret. It checks committed history, not uncommitted edits. To run it locally, keep a list file outside the repository and run:

    BARRED_STRINGS_PATH=/path/to/list python3 ci/barred_strings.py

The first entry in the list must be a canary: `barred-strings-canary-` followed by at least 8 letters or digits. Run locally, the scan prints each hit's entry number and where it was found; in CI it prints only the number of hits. It never prints the matched text. Exit 0 means clean, 1 a hit, 2 the scan could not run.

An intentional use of a barred entry in one file's contents or one commit (a commit that quotes a barred string on purpose, say) can be approved privately by the maintainer; the scan then accepts that entry there and still fails everywhere else. A file name or branch name is never approved.
