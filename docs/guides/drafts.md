# `track-record drafts`

A cover letter or a résumé goes through many versions, and which one is current, what changed and why, and what each one earned are easy to lose. Keep them in one plain-text file per document, in the order they were written, and add to it only at the end: a version when you write it, a result when another command has read it, and the send mark when you choose the copy to send. The drafts command checks that file. It never writes to it, and it never prints what a version says, what a change note says or what a result note says: output holds only the file's path, ids, line numbers and counts.

The file is a run of sections, each starting with a header line (`## v2`, `## result` or `## send`). A version holds only what is known when you write it; its text is every line after `text:` up to the next header line. The `sha256:` line and a result's `note:` line are optional. A result names its run folder as a path relative to the draft file's folder. A section's date is the day you added it. Here is the spec's invented example letter in three versions, the file the runs below check:

```text
## v1
parent: none
date: 2026-03-02
change: first draft
text:
Dear Example Corp team,

I would like to apply for the analyst role.

## v2
parent: v1
date: 2026-03-04
change: a shorter opening
text:
Dear Example Corp team,

I am applying for the analyst role.

## result
version: v1
date: 2026-03-05
run: runs/panel-01
note: two readers found the opening slow

## v3
parent: v2
date: 2026-03-06
change: names the team
sha256: e9db1dc84b01be6dbafe216e3dd033b3ecb1c83db3143a2925d3381348bfe6b8
text:
Dear Example Corp data team,

I am applying for the analyst role.

## send
version: v3
date: 2026-03-07
```

There are two commands. `track-record drafts check FILE [--earlier COPY]` checks the file. `track-record drafts extract FILE ID --out OUT [--earlier COPY]` checks it and then writes version `ID`'s text, and nothing else, to the new file `OUT`, so that you can hand it to `track-record ab`, `panel`, `barred` or `claims`. `--earlier COPY` names a copy of the file from before your latest additions; the check then proves that the copy is still, byte for byte, the start of the file, so nothing already in it was edited. A blank line removed from the part the copy holds is an edit.

From a clone, in a copy of the repository's own test fixtures (`tests/fixtures/drafts/`) made in a folder outside the clone, with the run folder the example cites, the check gives:

    mkdir -p /tmp/drafts-example/runs/panel-01
    cp tests/fixtures/drafts/letter*.txt /tmp/drafts-example
    cd /tmp/drafts-example
    track-record drafts check letter.txt --earlier letter-before.txt
    OK    letter.txt: versions 3, parents resolved 3, results 1, run folders found 1, send entries 1; send copy v3; earlier copy 259 bytes, file 600 bytes

`letter-edited.txt` is the earlier copy with a result written into the middle instead of at the end:

    track-record drafts check letter-edited.txt --earlier letter-before.txt
    FAIL  letter-edited.txt: versions 2, parents resolved 2, results 1, run folders found 1, send entries 0; faults 1; earlier copy 259 bytes, file 359 bytes
    letter-edited.txt:10: differs from the earlier copy

The check reports a section that breaks the form (a key out of order, an unknown key, a version with no text, a line outside any section), a repeated id or one out of order, a parent or a named version that does not exist or comes later, an empty change note, a date that is not a real day or comes before the section just before it, a second send entry, a `sha256:` line that does not match the text, an earlier copy that is no longer the start of the file, and a run folder that does not exist. A version's sha256 is taken over its text lines, once the blank lines at the end are dropped, so the line breaks of the file and the blank lines between sections do not change it; `extract` writes exactly those bytes.

`extract` stops on any fault except a missing run folder: it writes no file, writes the lines `check` would write to standard error, and exits as `check` would. A missing run folder is written to standard error and the version is still written. Without `--earlier`, it says so on standard error. It refuses an `OUT` that already exists, and never deletes a path it did not create.

A check that looked at nothing is DEAD, never OK: the file is empty or holds no version, or the earlier copy is missing, cannot be read, is empty or is the draft file itself. Before it reads your file, the command runs each of its nine rules on built-in invented files with one planted fault each, and stops with `cannot run: self-test failed: rule N` if one does not find exactly its fault. Exit 0 means every rule holds, 1 means a fault that `check` reports or `extract` refuses, and 2 means a DEAD check or that the command could not run, for example because the draft file cannot be read. Spec: [docs/specs/drafts.md](../specs/drafts.md).

Known limit: a text that holds a complete, well-formed version header or entry cannot be told from a real one.
