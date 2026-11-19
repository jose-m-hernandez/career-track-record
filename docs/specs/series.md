# Series file: behaviour spec

Date: 2026-11-18.
Revision: 1. The public edition of the signed spec (signed by the method owner; text sha256 aca76ec47091352ab291613a861e0efaacffcf0e00a562cc19639da400a8a037) is reproduced below verbatim. It is a new spec and adds the keys `series` and `series-note`; it does not change `reader-ab.md` revision 4.

In the signed text, `tie-spec-r1.7.md` is this repository's `docs/specs/reader-ab-aa-band.md`, and `series-row-spec-r1.md` is `docs/specs/series.md`.

## Signed spec

<!-- signed spec begins: sha256 aca76ec47091352ab291613a861e0efaacffcf0e00a562cc19639da400a8a037 -->
# Series file: behaviour spec (draft r1.4)

Base: `career-track-record` at `cc6b1c9`. Every `reader-ab.md:N`, `drafts.md:N`, `record-check.md:N` and `reader-panel.md:N` is a line of the file of that name in `docs/specs/` at `cc6b1c9`; `ab.py:N`, `reader_harness.py:N`, `record_check.py:N` and `keywords.py:N` are lines of `src/career_track_record/` at `cc6b1c9`.
Date: 2026-11-17.
Revision: 1.6. If merged into the repo it is a new file, `docs/specs/series.md`, and `reader-ab.md` gains the two plan keys of section 4 and the exit cause of section 8 as revision 5 (the same revision as `tie-spec-r1.7.md`).

