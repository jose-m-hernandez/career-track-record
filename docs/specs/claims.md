# Claim gate: behaviour spec

Status: draft. Revision 2 below is not signed; its owner signs the text between the draft markers as it stands.
Date: 2026-11-05.
Revision: 2. A draft: the text between the markers below (sha256 9a9a11f17553d56a457ec0ca1341e8cc822b7db4f8fee7b8a66a096ff6d5844a) is revision 2 in full. It is revision 1's signed text (sha256 bedcdc2861b6a0990d629733fa4a262bc449b2a2a3c35f5cb39bb68922620ac4) with the quote check added. The build readings of revision 1 follow it and still apply.

## Draft spec (revision 2, not signed)

<!-- draft spec begins: sha256 9a9a11f17553d56a457ec0ca1341e8cc822b7db4f8fee7b8a66a096ff6d5844a -->
# Claim gate: behaviour spec

Status: revision 2, drafted on 2026-11-05 for the owner's signature. Revision 2 adds a quote check, a port of an evidence-check method in which a quote must appear in the source it cites; nothing in it comes from any private tool or record.
Date: 2026-11-05.
Revision: 2. Adds the quote line, --check-sources and the number boundary (sections 2, 3.0, 3.1, 3.4, 3.5, 6, 7, 8, 9 and 10).

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
- on request, a report of approved entries that no input file uses;
- on request, a quote check: each quote written under an entry is looked for, word for word, in the local file the entry cites as its source (section 3.5).

Out:
- judging whether a claim is true, checking the claim's sentence itself against its source, or fetching anything over the network;
- reading a source that is an Office file, or a git commit subject as a source; both are out of scope for this release and left for a later one;
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
| `--check-sources` | Also check each quote against its entry's source (section 3.5). Repeating it changes nothing. |
| `-h`, `--help` | Write the fixed summary of section 3.4 to standard output and exit `0`, under the same rules as barred.md section 3.0: it reads no list, control or input file, and wins over every other argument; after `--`, every argument is a file name. |

Every other argument is an input file.

### 3.1 The claims list

- UTF-8 text, with the same rules as barred.md section 3.1 for the byte-order mark, line ends, blank lines and `#` comment lines. A file that is not valid UTF-8 cannot be used (section 7).
- One entry per line, in tab-separated fields:
  1. **status**: `approved`, `proposed` or `refused`, in any case;
  2. **sentence**: the text of the claim, one or more sentences as they should appear in the copy;
  3. **source** (optional): where the claim's evidence lives, in any form the user likes (a file path, a URL, a record id). It is the third field trimmed of surrounding whitespace; an entry has no source when it has no third field or that field is empty once trimmed. It is never printed. With `--check-sources`, it is read as a file path relative to the folder of the list file (section 3.5);
  4. anything after a third tab is a note. A note is never matched and never printed.
- A **quote line** is a line whose first field, trimmed of whitespace and in any case, is `quote`. Its second field is the **quote**: a phrase that should appear word for word in the entry's source. Anything after a second tab on a quote line is a note, never read and never printed. A quote line belongs to the nearest entry line above it; blank lines and `#` comment lines between them are skipped, as everywhere in the list. A quote line is not an entry and takes no entry number. An entry has at most one quote line.
- Entries are numbered from 1 in file order, counting only entry lines. Output names an entry only by this number.
- The list cannot be used (section 7) when any entry has an unknown status, has no sentence field, or has a sentence that is empty once prepared (section 4), or when two entries have the same prepared sentence, whatever their statuses. The message names both entry numbers and no text.
- The list also cannot be used when a quote line comes before the first entry line; when an entry has two quote lines; when an entry with a quote line has no source; or when a quote line has no second field, or its quote holds no letter or digit once prepared (section 4). These hold with and without `--check-sources`. They are checked in file order as the list is read, alongside the unknown-status and no-sentence checks, and for one quote line in the order just given; the same-sentence check comes after the whole list is read. Each message names the entry number and no text (section 7).

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
    [--stale-check] [--check-sources] FILE...

