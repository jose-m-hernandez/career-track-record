# `track-record absence`: behaviour spec

Status: accepted.
Date: 2026-11-20.
Revision: 2. The public edition (sha256 9cd89599…) is reproduced below verbatim. It is revision 1's signed text (sha256 b744868a…) with the two sentences its own Revision line names, both ruled by the method owner on 2026-11-20 as readings of revision 1. The whole of this file before this revision has sha256 36065912d97c9e0217e07148e307f9fb9f66cdc9851c285408646fe525f9534c.

## Signed spec

<!-- signed spec begins: sha256 9cd89599f133ac4a9c0449638cfed7c2ddb51ec6f49b2e1e6337e5b4206b159c -->
# Absence search: behaviour spec

Status: revision 1, drafted on 2026-11-14 for the owner's signature. This design follows the method owner's written answers of 2026-11-14 about proving that a term is absent from a set of files.
Date: 2026-11-14.
Revision: 2. Clarifies section 3.3 and the Privacy rule, each by one sentence, as readings of revision 1; no behaviour changes.

The command is `<cli> absence`.

Every example in this file and in the tool's fixtures is invented. None of it comes from a real person's records, lists, employers or claims.

## 1. Purpose

Some claims are claims of absence: a term appears nowhere in a set of files. A search that finds nothing proves that only if it could see the place where the term would be, read every file it was given, and says which files it left out. This command proves that a term is absent from a set of files, and shows the evidence for each of those three conditions.

Its purpose differs from `barred`'s. `barred` checks that files hold no listed wording. This command proves an absence and reports how it looked. It follows rule 6 of the method ("Test before you trust"): a search that finds nothing must show it was looking.

## 2. Scope

In:
- one declaration file, in the plan-file syntax, naming everything the run depends on; the output prints its sha256, so an absence claim can cite it (section 3.1);
- the terms to search for: one list file in barred's format, read exactly as barred reads it, with entry numbers, the `word` flag and the canary. Output names a term by its entry number only (section 3.2);
- a search set of files and folders, searched recursively (section 3.3);
- each file's name, searched as well as its text (section 4);
- the place where the fact would live: a file or a folder inside the search set, with a control phrase that must be found there (section 3.4);
- stated exclusions, each with a reason (section 3.5);
- folding and matching exactly as barred.md section 4 does, in the forms barred.md gives each file and each file name (section 4);
- a count of every file found, which must reconcile (section 5).

Out:
- section-level locations inside a file: too fragile;
- printing a term, any matched text or the control phrase;
- following symbolic links;
- fetching anything over the network.

This spec reuses barred.md's folding and matching forms. It is signed after barred revisions 7.1 and 8 are settled, so that it names the forms they leave.

## 3. Inputs

### 3.0 Options

| Option | Meaning |
|---|---|
| `DECLARATION` | The declaration file. Exactly one is required. |
| `-h`, `--help` | Write the fixed summary of section 3.6 to standard output and exit `0`. It reads no file, and wins over every other argument; after `--`, every argument is a file name. |

`-` alone is a file name, not standard input. The command is run as `<cli> absence DECLARATION`.

### 3.1 The declaration

- UTF-8 text. A byte-order mark at the very start is dropped. It uses the plan-file syntax of reader-ab.md section 3.1, as record-check.md section 3.1 reads it: each line is `key: value`; a list value is one item per indented line under its key; blank lines and lines starting with `#` are ignored; an unknown or repeated key is a problem. An item is fields separated by ` | `, each field trimmed, and an empty field is a problem.
- Paths in the declaration are relative to the declaration's folder. A path may also be absolute, or climb out of that folder with `..`; it is opened as written. Output prints each path as the declaration writes it, and a file found inside a folder as the folder's path, `/`, then the file's path inside it.

| Key | Value or item | Meaning |
|---|---|---|
| `label` | a name | The run's name in the output: letters, digits and `-` only. Required. |
| `list` | a path | The list file (section 3.2). Optional. |
| `search` | `path` | A file or a folder in the search set. Required: at least one item. |
| `place` | a path | Where the fact would live: a file or a folder (section 3.4). Required. |
| `control` | text | The control phrase (section 3.4). Required. |
| `exclusions` | `path \| reason` | A path inside the search set, and why it is excluded, one line of free text. The reason is required. Optional key. |

