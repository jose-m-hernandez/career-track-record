# Every file has a provenance row

Date: 2026-11-01

## The rule

> **Every committed file has exactly one row in docs/provenance.md, which
> records only path, harness, model and date. A change that adds or edits a
> file updates that row.**

## Why

The repository records which harness and model are recorded writing each file.
It does this in a file, `docs/provenance.md`, rather than in commit trailers, so
the answer sits next to the code and can be read and checked in one place.

The four columns are the only ones that may be public. Nothing else from the
records that the ledger is built from belongs in the repository.

Where the records hold no write to a file, the row says `not recorded`. A guess
would read as a fact, so the ledger leaves the cells honest instead.

`tests/test_provenance.py` enforces presence: it fails if a file has no row, a
row has no file, or the table has any column other than these four.
