# A reader command is the one outside program a user names

Date: 2026-10-29

## The rule

> **A reader command is the one outside program a user names.
> `ab_reader_command.py` is the only module that starts it. It makes one
> `subprocess.run` call with an argument list, never a shell, and is excused in
> the `ALLOW_LIST` of `tests/test_no_network.py` for importing `subprocess` and
> nothing else. Its call shape is pinned like `pdf_text.py`'s, with `cwd` as the
> one added keyword.**

## Why

`track-record ab` must run a reader that the user configures, so the program
cannot be pinned as a literal the way `pdftotext` is. The shape of the call is
pinned instead, so that a test fails if it changes: one call, a list of
strings, no shell, no `env` and no `executable`, and only the keywords `stdin`,
`capture_output`, `timeout`, `check` and `cwd`.

This follows the rule recorded in `2026-10-27-one-module-per-outside-program.md`
that one module starts each outside program. That record is unchanged, and
`pdf_text.py` still may not pass `cwd`.

The ban on network and mail imports is unchanged. What the reader program
itself does is outside what the test can see.