**Verdict changes: none.** (The TIE spec's key `aa-band` is separate; a series row only records the verdict words a result gives.) No existing plan's verdict, prompt or read changes. A plan with no `series` key behaves byte for byte as it does at `cc6b1c9` and touches no series file. A plan with a `series` key gains the refusals of section 6 (exit `2`), one more line of output (section 5) and one write to the series file; it gains no other effect on its verdicts.

Every example in this file is invented. None comes from a real person's résumés, postings, employers, prompts or results.

## 1. Purpose

A tailored draft is a descendant of another draft, read by `ab` against its parent. The series (which draft came from which, what each was read against, and what the round said) lives today in a person's head or in a hand-kept note. This spec adds one file per series of drafts, with one row per draft, written by `ab` when it scores the round that admits a draft and added to when a follow-up round of that draft is scored, and checked by `record`, the checker that already ships.

It follows rule 1 of the method ("Never overwrite") as far as the rulings allow: a row is appended once, never removed or reordered (the lock of section 5 is what keeps that true when two commands write at once), and the only change ever made to a row is that its `result` cell grows by one item at its end; every other byte of the file stays as it was (section 5; the consequence for `record`'s `earlier` check is in section 7). It follows rule 6 ("Test before you trust"): every row the tool writes is a row `record` accepts, and the tool refuses to write one it would fault.

## 2. Scope

In:
- the series file: one TSV per series, its columns and its rules (section 3);
- two optional plan keys of `ab` that name the file and say what to write (section 4);
- the row's admission and the growth of its `result` cell, once per frozen plan, when a result is written (section 5);
- the checks before any read and before any result (section 6);
- a `record` declaration that checks the file (section 7).

Out:
- `panel`. A panel plan names one `version` and no parent (`reader-panel.md:54-55`), and the signed panel spec puts "version ledgers" out of scope (`reader-panel.md:43`). Panel rows wait for the panel revision of the same release (ruled: `ab` only in r1);
- the `drafts` file (`drafts.md`), which keeps versions with their text, parents and result entries by hand and which the tool never writes (`drafts.md:35`). The series file does not replace it and no command compares the two (ruled: both are kept in r1);
- creating the series file: a person writes its header and its first rows by hand (section 3);
- editing any cell of a row but `result`, removing, reordering or "repairing" any row, ever;
- a new command, a new option or a change to `record`.

## 3. The file

UTF-8 text, no byte-order mark, LF line breaks only (a CR anywhere is refused), tab-separated, no quoting, no comment lines, no blank lines. The first line is the header, exactly:

```text
draft	parent	file_sha256	posting_sha256	round	plan_sha256	result	date	note
```

Every later line has exactly nine fields, so a row with empty cells at its end still ends with its tabs. The file ends with a line break. A cell that is empty is empty: no spaces. Each row:

| Column | Holds |
|---|---|
| `draft` | The draft's id: letters, digits and `-` (the names rule of the plan, `reader-ab.md:449`), not empty, unique in the file, compared exactly. |
| `parent` | Empty for a root (a draft that did not come from another, such as the starting résumé, or a rewrite from scratch, as `drafts.md:109` allows). Otherwise the `draft` of exactly one **earlier** row. |
| `file_sha256` | 64 lowercase hexadecimal digits: the sha256 of **what the comparison read** of the draft's file. For a file whose name ends in `.pdf`, compared case-insensitively as `ab` does (`reader_harness.py:672`), that is the UTF-8 bytes of the text `pdftotext FILE -` gives, the text the readers saw (`reader_harness.py:665-678`, `pdf_text.py:19-30`, the review spec's rule that a PDF draft's copy is its extracted text); for any other file it is the file's bytes, which `ab freeze` hashes (`reader_harness.py:431-443`). Required. For a text file that `drafts extract` wrote, this equals that version's `sha256:` (`drafts.md:110-112`). |
| `posting_sha256` | 64 lowercase hex digits for the posting the round read; empty exactly when `round` is empty (a draft that was never read). |
| `round` | Empty for a draft that was never read. Otherwise the run folder of the round that admitted the draft, as a relative path, written with `/`, with no segment equal to `.` or `..`, no empty segment, no leading or trailing `/`, no `;`, no `@` and no control character (Unicode category Cc, tab, CR and LF included), and below the folder that holds the series file (never that folder itself). It is the plan's folder (`reader-ab.md:83`). |
| `plan_sha256` | Empty for a draft that was never read, otherwise 64 lowercase hex digits: the sha256 of the plan file of the admitting round, the one the freeze recorded (`reader_harness.py:443`). `round` and `plan_sha256` are both empty or both filled in a row the tool writes. |
| `result` | Empty for a draft that was never read, otherwise a list of items in run order, one per round of this draft: the admitting round first, then each extension, amendment or replicate (section 5). No tab, CR or LF. The only cell of a row that ever changes. |
| `date` | A real date, `YYYY-MM-DD`: the UTC day the row was written, that is, the day the draft was admitted (section 5). Follow-up rounds do not change it. Required. |
| `note` | One line of the person's words, or empty. No tab, CR or LF. The tool writes the plan's `series-note` here and checks nothing else about it. |

Invented example (tabs shown as spaces; `…` shortens the hashes of the first three columns and `<plan64>` stands for a 64-digit digest; the empty cells are really empty). A row's `result` cell is a list of items in the grammar of section 5, so even a single round is written `<round>@<plan64>: <verdicts>`:

```text
draft    parent    file_sha256  posting_sha256  round  plan_sha256  result                                           date        note
base               3f…                                                                                            2026-11-15  the one you start from
labs-v1  base      9a…          c2…             r1     <plan64>     r1@<plan64>: h1 SUPPORTED                        2026-11-15  tailored to the data posting
labs-v2  labs-v1   1b…          c2…             r2     <plan64>     r2@<plan64>: h1 TIE                              2026-11-16  shorter summary
```

(In each row the digest in `plan_sha256` is the one in the item's `@<plan64>`; check 1 refuses a row where they differ. Abbreviated hashes, here and in the cases, are for reading only: a file never holds one.)

A person adds a row for a draft that was never read, and the root, by hand, at the end of the file. The tool never creates the file: it must exist, with its header and the parent's row, before a plan that names it can freeze. **Layout recommendation, not a rule the tool enforces:** the setup layout has a `plans/` folder for frozen plans, and the guide suggests the file lives there, as `plans/<name>.series.tsv`, with each run folder a subfolder of `plans/`. The tool checks only what section 6 says: that the plan's folder lies strictly below the series file's folder.

**Known limits.** The tool cannot check that a hand-written row's hashes describe the file it names, only that they are well formed (section 6 check 1). Every write by this tool is made under the lock of section 5, so two `ab` commands writing at once both survive. What remains is a writer that ignores the lock: a hand edit, or any other program, between the tool's final read and its replacement can be lost, and the tool does not detect it. The lock is `flock`, present on the macOS and Linux platforms of the r1 setup. The parent must come before its child in the file because `record` reads that order (section 7). Because a `result` cell grows, a byte-for-byte earlier copy of the file is no longer a prefix of it (section 7).

## 4. Plan keys

`ab` plans gain two optional keys (`reader-ab.md:52-75` lists the rest; an unknown key is still exit `2`):

- `series`: the series file, a path relative to the plan's folder, as `posting` is (`ab.py:802-810`). It is not one of the plan's hashed inputs: the plan file's own hash covers the path, and the file's bytes change as rounds are added. A plan with no `series` key writes nothing and is checked for nothing here.
- `series-note`: optional, one line for the row's `note` when the plan admits a draft; no tab, CR or LF; a plan line that would break that is refused at freeze, exit `2`, naming the plan line. On a follow-up plan (below) it is read for that rule and otherwise ignored, because an extension must carry its first plan's lines (`ab.py:1005-1015`) and a replicate is byte-identical to its first (`reader-ab.md:86`).
- No key names the draft or its parent. The row's `draft` is the second-listed version of the plan's one comparison (`Y` in `X vs Y`, the version the hypotheses are about, `reader-ab.md:67`) and its `parent` is the first-listed version (`X`). Version names are the draft ids, so a plan that is to join a series names its versions as the series names them.

A plan with `series` must have **exactly one comparison**.

**Two kinds of plan with `series`.** An **admitting plan** has none of `extends`, `amends` and `replicate-of`: its draft must have no row, and it enters the series once, with its parent and the comparison that admitted it. A **follow-up plan** has one of them (`reader-ab.md:85-86`; a plan may carry only one, `:85`): it adds no row, and the run's reference is appended to the `result` cell of its draft's row (section 5). A draft that is read by a plan whose draft already has a row and is not a follow-up is refused (section 6).

## 5. When a row is written, and what changes

After the result file is written (`reader_harness.py:1023-1075`, which both `run` and `score` end in through `ab.py:1871`), when the result's own exit status is `0` or `1`, the tool changes the series file. A result with exit status `2` (a stopped run, `reader_harness.py:1049`) changes nothing. A dead run, a run with a failed read and a run cut by its spend ceiling are rounds, and are recorded with the verdicts they gave.

**An item** is `<round>@<plan64>[ <kind>]: <verdicts>`:
- `<round>`: the plan's folder relative to the series file's folder, as for the `round` column; `<plan64>`: the full sha256, 64 lowercase hexadecimal digits, that the freeze recorded for the plan file (the whole digest is stored and compared; only messages abbreviate it, to its first 12 digits, for display);
- `<kind>`: absent for the admitting round, otherwise `extends`, `amends` or `replicate`, the plan's own key;
- `<verdicts>`: for each hypothesis in plan order, `<h> <VERDICT>` (`h1 SUPPORTED`, `h2 INCONCLUSIVE`) joined by `, `. A hypothesis whose verdict is TIE (`tie-spec-r1.7.md` § 3) is written `<h> TIE` like the others (`h1 TIE`); the TIE sentence of that spec stays in the result file in `<round>`, and the cell never holds it. The verdicts are the ones the result file gives, the bare words only, with none of the `holds only when slightly counts as a pick` sentence, reasons or evidence lines (the result file in `<round>` holds those). A `round` may hold spaces and commas (`review, final` is a legal folder name) but never `;` or `@` (section 3). A reader parses an item from its left: the round up to the first `@`, the 64 digits, an optional ` <kind>`, then `: `; only after that does it split the verdicts on `, `. The items of a cell are split on `; `, which no round, digest, kind or verdict can hold (no verdict piece holds either).
- Items are joined by `; ` in run order, an item for each plan scored, so the cell is a list of the draft's rounds. Example: `r1@<64 hex>: h1 SUPPORTED; r2@<64 hex> extends: h1 SUPPORTED`.

**Admitting round.** One row is appended: `draft`, `parent`, `file_sha256` (what the comparison read of the draft's file), `posting_sha256` (the hash the freeze recorded for the posting), `round`, `plan_sha256` (the hash the freeze recorded), `result` (one item, no kind), `date`, `note` (the plan's `series-note`, or empty). The line is the nine cells joined by tabs and ended by one LF. `date` is the UTC day at the moment the row is written. Tests give the code a clock through a parameter, as `keywords.py:370` already takes `today`; no option, plan key or environment variable sets the date.

**Follow-up round.** The draft's row gains one item at the end of its `result` cell, preceded by `; `. No other cell changes.

**How the file is written.** Every write is made under a lock, in this order:
1. **Open.** `os.lstat` the lock path first: if the leaf exists and is not a regular file (a symbolic link, a FIFO, a device, a directory), refuse without opening it. Otherwise open `<series file>.lock` (same folder) with `os.open(path, O_RDWR | O_CREAT | O_NOFOLLOW | O_NONBLOCK, 0o600)`, so that no open can block and no link is followed, and call `os.fstat` on the descriptor: anything but a regular file is refused (the authoritative check, for a leaf that changed after the `lstat`). A lock file that cannot be opened for reading and writing (unwritable, not regular) is a series-write failure, never a read-only lock. **Only when this call created the file** (the `lstat` found no leaf and the open created one), call `os.fchmod(fd, 0o600)`, so a restrictive umask cannot leave an owner-unwritable lock; an existing lock file keeps its mode. The lock file is never read and never removed by the tool, whether it is empty, idle, or left behind by a failure.
   **Lock.** Take an exclusive lock with `fcntl.flock(fd, LOCK_EX | LOCK_NB)` (`fcntl` is imported as section 5a says), retrying every 100 milliseconds until one deadline of ten seconds counted from the start of step 1 (tests set it shorter), then fail. The open and the lock share that deadline and nothing in step 1 blocks past it, so a special file that blocks is refused or times out inside it.
2. **Under the lock**, reread the series file from disk (nothing read earlier is used), and run section 6 checks 1, 2 and 4 or 5 again on what was read, the once-per-plan test included.
3. Build the new bytes: the old bytes plus the new line, or the old bytes with the one item inserted at the end of the one `result` cell. Parse and validate the new bytes with the checks of section 6 check 1 (every column rule), and check that they equal the old bytes everywhere but the added line or item.
4. Write the new bytes to a new file in the same folder and replace the series file with it in one step (`os.replace`). `os.replace` is the commit point.
**Release, on every path.** A `finally` closes the lock descriptor, which releases the lock, and removes the temporary file if it still exists, on every path after step 1 begins (success, any failure, an exception). Nothing relies on the process ending to release the lock, so a second acquisition in the same process after any failure succeeds.

**The commit phase.** The result file exists before step 1. From step 1 on, a failure of any kind before `os.replace` has returned (the lock, the reread, a section 6 rule on the reread file, the build, the validation of the new bytes, the write or the replacement itself) is a series-write failure; an error after `os.replace` has returned (in the close or the release) is never reported as "not written": the series file is already replaced, the row or item is in it, and the command reports as it would have (a stderr line `series: lock release failed after the write: <reason>` is allowed and changes no exit status). A series-write failure is: the result file and the old series file stay as they were, no temporary file remains, `series: not written: <reason>` is printed, and the exit status is the higher of the result's and `1`. It is never exit `2` once the result exists. Before the result exists (`freeze`, the checks of `run` before any read, the checks of `score` before it writes a result), a rule failure is exit `2` and writes nothing.

**5a. A platform without `fcntl`.** Writing the series file needs a POSIX file lock. `fcntl` is imported lazily, whenever a command validates a plan that contains `series` (`freeze`, the checks of `run` before any read, the checks of `score` before it writes a result, and the write itself) and never for a plan that has no `series` key, so such plans are unchanged on every platform. All of those commands use the one same capability check, an attempt to import `fcntl`. On a platform where it fails, `freeze` refuses a plan that names `series`, exit `2`, naming the plan line: `series needs a POSIX file lock (fcntl), which this platform does not have`, and `run` and `score` refuse the same plan the same way before any read or result. The guide says it in one sentence: *A plan that names `series` needs a POSIX file lock, so it cannot be frozen on Windows.* (`docs/guides/ab.md:69-74` names Windows steps for the rest of `ab`; they are unaffected.)

The tool never opens the series file for writing in place. A series file that is a symbolic link is refused at section 6 check 1, because the replacement would swap the link and not change its target. If the lock cannot be taken, the failure is reported as the commit phase says, with `series: not written: cannot take <series file>.lock: <reason>`.

**Once per plan.** If a row's `plan_sha256` is this plan's, or the `<plan64>` of an item in a row's `result` is this plan's (the full 64 digits are compared), nothing is written, the run's exit status is the result's, and one line is printed after the result: `series: no change: plan <first 12 hex digits of its sha256> is already recorded in row <draft> (line <n>)`. A new plan is a new item (follow-up) or a new row (admitting). Re-scoring a frozen plan writes a new result file (`reader-ab.md:237`) and changes nothing else.

After a write, one line is printed after the result: `series: added row <draft> to <series file as the plan writes it>` or `series: added result of <round> to row <draft> in <series file as the plan writes it>`. These lines print their names the way every other `ab` line does (`ab.py` `_show`). They are not written into the result file, which was written first.

**If the write fails** after the result was written (an operating-system error the section 6 checks could not foresee, or a lock that could not be taken), the result file and the old series file stay as they were, the line `series: not written: <reason>` is printed, and the exit status is the higher of the result's and `1`. The result file's own `exit status:` line is not rewritten. Re-running `score` on the same plan writes it, since no row or item holds its hash (this is the way back).

## 6. Checks before any read and before any result

`freeze`, `run` (before any read, with the isolation check, `reader-ab.md:101-112`) and `score` (before it writes a result, and again just before the write of section 5) each check the following. A failure before the result exists is exit `2`, names the cause, writes nothing and reads nothing; the repeat under the lock, once the result exists, is the commit phase of section 5 and exits with the higher of the result's status and `1`. `freeze` writes no freeze file. The checks are repeated at `run` and `score` because the series file can change after the freeze (another round added a row or an item).

1. The series file exists, is a regular file and not a symbolic link, can be read, is in a folder that can be written, is UTF-8, has the exact header, ends with a line break, holds no CR, and every line has nine fields; and **every column rule of section 3 holds on every row**, so a hand-written row is checked as well as the tool's own: `draft` is letters, digits and `-`, not empty, unique; `parent` is empty or the `draft` of an earlier row; `file_sha256` is 64 lowercase hex digits; `posting_sha256` and `plan_sha256` are empty or 64 lowercase hex digits; `round`, `posting_sha256` and `plan_sha256` are all empty or all filled; a filled `round` is a normalized relative path (no segment equal to `.` or `..`, no empty segment, no leading or trailing `/`, no `;`, no `@`, no control character); `result` is empty exactly when `round` is, and otherwise a list of items in the strict grammar of section 5 (first item without a kind and with this row's `round` and `plan_sha256` as its round and digest, later items with kind `extends`, `amends` or `replicate`, each verdict piece `h<n> SUPPORTED`, `h<n> REFUTED`, `h<n> INCONCLUSIVE` or `h<n> TIE`, joined by `, `); `date` is a real `YYYY-MM-DD`; `note` holds no tab, CR or LF. The first line that breaks any of this is named: `<series file>:<line>: <column>: <fault>`. (`record` checks none of the hash, round and result rules, so this check is the only one.)
2. `parent` (the plan's first-listed version) is the `draft` of exactly one row, and that row's `file_sha256` equals the hash of what the comparison read of the parent's file (for a PDF its extracted text, as in section 3). A plan that tests a parent file other than the one the series records is refused, and the message prints the hash the tool computed so a person can see what it read, and, for a PDF, that it is the hash of the `pdftotext` text and not of the PDF: `<parent>: the plan's file is not the file the series records (computed <64 hex> from <the file's bytes|the pdftotext text of the file>; the row holds <64 hex>)`. The same message, naming the draft, refuses a follow-up whose draft file differs from its row (check 5).
3. The plan's folder is strictly below the series file's folder, so `round` is a relative path with no segment equal to `.` or `..` (a dot inside a name, as in `r1.2`, is allowed), and no segment of it holds `;`, `@` or a control character (tab, CR, LF and the rest of Unicode category Cc): otherwise the plan is refused, `<plan folder>: the folder name holds a character a series row cannot carry (; @ or a control character)`. The path is refused, never encoded.
4. For an **admitting plan**: `draft` (the second-listed version) is the `draft` of no row, except a row whose `plan_sha256` is this plan's (section 5, once per plan). A row of that draft with another plan hash is refused, naming its line and the three keys that admit a second round: `<draft>: the series already holds this draft (line <n>); a second round of a draft is a follow-up plan, with extends, amends or replicate-of`. Today's UTC day is not before the parent row's `date`; otherwise the new row would be one `record` faults as `dated before the row it corrects` (`record-check.md:141`), and the tool does not write a row `record` would fault.
5. For a **follow-up plan**: `draft` is the `draft` of exactly one row, that row's `file_sha256` equals what the comparison read of the draft's file, that row's `parent` is this plan's first-listed version, and the earlier plan that this plan's `extends`, `amends` or `replicate-of` names (the plan file beside the named freeze file, whose hash that freeze records: `reader_harness.py:562-569` parses the freeze entries, `ab.py:888-893` authenticates an amended plan, `ab.py:991-996` a first plan, `reader_harness.py:531-537` a replicate's) is one the row records: its full digest is the row's `plan_sha256` or the `<plan64>` of one of the row's items. An earlier plan that is itself a follow-up qualifies once its own item is in the row. Otherwise the plan is refused, naming the key and the row.
6. Each of the hashes a row needs is on file in the freeze (`ab score` already refuses a missing one, `reader_harness.py:573-630`).

## 7. Checking the file

`record` checks it, with this declaration (every path relative to the declaration's folder, `record-check.md:60`):

```text
tables:
  series | labs.series.tsv | tsv | draft
required:
  series | file_sha256
  series | date
dates:
  series | date
corrections:
  series | parent | date
```

`corrections` is the parent check, not `references`: it reads an empty `parent` as no reference and reports a parent that is the row itself (`corrects itself`), a parent that is no row (`corrects a missing row`), a parent that is a later row (`corrects a later row, line <m>`) and a child dated before its parent (`dated before the row it corrects, line <m>`) (`record-check.md:131-141`, `record_check.py:349-394`). A `references` check on `parent` would also report a missing parent, but not a later one and not a self-parent (`record-check.md:115-117`), and it reads a root written `none` as a dangling reference (`record-check.md:90`). That is why a root's `parent` is empty here and not `none`, which is the word `drafts` uses (`drafts.md:109`). The `table` check reports a repeated `draft` (`record-check.md:113`, "repeated key") and a ragged row, which is how a hand row that lost its trailing tabs is found.

**Do not declare `earlier` for the series file.** `record`'s earlier-copy check needs the earlier copy to be the start of the file, byte for byte (`record-check.md:145`), and a `result` cell that grew in the middle of the file breaks that for every copy made before the growth. The draft's file hash and the run folders stay the evidence.

This spec adds no `record` feature: the declaration above is the one pinned by section 9 cases SR12 and SR13 (rehearsed on 3.9.6 at `cc6b1c9`).

## 8. Exit status

Unchanged for a plan without `series`. For a plan with `series`: `0` and `1` as `reader-ab.md:241-242` define them, plus `1` when the series file could not be written (section 5); `2` gains the causes of sections 4 and 6, which stop the command before any read or any result.

## 9. Acceptance tests (known answers)

Numbered SR1 to SR40. The plan is the default plan of `reader-ab.md:311` (`base vs skills-top`, the fake reader, 12 reads per arm, the example hypothesis `h1`: `SUPPORTED if skills-top preferred in 6 of 6; REFUTED if base preferred in 4 or more; otherwise INCONCLUSIVE`) with `prefer containing "At a glance" | clearly` on the comparison, in the folder `F/r1/`, with `series: ../labs.series.tsv` and the series file `F/labs.series.tsv` holding the header and one hand row, `base`, whose `file_sha256` is the sha256 of `base.txt`, empty `parent`, empty `round` and `plan_sha256`, and the date `2026-11-15`. The clock gives `2026-11-16T10:00:00Z` unless a test says otherwise.

- SR1: `ab freeze`, then `ab run` exit `0`. The series file has gained exactly one line, after the two it had, which are byte-identical to before: `skills-top`, `base`, the sha256 of `skills-top.txt`, the sha256 of the posting, `r1`, the sha256 of `plan.txt`, `r1@<64 hex>: h1 SUPPORTED`, `2026-11-16`, and an empty note (the line ends with a tab). The output ends with `series: added row skills-top to ../labs.series.tsv`. `record` with the section 7 declaration exits `0`.
- SR2: the same with `series-note: shorter summary`: the note cell is `shorter summary`.
- SR3: `ab score` on the finished folder writes `result-2.txt`, changes nothing (the series file is byte-identical to after SR1), prints `series: no change: plan <first 12 hex> is already recorded in row skills-top (line 3)`, exit `0`.
- SR4: with TIE (`tie-spec-r1.7.md` T1's A/A and comparison reads and `aa-band: on`, hypothesis `SUPPORTED if skills-top preferred in 4 or more; otherwise INCONCLUSIVE`): the item is `r1@<64 hex>: h1 TIE`, and the result file in `r1/` holds the TIE line of that spec, which the cell does not. With two hypotheses `h1` (SUPPORTED) and `h2` (INCONCLUSIVE) the verdicts read `h1 SUPPORTED, h2 INCONCLUSIVE`; with `h1` TIE and `h2` SUPPORTED, `h1 TIE, h2 SUPPORTED`.
- SR5: a cut run (spend ceiling), a run with `omit PREFER | read 1`, and a dead run (`all | omit PREFER`) each add a row whose item is `r1@<64 hex>: h1 INCONCLUSIVE` and exit `1` as the run does. A result with exit status `2` changes nothing.
- SR6: the series file without a `base` row: `freeze` exits `2` naming `base`, no freeze file. The same with a row whose `draft` is `base2` only.
- SR7: a series file that already has a hand row `skills-top` with empty `plan_sha256`: an admitting plan's `freeze` exits `2` with `skills-top: the series already holds this draft (line 3); a second round of a draft is a follow-up plan, with extends, amends or replicate-of`. With a row `skills-top` whose `plan_sha256` is another plan's: `run` exits `2` before any read and writes no reply; the same at `score` of a finished folder: no result file is written.
- SR8: `base.txt` edited after `base`'s row was written (the hashes differ): `freeze` exits `2` with `base: the plan's file is not the file the series records (computed <64 hex> from the file's bytes; the row holds <64 hex>)`, the computed hash being the sha256 of the file as it now is. With `base.pdf` as the parent file, the row holds the sha256 of its `pdftotext base.pdf -` text, and a plan reading `base.pdf` freezes; a row holding the sha256 of the PDF's bytes is refused with the same message, which prints the sha256 of the `pdftotext` text (`computed <64 hex> from the pdftotext text of the file`), so the person can correct the row by hand without computing it. With the file named `BASE.PDF` the same holds: the test of the extension is case-insensitive, as `ab`'s (`reader_harness.py:672`).
- SR9: a plan folder that is the series file's own folder, or a plan folder outside it (`round` would need `..`): `freeze` exits `2`. A plan folder two levels below is accepted and `round` is `sub/r1`.
- SR10: each of these series files makes `freeze` exit `2` naming `<file>:<line>:` and the fault: a wrong header, a missing final line break, a CR, a row with eight fields, a row with ten, a byte-order mark, invalid UTF-8; a missing file is exit `2` and the file is not created; a series file that is a symbolic link is exit `2`; and, naming `<file>:<line>: <column>: <fault>`, a malformed column on a hand-written row, one case each: a `draft` with a space, an underscore or a dot (anything outside letters, digits and `-`), a repeated `draft`, a `parent` that is no earlier row, a `file_sha256` of 63 digits, of 65, with an upper-case digit, or empty, a `posting_sha256` or `plan_sha256` with a non-hex digit, a `round` filled and `plan_sha256` empty (and the reverse), a `round` filled and `posting_sha256` empty, a `round` empty and `posting_sha256` filled, a `round` of `/abs`, `a//b`, `a/`, `./a`, `a/../b`, a filled `round` with an empty `result`, a `result` item whose digest differs from the row's, whose first item has a kind, whose kind is `other`, with a verdict piece `h1 MAYBE`, with `h1SUPPORTED`, or with `h1 TIED`, `h1 tie` or the old TIE sentence in place of `h1 TIE`, a `date` of `2026-02-30`, a `note` holding a tab (a ninth tab makes ten fields).
- SR11: a plan with `series` and two comparisons is refused at freeze, exit `2`. A plan with no `series` key behaves as before and leaves the series file's bytes and modification time alone.
- SR12: the declaration of section 7 on a file with, in turn, a root written `none`, a parent that is the row itself, a parent that is a later row, a parent that is no row, a child dated before its parent, and a row with its trailing tabs missing gives exit `1` each time with the findings `corrects a missing row`, `corrects itself`, `corrects a later row, line <m>`, `corrects a missing row`, `dated before the row it corrects, line <m>` and `fields <n>, the header has 9`. The same file with the root's `parent` empty and every parent earlier exits `0`.
- SR13: a file of three rows, root, child, grandchild, each parent earlier and dated on or after its parent: `record` exits `0`. Two rows with one `draft` give `repeated key, first on line <m>`.
- SR14: dates. With the clock at `2026-11-16T23:59:59Z` the row's date is `2026-11-16`; at `2026-11-17T00:00:00Z` it is `2026-11-17`, in a process whose local time zone is a day behind UTC and in one a day ahead. With the parent row dated `2999-01-01`, an admitting plan's `freeze`, `run` and `score` exit `2` naming the parent and the date, and write nothing.
- SR15: `series-note` holding a tab is refused at freeze, exit `2`, naming the plan line.
- SR16: write failure. A test that makes the replacement fail after the result was written leaves the result file and the old series file byte-identical, prints `series: not written: <reason>`, and exits `1` (SR1's run would have exited `0`); the result file still says `exit status: 0`. A second `ab score` writes the row (exit `0`).
- SR17: the series file changed between `run` and `score` so that it no longer ends with a line break: `score` exits `2` before it writes a result.
- SR18: the versions swapped relative to the series (`skills-top vs base` with `skills-top` not yet in the file and `base` already there): `freeze` exits `2` naming `skills-top` (it is not a row, section 6 check 2).
- SR19: two admitting plans, `F/r1/` and `F/r2/`, each scored in turn, the second a child of the first's draft (its first-listed version the first's `draft`, whose row now exists, `file_sha256` matching): two rows; `record` exits `0`.
- SR20: names escape as other `ab` lines do: a series path holding a newline or an ESC is printed escaped (`ab.py` `_show`) in the `series:` line.
- SR21: an extension. SR1's folder extended by `F/r1x/` (`extends: ../r1/plan.txt.freeze`, `series` and `series-note` as the first plan's, as `ab.py:1005-1015` requires): no row is added; the row's `result` ends `...; r1x@<64 hex> extends: h1 SUPPORTED`, every other byte of the file is as before, and the output ends `series: added result of r1x to row skills-top in ../labs.series.tsv`. `record` exits `0`. The date, `round` and `plan_sha256` cells are unchanged.
- SR22: an amendment (`amends` naming SR1's freeze, read count doubled, rules restated at their share) and a replicate (`replicate-of` naming SR1's freeze) each add an item with kind `amends` and `replicate`, in run order after the earlier items, and a replicate's plan hash is its own. Scoring either twice changes nothing the second time (SR3's line).
- SR23: follow-up refusals, each `freeze` exit `2` (a draft-file mismatch with the message of check 2 naming the draft; a missing row, a named earlier plan the row does not record and a wrong parent naming the key and the row): a follow-up whose draft has no row; whose row's `file_sha256` differs from what the comparison read of the draft's file; whose named earlier plan is not the row's `plan_sha256` or any item's `<plan64>`; whose first-listed version is not the row's `parent`. An admitting plan whose draft already has a row (a second round that is not a follow-up) is refused as SR7.
- SR24: the row's other bytes. After SR21, the new file equals the old file with `; r1x@<64 hex> extends: ...` inserted at the end of one `result` cell and nothing else (byte comparison); a test that makes the builder change another byte makes `score` keep its result, leave the old series file byte-identical, print `series: not written: <reason>` and exit `1` (the commit phase).

- SR25: two processes. Two admitting plans for two different drafts (`skills-top` and `skills-top-short`, both children of `base`), scored at the same moment by two processes released together by a test that holds the lock until both are waiting: both exit `0`, the series file holds both rows (in either order, each after `base`), `record` exits `0`, and no row is missing. The same with two follow-up rounds of two drafts, and with one admitting plan and one follow-up of another draft: every update survives.
- SR26: the lock cannot be taken before the deadline. A test process holds the lock on `<series file>.lock`; with the deadline set to a fraction of a second, `ab score` writes the result, leaves the series file byte-identical, prints `series: not written: cannot take <series file>.lock: <reason>` and exits `1`, within the deadline plus one retry interval (it does not block); after the holder lets go, a second `ab score` of the same plan writes the row, exit `0`.
- SR27: the reread. A test changes the series file after the section 6 checks of `score` passed and before the lock is taken (another process added a row for another draft and released): the row written afterwards is built on the changed file, and both rows are present. A test that makes the changed file break a section 6 rule at that moment makes `score` keep its result, print `series: not written: <reason>`, leave the changed file as it is and exit `1`.
- SR28: the whole digest. A hand-written first item whose digest equals the real plan's first 12 hex digits and differs after them (the last 52 digits changed) is not this plan's: `score` appends the new item, not `series: no change`, and a follow-up that names the real plan is refused by check 5 (its full digest is neither the row's nor any item's). A row whose item holds the real plan's full digest gives `series: no change`.
- SR29: a follow-up of a follow-up. After SR22 (an amendment A1 of SR1's plan has its item in the row), an amendment A2 whose `amends` names A1's freeze, with the read count doubled again and rules restated at their share, freezes and scores: its item (kind `amends`) is added after A1's. The same A2 with A1's item removed from the cell by hand (the row now records only the admitting plan) is refused by check 5, naming `amends` and the row.
- SR30: `round` characters. A plan whose folder name holds, one case each, `;`, `@`, a tab, a CR, an LF, an ESC (U+001B) and U+0085 is refused at freeze (check 3), exit `2`, with `<plan folder>: the folder name holds a character a series row cannot carry (; @ or a control character)` (the folder named in that message printed escaped, SR20); the series file is untouched. A folder name with a space, a `,` or a `:` is accepted and the row is written and read back by check 1 without ambiguity. Accepted, one case each: `r1.2`, `2026.11.17`, `labs.r1` and `review, final` (an item `review, final@<64 hex>: h1 SUPPORTED` is parsed from the left and its verdicts split only after `: `, so the round is not cut at its comma); refused: a folder that is exactly `.` or `..` as a segment of the relative path.
- SR31: the new file is validated before it replaces the old: a test that makes the builder produce an item breaking the grammar makes `score` keep its result, leave the series file byte-identical, print `series: not written: <reason>`, exit `1`, and leave no temporary file in the folder.
- SR32: the lock file is not a series file: it is never read by a check, and `record` is not declared on it.
- SR33: no hash is abbreviated in the file: after SR21 and SR22 every item holds a 64-digit digest; the messages of `series: no change` and `series: added ...` hold at most 12.

- SR34: the lock file's creation. With no lock file, the first write creates `<series file>.lock` and its mode is `0o600` under the default umask and under a restrictive umask (`0o277`, which would clear the owner's write bit without `fchmod`): a second write then succeeds. With an existing lock file of another mode (`0o644`), the write succeeds and the mode is unchanged (no `fchmod`).
- SR35: an unwritable lock file (`0o444`, owned by the user): the lock is not taken read-only; `ab score` keeps its result, leaves the series file byte-identical, prints `series: not written: cannot take <series file>.lock: <reason>` and exits `1`. A lock file that is a symbolic link, and one that is a directory, give the same.
- SR36: a non-regular lock file: with `<series file>.lock` a FIFO, the write fails as SR35 without opening it, within the deadline. Where a device node can be made, or with a test double whose `open` blocks until the deadline, the same: the command fails as SR35 no later than the deadline plus one retry interval, not hung. A leaf swapped for a FIFO between the `lstat` and the open is refused by the `fstat`.
- SR37: no `fcntl`. A test hides the `fcntl` module (an import that raises `ImportError`): a plan that names `series` is refused at `freeze`, exit `2`, with `series needs a POSIX file lock (fcntl), which this platform does not have`, naming the plan line, and writes no freeze file; `run` and `score` refuse such a plan the same way before any read or result. A plan without `series` freezes, runs and scores as before with `fcntl` hidden, and importing the tool's modules with it hidden succeeds.
- SR38: the lock file stays. After a successful write, after SR26's failed one and after SR35's, `<series file>.lock` still exists (it may be empty); the tool removes no lock file.

- SR39: the lock is released on every path. A test injects a failure under the lock, one case each in the reread, the build, the temporary-file write and `os.replace`: the command prints `series: not written: <reason>`, exits `1`, leaves the old series file byte-identical and no temporary file in the folder; a second write in the same process, with the failure no longer injected, takes the lock at once and succeeds. A test that injects an error in the close or release after `os.replace` has returned leaves the new row or item in the file and the command exits as it would have (`0` for SR1's run): it never reports "not written".
- SR40: the capability check is one check. With `fcntl` hidden (SR37), `freeze`, `run` and `score` of a plan that names `series` each refuse with the same stated message, before a freeze file, a read or a result; with `fcntl` present and the plan without `series`, `fcntl` is never imported (a test that fails the process if it is imported passes).

## 9a. Docs this release changes

The release adds a short section on the series file to `docs/guides/ab.md` (or the guide it names), which does these things, each once, and no more:
1. **Glosses three words** where a reader meets them: `draft` is the plan's version (the version name is the draft id); `round` is the run folder; an empty `parent` is what the `drafts` file writes `none` (`drafts.md:109`).
2. **Says in one line when to use which:** the `drafts` file keeps a document's versions by hand, with their text, parents and your notes; the series file records, from the tool, which draft was read against which parent and what each round said. Both name parents today, and no command compares them.
3. **Says how to date a hand-written row:** write the UTC day (`date -u +%F`), as the tool does for its own rows.
4. **Uses only the word "series"** for this record, here and in the rest of the guide, never "lineage" or another word for it.

<!-- signed spec ends -->

## Build interpretations of revision 1 (maintainer, 2026-11-18)

Revision 1 is the signed text above and is not edited. These readings fill points the signed text leaves open, each stated as one rule:

1. **The `series:` lines are printed, never written to the result file.** The `series:` line goes to the text `ab run` and `ab score` print, after the result is written. The result file is the one a plan without `series` gets. A `series: not written:` line is printed on standard output, and the one lock-release warning after the write goes to standard error.
2. **A temp file takes the mode of the series file it replaces.** The replacement is written with the permission bits of the file it replaces, so a replaced series file keeps its mode.
3. **A plan with `series` and no hypotheses is refused at freeze.** Exit status 2, before any read, with the line `the plan names a series file but no hypothesis; add a hypothesis, or remove the series line`.
4. **The once-per-plan test skips the parent-date refusal for an already recorded plan.** Scoring a plan again reports `series: no change: ...` and does not apply the parent-date check to that plan.
5. **The clock is a parameter.** The date of a row comes from an optional keyword that defaults to the real UTC time. No plan key, environment variable or command-line option sets it; tests pass it.
6. **The series write is checked against the setup record folder.** `freeze`, `run` and `score` check the series file, its lock file and its temporary file before any read and before anything is written, and a refusal that comes only after the result exists keeps the result and exits 1.
7. **A `series-note` without `series` is refused at freeze.** Exit status 2, naming the plan line: `series-note is set but the plan names no series file; add a series line, or remove series-note`. Without it the note would be dropped without a word.