The control phrase and the exclusions live in the declaration so that one hashed file holds what was searched, where the fact would live, the control and what was left out, and so that the control phrase stays out of the shell history.

### 3.2 The list

The list file is read exactly as barred.md section 3.1 reads it: entries numbered from 1 in file order, the `word` flag, notes never matched or printed, and the canary as entry 1. When the declaration has no `list` key, the list is the file named by the environment variable `BARRED_STRINGS_PATH`, as barred.md section 3.0 says; an unset or empty variable counts as absent. Output names a term only by its entry number.

### 3.3 The search set

- Each `search` item is a file or a folder. A folder is searched recursively. Every file and symbolic link met is **found**; a file reached through two `search` items is found once.
- Hidden files and folders, whose names start with `.`, are read like any other. A search that skipped them would have a blind spot.
- Symbolic links are not followed. Each link met, given as a `search` item or found in a folder, inside an exclusion or not, is counted as a **link not followed**, and is neither read nor unreadable. Every component of a path is checked as the declaration writes it, and if any component is a symbolic link, including a system link such as `/tmp` on macOS, the item is counted once as a link not followed and is not read; to search it, write the resolved path.
- Files are read as barred.md section 3.2 reads input files: a PDF through `pdftotext`, in its default text and its layout text, and any other file as UTF-8, each invalid byte sequence replaced. A file that is not a PDF is read as text and counted as read, whatever it holds. There is no `--strip-comments`: every file is read whole. barred's minimum length and its control on each file do not apply here; this command's one control is at the place (section 3.4).
- A file is **unreadable** when it could not be opened or read, or it is a PDF that could not be converted: `pdftotext` is missing or fails on either of its two reads (barred.md section 7, case 6). A `search` item that does not exist is one file found and unreadable. An unreadable file makes the run DEAD (section 5), unless it lies inside an exclusion, where it is counted as excluded and not read.
- **Known limit: files that are not text.** The search cannot see words inside a file that is not text, such as an image or an archive, although the file counts as read. Its name is still searched (section 4).
- Paths are taken in the order of the `search` items, and inside a folder in code-point order of their paths inside it. That order numbers every path found, links included, from 1, for the label `file #<i>` (section 6).
- **Inside the search set** means: the path is a `search` item, or lies under a `search` folder. Paths are compared as written, after `.` and `..` parts are resolved; no link is followed to compare them.

### 3.4 Where the fact would live

- `place` is a file or a folder, and `control` is a phrase that must be found there. The control proves that the search could see the place the fact would live.
- The place must lie inside the search set. Searching it in addition would let a wrongly drawn search set pass.
- The control phrase is prepared and matched with the same folding and matching as the terms (section 4), as an entry without the `word` flag, so the control tests the instrument that does the search. A file place holds the control when the phrase matches in it; a folder place holds it when at least one file read inside it does.
- The control phrase is never printed.
- A term that matches the control phrase would always be found at the place, so the run cannot go ahead (section 7), and the message gives the term's entry number. A term matches the control phrase when, prepared, it matches inside the prepared phrase under section 4's rules, `word` flag included.

### 3.5 Exclusions

Each exclusion is a path inside the search set, with a reason. A readable file inside an excluded path is read and its hits are counted, but they are not hits of the run: they are shown as a number per excluded path, never as matched text. A file inside an excluded path that cannot be read is counted as excluded and not read, and does not make the run DEAD. So an exclusion is not a blind spot: the output says how much it hid and how much of it was not read. The reason is required and is never printed: it is free text, and could carry a term. The printed declaration hash makes it citable. The closing line names every exclusion.

### 3.6 The help summary

`<cli> absence --help` writes exactly this, followed by a line break:

```text
usage: track-record absence DECLARATION

Show that your listed terms appear nowhere in the files you declare.

  -h, --help  show this summary and exit

exit: 0 clean, 1 a term found, 2 DEAD or cannot run
```

## 4. Folding and matching

As barred.md section 4: the same folding, the same matching rules and the same `word` flag, in the forms that barred.md gives each file. A term's count in a file is the largest of its counts in those forms.

