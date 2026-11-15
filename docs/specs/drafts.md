# Versioned draft file: behaviour spec

Status: accepted.
Date: 2026-11-14.
Revision: 1. The signed spec (sha256 e75158e6844427dfc19ffcbb5f6616fafb4b79454f186ef3592c13f01c374426) is reproduced below verbatim. Its owner signed it on 2026-11-14.

## Signed spec

<!-- signed spec begins: sha256 e75158e6844427dfc19ffcbb5f6616fafb4b79454f186ef3592c13f01c374426 -->
# Versioned draft file: behaviour spec

Status: revision 1, drafted on 2026-11-14 for the owner's signature. This design follows the method owner's written answers of 2026-11-14 about keeping versions of a document by hand.
Date: 2026-11-14.
Revision: 1. The first revision.

The command is `<cli> drafts`, with two subcommands, `check` and `extract`.

Every example in this file and in the tool's fixtures is invented. None of it comes from a real person's letters, résumés, essays, employers or results.

## 1. Purpose

A document such as a cover letter or a résumé goes through many versions. Without a record, which version is current, what changed from one version to the next and why, and what evidence each version earned live only in memory. This command keeps them in one file per document and checks that file, so the answers come from the file, not from memory.

It follows rule 1 of the method ("Never overwrite"): nothing already in the file is edited. A new version, a result and the send mark are each added at the end, and the check proves it against an earlier copy of the file. It follows rule 6 ("Test before you trust"): every check runs its self-test first, and a check with nothing to look at is DEAD, never OK.

## 2. Scope

In:
- one draft file per document (one letter, one résumé, one essay), holding every version, and every result and send entry, in the order they were written (section 3.1);
- `check`: the rules of section 4, reported by file and line (section 6);
- `extract`: one version's text written to a new file, so it can be given to `ab`, `panel`, `barred` or `claims` (section 7);
- a self-test on built-in invented files before the draft file is read (section 5.2).

Out:
- writing to the draft file. The tool never writes to it. A person writes each new version, each result entry and the send entry, by hand, at the end of the file;
- running any other command. A result entry cites a run folder; nothing runs a command by itself;
- PDF. A PDF is an output of a version, not a version;
- judging whether a version is better, or whether a change note is true;
- fetching anything over the network.

## 3. Inputs

### 3.0 Options

| Form | Meaning |
|---|---|
| `<cli> drafts check FILE [--earlier COPY]` | Check the draft file (section 4). `--earlier COPY` names an earlier copy of the file, for rule 8. It is given at most once. |
| `<cli> drafts extract FILE <id> --out OUT [--earlier COPY]` | Write version `<id>`'s text to the new file `OUT` (section 7). `--earlier COPY` is as for `check`. |
| `-h`, `--help` | Write the fixed summary of section 3.3 to standard output and exit `0`, under the rules of barred.md section 3.0. `<cli> drafts`, `<cli> drafts check` and `<cli> drafts extract` write the same summary. |

### 3.1 The draft file

UTF-8 text only. A byte-order mark at the very start is dropped. Line breaks follow barred.md section 3.2. Lines are numbered from 1.

The file is a run of sections, in file order. Each section starts with a header line, and is added at the end of the file when it is written. There are three kinds.

A **version** is written when the version is written, and holds only what is known then:

```text
## v<n>
parent: <id, or none>
date: <YYYY-MM-DD>
change: <one line>
sha256: <64 lowercase hexadecimal digits>
text:
<the version's text>
```

The `sha256:` line is optional. The version's text is every line after its `text:` line, up to the next header line or the end of the file.

A **result entry** is added when a version has been read by another command:

```text
## result
version: <id>
date: <YYYY-MM-DD>
run: <run folder>
note: <one line>
```

The `note:` line is optional. The run folder is the folder the other command made for that run, as a path relative to the draft file's folder.

A **send entry** is added when a version is chosen as the send copy:

```text
## send
version: <id>
date: <YYYY-MM-DD>
```

An entry names the version it is about and carries its own date. It comes after that version in the file, and later versions and entries may follow it.

In every section, `date` is the day the section was added to the file. A version drafted on one day and added on a later day carries the later day; its change note can say when it was drafted.

The form:

- A header line is exactly `## v<n>`, `## result` or `## send`.
- A key line is the key, a colon, a space and the value. In each section, the key lines follow the header directly, one per line, with no blank line between them, in the order shown above. No key is repeated. An optional key may be left out; every other key is required.
- A version's header is followed by its `parent:` line, and its key lines end at its `text:` line.
- An entry's header is followed by its `version:` line, and its key lines end at the first blank line or the next header. After them, only blank lines may stand before the next header.
- Before the first header, only blank lines may stand.
- A blank line is one that is empty or holds only spaces and tabs.

