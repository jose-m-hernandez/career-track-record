# Known limits sit beside their tests

Date: 2026-10-27

## The rule

> **A limit that is accepted rather than fixed gets a one-line `# Known limit:`
> comment beside the nearest test, not a separate doc file. A limit that a user
> of a tool can meet is also stated in that tool's spec or the README.**

## Why

A reader of a test meets a limit where the behaviour is tested. A user meets it
where they read about the tool. Each reader should find it in their own place.
`tests/test_barred.py` carries its known limits as `# Known limit:` comments.
The PDF hyphen-wrap limit is stated in the barred spec, first in revision 6.1,
and in the README.

A separate file of limits would be a place neither reader looks.

The cost is that a limit stated in a spec or the README has to be kept true
there as well as in the comment.
