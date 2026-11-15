# No file ships with a sentence still to be worded

Date: 2026-11-14

## The rule

> **A sentence that its owner has still to word is marked with the placeholder
> marker that `tests/test_placeholders.py` builds. That test fails, naming each
> file, while the marker is in any file of the repository, so the sentence
> cannot ship unworded.**

## Why

Some sentences are not the author's to write: a spec's account of where its
method comes from belongs to the spec's owner. A change can leave the place
for it, but a place left empty can be forgotten, and a person reading a diff
can miss it.

A marker that a test looks for cannot be forgotten. The test walks every file
except the top `.git` folder and the `__pycache__` folders, so it finds the
marker in a spec, a changelog line or anywhere else, and the suite stays red
until the owner words the sentence and the marker is gone.

The match is wider than one spelling: the test finds the marker's two words in
any case, with any run of characters that are neither letters nor digits
between them (a hyphen, a space, an underscore, a dash that is not ASCII, a
line break), in a file read as UTF-16 after a UTF-16 byte-order mark and as
UTF-8 otherwise, so a changed spelling does not slip past it.

The marker itself is not written here, because this file is one of the files
the test reads, and neither are its two words.

The cost is that the suite is red from the day the marker is added until the
sentence is worded. That is the point: the change that adds a marker does not
merge, and a release is not cut, while it stands.
