# Claim gate: behaviour spec

Status: accepted.
Date: 2026-11-01.
Revision: 1. The signed spec (sha256 bedcdc2861b6a0990d629733fa4a262bc449b2a2a3c35f5cb39bb68922620ac4) is reproduced below verbatim, and the build readings follow it.

## Signed spec

<!-- signed spec begins: sha256 bedcdc2861b6a0990d629733fa4a262bc449b2a2a3c35f5cb39bb68922620ac4 -->
# Claim gate: behaviour spec

Status: accepted. Signed by the owner on 2026-11-01. Drafted by the Career Officer from the README's promise at fe3a9ce and the conventions of barred.md (Revision 6.3) and tone-and-tells.md (Revision 6); nothing in it comes from any private tool or record.
Date: 2026-11-01.
Revision: 1.

The command is `<cli> claims` (working name; the release names it).

Every example in this file and in the tool's fixtures is invented. None of it comes from a real person's résumés, postings, employers or claims.

## 1. Purpose

Fail when a sentence in your career copy has no matching entry in a claims list you approve. A sentence you changed is a new sentence: it fails until you approve it again. The tool never decides whether a claim is true. Approving it is yours.

## 2. Scope

In:
- one claims list file;
- one or more named input files: plain text, Markdown read as text, and PDFs;
- folding, so that case, a ligature, an invisible character, a curly quote or a non-breaking hyphen cannot make an approved sentence fail, or an unapproved one pass;
- a positive control on every file;
- on request, a report of approved entries that no input file uses.

Out:
- judging whether a claim is true, reading or checking its source, or fetching anything over the network;
- suggesting, rewriting or ranking wording;
- Markdown inline markup: `**`, `_`, backticks and link syntax are ordinary text (section 4, known limits);
- any decision about what belongs on the list. The list is the user's data.

## 3. Inputs

### 3.0 Options

| Option | Meaning |
|---|---|
| `--list FILE` | The claims list. Required, given exactly once. |
| `--control TEXT` | A control string. Required; may be given more than once. A file passes its control when it contains any one of them (section 3.3). |
| `--stale-check` | Also report approved entries that no input file uses (section 6). Repeating it changes nothing. |
| `-h`, `--help` | Write the fixed summary of section 3.4 to standard output and exit `0`, under the same rules as barred.md section 3.0: it reads no list, control or input file, and wins over every other argument; after `--`, every argument is a file name. |

Every other argument is an input file.

### 3.1 The claims list

- UTF-8 text, with the same rules as barred.md section 3.1 for the byte-order mark, line ends, blank lines and `#` comment lines. A file that is not valid UTF-8 cannot be used (section 7).
- One entry per line, in tab-separated fields:
  1. **status**: `approved`, `proposed` or `refused`, in any case;
  2. **sentence**: the text of the claim, one or more sentences as they should appear in the copy;
  3. **source** (optional): where the claim's evidence lives, in any form the user likes (a file path, a URL, a record id). In this release it is stored and never read, checked or printed;
  4. anything after a third tab is a note. A note is never matched and never printed.
- Entries are numbered from 1 in file order, counting only entry lines. Output names an entry only by this number.
- The list cannot be used (section 7) when any entry has an unknown status, has no sentence field, or has a sentence that is empty once prepared (section 4), or when two entries have the same prepared sentence, whatever their statuses. The message names both entry numbers and no text.

### 3.2 Input files

- A file whose name ends in `.pdf` (any case) is read as the text `pdftotext` writes for it in its default mode, as barred.md section 3.2 says, with the same known limit for wraps inside a page.
- Any other file is read as UTF-8; each invalid byte sequence becomes U+FFFD and is not fatal. A sentence holding one will not match an entry, so it fails rather than passes.
- Line breaks and line numbers follow barred.md section 3.2.

### 3.3 The control

As barred.md section 3.3: prepared as section 4 says and matched as a substring of the file's prepared text. With no usable control, the run cannot go ahead (section 7).

### 3.4 The help summary

The summary is the text below, byte for byte, ending in one line feed.

```text
usage: track-record claims --list FILE --control TEXT [--control TEXT]...
    [--stale-check] FILE...

Fail on any sentence your claims list has not approved.

  --list FILE      the claims list (required)
  --control TEXT   a string each file must hold (repeatable, any one counts)
  --stale-check    also report approved entries no file uses
  -h, --help       show this summary and exit

exit: 0 every sentence approved, 1 a sentence not approved, 2 a DEAD file or cannot run
```

