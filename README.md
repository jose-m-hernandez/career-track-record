# career-track-record

Early development. This repository is private and not yet published, and
nothing here is ready to use yet.

- What changes, and when: [CHANGELOG.md](CHANGELOG.md)
- How changes are made: [CONTRIBUTING.md](CONTRIBUTING.md)

## Licence

GNU Affero General Public License v3.0 or later; see [LICENSE](LICENSE).
A commercial licence is also available from the copyright holder.

## Development: running the tests and the barred-strings scan

Run the tests from the repository root:

    python3 -m unittest discover -s tests -t . -v

The barred-strings scan, `ci/barred_strings.py`, runs in CI on every push and pull request against a private list held in a repository secret. It checks committed history, not uncommitted edits. To run it locally, keep a list file outside the repository and run:

    BARRED_STRINGS_PATH=/path/to/list python3 ci/barred_strings.py

The first entry in the list must be a canary: `barred-strings-canary-` followed by at least 8 letters or digits. The scan prints entry numbers only, never the matched text. Exit 0 means clean, 1 a hit, 2 the scan could not run.