Fail on any sentence your claims list has not approved.

  --list FILE      the claims list (required)
  --control TEXT   a string each file must hold (repeatable, any one counts)
  --stale-check    also report approved entries no file uses
  --check-sources  also check each quote against the source file it cites
  -h, --help       show this summary and exit

exit: 0 every sentence approved, 1 a sentence not approved, 2 a DEAD file or cannot run;
    with --check-sources, also 1 a quote not found, 2 a source that cannot be read
```

### 3.5 Quotes and sources

The quote check is a port of an evidence-check method in which a quote must appear in the source it cites. It runs only with `--check-sources`, and only when the run goes ahead (section 7).

- **Which entries.** Every `approved` and `proposed` entry that has a quote line is checked, whether or not any input file used it. A `refused` entry is never checked, never printed and never counted. An entry without a quote line is never checked or counted. The check does not depend on the input files: it runs even when an input file is DEAD.
- **Resolving the source.** The source is joined to the folder that holds the list file; an absolute source stays absolute. The resulting path is looked up without following a final symbolic link. When the lookup reports that nothing is at the path (no such file, or a part of the path that is not a folder) or that no file can have that name (a name too long, a character the system refuses, including a NUL character), the quote is **unverified**: the source is not a local file (a URL, a record id, a path that does not exist) and nothing is read. Any other failure of the lookup (for example no permission to look, or a loop of symbolic links) makes the source **unreadable**, `cannot read`: a lookup that was refused never looked, so it is not evidence that the source is absent. A dangling symbolic link is something at the path, so the lookup succeeds, following it fails, and it is unreadable, `cannot read`.
- **Formats.** A source whose name ends in `.pdf`, in any case, is read as the text `pdftotext` writes for it, as section 3.2 says. Any other source must be UTF-8 text; one leading byte-order mark is dropped. No other format is read: an Office file is bytes that are not UTF-8 text.
- **Unreadable.** A source that is there but cannot be checked is **unreadable**, with a reason: `not a regular file` (a directory, a FIFO, a device or a socket, or a symbolic link to one; the path is checked before anything opens it), `cannot read` (a path the lookup was refused, for example one inside a folder without permission; a dangling symbolic link; a file that cannot be opened), `not UTF-8`, `pdftotext not found`, `pdftotext failed`, or `cannot check` for any other error.
- **Finding the quote.** The quote is prepared as a run is (section 4), one final `.`, `!` or `?` removed; the source's text is prepared the same way, without that removal. The quote is **found** when its prepared form occurs in the source's prepared text with a word boundary at each end of the quote that is a word character: the source character just outside that end is not a word character, or there is none. A word character is a letter, a number or an underscore, or a combining mark that folding leaves uncomposed. An end that is not a word character needs no boundary, so `.NET` is found in `ASP.NET`. Otherwise the quote is **not found**.
- **The number boundary.** When the prepared quote ends in a digit (Unicode category Nd), a match also needs the number to stop there: the next source character is not a digit, and is not a `.` that is followed by a digit. So `Version 2.`, prepared to `Version 2`, is not found in `Version 2.5`, and is found in `Version 2. Then we rested.` Known limits: only a `.` is tested, so `Version 2` is found in `Version 2,5`; and only the end after the quote is tested, so `2 engineers` is found in `1.2 engineers`.
- **Exit status.** An approved quote that is not found makes the exit status at least `1`. An approved source that is unreadable makes it `2`. **An unverified quote is printed and counted, and does not change the exit status.** A proposed entry never changes the exit status, whatever its result. Section 6 gives the lines.

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

With `--check-sources`, after the file lines and after any stale lines, one line for each checked entry (section 3.5) whose quote is not found, unreadable or unverified, in entry order; a found quote prints no line. `<S>` is the entry's status, `approved` or `proposed`, and `<r>` is the reason of section 3.5:

```text
<S>, entry #<N>: quote not found
<S>, entry #<N>: source unreadable (<r>)
<S>, entry #<N>: source unverified
```

Then always these two lines, last:

```text
quotes, approved: <a> found, <b> not found, <c> unreadable, <d> unverified
quotes, proposed: <a> found, <b> not found, <c> unreadable, <d> unverified
```

Counts are printed as numbers, `0` included. Without the flag none of these lines appear.

**Privacy.** Output never contains a source field, a resolved source path, any text read from a source, a quote, a note, the list file's path, or the sentence of an entry that covered nothing. A source line names the entry only by its number. A finding prints only text that is in the input file. A test greps the captured output of the known-answer runs for every source and note in the fixtures and finds none. Another greps the captured output of the runs under `--check-sources` for every quote, source field and resolved source path, a string written only inside the source files, every note and the list's path, and finds none.

**Exit status:** `0` when every file is OK and no stale entry is reported; `1` when any file FAILs or any stale entry is reported, and none is DEAD; `2` when any file is DEAD or the run cannot go ahead. With `--check-sources`, an approved quote not found makes it at least `1`, and an approved source unreadable makes it `2`; an unverified quote, and any result of a proposed entry, change nothing (section 3.5). The highest applies.

## 7. When it cannot run

The run exits `2`, writes nothing to standard output and one `cannot run: <reason>` line to standard error, naming no entry text and not the list's path, when: no input file is named; `--list` is missing, given twice, or names a file that is missing, unreadable, not UTF-8, or unusable under section 3.1; no usable `--control` is given; an option is unknown. The four quote-line reasons of section 3.1 are `a quote line comes before the first entry`, `entry #<N> has two quote lines`, `entry #<N> has a quote but no source` and `entry #<N> has an empty quote`, where `<N>` is the entry the quote line belongs to. When the output cannot be written, it follows the rule cli.md section 4 and barred.md state: exit `2`, one line `cannot run: cannot write output`, no traceback. A closed standard error never changes the exit status.

