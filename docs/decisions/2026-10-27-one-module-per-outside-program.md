# One module per outside program

Date: 2026-10-27

## The rule

> **A module that must start an outside program is the only module that starts
> it, makes one call, and is excused in the `ALLOW_LIST` of
> `tests/test_no_network.py` for importing `subprocess` and nothing else.**

## Why

With one module and one call, the no-network test can excuse a single import in
a single file and pin the shape of that call. A second program, or a second
call, fails the test.

Today that module is `pdf_text.py`, which runs `pdftotext`.

The test does not track aliases, chains of `getattr` or other lookups, or names
built from strings, and those stay stated limits in the test's docstring.
`getattr` itself is allowed, because the tools use it.