## 4. Sentences, folding and matching

**Folding** is barred.md section 4's folding (NFKC, full case folding, NFKC again, removal of every format character), then two further steps: the hyphen (U+2010) and non-breaking hyphen (U+2011) become a hyphen-minus (U+002D); and the curly quotes U+2018 and U+2019 become `'`, and U+201C and U+201D become `"`. The en dash, the em dash and every other dash stay as they are, as in barred.md.

**Line-end hyphens.** Before sentences are found, a line-end hyphen-minus is joined as barred.md section 4, form 3 (hyphen-kept) says: `end-`, a line break, then `to-end` becomes `end-to-end`. No other form is used. A word that layout split with a hyphen (`engi-`, `neers`) becomes `engi-neers` and so fails until fixed or approved; the gate fails closed.

**Blocks.** A blank line (a line holding nothing, or only spaces and tabs) ends a block. A line that starts, after any spaces or tabs, with a **line marker** also starts a new block. The line markers are: `-`, `*`, `+` or `•` (U+2022) followed by a space or tab; one to three digits followed by `.` or `)` and then a space or tab; and one to six `#` followed by a space or tab. The marker and the whitespace after it are not part of any sentence. So each résumé bullet and each Markdown heading is its own block, with or without a final full stop.

**Sentences.** Inside a block, a sentence end is a `.`, `!` or `?`, followed by any closing quotes or brackets (`"`, `'`, `)`, `]`), followed by whitespace or the end of the block. This is tone-and-tells.md's rule, applied after folding. A sentence runs from the start of the block or just after the previous sentence end, up to and including its own end, or to the end of the block. A sentence with no letter or digit in it is skipped: it is never checked and never counted.

**Prepared form.** A run of sentences (one or more consecutive sentences in a block), an entry's sentence field and a control are each prepared by folding, turning every run of whitespace (barred.md's 29 characters, line breaks included) into one space, and trimming. A run is prepared from its whole text, from the start of its first sentence to the end of its last. For a run or an entry, one final `.`, `!` or `?` is then removed, together with any closing quotes or brackets after it. So `Led the team.` and `Led the team` are the same entry. A file's **prepared text**, used for the control, is its whole text after folding and the line-end hyphen join, with every whitespace run turned into one space.

**Matching.** An entry matches a run when the run's prepared form is exactly equal to the entry's prepared sentence. Equality is exact: an entry never matches part of a sentence, and a sentence that contains an entry and more is not matched by it. Runs let one entry cover a claim that the sentence rule splits, such as `Joined Example Corp. in 2019.`, which the rule reads as two sentences.

**Covering.** In each block, from the first sentence on, the tool takes the longest run starting at that sentence that matches an entry, of any status. The run is covered by that entry, and the search goes on after it. A sentence where no run matches is **unlisted**, and the search goes on from the next sentence.

**Results.** A run covered by an `approved` entry passes. A run covered by a `proposed` or `refused` entry is a finding, and so is each unlisted sentence.

**Known limits.**
- Markdown inline markup is text. `**Led** the team` matches an entry `**led** the team`, not `led the team`.
- Table rows, block quotes and other Markdown structures that aren't line markers are read as ordinary text.
- The sentence rule has no abbreviation list. Runs cover most splits it makes (above); an entry written with the split in it always matches.

## 5. A file is DEAD when

- it is missing or cannot be read, or it is a PDF that `pdftotext` cannot read;
- none of the controls is found in it;
- it holds no checked sentence (section 4).

A DEAD file gets no finding lines.

## 6. Output and exit status

Each input file is labelled by its printed path, escaped as in barred.md section 6. One status line per file, in argument order:

- `OK    <label>: <s> sentences, all approved (control found)`, where `<s>` is the number of checked sentences;
- `FAIL  <label>: <k> of <s> sentences not approved`, then one finding line per unapproved run or sentence, in file order: `<label>:<line>: <kind>: <sentence>`. `<kind>` is `unlisted`, `proposed, entry #<N>` or `refused, entry #<N>`. `<line>` is the line where the run's first character stands. `<sentence>` is the run as it appears in the file, not folded, line markers removed, whitespace runs turned into one space and trimmed, escaped as printed paths are;
- `DEAD  <label>: <reason>`, naming the case from section 5.