**File names.** A term in a file's name is an appearance of the term, so names are searched as barred.md section 6 checks a file's name. Every path found, a file or a symbolic link, inside an exclusion or not, is checked: its path as section 3.1 writes it matches an entry when it matches, under the rules above, `word` flag included, in any of the forms that barred.md gives each file name, or when its printed path (section 6), folded, matches. Each entry that matches a path's name adds one hit to that path.

A path's hit count is the sum of its terms' counts in its text and its name hits. A link has name hits only, since it is never read.

## 5. The reconciliation, and DEAD

Every run accounts for every file it found, in four buckets that do not overlap:

- **read**: files outside every exclusion that were read;
- **excluded**: files inside an exclusion, read or not;
- **unreadable**: files outside every exclusion that could not be read;
- **links not followed**: every symbolic link met.

Found must equal read plus excluded plus unreadable plus links not followed. The counts are checked before any line is written. Counts that disagree mean the tool, or the files under it, changed during the run: that is not a check that looked at nothing, so it is not DEAD, and the run cannot go ahead (section 7).

A run is DEAD when, in this order, the first that applies:

1. the search set holds no file other than links (`no file in the search set`);
2. the place is not inside the search set (`the place is not in the search set`);
3. the place lies inside an exclusion (`the place is inside an exclusion`);
4. any file is unreadable (`<u> unreadable files`);
5. the control phrase is not found at the place, which for a folder means no file read inside it holds the phrase (`control not found at the place`).

## 6. Output and exit status

Every run that can go ahead writes, in this order:

1. `declaration sha256 <hex>`, the sha256 of the declaration file's bytes;
2. one line per exclusion, in declaration order: `excluded <path>: <h> hits in <f> files, <u> not read`, where `<f>` counts the files inside it and `<u>` those that could not be read;
3. for a run that finds a hit outside the exclusions, one line per path holding one, a file or a link, in file order: `hit <path>: <c> hits, entries #<N>, #<M>`, the entry numbers in list order, separated by `, `;
4. the reconciliation line, on every run, clean or not: `files: found <F>, read <R>, excluded <E>, unreadable <U>, links not followed <L>`;
5. one closing line:
   - `CLEAN  <label>: 0 hits in <n> files, <l> links not followed, control found; excluding <paths>`;
   - `FOUND  <label>: <h> hits in <n> files, <k> with hits, <l> links not followed, control found; excluding <paths>`, when any hit is found outside the exclusions;
   - `DEAD   <label>: <reason>`, with the reason of section 5.

`<n>` is the number of files read; `<h>` is the sum of the hit counts of the files read and the links outside every exclusion; `<k>` is the number of those paths with a hit. An exclusion's `<h>` counts the hits of every path inside it, names included. With no exclusions, the CLEAN and FOUND lines end at `control found`. A DEAD run writes the declaration line, the reconciliation line and the DEAD line only: a search that could not see proves nothing, and its hits are not reported. Counts are printed as numbers, `0` included.

`<label>` is the declaration's `label`. `<paths>` lists the exclusions in declaration order, separated by `, `. Every printed path is escaped as barred.md section 6 escapes printed paths, and a comma in a path is escaped too, as `\x2c`, so that the list can be split at `, ` without doubt. A path whose name matches an entry (section 4) is printed as `file #<i>`, where `<i>` is its number in file order (section 3.3), never by its name, and an exclusion whose path matches an entry the same way is printed as `exclusion #<i>`, where `<i>` is its position among the exclusions. So no printed path can show an entry.

**Privacy.** Output never contains a term, any matched text, the control phrase, an exclusion's reason, the list's path or a path whose name matches an entry. Hits are shown as numbers only. The fixed words of the output format are not taken from any input; a term or control phrase that coincides with them is not printed by the run.

**Exit status:** `0` for CLEAN; `1` for FOUND; `2` when the run is DEAD or cannot go ahead. The highest applies.

## 7. When it cannot run

The run exits `2`, writes nothing to standard output, and writes `cannot run: <reason>` lines to standard error, without printing a term, the control phrase or the list's path, when:

- no DECLARATION is named, or more than one (`absence needs a DECLARATION file`, `absence takes one DECLARATION file, not several`); or an option is unknown (`unknown option <option>`);
- the declaration is not a regular file or cannot be read (`cannot read the declaration`), or is not UTF-8 (`the declaration is not valid UTF-8`). The declaration's name is not printed: the list has not been read yet, so the name could not be checked against it;
- the declaration has problems, one line each (`declaration line <n>: <problem>`): a `label` with a character other than a letter, a digit or `-`; an exclusion with no reason; an exclusion that is not inside the search set; or a required key that is missing (`the declaration has no <key>`);
- the list cannot be used, for any reason barred.md section 7, case 3 gives, with barred's message;
- the control phrase is empty once prepared (`the control phrase is empty`);
- a term matches the control phrase (`entry #<N> matches the control phrase`), or the label matches an entry (`the label matches entry #<N>`);
- the files do not reconcile (section 5): `the files do not reconcile: found <F>, read <R>, excluded <E>, unreadable <U>, links not followed <L>`.

When the output cannot be written, it follows cli.md section 4: exit `2`, one line `cannot run: cannot write output`, and no traceback. The run never shows a traceback.

## 8. Decisions, with reasons

1. **A new command, not `barred` flags.** Its purpose differs: it proves an absence. It reuses `barred`'s folding and matching, so one list means the same to both.
2. **A path plus a control phrase**, because a section-level location is too fragile.
3. **Hits in exclusions are counted, never shown.** An exclusion is not a blind spot: the user sees how much it hid.
4. **The files reconcile**, so a file that was found but not read cannot hide.
5. **One declaration file.** An absence claim is cited later, so what was searched, where the fact would live, the control phrase and the exclusions belong in one file that can be hashed. The output prints that hash.
6. **Hidden files are read; links are not followed.** A search that skips hidden files has a blind spot. A link is counted in its own bucket, so the user sees it was not followed.
7. **The place must lie inside the search set.** Searching it in addition would let a wrongly drawn search set pass.
8. **An exclusion carries a reason, never printed.** The reason is free text and could carry a term; the declaration's hash makes it citable.
9. **A failed reconciliation is a cannot-run error, not DEAD.** DEAD means a check that looked at nothing; counts that disagree mean the tool or the files changed under it.
10. **The control is matched as the terms are, and never printed.** So the control tests the instrument that does the search. A term that matches the control would always be found at the place, so it stops the run.
11. **File names are searched.** A term in a file's name is an appearance of the term, and an absence proof that skips names has a blind spot. A file whose name matches is shown by its number, never by its name.
12. **Files that are not text are read as text.** The reader reads any file that is not a PDF as text, so an image is read, not refused, and counts as read. What it cannot see inside such a file is a stated limit (section 3.3).

## 9. Known answers

The fixtures are invented. Every line of every fixture ends with LF. `→` stands for a tab.

The list, `terms.txt`:

```text
# an invented list
orbit-lantern
velvet compass
quill→word
lanternfish
```

The declaration, `absence.txt` (sha256 `d0fd170273c50a854e05eac8261ba2fd2a66c506dddbd7121a323648fcdb373a`):

```text
# an invented declaration
label: no-vendor-terms
list: terms.txt
search:
  notes
  summary.txt
place: notes/vendors.txt
control: approved vendors
```

The files: `notes/vendors.txt` holds `Approved vendors: Example Corp and Sample Ltd.`; `notes/plan.txt` holds `The team sharpened its quills before the review.`; `summary.txt` holds `A quarterly summary of invented work.` Each case below changes only what it names, and a changed declaration prints its own sha256 on the first line.

- **9.1 Clean.** `<cli> absence absence.txt` writes the lines below and exits `0`. `quills` is not a hit, because entry 3 carries the `word` flag. With `place: notes` the output is the same apart from the hash line.

```text
declaration sha256 d0fd170273c50a854e05eac8261ba2fd2a66c506dddbd7121a323648fcdb373a
files: found 3, read 3, excluded 0, unreadable 0, links not followed 0
CLEAN  no-vendor-terms: 0 hits in 3 files, 0 links not followed, control found
```

- **9.2 An excluded folder.** `notes/archive/old.txt` holds two lines, `velvet compass` and `Velvet  compass`, and the declaration gains `exclusions:` with the item `notes/archive | drafts kept for the record`. Exit `0`:

```text
declaration sha256 <its sha256>
excluded notes/archive: 2 hits in 1 files, 0 not read
files: found 4, read 3, excluded 1, unreadable 0, links not followed 0
CLEAN  no-vendor-terms: 0 hits in 3 files, 0 links not followed, control found; excluding notes/archive
```

  Without the exclusion, the run finds the hits. Exit `1`:

```text
declaration sha256 d0fd170273c50a854e05eac8261ba2fd2a66c506dddbd7121a323648fcdb373a
hit notes/archive/old.txt: 2 hits, entries #2
files: found 4, read 4, excluded 0, unreadable 0, links not followed 0
FOUND  no-vendor-terms: 2 hits in 4 files, 1 with hits, 0 links not followed, control found
```

- **9.3 The control is missing.** `notes/vendors.txt` holds `Vendors we use: Example Corp.` The run writes `files: found 3, read 3, excluded 0, unreadable 0, links not followed 0` and `DEAD   no-vendor-terms: control not found at the place`, and exits `2`. With `place: notes`, the same: no file in the folder holds the phrase.
- **9.4 The place outside the search set.** With `summary.txt` as the only `search` item: `files: found 1, read 1, excluded 0, unreadable 0, links not followed 0` and `DEAD   no-vendor-terms: the place is not in the search set`. Exit `2`.
- **9.5 The place inside an exclusion.** With the exclusion `notes | everything under notes`: `files: found 3, read 1, excluded 2, unreadable 0, links not followed 0` and `DEAD   no-vendor-terms: the place is inside an exclusion`. Exit `2`.
- **9.6 An unreadable file.** `notes/broken.pdf` is a text file named as a PDF, on which `pdftotext` fails: `files: found 4, read 3, excluded 0, unreadable 1, links not followed 0` and `DEAD   no-vendor-terms: 1 unreadable files`. Exit `2`. With the exclusion `notes/broken.pdf | a scan with no text layer`, it is listed, not DEAD. Exit `0`:

```text
declaration sha256 <its sha256>
excluded notes/broken.pdf: 0 hits in 1 files, 1 not read
files: found 4, read 3, excluded 1, unreadable 0, links not followed 0
CLEAN  no-vendor-terms: 0 hits in 3 files, 0 links not followed, control found; excluding notes/broken.pdf
```

- **9.7 A hidden file.** `notes/.draft.txt` holds `a velvet compass`: `hit notes/.draft.txt: 1 hits, entries #2`, `files: found 4, read 4, excluded 0, unreadable 0, links not followed 0` and `FOUND  no-vendor-terms: 1 hits in 4 files, 1 with hits, 0 links not followed, control found`. Exit `1`.
- **9.8 A symbolic link.** `notes/link.txt` is a symbolic link to `../summary.txt`: `files: found 4, read 3, excluded 0, unreadable 0, links not followed 1` and `CLEAN  no-vendor-terms: 0 hits in 3 files, 1 links not followed, control found`. Exit `0`.
- **9.9 Line-end hyphens.** `summary.txt` holds three lines, `the orbit-`, `lantern and the lantern-` and `fish`. Entry 1 matches in the hyphen-kept form and entry 4 in the rejoined form, as in barred.md 10.1 and 10.9: `hit summary.txt: 2 hits, entries #1, #4`, and `FOUND  no-vendor-terms: 2 hits in 3 files, 1 with hits, 0 links not followed, control found`. Exit `1`.
- **9.10 A term in a file's name.** `notes/velvet compass.txt` holds `nothing to see`. Its name matches entry 2, and it is shown by its number, 2 in file order (`notes/plan.txt`, `notes/velvet compass.txt`, `notes/vendors.txt`, `summary.txt`). Exit `1`:

```text
declaration sha256 d0fd170273c50a854e05eac8261ba2fd2a66c506dddbd7121a323648fcdb373a
hit file #2: 1 hits, entries #2
files: found 4, read 4, excluded 0, unreadable 0, links not followed 0
FOUND  no-vendor-terms: 1 hits in 4 files, 1 with hits, 0 links not followed, control found
```

