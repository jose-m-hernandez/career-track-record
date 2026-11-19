# `track-record wrapped-compounds`: behaviour spec

Status: accepted.
Date: 2026-11-19.
Revision: 6. The public edition of the signed spec (signed by the method owner; text sha256 67900aa355e20e974e7ab7856d08fe1b45a048d8d1c4f521eba73db96fcb5692) is reproduced below verbatim. It is the first signed text of this command in this repository.

## Signed spec

<!-- signed spec begins: sha256 67900aa355e20e974e7ab7856d08fe1b45a048d8d1c4f521eba73db96fcb5692 -->
# CTR spec (2): `track-record wrapped-compounds`

Depends on: `src/career_track_record/pdf_text.py` as shipped, in both modes (default, and `layout=True`). No new program.
Size: small. About 90 lines of logic and 16 cases: 4 run on generated PDFs, and 12 run on literal text through the pure function.

Every example here is invented. None comes from a real person's résumé, posting, employer or results.

## 1. Problem

A hyphenated compound (`well-known`, `cross-team`) can wrap at its hyphen in a PDF. When it does, `pdftotext`'s default text drops the hyphen and the line break and joins the halves into `wellknown`, a word no reader or keyword search will match. On screen the PDF looks right, so the author never sees it. `barred` already reads the layout text, so a barred entry wrapped at its hyphen is still caught (`docs/specs/barred.md` § 3.2), but only for words on a list. No existing check reports each wrapped compound.

**Premise, measured at build.** The join described above is what poppler 26.07.0 does (the version `barred.md` § 3.2 names). Case W1 is the measurement: if W1's generated PDF shows the default text keeping the hyphen, the premise is false. In that case the build stops and the spec returns to its author. The check is not shipped in a form that can never fire.

## 2. Synopsis

```text
usage: track-record wrapped-compounds --control TEXT [--control TEXT]... FILE...

Checks a PDF for hyphenated words (such as well-known) that are split across
two lines. Some programs that read a PDF's text join the two halves into one
word ("wellknown"), so a text search misses it even though the page looks right.

Run it on the final PDF, after your last edit. Exit 0 means no split hyphenated
word needs a fix. It checks nothing else about the file.

  --control TEXT  text that must appear in the file, such as your name;
                  repeatable; if none appears the file is reported DEAD
                  (it could not be checked), never OK
  -h, --help      show this summary and exit

exit: 0 no finding, 1 a finding, 2 no verdict (a file is DEAD, or the command
      could not run); 2 is not a pass
```

- `FILE` is positional and repeatable, and files are checked in argument order. A file whose name does not end in `.pdf` (any case) is DEAD with `not a PDF; give the PDF file` (§ 3, the one form of that reason).
- `--control` is required and repeatable. A control is prepared as `barred.md` § 3.3 prepares one (folded, whitespace runs collapsed, trimmed) and matched as a substring of the file's default text in its joined form (`barred.md` § 4, form 1). A file in which no control is found is DEAD. A control that is empty after preparing is dropped; when every control is empty after preparing, that is a usage error (below), as in `barred.md` § 3.3.
- `-h` / `--help` writes the summary above and exits `0`. It reads no file and wins over every other argument.
- **Options** are parsed as `barred`'s are: `--control=TEXT` is the same as `--control TEXT`; after `--` every argument is a file name; a lone `-` is a file name; an argument that is exactly `-h` or `--help` asks for help wherever it stands (`barred.md` § 3.0).
- **Usage errors** exit `2` before any file is read, with one line on standard error. Checked in this order, the exact lines are: an unknown option, `cannot run: unknown option`; `--control` with no value, `cannot run: --control needs a value`; no `FILE`, `cannot run: no input file`; no `--control`, `cannot run: no --control given`; every control empty after preparing, `cannot run: no usable --control given`. These are `barred`'s words for the same cases.
- **Configuration.** The command reads no configuration file, and nothing from the setup configuration of release 0.11.0. Its only inputs are its arguments and the files they name.
- **The printed path** of each file follows `barred.md` § 6 ("The printed path", the escaping rules). No list is involved, so a path is always printed and never replaced by `file #<i>`.
- **Scope.** A pass covers only hyphenated words split at a line end, in PDFs. Words broken without a hyphen, soft-hyphen breaks, scanned images, multi-column pages and other layout problems are not checked; the guide lists the limits (§ 8).

