# Committed files are UTF-8

Date: 2026-10-27

## The rule

> **Every committed file is valid UTF-8. A test that needs invalid bytes writes
> them at run time.**

## Why

The maintainer barred-strings scan fails closed on a file in history that is not
UTF-8 text. A committed fixture that is not UTF-8 would therefore block every
push.

`test_every_committed_fixture_is_utf8` guards `tests/fixtures/`. The guard on
the test sources checks something else: it catches invisible characters in test
code.
