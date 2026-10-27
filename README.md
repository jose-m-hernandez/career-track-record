# career-track-record

Tools for people managing their own career. Three ship:

- **The barred-wording check** finds wording you've barred in files you're about to send.
- **The keyword scan** shows what job postings ask for that your own copy (a résumé, a cover letter, a profile) never says.
- **The voice and tone check** flags hype, hedges and filler in that copy.

These tools are safe to leave running. They import no network or mail library: a [test](tests/test_no_network.py) fails if any of them does, and the only outside program a tool starts is `pdftotext`. So they can't apply for a job, publish a post, or send a message for you. That holds for these tools only, not for what your AI agent does on its own or what you share with your AI provider.

The method behind them, and which parts are built so far, is in [METHOD.md](METHOD.md).

## Install

Python 3.9 or later, with no other dependencies. Reading a PDF also needs `pdftotext` (from Poppler) on your `PATH`.

    git clone https://github.com/jose-m-hernandez/career-track-record.git
    cd career-track-record
    python3 -m pip install .

This installs the `track-record` command. If your shell can't find it, run `python3 -m career_track_record` instead. To check it works:

    track-record --help

## The tools

### `track-record barred`

Keep a private list of wording that must never appear in what you send: a UTF-8 text file with one entry per line, where a line starting with `#` is a comment. To have an entry match only as a whole word, put a tab character after it and then exactly `word`, in any case, so that a letter or digit directly before or after it rules the match out. For each file that uses an entry, the check reports only the entry's number, so the wording itself never shows up in its output or your logs. Case, ligatures, invisible characters and a word split across a line break can't hide a match. One exception is in PDFs. When a hyphenated word such as `zebra-word` wraps at its hyphen inside a page, `pdftotext` removes the hyphen and the line break before the check reads the text, so the check sees `zebraword` (measured with poppler 26.07.0). An entry `zebra-word` is then not caught, and neither is a `word`-flagged entry for one half of it, `zebra` or `word`. Across a page break, and in text files, both are caught.

Every run names a control phrase, such as your own name, that must appear in each file, so a file read as blank or garbled can't pass as clean. A file that is too short, or that lacks the control, is reported DEAD, never OK.

    track-record barred --list barred.txt --control "Your Name" resume.pdf letter.md

From a clone, in the repository's own test fixtures (`tests/fixtures/barred/`), the check gives:

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

## Coming

Building and reviewing a résumé from one source file, tracking applications and contacts, and keeping a dated record of what you did each week. Each arrives with its own spec and tests.

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