With `--stale-check`, after the file lines, one line per approved entry that covered no run in any input file of the run, in entry order: `stale entry #<N>`. Without the flag nothing about staleness is checked, because a run over one file need not use every entry.

**Privacy.** Output never contains a source field, a note, the list file's path, or the sentence of an entry that covered nothing. A finding prints only text that is in the input file. A test greps the captured output of the known-answer runs for every source and note in the fixtures and finds none.

**Exit status:** `0` when every file is OK and no stale entry is reported; `1` when any file FAILs or any stale entry is reported, and none is DEAD; `2` when any file is DEAD or the run cannot go ahead. The highest applies.

## 7. When it cannot run

The run exits `2`, writes nothing to standard output and one `cannot run: <reason>` line to standard error, naming no entry text and not the list's path, when: no input file is named; `--list` is missing, given twice, or names a file that is missing, unreadable, not UTF-8, or unusable under section 3.1; no usable `--control` is given; an option is unknown. When the output cannot be written, it follows the rule cli.md section 4 and barred.md state: exit `2`, one line `cannot run: cannot write output`, no traceback. A closed standard error never changes the exit status.

## 8. Decisions, with reasons

1. **Every sentence, no exemptions by length or position.** A three-word sentence can carry a claim ("Led forty engineers"). A gate that skips short lines or contact lines lets the claim through. Lines the user doesn't consider claims (a greeting, a contact line) are approved like any other.
2. **Three statuses.** `proposed` lets a drafter list a sentence for the owner to approve without it passing first. `refused` records a claim the owner turned down, so the same sentence fails with that reason if it comes back.
3. **Exact equality after folding.** Any edit to an approved sentence makes it a new sentence. Folding removes only differences a reader cannot see or that do not change the words (case, invisible characters, ligatures, curly quotes, the U+2010 and U+2011 hyphens, a final full stop).
4. **Hyphens.** U+2010 and U+2011 fold to a hyphen-minus here. Register item K22 notes that barred does not fold them. The owner's recommendation is that barred's next revision adopts the same fold, so both tools agree; that change is barred's, not this spec's.
5. **Sources stored, not checked.** METHOD.md section 5 asks every claim to link back to its source. This release stores the link; checking it, and flagging an approved entry without one, come in a later release with their own spec.
6. **The control and DEAD rules follow barred.** METHOD.md section 6: a run that finds nothing must show it was looking.

## 9. Known answers

**List L1** (tab-separated; invented):

```text
# invented list
approved	Led a team of six engineers at Example Corp.	notes/offer-letter.txt
approved	Shipped the Example importer in 2021.
approved	Joined Example Corp. in 2019.	notes/start.txt	invented note
approved	Built an end-to-end import pipeline.
proposed	Cut build times by forty percent.	notes/draft.txt
refused	Increased revenue tenfold.
```

Every run below uses `--list L1 --control "example"` unless it says otherwise.

