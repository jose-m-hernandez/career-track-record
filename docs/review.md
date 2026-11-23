# Review before you send

This file sets the sequence of checks for a single draft that answers one saved posting. The last step is a review sheet that declares the draft ready or names the gate still open. It adds no command; the person sends the draft.

## The gate order

Stop at the first hard failure. A step that names a command says which; a step that no command does says so. The review sheet below records each step's result.

**Gate 0. Scope.** Name the draft, its parent, the saved posting and who the reader is. If the posting may have closed, say so on the sheet. No command checks whether a posting is still open: the tools import no network library (`tests/test_no_network.py:1-3`).

**Gate 1. Structure before lines.** If the draft is new or restructured, the person reads it once through for structure before any line work. No command does this: it is a human read. A section a reader would cut makes line work on it wasted. `panel` needs a frozen plan (`docs/specs/reader-panel.md:78`), and plans freeze at gate 4, so the structure read by a reader is the cold read of gate 4. A structural finding from that read sends the draft back to gate 2 as a new draft, under a new plan.

**Gate 2. Claims.** `<cli> claims --list FILE --control TEXT FILE...`, with `--check-sources` where entries cite local files (`docs/specs/claims.md:47-50`). Every sentence must be approved. The method adds three rules the tool does not decide, for the person to rule on:

- **Verbs both ways.** Check the record before weakening "built" to "helped", and before strengthening "helped" to "led".
- **The number test.** Each number must be *relevant* (it lands something for this reader), *scaled* (the reader can tell big from small: a unit, a baseline or a denominator) and *defensible* (the person can say where it came from, and the record says the same). A number that fails is cut or kept for the interview. It is not shaved down or rounded up.
- **Missing numbers are asked for, not estimated.** Ask one at a time: how many people, teams, customers or requests it touched; the number before and after; how long it took, and how long before; how often it ran; whose number it is (the person's or the team's, which decides the verb). The answer goes into the record, with how it is known, before any sentence uses it.

**Gate 3. Mechanical checks, each with its own dead-instrument guard.** A guard is what stops a check that read nothing from passing as clean. `barred` and `claims` take a control phrase (`docs/specs/barred.md:44`, `docs/specs/claims.md:48`). `tone` has no control option; it self-tests every rule against its own examples before it checks any file (`docs/specs/tone-and-tells.md:20`, `:119`; `src/career_track_record/tone.py:531`). `keywords report` has the posting's recorded SHA-256 (`docs/guides/keywords.md:5`). `parse` has `--name`: a PDF that does not hold the given name is DEAD, and a DEAD file exits `2`, which is not a pass (`docs/specs/parse.md:36-38`, `:197`).

- `<cli> barred`, with a control phrase (`docs/specs/barred.md:44`). A file shorter than the tool's minimum length (default 500, `docs/specs/barred.md:46`) is DEAD (`docs/specs/barred.md:164`, item 4). For intentionally short copy, run `barred` with `--min-chars 0` and a control phrase that is in that copy itself (for example a name in its contact line), so that the draft, not a filler file, supplies the control. `barred` checks length and control for each file on its own (`src/career_track_record/barred.py:384-388`), and `--min-chars` accepts `0` (`docs/specs/barred.md:46`). Do not join a short draft to another file: a clean file can supply both the length and the control when the draft supplies no usable text.
- `<cli> tone` (`docs/specs/tone-and-tells.md:17`), with the shipped or the person's rule file.
- `<cli> keywords report --postings DIR --terms FILE --copy FILE...` against the saved posting. `keywords report` scans every `.txt` file in `DIR` (`src/career_track_record/keywords.py:206-213`, `:218`), so for this step `DIR` holds only the target posting: a folder of one, even when the default postings folder (`postings`, `src/career_track_record/cli.py:1131`) holds many. For a PDF draft, `--copy` is the extracted UTF-8 text saved at the extraction step below, never the PDF: `keywords` reads each copy as UTF-8 text and has no PDF branch (`src/career_track_record/keywords.py:195-199`). A keyword gap is closed only by a true line from the record, never by pasting the posting's phrase in, and there is no density target.
- `<cli> parse --name TEXT --contact TEXT FILE`, for a PDF draft only: `parse` reads PDFs and nothing else, and any file whose name does not end in `.pdf` is DEAD (`docs/specs/parse.md:157`). `--name` is the person's name as it appears in the PDF; `--contact` is repeated for each email, phone number or link that belongs on page 1; `--sections` names the section families the résumé has, because the default requires `experience` and `skills` (`docs/specs/parse.md:36-43`). It checks text on every page, the name and each contact on page 1, section headings, one date format and wrapped compounds, in that order (`docs/guides/parse.md:9-14`). It exits `0` with no finding, `1` with a finding and `2` with no verdict (`docs/specs/parse.md:48-49`, `:197`): only `0` passes.
- **PDF extraction and what `parse` does not check: by hand.** Extract the text once with `pdftotext FILE -`, the program the tools run (`src/career_track_record/pdf_text.py:21`), save it as a UTF-8 file, and use that one file for the checks below, for `keywords --copy` and for the extracted-text hash of the review sheet below. `parse` writes no file (`docs/guides/parse.md:16`), and of the commands listed at `docs/specs/cli.md:25-37` none is described as writing a PDF's extracted text. On the extracted text, check by hand that the name and contact line are in the body, not lost to a header or footer (`parse` cannot tell a header or footer region from the body: `docs/guides/parse.md:67`), that no text is lost against the source, and that no columns read out of order (`parse` does not check reading order: `docs/guides/parse.md:68`). `parse` knows English section names only, counts only a date range that sits on one line, and misreads day-first dates (`docs/guides/parse.md:69-71`): where the résumé's headings, ranges or dates are outside that, check the section names and the date format by hand as well.

