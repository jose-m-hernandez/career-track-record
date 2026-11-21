# `track-record barred`

Keep a private list of wording that must never appear in what you send: a UTF-8 text file with one entry per line, where a line starting with `#` is a comment. To have an entry match only as a whole word, put a tab character after it and then exactly `word`, in any case, so that a letter or digit directly before or after it rules the match out. For each file that uses an entry, the check reports only the entry's number, so the wording itself never shows up in its output or your logs. Case, ligatures, invisible characters and a word split across a line break can't hide a match. The check reads each PDF twice with `pdftotext`, in its default mode and in its layout mode, which keeps a hyphen that ends a line. So an entry `zebra-word` wrapped at its hyphen is caught inside a page, across a page break and in text files, and so is a `word`-flagged entry for one half of it, `zebra` or `word` (measured with poppler 26.07.0). One exception remains, in a page set in columns: a wrap with another column's text beside it on the same line is not caught.

Every run names a control phrase, such as your own name, that must appear in each file, so a file read as blank or garbled can't pass as clean. A file that is too short, or that lacks the control, is reported DEAD, never OK.

    track-record barred --list barred.txt --control "Your Name" resume.pdf letter.md

You can leave out `--list` once `track-record setup` has named a record folder that holds `barred-list.txt`; a `$BARRED_STRINGS_PATH` in your environment is used before the record folder. The run then says on standard error which list it used, for example, with invented paths, `using /home/you/my-record/barred-list.txt (from config /home/you/.config/track-record/config.json)`. See [the setup guide](setup.md).

From a clone, in the repository's own test fixtures (`tests/fixtures/barred/`), the check gives:

    cd tests/fixtures/barred
    track-record barred --list list-l1.txt --control Example\ Corp clean.txt two.txt nocontrol.txt
    OK    clean.txt: 0 of 5 entries (control found; 1209 chars)
    FAIL  two.txt: 2 entries
    two.txt:13: entry #1 (2 x)
    two.txt:13: entry #2 (1 x)
    DEAD  nocontrol.txt: control not found

The run exits 2 because one file is DEAD: it has no control phrase, so the check cannot vouch for it.

Exit 0 means every file is OK, 1 means a match, and 2 means the check couldn't vouch for a file, or couldn't run. Spec: [docs/specs/barred.md](../specs/barred.md).

## `--min-chars`

`--min-chars N` sets the minimum length of each file. The default is 500. `N` is a whole number, 0 or more, with at most 18 significant digits. The joined form of a file is its text after the tool's folding (which evens out case and ligatures and drops invisible characters), with every run of whitespace, line breaks included, turned into one space and nothing trimmed, so a final line feed counts as one space. A joined form of exactly 499 characters is DEAD, and one of exactly 500 is OK. `--min-chars -1`, `--min-chars x` and a value of 19 digits each exit 2 before any file is read. Spec: [docs/specs/barred.md](../specs/barred.md).