## 8. Decisions, with reasons

1. **Every sentence, no exemptions by length or position.** A three-word sentence can carry a claim ("Led forty engineers"). A gate that skips short lines or contact lines lets the claim through. Lines the user doesn't consider claims (a greeting, a contact line) are approved like any other.
2. **Three statuses.** `proposed` lets a drafter list a sentence for the owner to approve without it passing first. `refused` records a claim the owner turned down, so the same sentence fails with that reason if it comes back.
3. **Exact equality after folding.** Any edit to an approved sentence makes it a new sentence. Folding removes only differences a reader cannot see or that do not change the words (case, invisible characters, ligatures, curly quotes, the U+2010 and U+2011 hyphens, a final full stop).
4. **Hyphens.** U+2010 and U+2011 fold to a hyphen-minus here. Register item K22 notes that barred does not fold them. The owner's recommendation is that barred's next revision adopts the same fold, so both tools agree; that change is barred's, not this spec's.
5. **Sources checked only for a quote, and only on request.** METHOD.md section 5 asks every claim to link back to its source. With `--check-sources`, the gate checks that an entry's quote appears word for word in the local file its source names. It never checks the claim's sentence against the source: the sentence is how the copy puts the claim, and the quote is the evidence for it. Without the flag the source is stored and never read, so a run without it gives what revision 1 gave. Flagging an approved entry without a source comes in a later release.
6. **The control and DEAD rules follow barred.** METHOD.md section 6: a run that finds nothing must show it was looking.
7. **A quote line, not a fourth field.** In revision 1 anything after an entry's third tab is a note. A quote in a fourth field would change the meaning of lists that already carry notes, and would make `approved<TAB>sentence<TAB><TAB>note` a list error. A first field of `quote` is an unknown status under revision 1, so no list that revision 1 accepts changes meaning.
8. **An unverified quote does not change the exit status.** A URL or a record id is a source this tool does not read, since it fetches nothing over the network (section 2). Such a quote was not checked, so it is neither DEAD nor a pass: it is printed and counted, so the user sees how many quotes went unchecked.
9. **Proposed entries are reported but never change the exit status.** A proposed entry already fails wherever the copy uses it (section 4, Results). Its quote result is information for the owner deciding whether to approve it.
10. **The number boundary.** A full stop is not a word character, so without it `Version 2.` would be found in `Version 2.5`, and a quote would be verified by a figure the source does not state.

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