**Gate 4. Readers, under a plan frozen first.**

- **Edit review:** the draft against its parent, run as `<cli> ab freeze PLAN`, then `<cli> ab run PLAN`, then `<cli> ab score PLAN` (`docs/specs/reader-ab.md:79`; `docs/specs/cli.md:15`).
- **Cold read:** one draft alone, run as `<cli> panel freeze PLAN`, then `<cli> panel run PLAN`, then `<cli> panel score PLAN`, through the lenses the person names, with strong and weak anchors (`docs/specs/reader-panel.md:56-58`, `:78`). It is the structure read by a reader that gate 1 leaves to this gate.
- Both texts in any comparison come from the same extraction, with the same flags. A difference voids the comparison.
- A reader that may know the person is declared `not-blind`, and its reads count in no verdict (`docs/specs/reader-panel.md:139`; the option is defined at `:60`).
- **Read the readers' paraphrase both ways.** A reader that restates a claim more strongly than the record supports means tighten the sentence. A reader that restates it more weakly means the line undersells, which is a framing finding.
- **Count each flag across rounds.** For each thing fixed, count the readers who still raise it. A fix that moved no count did not close its flag.
- **Fresh or inherited.** Say on the sheet whether this draft's reads are its own or its parent's, and why. A draft whose summary or opening lines changed needs its own cold read.
- **Stop rule.** A new draft replaces the current one only when the frozen plan's rule says so. Otherwise keep the current draft. A structural ceiling is not fixed by more rounds.

**Gate 5. Diff against the parent.** `ab` reports the changed lines between two versions and marks each as inside or outside the declared change scope, before any read (`docs/specs/reader-ab.md:101-103`). No command decides whether each change was intended or validates moved references. Confirm by hand that only the intended lines changed. When lines move, check references between them ("that pipeline", "the same tool"), since a moved line can point at nothing. Re-run `barred` on the final file. Record the hashes the `hashes` line of the review sheet below requires: for a PDF draft, the SHA-256 of the PDF and of its extracted text; for a text or Markdown draft, the SHA-256 of the draft file; and, wherever a parent exists (always, since a first draft's parent is the person's default résumé), the SHA-256 of the parent, so a PDF draft has three hashes and a text or Markdown draft has two. Neither `ab freeze` nor `panel freeze` is a general-purpose hash command, and neither supplies a separate hash of the extracted text: they hash the plan, its inputs and the built-in prompt (`docs/specs/reader-panel.md:78`, `docs/specs/reader-ab.md:79`).

## Ready means three gates, and every check passed

A draft is **ready to send** only when both hold:

**A. The three gates.**
1. the tailoring is decided;
2. a cold read has run against the saved posting, its own or inherited with the reason written;
3. the application's form questions are pulled and answered.

**B. Every check passed.** Each line of gates 1 to 5 reads `pass`. A line passes as follows:

| Sheet key | Passes when |
|---|---|
| `structure` | the person read it through and no section needs cutting or moving (by hand) |
| `claims` | `claims` exited `0` with its control found (`docs/specs/claims.md:170`), and the three method rules of gate 2 hold |
| `barred` | `barred` exited `0` with its control found (`docs/specs/barred.md:153`) |
| `tone` | `tone` exited `0`: warnings are allowed, an error is not (`docs/specs/tone-and-tells.md:158`) |
| `keywords` | `keywords report` exited `0`, and each gap is closed by a true line from the record or left open with the reason written |
| `parse` | for a PDF draft: `parse` exited `0` (`1` or `2` does not pass), and every check of gate 3's by-hand extraction step holds (by hand). For a text or Markdown draft there is no parse step and the line reads `pass (not a PDF: no parse step)` |
| `edit review` | `ab score` exited `0` and the frozen plan's rule says this draft replaces its parent |
| `cold read` | `panel score` exited `0` and the plan's rules give `PASS` |
| `diff` | `ab`'s scope check passed, and by hand every changed line was intended and every moved reference holds |

`tailoring` reads `decided`, `form questions` reads `answered`, and `hashes` reads `recorded`. A line that reads `fail` or `pending` means the draft is not ready, and the sheet's `ready:` line is `no`, naming the first open or failed key. No command does gates A1 or A3, or the hand checks above. The person reads the sheet last and sends the draft themselves (AGENTS.md standing order 1).

## The review sheet

One line per key, in this order: `draft`, `parent`, `posting`, `structure`, `claims`, `barred`, `tone`, `keywords`, `parse`, `edit review`, `cold read`, `diff`, `hashes`, `tailoring`, `form questions`, `ready`. After the colon, the lines for `structure` to `diff` start with `pass`, `fail` or `pending`; `hashes` starts `recorded` or `pending`; `tailoring` starts `decided` or `pending`; `form questions` starts `answered` or `pending`. Invented example (hash values abbreviated here; the real line holds each full value):

```text
draft: example-corp-v2.pdf
parent: example-corp-v1.pdf
posting: sample-labs-data-platform.txt (sha256 recorded)
structure: pass (read by hand: no section to cut)
claims: pass (exit 0, control found)
barred: pass (exit 0, control found)
tone: pass (exit 0: 0 errors, 1 warning)
keywords: pass (exit 0: 2 gaps, both left open: no true line in the record)
parse: pass (exit 0: name and contact on page 1, one date format; checked by hand: name in body, no text lost, columns in order)
edit review: pass (exit 0, ab SUPPORTED, plan sha256 recorded)
cold read: pass (exit 0, panel PASS, recruiter and hiring-manager lenses; own read: the summary changed from the parent)
diff: pass (ab run exit 0: 2 lines changed, both in scope; checked by hand: both intended, references hold)
hashes: recorded (pdf sha256 3f1a...9c0e, extracted text sha256 7b42...d518, parent sha256 a90c...41e7)
tailoring: decided
form questions: pending
ready: no (form questions pending)
```

Every line whose result comes from a command contains `exit N`, the command's exit status, as shown. A verdict word (`SUPPORTED`, `PASS`) is the tool's reading of its frozen rule, not an exit status, and sits beside the exit status, not instead of it. A keyword gap still exits `0` (`src/career_track_record/keywords.py:415`), so the line names the gaps as well as the exit. A `parse` finding exits `1` and a DEAD PDF exits `2`; both read `fail` and name the exit. A result that comes from the person's hand says so ("read by hand", "checked by hand", "decided").

`ready: yes` follows the rules above exactly. Six failing lines, each of which makes the sheet end `ready: no`; any other line that reads `fail` does the same:

```text
claims: fail (exit 1, 1 sentence not approved)           ready: no (claims failed)
barred: fail (exit 1, 1 entry found)                     ready: no (barred failed)
tone: fail (exit 1, 1 error)                             ready: no (tone failed)
edit review: fail (exit 0, ab INCONCLUSIVE)              ready: no (edit review failed)
cold read: fail (exit 0, panel FAIL)                     ready: no (cold read failed)
diff: fail (ab run exit 0: 3 lines changed, all in scope; checked by hand: 1 not intended)             ready: no (diff failed)
```

The `hashes` line holds a SHA-256 for each artifact the draft's form needs (gate 5 above).

This method adapts a private review skill of the maintainer's. No prompt, result, record or example from it is reproduced here, and every example is invented.