Rule 1 (section 4) reports each break of this form. So a stray text line that reads `## v4`, say, opens a section with no `parent:` line, and is reported by its line instead of silently splitting the text. **Known limit:** a text that holds a complete, well-formed version header, or a complete, well-formed entry, cannot be told from a real one.

### 3.2 Ids, parents and the sha256

- An id is `v` followed by a whole number. Ids are unique and increase in file order.
- Each version names exactly one parent: the id of an earlier version, or `none`. The first version names `none`. A later version may name `none` too: a rewrite from scratch did not come from any earlier version.
- The tool computes each version's sha256 over these bytes: each line of its text, without its line break, followed by one line feed, once any blank lines at the end of the text are dropped. So the bytes end with exactly one line feed, whatever line breaks the file uses and however many blank lines stand before the next section. A version's text always holds a line that is not blank: a text that is all blank is a form fault (rule 1).
- A `sha256:` line, when present, must match it.
- `extract` writes exactly these bytes (section 7), so the sha256 of an extracted file equals its version's sha256.

### 3.3 The help summary

The summary is the text below, byte for byte, ending in one line feed. `track-record` is the release's command name: if the name changes, the summary changes with it.

```text
usage: track-record drafts check FILE [--earlier COPY]
       track-record drafts extract FILE ID --out OUT [--earlier COPY]

Check the file that holds a document's versions, or write out one version.

  --earlier COPY  an earlier copy that must still be the start of FILE
  --out OUT       the new file extract writes; it must not exist
  -h, --help      show this summary and exit

exit: 0 OK, 1 a fault that check reports or extract refuses,
      2 a DEAD check or cannot run
```

## 4. The rules

`check` applies these rules. Each fault is reported as `<file>:<line>: <fault>`, in the record check's style (record-check.md section 6), where `<line>` is the line of the header or the key line the fault is about. Findings come in line order, and on one line in rule order.