| # | Input file (text) | Expected |
|---|---|---|
| 9.1 | `Led a team of six engineers at Example Corp. Shipped the Example importer in 2021.` | OK, 2 sentences; exit 0 |
| 9.2 | `led a team of six  engineers` / line break / `at EXAMPLE corp` (no final full stop) | OK, 1 sentence; exit 0 |
| 9.3 | `Led a team of seven engineers at Example Corp.` | FAIL, line 1, unlisted; exit 1 |
| 9.4 | `Led a team of six engineers at Example Corp and Example Two.` | FAIL, unlisted: containing an entry is not matching it; exit 1 |
| 9.5 | `Example work. Cut build times by forty percent.` | FAIL, 2 findings: `Example work.` unlisted; `Cut build times…` proposed, entry #5; exit 1 |
| 9.6 | `Example: Increased revenue tenfold.` on line 1, a blank line, then `Increased revenue tenfold.` | FAIL: line 1 unlisted (the whole line is one sentence); line 3 refused, entry #6; exit 1 |
| 9.7 | `- Led a team of six engineers at Example Corp` / `- Shipped the Example importer in 2021` (two bullet lines, no full stops) | OK, 2 sentences; exit 0 |
| 9.8 | `- Shipped the Example importer in 2021` / `- Mentored interns` | FAIL, line 2, unlisted: `Mentored interns`; exit 1 |
| 9.9 | `Joined Example Corp. in 2019.` | OK, 1 run of 2 sentences covered by entry #3; exit 0 |
| 9.10 | `Built an end‑to‑end import pipeline.` with U+2011 hyphens, and `--control "pipeline"` | OK, covered by entry #4; exit 0 |
| 9.11 | `Built an end–to–end import pipeline.` with en dashes, and `--control "pipeline"` | FAIL, unlisted: an en dash is not a hyphen; exit 1 |
| 9.12 | `Built an end-` / line break / `to-end import pipeline.`, and `--control "pipeline"` | OK: the line-end hyphen joins, covered by entry #4; exit 0 |
| 9.13 | `Led a team of six engineers at Example Corp.` with `--stale-check` | FAIL: `stale entry #2`, `stale entry #3`, `stale entry #4`, in that order; the file line is OK; exit 1 |
| 9.14 | 9.1's file with `--control "zebra"` | DEAD, control not found; no finding lines; exit 2 |
| 9.15 | a file holding only `- * -` and blank lines, with `--control "-"` | DEAD, no checked sentence; exit 2 |
| 9.16 | L1 with a seventh line `approved	led a team of six engineers at example corp` | cannot run: entries #1 and #7 are the same sentence; nothing on standard output; exit 2 |
| 9.17 | L1 with a line `maybe	Example.` | cannot run: unknown status in entry #7; exit 2 |
| 9.18 | the output of 9.1 to 9.13 | contains none of `notes/`, `invented note`, or the list's path |
| 9.19 | `--help` alongside any other arguments | the summary of 3.4, byte for byte; exit 0 |

Each case's file holds its control, except 9.14.

## 10. Command line (cli.md, Revision 3)

cli.md section 2 adds `<cli> claims`, run under this spec. Section 4's help list gains a fifth line, after `ab`:

- claims: fail on sentences your claims list hasn't approved

and section 4's list of levels where `-h` and `--help` are accepted adds `<cli> claims`. Section 5 adds claims to the commands that promise fixed help text (this spec, section 3.4). Nothing else in cli.md changes.
<!-- signed spec ends -->

## Build readings (maintainer, 2026-11-01)

Revision 1 edits no sentence of the signed spec. It reads points of sections 4 to 7 as stated below, and reading 8 settles a case the signed text leaves open.

1. **The count in a FAIL line.** In `FAIL  <label>: <k> of <s> sentences not approved`, `<k>` counts sentences. It does not count finding lines.
2. **A finding keeps the run as it stands in the file.** The line-end hyphen join of section 4 is for matching only. A finding prints the run as it appears in the file, with each whitespace run turned into one space, so `end-`, a line break and `to-end` print as `end- to-end`.
3. **No stale lines beside a DEAD file.** With `--stale-check`, when any file is DEAD, no `stale entry` line is printed, because a DEAD file's sentences were never checked.
4. **Counts are printed as written.** A count of one prints as `1 sentences`.
5. **DEAD reasons.** `cannot read`, the PDF message the barred check uses, `control not found`, `no checked sentence` and `is the list` (reading 8).
6. **Cannot-run reasons** are one line each, as listed in the build. A list with no entries is not unusable: it runs, and every sentence is unlisted.
7. **The line-end join comes first.** A line ending in `end-` followed by a line starting `1. ` joins into one sentence. Digits in a line marker are tested after folding.
8. **The list given as an input.** § 6's privacy promise makes the list, given as an input, a DEAD file. Section 6 says "Output never contains a source field, a note, the list file's path, or the sentence of an entry that covered nothing" and "A finding prints only text that is in the input file"; when an input is the list, both hold only if the gate refuses it. So an input that is the same file as the list (`os.path.samefile`, which counts `./L` and a symlink) is not read, and pdftotext is not run on it. It prints one line, `DEAD  file #<i>: is the list`, where `<i>` is its 1-based position among the input files, never its path (barred.md § 6, File labels). It counts as DEAD for the exit status and for reading 3. Other files are checked as usual. Known limit: a copy of the list under another name is not the same file, so it is checked like any input, and its findings can print the sources and notes it holds. The check tells files apart by identity, not by content.