**List L2** (tab-separated; invented), saved in the working folder with its sources under it: `evidence/offer.txt` holds `Dana Example will lead a group of six engineers at Example Corp. Ref 555-0199.`, `evidence/review.txt` holds `Dana Example cut build times by a third. Ref 555-0199.`, and `evidence` is the folder that holds them.

```text
# invented list L2
approved	Led a team of six engineers at Example Corp.	evidence/offer.txt
quote	will lead a group of six engineers
approved	Shipped the Example importer in 2021.	evidence/offer.txt
proposed	Cut build times by forty percent.	evidence/review.txt
quote	cut the build time in half
refused	Increased revenue tenfold.	evidence
quote	revenue grew tenfold
```

Every run below uses `--list L2 --control "example" --check-sources` and the input file `Led a team of six engineers at Example Corp.` unless it says otherwise. "OK" is that file's line, `OK    <label>: 1 sentences, all approved (control found)`. The added lines in 9.21 to 9.27 are each two lines, an entry line and its quote line, appended to L2.

| # | Run | Expected |
|---|---|---|
| 9.20 | L2 | OK; `proposed, entry #3: quote not found`; `quotes, approved: 1 found, 0 not found, 0 unreadable, 0 unverified`; `quotes, proposed: 0 found, 1 not found, 0 unreadable, 0 unverified`; exit 0. Entry #1's quote is found and prints no line; entry #2 has a source and no quote and is not counted; refused entry #4 is not checked |
| 9.21 | L2 with `approved	Joined Example Corp. in 2019.	evidence/offer.txt` and `quote	hired forty interns` | OK; entry #3's line; `approved, entry #5: quote not found`; counts approved 1, 1, 0, 0 and proposed 0, 1, 0, 0; exit 1 |
| 9.22 | L2 with `approved	Joined Example Corp. in 2019.	evidence` and `quote	joined the team` | OK; entry #3's line; `approved, entry #5: source unreadable (not a regular file)`; counts approved 1, 0, 1, 0; exit 2 |
| 9.23 | L2 with `approved	Joined Example Corp. in 2019.	https://example.com/records/1` and `quote	joined the team` | OK; entry #3's line; `approved, entry #5: source unverified`; counts approved 1, 0, 0, 1; exit 0 |
| 9.24 | L2 with `proposed	Joined Example Corp. in 2019.	evidence` and `quote	joined the team`, then `proposed	Built an end-to-end import pipeline.	REC-0042` and `quote	built the pipeline` | OK; entry #3's line; `proposed, entry #5: source unreadable (not a regular file)`; `proposed, entry #6: source unverified`; counts approved 1, 0, 0, 0 and proposed 0, 1, 1, 1; exit 0 |
| 9.25 | L2 saved as `lists/L2` with its sources under `lists/evidence/`, given as `--list lists/L2`; the working folder's `evidence/offer.txt` holds other text, without entry #1's quote | the output of 9.20, exit 0: each source is read beside the list. The same with entry #1's source an absolute path to `lists/evidence/offer.txt` |
| 9.26 | (a) 9.22's list with 9.3's file; (b) 9.21's list with `--control "zebra"`; (c) 9.21's list with `proposed	Built an end-to-end import pipeline.	evidence` and `quote	built the pipeline` | (a) the FAIL lines, entry #3's line, entry #5 unreadable, the counts; exit 2. (b) `DEAD  <label>: control not found`, entry #3's line, entry #5 not found, the counts; exit 2. (c) OK, entry #3's line, entry #5 not found, `proposed, entry #6: source unreadable (not a regular file)`, the counts; exit 1 |
| 9.27 | 9.21's list with `--stale-check`; then the same with `--control "zebra"` | OK, `stale entry #2`, `stale entry #5`, entry #3's line, entry #5's line, the two count lines, in that order; exit 1. With the DEAD file: the DEAD line, no stale line, entry #3's and entry #5's lines and the counts; exit 2 |
| 9.28 | L2 with a first line `quote	will lead a group`; L2 with a last line `quote	a second quote`; L2 with `approved	Joined Example Corp. in 2019.` and `quote	joined the team`; L2 with `approved	Joined Example Corp. in 2019.	evidence/offer.txt` and a line `quote` alone | cannot run, in turn: `a quote line comes before the first entry`; `entry #4 has two quote lines`; `entry #5 has a quote but no source`; `entry #5 has an empty quote`. Nothing on standard output; exit 2; the same without `--check-sources` |
| 9.29 | L2 with the input file `Led a team of six engineers at Example Corp. Cut build times by forty percent.` | FAIL, 1 of 2: line 1, `proposed, entry #3` (a quote line takes no number); entry #3's line; the counts; exit 1 |
| 9.30 | L2 with its first quote line's first field written ` QUOTE ` (in capitals, with spaces) and, after the quote, a tab and `invented quote note` | the output of 9.20, exit 0; the note is never printed |
| 9.31 | L1 with 9.1's file | OK, 2 sentences; `quotes, approved: 0 found, 0 not found, 0 unreadable, 0 unverified`; `quotes, proposed: 0 found, 0 not found, 0 unreadable, 0 unverified`; exit 0 |
| 9.32 | 9.20 with `--check-sources` given twice; `--check-sources=1`; `--control --check-sources`; `--help` alongside `--check-sources` | the output of 9.20; `cannot run: unknown option --check-sources=1`; `cannot run: --control needs a value`; the summary of 3.4, exit 0 |
| 9.33 | the output of 9.20 to 9.32, and of runs with sources that are not UTF-8, a dangling symbolic link and PDFs | contains no quote, no source field, no resolved source path, no text written only inside a source, no note and not the list's path |
| 9.34 | 9.1 to 9.13 without `--check-sources`, with L1 and with L1 plus a quote line under each entry that has a source | the same standard output, standard error and exit status |
| 9.35 | L2 with `approved	Joined Example Corp. in 2019.	locked/in.txt` and `quote	joined the team`, where `locked` is a folder beside the list at mode 000 and `locked/in.txt` is a file holding the quote; then the same entry as `proposed` | OK; entry #3's line; `approved, entry #5: source unreadable (cannot read)`; counts approved 1, 0, 1, 0; exit 2. As proposed: OK; entry #3's line; `proposed, entry #5: source unreadable (cannot read)`; counts approved 1, 0, 0, 0 and proposed 0, 1, 1, 0; exit 0. The case does not apply when the run has the privileges to read through mode 000 |
| 9.36 | L2 with `approved	Joined Example Corp. in 2019.	<source>` and `quote	joined the team`, where `<source>` is a URL-like string longer than 4096 characters: `https://example.com/records/` followed by `part/` 900 times | OK; entry #3's line; `approved, entry #5: source unverified`; counts approved 1, 0, 0, 1; exit 0. The source is longer than any path the system allows, so no file can have that name |

## 10. Command line (cli.md, Revision 5)

cli.md revision 3 added `<cli> claims`: section 2 adds `<cli> claims`, run under this spec. Section 4's help list gains a fifth line, after `ab`:

- claims: fail on sentences your claims list hasn't approved

and section 4's list of levels where `-h` and `--help` are accepted adds `<cli> claims`. Section 5 adds claims to the commands that promise fixed help text (this spec, section 3.4).

cli.md revision 5 notes the quote check: section 2 ends with a sentence saying `claims` takes `--check-sources`, which also checks each quote in the claims list against the source its entry cites, and section 5 says that claims' summary lists `--check-sources` from this spec's revision 2. Section 4's help line for claims does not change. Nothing else in cli.md changes.
<!-- draft spec ends -->

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