## 3. Text preparation

Each file is read twice through `pdf_text`: the **layout text** (`layout=True`) and the **default text**. Both are then prepared in this order. The pure function of § 10 takes the two raw texts and runs these three steps itself:

1. **Normalise:** apply Unicode NFKC, which turns ligatures such as `ﬁ` into two letters and a no-break space into a space, then remove every format character (category Cf). Category Cf includes the soft hyphen, so a soft hyphen at a line end leaves a line that ends in a letter, and this check does not read it (W10; `barred` revision 8 owns soft hyphens). Case is kept for printing. Every comparison below is made on `str.casefold()` of both sides.
2. **Pages:** split at each form feed (U+000C). A single empty segment after the last form feed is dropped, because `pdftotext` ends every page with one. Pages are numbered from 1. If the two texts then have different page counts, the file is DEAD with `page counts differ (default <a>, layout <b>)`.
3. **Lines:** within a page, LF, CRLF and a lone CR each end a line (`barred.md` § 3.2, "Line breaks"). No other character ends a line. Note that Python's `str.splitlines()` also breaks on VT, FS, GS, RS, U+0085, U+2028 and U+2029, so it must not be used. Lines are numbered from 1 at the top of each page, blank lines included. A **blank** line holds only whitespace (`str.isspace`, or empty).

DEAD before the check runs, in this order, each as `DEAD  <path>: <reason>`.
Every reason but `barred`'s names its next step; for `barred`'s reasons, which are its words word for word, the guide says what to do:
- `not a PDF; give the PDF file`;
- the reason `barred` prints when the file can't be read, or when `pdftotext` is missing or fails on either read (`barred.md` § 7, case 6), word for word;
- `no text; the PDF holds no selectable text (a scan?), so export it again from the document`: the default text, after step 1, holds no letter or decimal digit (Unicode categories L and Nd) on any page;
- `no layout text; export the PDF again`: the default text holds one, and the layout text, after step 1, holds none;
- `page counts differ (default <a>, layout <b>); export the PDF again`;
- `control not found; check that the text in the PDF can be selected`.

## 4. Finding wraps (layout text)

Definitions:
- A **letter** is a character of Unicode category L, or M when it follows a letter.
- A **word run** is a maximal run of letters and hyphen-minus (U+002D) characters, with leading and trailing hyphens excluded from the run.

On each layout page, a line is a **wrap line** when all of these hold:
- with trailing whitespace removed, it ends in a hyphen-minus (U+002D after step 1, which folds the fullwidth U+FF0D and small U+FE63 forms into it; no other dash);
- the character before that hyphen is a letter;
- the next non-blank line on the same page, with leading whitespace removed, begins with a letter.

For each wrap line:
- The **left half** is the word run that ends just before the final hyphen. For `the state-of-the-` it is `state-of-the`.
- The **right half** is the maximal run of letters that begins the next non-blank line. It stops at the first character that is not a letter, a hyphen included: `art,` gives `art`, and `team-based` gives `team`.
- The **compound** printed is `<left half>-<right half>`.
- The **line** printed is the wrap line's number on its page.

A wrap line on the last non-blank line of a page is not a hit, even when the next page starts with a letter (W6).

## 5. Finding the join (default text, same page)

On the default text of the same page, the **tokens** are its word runs (§ 4), in page order. A token **joins** a hit when `casefold(token)` starts with `casefold(left + right[:3])`, or with `casefold(left + right)` when the right half is shorter than 3 letters.

Hits on a page are taken in page order. Each hit is given the first joining token on that page that no earlier hit has taken. So two wraps of the same pair need two joined tokens, and if the page holds only one, the second hit prints `(no join found)` (W11).

## 6. Outcome of each hit

Every hit line ends with exactly one of these three markers.

