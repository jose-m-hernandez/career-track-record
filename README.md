# career-track-record

Eight checks for the career copy you send. Open the repository in your own AI agent and ask in plain words. To try one now, go to [First run](#first-run).

## The tools

| Tool | Question | Guide |
| --- | --- | --- |
| `track-record barred` | Did any wording I ruled out get into this file? | [barred](docs/guides/barred.md) |
| `track-record keywords` | What do the postings I saved ask for that my copy never says? | [keywords](docs/guides/keywords.md) |
| `track-record tone` | Does this sound like hype? | [tone](docs/guides/tone.md) |
| `track-record ab` | Which of these two drafts reads better? | [ab](docs/guides/ab.md) |
| `track-record claims` | Is every sentence in this file one I approved? | [claims](docs/guides/claims.md) |
| `track-record record` | Do the tables of my record still point at each other? | [record](docs/guides/record.md) |
| `track-record drafts` | Which version of this letter is the current one, and is the file that keeps them still in order? | [drafts](docs/guides/drafts.md) |
| `track-record panel` | How does this one draft read to a recruiter, and to the hiring manager? | [panel](docs/guides/panel.md) |

Your agent runs the tools and tells you what they returned. Before you trust a clean result, each check shows it was looking.

- a control phrase that must be found
- a term that must be found in the postings
- rules tested against their own examples

The two reader tools measure their readers rather than prove them, and each result says how (see [Why you can trust a result](#why-you-can-trust-a-result)). It needs only Python 3.9 or later (reading a PDF also needs `pdftotext`), and it is under the AGPL.

Tested in a desktop AI agent app: none yet.

The method behind the tools, and which parts are built so far, is in [METHOD.md](METHOD.md).

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

Then point it at your own files: `track-record barred --list your-list.txt --control "Your Name" your-file.md`. The other seven tools are under [The tools](#the-tools).

New to the reader tests or the keyword scan? Try [Your first A/B test](docs/guides/ab.md#your-first-ab-test) and the [keywords worked example](docs/guides/keywords.md#a-worked-example), which come with invented files under `examples/`.

## Exit codes

Every tool exits 0, 1 or 2; what each means per tool:

- `track-record barred`: Exit 0 means every file is OK, 1 means a match, and 2 means the check couldn't vouch for a file, or couldn't run.
- `track-record keywords`: Exit status for every mode: 0 means the run worked, whether or not it found gaps; 2 means it cannot run. In this version no mode exits 1. Spec: [docs/specs/keyword-scan.md](docs/specs/keyword-scan.md).
- `track-record tone`: Exit 0 means no errors (warnings allowed), 1 means at least one error, and 2 means the check couldn't run.
- `track-record ab`: Exit 0 means `freeze` wrote the freeze file, or `run` or `score` completed and scored its replies, whatever the verdicts, or `run` only printed the commands because `--live` was absent. Exit 1 means it finished but a read failed, or the spend ceiling cut it short. Exit 2 means it couldn't run.
- `track-record claims`: Exit 0 means every file is OK. Exit 1 means a sentence is not approved, with `--stale-check` an approved entry no file uses, or with `--check-sources` an approved quote not found. Exit 2 means a file is DEAD, with `--check-sources` an approved entry's source cannot be read, or the gate couldn't run.
- `track-record record`: Exit 0 means every check is OK (or, with `--report-only`, none is DEAD), 1 means a check found a problem, and 2 means a check is DEAD or the check couldn't run.
- `track-record drafts`: Exit 0 means every rule holds, 1 means a fault that `check` reports or `extract` refuses, and 2 means a DEAD check or that the command could not run.
- `track-record panel`: The exit codes are those of `ab`.

## Why you can trust a result

- **A check that finds nothing shows it was looking.** Every barred-wording run names a control phrase that must be in each file. A file too short or lacking it is DEAD, never OK. The reader tools are different: their readers can't be checked the same way. Reader A/B reads one version against itself in every run, which shows how often a reader picks a side when the drafts are the same. It doesn't show that a reader noticed your change.
- **No network library in the package.** No tool under `src/` imports a network or mail library, and a [test](tests/test_no_network.py), which scans `src/` only, fails if one does. The example reader under `examples/` is outside the package and outside that test.
- **The rules are fixed before the answer.** A Reader A/B or reader panel plan is frozen by hash before the first read, and a run refuses anything that has changed since.

The tools start only two kinds of outside program: `pdftotext`, to read a PDF, and, in `track-record ab` and `track-record panel` only, a reader command you name yourself. That command runs only when you add `--live`, and the package ships no live reader (the built-in `fake` reader only tests a plan). The example reader under `examples/readers/` is not part of the package: it starts `codex` or, as a fallback, `claude`, which reach the network and spend your own plan. A reader command can do whatever its program does, including reaching the network, so choose it with care. Apart from that command, the tools can't submit an application, publish a post or send a message for you. None of this covers what your AI agent does on its own or what you share with your AI provider.

## Links

- [docs/specs/](docs/specs/)
- [METHOD.md](METHOD.md)
- [docs/record-model.md](docs/record-model.md)
- [CHANGELOG.md](CHANGELOG.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [LICENSE](LICENSE) and [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md)

## Coming

Later: more default rules for the voice and tone check, building and reviewing a résumé from one source file, tracking applications and contacts, and keeping a dated record of what you did each week. Each arrives with its own spec and tests.

## Maintainer

Maintainer: José Miguel Hernandez (@jose-m-hernandez) · https://jose.io

Designed and directed by José Miguel Hernandez, built with AI coding agents. Where it was recorded, [docs/provenance.md](docs/provenance.md) names the harness and model that wrote each file.

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
