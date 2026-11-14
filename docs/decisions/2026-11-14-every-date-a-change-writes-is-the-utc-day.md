# Every date a change writes is the UTC day

Date: 2026-11-14

## The rule

> **Every date a change writes is the UTC day it is written (`date -u +%F`): a
> provenance row, a CHANGELOG release heading, a decision record's `Date:` or
> `Updated` line, and a spec's `Date:` line.**

## Why

Two dates for one change confused readers: a provenance row, a release heading
and a decision record could name different days for the same work, depending on
whose clock and whose time zone wrote each one.

The provenance ledger already used one day for every row, the UTC day of the
latest recorded write (docs/provenance.md). This rule extends that day to every
other date a change writes, so one change carries one date wherever it appears.