1. `(no join found, not a finding)`: no token was free to join. Not a finding. The default text kept the hyphen, or broke the line in a way this check doesn't model.
2. `(note: "<token>" also appears unwrapped, nothing to fix)`: a token joined, **and** both of these hold:
   - in the whole default text (every page), more tokens equal `casefold(token)` than there are hits that joined to a token of that casefold. So at least one occurrence is not the product of a wrap.
   - no token in the whole default text equals `casefold(left + "-" + right)`.

   Not a finding. This is the **note case**: a long word that was broken at a line end and is still right when rejoined (`manage-` / `ment`).
3. `(finding)`: a token joined, and the note case does not hold. A broken word that appears only once can't be told from a compound, so it stays a finding (W7).

Hit lines:

```text
  wrapped compounds: page 1 line 14: "well-known" is split across lines; extracted text reads "wellknown" (finding)
  wrapped compounds: page 2 line 3: "cross-team" is split across lines; extracted text does not join it (no join found, not a finding)
  wrapped compounds: page 2 line 9: "manage-ment" is split across lines; extracted text reads "management" (note: "management" also appears unwrapped, nothing to fix)
```

## 7. Output and exit

One status line per file, in argument order:
- `OK    <path>: <h> split compounds looked at, 0 findings (control found)`. Then one hit line per hit, in page and line order, or `  wrapped compounds: none` when `<h>` is 0.
- `FAIL  <path>: <k> finding(s); lines marked "finding" need a fix, other lines are for information`, then every hit line in page and line order, then the line `  next: reword or change the layout so the word does not break at its hyphen, export the PDF again, and run this again`.
- `DEAD  <path>: <reason>`. A DEAD file gets no other line. DEAD means no verdict, not a pass; the reason says why and what to do (§ 3).

Exit `0` when every file is OK; `1` when at least one file FAILs and none is DEAD; `2` when any file is DEAD or the run cannot go ahead. The highest applies. A failed write to standard output follows `barred.md` § 7, case 8. Exit 2 outranks exit 1: when one file is DEAD and another FAILs, read every status line, not only the exit code.

Hit lines quote words from the user's own file (the compound and the token, as prepared by § 3 step 1, so a ligature or a format character shows in its folded form). That is the point of the check, and it differs from `barred`, which never quotes text because it matches a list the user keeps private.

## 8. Known limits (stated in the guide)

- **Columns.** In a page with two or more columns, one layout line holds more than one column, so a hyphen at the end of a left-column line is not at the line's end and is missed (W9). The check reports what it finds and does not claim it found every wrap.
- Only hyphen-minus is read, with its fullwidth and small forms. Other dashes are not.
- **Soft hyphens are invisible here.** A word broken at a soft hyphen (U+00AD) is not reported. This differs from `barred`, which reads a line-end soft hyphen as a hyphen; turn off automatic hyphenation to avoid both.
- A right half shorter than 3 letters joins on its whole length, so a short prefix can join the wrong token on a crowded page.

**Guide sentence (exact, for § 9):** "A word your word processor broke at the end of a line, such as manage- / ment, looks the same as a wrapped compound. If the joined word also appears unbroken elsewhere in the file, the line is a note, not a finding. To clear both, turn off automatic hyphenation or widen the line so the word doesn't wrap."

## 9. When `track-record parse` ships (not a dependency)

If spec 1 is signed and built, `parse` calls the same function and prints the same hit lines inside its own block, under its own DEAD rules and its `--name` in place of `--control`. The stand-alone command stays. Nothing in this spec waits on that.

## 10. Cases

The pure function takes the two prepared texts and returns the hits. Text cases call it with literal raw strings, which it prepares itself (§ 3 steps 1 to 3): `L` is the layout text, `D` the default text, and `\f` a form feed. PDF cases run the command on PDFs generated in the test run by `tests/fixtures/barred/make_fixtures.py`, the generator the existing PDF tests use.

