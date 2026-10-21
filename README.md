# career-track-record

Tools for people managing their own career. Three ship today: the barred-wording check, which finds wording you've barred in files you're about to send; the keyword scan, which shows what job postings ask for that your own copy (a résumé, a cover letter, a profile) never says; and the tone check, which flags hype, hedges and filler in that copy.

These tools are safe to leave running. They import no network or mail library: a [test](tests/test_no_network.py) fails if any of them does, and the only outside program a tool starts is `pdftotext`. So they can't apply for a job, publish a post, or send a message for you. That holds for these tools only, not for what your AI agent does on its own or what you share with your AI provider.

The rules these tools are being built to are in [METHOD.md](METHOD.md).

## The tools

### `track-record barred`

Keep a private list of wording that must never appear in what you send: a UTF-8 text file with one entry per line, where a line starting with `#` is a comment. For each file that uses an entry, the check reports only the entry's number, so the wording itself never shows up in its output or your logs. Case, ligatures, invisible characters and a word split across a line break can't hide a match.

Every run names a control phrase, such as your own name, that must appear in each file, so a file read as blank or garbled can't pass as clean. A file that is too short, or that lacks the control, is reported DEAD, never OK.

    track-record barred --list barred.txt --control "Your Name" resume.pdf letter.md

Exit 0 means every file is OK, 1 means a match, and 2 means the check couldn't vouch for a file, or couldn't run. Spec: [docs/specs/barred.md](docs/specs/barred.md).

### `track-record keywords`

Keep a folder of job postings you've saved yourself and a table of the terms you care about. The scan shows which terms the postings ask for and your copy never uses. Each posting is a `.txt` file whose short header, or `.meta.json` sidecar, records its SHA-256. A posting that no longer matches is refused. [keyword-scan.md § 4](docs/specs/keyword-scan.md) shows both formats. The term table is a tab-separated file with the columns `family`, `pattern` and `note`. For `demand` and `report`, mark at least one family `must-find` in its note, so a run that can't see the postings stops instead of reporting zeros. Mark a term `chosen` when it's your own choice of word.

    track-record keywords demand   --postings postings/ --terms terms.tsv
    track-record keywords coverage --terms terms.tsv resume.md
    track-record keywords report   --postings postings/ --terms terms.tsv --copy resume.md

It reports gaps and never rewrites your copy or sets a keyword-score target. A `chosen` term is labelled as yours in the report, and the scan never suggests dropping or replacing one your copy uses. Spec: [docs/specs/keyword-scan.md](docs/specs/keyword-scan.md).

### `track-record tone`

Checks your copy against a rule file of phrasings to avoid, each set as an `error` or a `warn`. Every finding names the sentence and the rule's reason, and only `error` rules fail a run. Before any file is read, each rule is tested against its own examples, so a broken rule stops the run instead of passing everything. An exemption lets one `error` rule pass a piece of wording you quote exactly, and the same wording anywhere else still fails. The check never edits a file or suggests a replacement. Without `--rules`, the shipped default rules run; to make your own, start from them:

    track-record tone --print-defaults > tone-rules.json
    track-record tone --rules tone-rules.json resume.md letter.md

Add `--warn-only` to run only the `warn` rules, and `--stale-check` to report exemptions whose wording appears in none of the files you name; a stale exemption counts as an error. Exit 0 means no errors (warnings allowed), 1 means at least one error, and 2 means the check couldn't run. Spec: [docs/specs/tone-and-tells.md](docs/specs/tone-and-tells.md).

## Install

Python 3.9 or later, with no other dependencies. From a clone:

    python3 -m pip install .

Reading a PDF needs `pdftotext` (from Poppler) on your `PATH`.

## Coming

Building and reviewing a résumé from one source file, tracking applications and contacts, and keeping a dated record of what you did each week. Each arrives with its own spec and tests.

## Licence

GNU Affero General Public License v3.0 or later; see [LICENSE](LICENSE).
A commercial licence is also available from the copyright holder.

## Development: running the tests and the barred-strings scan

Run the tests from the repository root:

    python3 -m unittest discover -s tests -t . -v

The barred-strings scan, `ci/barred_strings.py` (a maintainer check on this repository's history, not the `barred` tool), runs in CI on every push and pull request against a private list held in a repository secret. It checks committed history, not uncommitted edits. To run it locally, keep a list file outside the repository and run:

    BARRED_STRINGS_PATH=/path/to/list python3 ci/barred_strings.py

The first entry in the list must be a canary: `barred-strings-canary-` followed by at least 8 letters or digits. The scan prints entry numbers only, never the matched text. Exit 0 means clean, 1 a hit, 2 the scan could not run.