- **9.11 A term in a link's name.** `notes/lanternfish.txt` is a symbolic link to `../summary.txt`, first in file order: `hit file #1: 1 hits, entries #4`, `files: found 4, read 3, excluded 0, unreadable 0, links not followed 1` and `FOUND  no-vendor-terms: 1 hits in 3 files, 1 with hits, 1 links not followed, control found`. Exit `1`.
- **9.12 A comma in a path.** 9.2's run, with a folder `notes/drafts, old` holding `old.txt` (`nothing here`) and the second exclusion item `notes/drafts, old | kept apart`. Exit `0`:

```text
declaration sha256 <its sha256>
excluded notes/archive: 2 hits in 1 files, 0 not read
excluded notes/drafts\x2c old: 0 hits in 1 files, 0 not read
files: found 5, read 3, excluded 2, unreadable 0, links not followed 0
CLEAN  no-vendor-terms: 0 hits in 3 files, 0 links not followed, control found; excluding notes/archive, notes/drafts\x2c old
```

- **9.13 A file that is not text.** `notes/logo.png` is an invented image, the eight-byte PNG signature followed by bytes that hold no entry: it is read and counted, `files: found 4, read 4, excluded 0, unreadable 0, links not followed 0`, and the run is CLEAN with `0 hits in 4 files`. Exit `0`.
- **9.14 A term that matches the control.** `terms.txt` gains a fifth entry, `vendors`: the run writes nothing to standard output and `cannot run: entry #5 matches the control phrase` to standard error, and exits `2`. With `label: quill-check` and the list unchanged, it writes `cannot run: the label matches entry #3`: the `-` after `quill` is a boundary character.
- **9.15 Declaration problems.** An exclusion with no reason, an exclusion outside the search set, a `label` holding a space, and a declaration with no `control` each exit `2` with one `cannot run: declaration line <n>: …` line, or `cannot run: the declaration has no control`, and nothing on standard output.
- **9.16 Counts that disagree.** A test that makes the tool's own counts disagree gets `cannot run: the files do not reconcile: found 3, read 2, excluded 0, unreadable 0, links not followed 0` and exit `2`, with nothing on standard output.
- **9.17 Nothing private is printed.** Over every case above, neither standard output nor standard error holds any entry, any matched text, the control phrase, an exclusion's reason, the list's path, or the path of 9.10 or 9.11 (barred.md 10.8 style).
- **9.18 Output that cannot be written.** Closed standard output, and a broken pipe, each exit `2` with `cannot run: cannot write output`; a closed standard error changes no exit status.
- **9.19 Help.** `-h` and `--help` write section 3.6's summary, byte for byte, and exit `0`, reading no file.
- **9.20 A line-end soft hyphen in a text file.** `summary.txt` holds two lines: `the lantern` followed by a soft hyphen (U+00AD), and `fish shop`. barred.md gives a text file its text after the soft-hyphen rule, in which that soft hyphen, last on its line after a word character, becomes a hyphen-minus, so the rejoined form holds `lanternfish`: `hit summary.txt: 1 hits, entries #4`, `files: found 3, read 3, excluded 0, unreadable 0, links not followed 0` and `FOUND  no-vendor-terms: 1 hits in 3 files, 1 with hits, 0 links not followed, control found`. Exit `1`. Without that rule, folding removes the soft hyphen, and no form holds the entry.
- **9.21 Two entries in one name.** `notes/velvet compass lanternfish.txt` holds `nothing to see`. Its name matches entries 2 and 4, one hit each: `hit file #2: 2 hits, entries #2, #4`, and `FOUND  no-vendor-terms: 2 hits in 4 files, 1 with hits, 0 links not followed, control found`. Exit `1`. A name that holds one entry twice, `notes/velvet compass velvet compass.txt`, gives `hit file #2: 1 hits, entries #2`.

## 10. Command line (cli.md, Revision 7)

cli.md revision 7 adds `<cli> absence` to sections 1, 2, 4 and 5: it names absence.md among the commands' specs, runs `<cli> absence DECLARATION` under it, lists it with the one-line description `absence: show that your listed terms appear nowhere in the files you declare`, so `<cli> --help` lists eight commands, and lists `absence` among the commands whose fixed help text is stated in their own spec.
<!-- signed spec ends -->