1. **Form.** Each section follows section 3.1. A section that does not gets one finding, the first that applies, and no other rule looks at it: none of its keys is checked, and no parent or entry can name it.
   1. `no <key> line after the header`: a version's header is not followed by its `parent:` line, or an entry's by its `version:` line (at the header's line);
   2. `unknown key`: a line among the key lines is not one of the section's keys (in a version, a blank line there counts as one);
   3. `key out of order`: a key is repeated, or stands out of the order of section 3.1;
   4. `no <key> line`: a required key is missing, `text` included (at the header's line);
   5. `empty text`: a version's text has no line that is not blank (at the header's line). A version with no text is not a version;
   6. `line after an entry`: a line that is not blank follows an entry's key lines.

   A line that is not blank before the first header is reported as `line before the first section`.
2. **Ids.** Ids are unique and increase in file order: `repeated id, first on line <m>`, or `id out of order, line <m>`, where line `<m>` holds the version before it.
3. **Parents, and the versions that entries name.** The first version names `none`: `first version has a parent`. Every other version's parent is `none` or the id of a version earlier in the file: `parent is itself`, `parent comes later, line <m>`, or `parent not found`. Each entry names a version earlier in the file: `version comes later, line <m>`, or `version not found`. Each is reported at its `parent:` or `version:` line.
4. **Change notes.** Each version has a change note: `empty change note`.
5. **Dates.** Each section's date, a version's or an entry's, is a real calendar day written `YYYY-MM-DD`: `not a date`. It is never earlier than the date of the section just before it in the file, of whatever kind: `dated before the section on line <m>`. The file only grows at its end, so file order is the order the sections were added, and this rule says what rule 8 says. When that section's date is not a real day, the finding is `dates cannot be compared, line <m>`. The same date is not a fault. The first section has no section before it. The comparison is with the nearest section before it that rule 1 accepts.
6. **Send entries.** There is at most one send entry: `a second send entry, first on line <m>`.
7. **sha256.** A `sha256:` line equals the version's sha256 (section 3.2), written as 64 lowercase hexadecimal digits: `sha256 does not match the text`.
8. **Earlier copy.** Given `--earlier`, the earlier copy must still be the start of the file now, byte for byte, as in record-check.md section 4.7: `differs from the earlier copy`, at the line of the first byte that differs, or `<file>: shorter than the earlier copy`. The sha256 ignores blank lines at the end of a text, but this check does not: removing a blank line in the part of the file the earlier copy holds is an edit of earlier bytes, and is a fault. Without `--earlier`, this rule is not applied, and the status line says so (section 6).
9. **Run folders.** Each result entry's run folder exists: `run folder not found`, at its `run:` line.

## 5. DEAD, and the self-test

### 5.1 A check is DEAD when

- the file is empty (`empty file`), or holds no version that rule 1 accepts (`no version`);
- the earlier copy named by `--earlier` cannot be found (`earlier copy not found`) or read (`earlier copy cannot be read`).

A DEAD check is never reported OK.

### 5.2 The self-test

Before the draft file is read, each rule runs on a built-in invented file with one planted fault, and must report exactly that fault. If any rule does not, the run cannot go ahead (exit `2`, section 8).

## 6. Output and exit status

`check` writes one status line, then its finding lines (section 4):

- `OK    <file>: <counts>; send copy <id>; <earlier>`, with `send copy none` when the file has no send entry;
- `FAIL  <file>: <counts>; faults <k>; <earlier>`, then one line per fault;
- `DEAD  <file>: <reason>; <counts>`, with a reason from section 5.1, and no finding lines.

`<counts>` is `versions <v>, parents resolved <p>, results <r>, run folders found <f>, send entries <s>`: the versions that rule 1 accepts, the versions whose parent holds under rule 3, the result entries, the result entries whose run folder exists, and the send entries. `<earlier>` is `earlier copy <b> bytes, file <B> bytes`, or `no earlier copy given`. Counts are printed as numbers, `0` included, so a silent run cannot pass for a clean one. `<file>` is the path as given, escaped as printed paths are in barred.md section 6.

**Privacy.** Neither `check` nor `extract` prints a version's text, its change note or a result's note: only the file's path, ids, line numbers and counts.

**Exit status:** `0` when every rule holds; `1` when any rule FAILs and none is DEAD; `2` when any check is DEAD or the run cannot go ahead (section 8). The highest applies. Output that cannot be written follows cli.md section 4.

## 7. Extract

`extract FILE <id> --out OUT` first applies the rules of section 4 to `FILE`.

- A fault under rules 1 to 8, or a DEAD check, stops it: it writes no file, writes the status line and finding lines that `check` would write to standard error, and exits as `check` would (`1` for a fault, `2` for DEAD).
- A fault under rule 9, a cited run folder that does not exist, does not stop it: the finding line goes to standard error, and the version is still written. Run folders get moved, and the text is still the text.
- `--earlier COPY` is taken as `check` takes it, so rule 8 can be applied. Without it, rule 8 is not applied, and standard error says so in one line: `no earlier copy given: rule 8 not applied`.

Otherwise it writes version `<id>`'s bytes (section 3.2), exactly, to `OUT`, writes nothing to standard output, and exits `0`. `OUT` must not exist: the tool refuses to write over a path, and never deletes one it did not create.

## 8. When it cannot run

The run exits `2`, writes nothing to standard output, writes nothing to `OUT`, and writes `cannot run: <reason>` lines to standard error, when:

- an option is unknown (`unknown option <option>`);
- `--earlier` is given more than once (`--earlier given more than once`);
- `extract` is given no `--out` (`extract needs --out OUT`);
- more than one FILE is named (`check takes one FILE, not several`, or `extract takes one FILE, not several`);
- `extract` names an id that no version in the file has (`no version <id>`). A section that rule 1 reports does not count as a version. An id is not private;
- `extract` is given an `OUT` that already exists (`--out names a path that already exists`);
- no FILE is named (`check needs a FILE`, or `extract needs a FILE`), `extract` is given no id (`extract needs a version id`), or the subcommand is missing (`drafts needs check or extract`) or unknown (`unknown subcommand <subcommand>`);
- the draft file is missing or cannot be read (`cannot read the draft file: <name>`). An empty draft file is not this case: it is DEAD (section 5.1);
- the self-test fails (`self-test failed: rule <n>`, section 5.2).

`<option>`, `<id>` and `<subcommand>` are escaped as printed paths are in barred.md section 6. `<name>` is the draft file's name without its folder, escaped the same way. When the output cannot be written, the run follows cli.md section 4: exit `2`, one line `cannot run: cannot write output`, and no traceback.

## 9. Decisions, with reasons

1. **One file per document.** A file holds one document's history, so its ids, parents and send copy are about one thing.
2. **The tool never writes to the draft file.** The record is written by a person; a tool that edits it could break METHOD.md rule 1.
3. **Text only.** A PDF is made from a version; checking the PDF is the other commands' work.
4. **Counts on every line.** A run that read nothing must not look like a clean one (METHOD.md rule 6).
5. **No text in the output.** A draft is private until it is sent.
6. **Results and the send mark are entries of their own, added at the end.** A version is read after it is written, and the send copy is chosen after the reads, usually once later versions exist. Writing either into the version's own section would edit an earlier part of the file, and rule 8 would refuse an honest file.
7. **The earlier copy is an option, not a line in the file.** A line naming it inside the draft file would itself be an edit to the file.
8. **A later version may name `none`.** A rewrite from scratch is real, and making it name a parent it did not come from would put a false link in the record.
9. **Blank lines at the end of a text are not hashed.** Blank lines between sections come and go when a file is edited by hand, and they are not the document. The earlier-copy check still sees them: removing one from an earlier part of the file is an edit of earlier bytes.
10. **The form fails closed.** Keys stand in a fixed order, an unknown key is a fault, and a header must be followed by its first key, so a stray line that reads like a header is reported by its line instead of silently splitting a text.
11. **A version with no text is a fault.** A zero-byte extract handed to a reader is the kind of silent empty the method exists to stop.
12. **Dates follow file order.** The file only grows at its end, so file order is the order the sections were added, and the date rule says the same thing the earlier-copy rule says. A date is therefore the day a section was added, not the day it was drafted.

## 10. Known answers

The fixtures are invented: a letter to Example Corp in three versions. `letter.txt`:

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

Every line ends with LF, so the file is 37 lines and 600 bytes. The folder `runs/panel-01` exists beside it. `letter-before.txt` is its first 17 lines (259 bytes): the copy taken when v2 was the latest version. The result for v1, v3 and the send entry were all added after that copy was taken.

`<cli> drafts check letter.txt --earlier letter-before.txt` writes the line below and exits `0`:

```text
OK    letter.txt: versions 3, parents resolved 3, results 1, run folders found 1, send entries 1; send copy v3; earlier copy 259 bytes, file 600 bytes
```

Without `--earlier`, the line ends `send copy v3; no earlier copy given`.

`letter-edited.txt` is `letter-before.txt` with a result entry for v1 written into the middle, between v1 and v2, instead of at the end: lines 10 to 14 are `## result`, `version: v1`, `date: 2026-03-03`, `run: runs/panel-01` and `note: two readers found the opening slow`, and line 15 is blank. It is 23 lines and 359 bytes. `<cli> drafts check letter-edited.txt --earlier letter-before.txt` writes these lines and exits `1`:

```text
FAIL  letter-edited.txt: versions 2, parents resolved 2, results 1, run folders found 1, send entries 0; faults 1; earlier copy 259 bytes, file 359 bytes
letter-edited.txt:10: differs from the earlier copy
```

`<cli> drafts extract letter.txt v3 --out v3.txt --earlier letter-before.txt` writes the 66 bytes of v3's text to `v3.txt`, whose sha256 is `e9db1dc84b01be6dbafe216e3dd033b3ecb1c83db3143a2925d3381348bfe6b8`, the value on v3's `sha256:` line. It writes nothing to standard output or standard error, and exits `0`. Without `--earlier`, it writes the same bytes, writes `no earlier copy given: rule 8 not applied` to standard error, and exits `0`. `<cli> drafts extract letter-edited.txt v2 --out v2.txt --earlier letter-before.txt` writes no file, writes the two lines above to standard error, and exits `1`.

One test per rule plants that rule's fault in a copy of `letter.txt` and finds it, with the fault line of section 4:

- form: a stray `## v4` line inside a text; an unknown key; keys out of order; a version with no `text:` line; a version whose text is all blank; a line after an entry; a line before the first section;
- ids: a repeated id; ids out of order;
- parents: a first version with a parent; a parent that is the version itself; a parent that comes later; a parent that does not exist; an entry that names a later version; an entry that names a version that does not exist;
- a version with an empty change note;
- dates: a date that is not a real day; a version dated before the result entry just before it; an entry dated before the version just before it;
- two send entries;
- a `sha256:` line that does not match;
- an earlier copy that is not the start of the file now, and a file shorter than its earlier copy. `letter.txt` with its blank line 9 removed gives `letter.txt:9: differs from the earlier copy` against `letter-before.txt`, although every version's sha256 is unchanged;
- a result entry whose run folder does not exist: `check` FAILs; `extract` writes the version, writes the finding to standard error and exits `0`.

And:

- a later version that names `none` is OK;
- the same versions with CRLF line breaks, or with more blank lines between sections, give the same sha256 for each version;
- an empty file and a file with no version are DEAD; so is a run whose earlier copy cannot be found;
- `extract` refuses an existing `--out`;
- each case of section 8 exits `2` with its `cannot run:` line, nothing on standard output and no `OUT`: an unknown option, `--earlier` given twice, `extract` with no `--out`, two FILEs, `extract letter.txt v9 --out v9.txt`, which gives `cannot run: no version v9`, an existing `OUT`, no FILE, no id, a missing subcommand, an unknown subcommand, and a draft file that does not exist;
- no output line, on standard output or standard error, holds any version's text, change note or result note;
- output that cannot be written: closed standard output, a broken pipe, closed standard error.

## 11. Command line (cli.md, Revision 7)

cli.md's revision 7 adds `<cli> drafts` and its subcommands `check` and `extract` to sections 1, 2, 4 and 5, with the one-line description `check a file of a document's versions, or extract one`, and lists `drafts` among the commands whose fixed help text is stated in their own spec.
<!-- signed spec ends -->