**PDF cases**
- **W1, planted positive, and the premise.** One page from `pages_pdf`: `PAD_LINE` (the generator's padding line, which holds `Example Corp`) twelve times, then the lines `The well-` and `known results held.`, then `PAD_LINE` twelve times. Run with `--control "Example Corp"`. Expected: `FAIL`, the hit line `page 1 line <n>: "well-known" is split across lines; extracted text reads "wellknown" (finding)`, where `<n>` is the line `well-` is on in that fixture's layout text, asserted from the fixture and not hard-coded. Exit `1`.
- **W2, negative control.** The same page with the two middle lines written as one line, `The well-known results held.`, so nothing wraps. Run with `--control "Example Corp"`. Expected: `OK … 0 split compounds looked at`, `wrapped compounds: none`, exit `0`. W1 and W2 together show the check can both fire and stay quiet.
- **W12, `pdftotext` missing** (the test removes it from `PATH`). Expected: DEAD with `barred`'s reason for the same case, exit `2`.
- **W13, control not found.** W2's PDF with `--control zzqx` (a string the padding and the text don't hold). Expected: `DEAD  <path>: control not found; check that the text in the PDF can be selected`, no other line, exit `2`.

**Text cases**
- **W3, Unicode letters.** `L = "bien-\nêtre\n"`, `D = "bienêtre\n"`. Expected: hit `bien-être`, `(finding)`.
- **W4, not letters.** `L = "2026-\n27\n"`. Expected: no hit.
- **W5, blank line between.** `L = "well-\n\n  known\n"`, `D = "wellknown\n"`. Expected: hit at line 1, `(finding)`.
- **W6, page edge.** `L = "well-\f known\f"`, `D = "wellknown\f\f"`. Expected: no hit. With the trailing segment dropped there are two pages each, and a wrap line that is last on its page is not a hit.
- **W7, broken word, appears once.** `L = "manage-\nment\n"`, `D = "management\n"`. Expected: `(finding)`.
- **W7a, note case.** `L = "manage-\nment\fmanagement\f"`, `D = "management\fmanagement\f"`. Expected: `(note: "management" also appears unwrapped, nothing to fix)`, no finding, exit `0`. Variant: `L = "manage-\nment\fmanagement manage-ment\f"`, `D = "management\fmanagement manage-ment\f"`. Expected: `(finding)`, exit `1`.
- **W8, default keeps the hyphen.** `L = "well-\nknown\n"`, `D = "well-known\n"`. Expected: `(no join found, not a finding)`, no finding. `well-known` is a single token, and it does not start with `wellkno`.
- **W9, two columns pinned.** `L = "alpha well-     beta\nknown gamma\n"`. Expected: no hit (the hyphen is not at the line end). If a later fix finds it, this case changes on purpose.
- **W10, soft hyphen.** `L = "well­\nknown\n"`. Expected: no hit (step 1 removes the soft hyphen).
- **W11, same pair twice, one join.** `L = "well-\nknown a\nwell-\nknown b\n"`, `D = "wellknown a well-known b\n"`. Expected: line 1 `(finding)` with `"wellknown"`, line 3 `(no join found, not a finding)`.
- **W14, chained left half and punctuation.** `L = "the state-of-the-\nart, today\n"`, `D = "the state-of-theart, today\n"`. Expected: hit `"state-of-the-art" is split across lines; extracted text reads "state-of-theart" (finding)`.
- **W15, fullwidth hyphen-minus.** `L = "well\uff0d\nknown\n"`, `D = "wellknown\n"`. Expected: hit `"well-known"`, `(finding)` (step 1 folds U+FF0D to U+002D). The same with the small form U+FE63.

## 11. Done when

- W1 to W15 and W7a pass in CI on the supported Python versions. W1 confirms the premise on the poppler that CI runs, and the release record (the CHANGELOG entry for the release) names that poppler version.
- The guide carries the sentence of § 8 word for word, the other known limits (soft hyphens included), and an example of each of the three markers.
- The ninth tool is reflected everywhere the tool count or tool list lives: `AGENTS.md` ("Eight tools ship"), the README tools table and its exit-code lines, `docs/specs/cli.md` (with the top-level help list line `- wrapped-compounds: find hyphenated words split across two lines in a PDF`, which tests pin, so the product read sees it), the CHANGELOG entry, and this spec under `docs/specs/` with a revision line like `barred.md`'s.
- The release's usual reads have passed before the push.
<!-- signed spec ends -->
