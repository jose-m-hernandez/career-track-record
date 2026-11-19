# `track-record parse`: behaviour spec

Status: accepted.
Date: 2026-11-19.
Revision: 5. The signed public edition (sha256 90800e13a23122829da577aec6f3559f8d5a96f2b7e97688896e1b36138dd7ae) is reproduced below verbatim. Its owner signed it. It is the first signed text of this command in this repository.

## Signed spec

<!-- signed spec begins: sha256 90800e13a23122829da577aec6f3559f8d5a96f2b7e97688896e1b36138dd7ae -->
# CTR spec (1): `track-record parse`

Depends on: `src/career_track_record/pdf_text.py` as shipped, in both modes (default, and `layout=True` for spec (2)'s check only); `docs/specs/barred.md` (folding, printed paths, the reasons for an unreadable file); spec (2), whose pure function `parse` calls. No new program.
Size: small to medium. One module, one shipped data file of section names, one shipped invented example PDF, one guide page, and 33 cases: 9 on generated PDFs, 19 on literal text through the pure function, and 5 on usage and output.

Every example here is invented. None comes from a real person's résumé, posting, employer or results.

## 1. Problem

A résumé PDF can look right on screen and still give a text extractor something else: no text at all (a scanned or image-only page), a name and contact line that never reach the text, headings no reader would take for sections, or dates in three different shapes. Someone sending a PDF to a form that extracts it by machine has no quick way to see what the text holds. CTR already extracts PDFs this way for `barred`, `claims` and `ab`, but no command reports on the extracted text itself.

## 2. Synopsis

```text
usage: track-record parse --name TEXT [--contact TEXT]... [--sections LIST]
                          [--min-page-chars N] FILE...

Shows what a program that reads a PDF's text gets from your résumé: whether
there is text on every page, whether your name and contact details are on
page 1, which common English section headings (such as Experience or Skills)
it can see, how many date formats your date ranges use, and whether a
hyphenated word is split across two lines.

It cannot tell what any particular hiring system will accept. A file can
pass here and still be misread by one.

  --name TEXT          your name as it appears in the PDF (required); if it is
                       not found the file is reported DEAD (it could not be
                       checked)
  --contact TEXT       an email, phone number or link, written as it appears
                       in the PDF, that should be on page 1; repeatable
  --sections LIST      section families that must appear, separated by commas
                       (default: experience,skills); families: experience,
                       education, skills, summary, projects, certifications
  --min-page-chars N   a page with fewer letters or digits than this is
                       reported as having little or no text (default 20)
  -h, --help           show this summary and exit

exit: 0 no finding, 1 a finding, 2 no verdict (a file is DEAD, or the command
      could not run); 2 is not a pass
```

- `FILE` is positional and repeatable, and files are checked in argument order.
- `-h` / `--help` writes the summary above and exits 0. It reads no file and wins over every other argument. `--` ends options. A path that starts with `-` is passed to `pdftotext` as `./` followed by the path, as `barred` passes one (`barred.md` § 3.2). The path is printed as given.
- Options are parsed as `barred`'s are (`barred.md` § 3.0): `--opt=VALUE` is the same as `--opt VALUE`, after `--` every argument is a file name, a lone `-` is a file name, and an argument that is exactly `-h` or `--help` asks for help wherever it stands. Each option given twice is a usage error, except `--contact`.
- **Usage errors** exit 2 before any file is read, with one line on standard error that begins `cannot run: `. Errors 1 to 3 are found while the arguments are read from left to right, and the first one found is printed. Errors 4 to 9 are then checked in the order listed. The parse follows `barred`'s in everything but the unknown-option line, which names the option as `claims`'s does:
  1. an unknown option: `cannot run: unknown option <opt>`, the option escaped as a printed path, as `claims` prints it;
  2. an option without its value: `cannot run: <opt> needs a value`;
  3. an option given twice where only once is allowed: `cannot run: <opt> given twice`;
  4. no `FILE`: `cannot run: no input file` (`barred`'s words);
  5. no `--name`: `cannot run: give --name, your name as it appears in the PDF`;
  6. a `--name` or `--contact` empty after preparing (§ 3a): `cannot run: <opt> is empty`;
  7. `--min-page-chars` that is not a whole number from 1 up, or has more than 18 significant digits: `cannot run: --min-page-chars takes a whole number of 1 or more`. 0 would stop the no-text guard from ever firing;
  8. `--sections` that is empty, holds an empty item (`a,,b`, a trailing comma), or names an unknown family (an empty item gives `cannot run: --sections: empty family name`): `cannot run: --sections: unknown family <name>; families: experience, education, skills, summary, projects, certifications`;
  9. the shipped section list missing or malformed: `cannot run: the shipped section list is missing or damaged; reinstall`.
- A failed write to standard output follows `barred.md` § 7, case 8.

## 3. Text preparation (shared with spec 2)

Each file is read twice through `pdf_text`: the **default text**, which every check of § 4 reads, and the **layout text**, which only spec (2)'s check reads. Both are prepared by spec (2) § 3, steps 1 to 3, word for word. Those steps are not restated here, so the two specs cannot drift apart:

1. **Normalise** (NFKC, then remove category Cf; case kept for printing).
2. **Pages:** split at form feeds, drop the single empty segment after the last form feed, and number pages from 1. A two-page file is two pages.
3. **Lines:** LF, CRLF or a lone CR end a line, and nothing else does (never `str.splitlines()`). Lines are numbered from 1 at the top of each page, blank lines included.

## 3a. Matching name and contacts

- `--name` and each `--contact` are **folded and prepared** as `barred.md` § 4 folds and prepares a control (NFKC, full case folding, NFKC, Cf removed, whitespace runs to one space, trimmed).
- Each page's default text is folded and prepared the same way, **page by page**. `barred`'s own preparation collapses form feeds into spaces, so this must be done per page, after step 2.
- A name or contact is found on a page when it occurs as a substring of that page's prepared text, and the character before and the character after are each absent or a boundary character (`barred.md` § 4's `word` rule: anything not a letter and not a decimal digit).

So a line break or a ligature inside the name doesn't cause a miss. A one-word name can still be found inside an email address (`Example` in `ada@example.com`, since `@` and `.` are boundaries). The guide says to give the full name. A name split across a page break is found on neither page.

## 4. The checks, in order

### 4.1 Text on each page

The count for a page is its letters and digits (Unicode categories L and Nd) after step 1. The replacement character U+FFFD, which `pdf_text` writes for bytes it can't decode, counts as neither.

- A page whose count is below `--min-page-chars` is reported `page <n>: little or no text (<count> letters or digits)`. This is a finding.
- If **no page holds a single letter or digit**, the file is DEAD with `no text; the PDF holds no selectable text (a scan?), so export it again from the document`. That is spec (2)'s reason, with spec (2)'s meaning (spec (2) § 3). A file in which every page is below the threshold but some page holds a letter or digit is not DEAD: each low page gets its line (a finding), and the other checks run.

**The default of 20, and its basis.** It is set to catch a page that came out as an image and carries at most a page number or a short running header. A page with any real résumé text holds far more than 20 letters or digits, so a short last page passes. 20 is a judgment, not a measurement on a sample of résumés. The guide says so.

### 4.2 Name

- Found on page 1: `name: page 1`.
- Found first on a later page: `name: found on page <n>, not page 1`. This is a finding.
- Found on no page: the file is DEAD with `name not found; check that the name you gave matches the PDF, and that its text can be selected`. The remedy doesn't name `--name`, because `build` prints this block with the name taken from the résumé file. The name is the file's planted control, so no other check vouches for text that doesn't hold it.

### 4.3 Contacts

One line for each `--contact`, in argument order:
- `contact "<TEXT>": page 1`;
- `contact "<TEXT>": found on page <n>, not page 1`, a finding;
- `contact "<TEXT>": not found`, a finding.

`<TEXT>` is printed as the user typed it, escaped as a printed path is (`barred.md` § 6). With no `--contact`, no contact line prints. Phone numbers match only as written: `(555) 010-0000` doesn't match `555-010-0000`. The guide lists this limit.

### 4.4 Section headings

**The list.** `data/section-names.txt` is UTF-8 with no byte-order mark. Each entry is a line `<family><TAB><heading>`. Blank lines, and lines whose first character is `#`, are ignored. Headings are folded and prepared (§ 3a) when the file is loaded. The file is loaded once per run, before any PDF is read, and loaded as `data/tone-default.json` is, and packaged through `setup.cfg` (§ 9). A missing file, a line with no tab, an unknown family or an empty heading is usage error 9. The shipped entries:

| Family | Headings |
|---|---|
| experience | experience, work experience, professional experience, relevant experience, employment, employment history, work history, career history |
| education | education, education and training, academic background |
| skills | skills, technical skills, core skills, key skills, skills and tools |
| summary | summary, professional summary, profile, about, about me, objective |
| projects | projects, selected projects, personal projects |
| certifications | certifications, certificates, licenses and certifications, licences and certifications |

**A heading** is a line of the default text whose folded and prepared text, with one trailing `:` removed, equals one heading in the list. Each family takes the **first** heading of that family in page and line order.

**`--sections`** is a comma-separated list of family names, each folded and trimmed. A family named twice counts once.

**Printed:** `sections:` and then, separated by `, `, each required family in the order the list file gives them (`<family> found (page <p> line <l>: <heading as printed>)` or `<family> missing`), then each family that was found but not required, in the same order and shape. A missing required family is a finding. A family that is neither required nor found is not printed. A line that looks like a heading but matches no entry isn't guessed at or reported.

### 4.5 Date formats

Dates are counted only where they form a **range**, on a single line of the default text after step 1, matched on the case-folded line from left to right without overlap.

- **A date** is one of these classes, tried in this order (longest first) at each position:
  1. `MM/DD/YYYY`: month `0?[1-9]|1[0-2]`, `/`, day `0?[1-9]|[12][0-9]|3[01]`, `/`, year;
  2. `MM/YYYY`: month, `/`, year;
  3. `YYYY-MM`: year, `-`, a two-digit month `0[1-9]|1[0-2]`;
  4. `Mon YYYY`: a month name, an optional `.`, one or more spaces or tabs, then a year. The month names are `jan`, `january`, `feb`, `february`, `mar`, `march`, `apr`, `april`, `may`, `jun`, `june`, `jul`, `july`, `aug`, `august`, `sep`, `sept`, `september`, `oct`, `october`, `nov`, `november`, `dec`, `december`;
  5. `YYYY`: a year.

  A **year** is `19[0-9][0-9]` or `20[0-9][0-9]`. A date must not touch a letter, a digit or `/` on either side. That rule keeps `2017-2019` from reading as `2017-20` followed by `19`, and keeps the `02/2019` inside `13/02/2019` from counting.
- **A range** is a date, then optional spaces or tabs, then one separator, then optional spaces or tabs, then a date or one of `present` or `current`, which must not be followed by a letter or digit (so `Presentation` is not an end). The separators are `-` (U+002D), `–` (U+2013), U+2014 (the em dash), or the word `to` with a space or tab on each side. A range whose two halves sit on different lines is not counted. The guide lists that as a limit.
- Each range counts its dates: two, or one when it ends in `present` or `current`.
- **Known limit:** a day-first date with a day of 12 or less (`03/02/2019` meant as 3 February) is classed `MM/DD/YYYY`. One with a day of 13 or more matches no class.

**Printed:** `dates: <k> format(s) (<class> <count>, …)`, classes in descending count, ties in the class order above. More than one class is a finding. With no range: `dates: no date ranges found`, which is not a finding.

### 4.6 Wrapped compounds (spec 2)

`parse` reads the layout text as well and calls spec (2)'s pure function (spec (2) § 10) with the two raw texts. The build names it `find_wrapped_compounds(default_raw, layout_raw)`. It returns a list of hits in page and line order, each holding: the page, the line, the compound as printed, the joined token or none, and one of the three markers of spec (2) § 6. `parse` prints each hit with spec (2)'s hit-line format.
- Spec (2)'s extra DEAD reasons apply here word for word, each checked when the layout read is made, after § 4.1 and before § 4.2: `pdftotext` failing or missing on the layout read (`barred`'s reason), `no layout text; export the PDF again`, and `page counts differ (default <a>, layout <b>); export the PDF again`.
- Each hit prints as spec (2) § 6 prints it, indented under the block. A `(finding)` hit makes the file FAIL. A `(note: …)` or `(no join found, not a finding)` hit does not.
- With no hits: `wrapped compounds: none`.
- Spec (2)'s `next:` line is not printed inside `parse`'s block. The guide carries it.

## 5. DEAD, in order

A file is DEAD at the first of these that holds. Each line is `DEAD  <path>: <reason>`. Reasons 1 and 4 to 6 name their next step. Reasons 2 and 3 are `barred`'s words, word for word; the guide says what to do.
1. `not a PDF; give the PDF file`: the name doesn't end in `.pdf` (any case), as in `barred.md` § 3.2 and spec (2). A file named `.pdf` that isn't a PDF reaches `pdftotext`, which fails on it (reason 3).
2. `cannot read`: the file can't be opened or read (`barred`'s reason, `barred.md` § 7, case 6).
3. The default read: `pdftotext not found` or `pdftotext failed` (`barred`'s reasons). An encrypted PDF, or one `pdftotext` takes more than 60 seconds on, ends here as `pdftotext failed`.
4. `no text; …` (§ 4.1).
5. The layout read: `pdftotext` not found or failed, `no layout text; …`, or `page counts differ …` (§ 4.6).
6. `name not found; …` (§ 4.2).

A DEAD block prints its status line and then the lines of the checks that ran before it. So reasons 1 to 3 print no other line, reasons 4 and 5 print the `text:` line and the low-page lines, and reason 6 prints those as well.

## 6. Output and exit

**Block grammar,** one block per file in argument order:

```text
<STATUS>  <path>[: <reason>]          STATUS is OK, FAIL or DEAD; a reason for DEAD and FAIL
  text: <p> page(s), <q> with text     q = pages at or above --min-page-chars
  page <n>: little or no text (<c> letters or digits)      zero or more, by page
  name: …                              § 4.2
  contact "<TEXT>": …                  zero or more, argument order
  sections: …                          § 4.4
  dates: …                             § 4.5
  wrapped compounds: …                 § 4.6, one line per hit, or "none"
```

OK and FAIL blocks print every line. `OK    <path>` carries no reason. A FAIL status line is `FAIL  <path>: <k> finding(s); fix them in the document the PDF was made from, make the PDF again, and run this again`, where `<k>` counts: each `page <n>: little or no text` line; the name, when it is found only on a later page; each contact that is not found or is found only on a later page; each missing required section; the dates line, when it shows more than one format; and each `(finding)` hit of § 4.6. `(s)` is printed as the plain singular or plural (`1 finding`, `2 findings`), here and wherever a line in this spec writes `(s)`. The wording avoids "export" on purpose, since inside `build` the PDF is made by `build`; there is no separate `next:` line. The printed path follows `barred.md` § 6's escaping, with no list involved, so a path is never replaced by `file #<i>`.

**Sample.** `examples/good.pdf` (§ 7), run with `--name "Ada Example" --contact ada@example.com`:

```text
OK    good.pdf
  text: 2 pages, 2 with text
  name: page 1
  contact "ada@example.com": page 1
  sections: experience found (page 1 line <l1>: Experience), skills found (page 1 line <l3>: Skills), education found (page 1 line <l2>: Education)
  dates: 1 format (Mon YYYY 5)
  wrapped compounds: none
```

`<l1>` to `<l3>` are the heading lines in that fixture's default text, taken from `pdftotext` itself in the test and not hard-coded (as `barred.md` § 10.11 takes its line numbers).

**Exit:** `0` when every file is OK; `1` when at least one file FAILs and none is DEAD; `2` when any file is DEAD or the run can't go ahead. The highest applies, and every file's block prints before the exit. Exit 2 outranks 1, so read every block, not only the exit code.

## 7. Cases

Two tiers, as in spec (2) § 10.
- **PDF cases** run the command on PDFs generated in the test run by `tests/fixtures/barred/make_fixtures.py`, through `pages_pdf`. The generator gains `parse_good_pdf` (the base fixture), `parse_name_page2_pdf`, `parse_empty_page2_pdf` and `parse_empty_pdf` (one empty page, for P5). An empty page stands in for an image-only page. That is the text `pdftotext` gives for one.
- **Text cases** call the pure function `check_text(default_raw, layout_raw, name, contacts, sections, min_page_chars)`, which returns the block's lines and its status. Unless a case says otherwise, each is called with `min_page_chars=1`, `name="Ada Example"` and the line `Ada Example` at the top of page 1 of both texts, so the name guard passes and no page is low. When a case gives only `D`, `L` is the same text. Ligatures, en dashes and non-ASCII letters are tested here, so the generator needs no new encodings.

**Base fixture** `good.pdf`, also shipped as `examples/good.pdf`, ASCII only. Page 1 holds `Ada Example`, `ada@example.com`, then the headings `Experience`, `Education` and `Skills`, each on its own line and each followed by two lines of invented text, with three ranges `Jan 2020 - Present`, `Mar 2017 - Dec 2019` and `Jun 2014 - Feb 2017`. Page 2 holds `PAD_LINE` repeated six times. Page 1 holds well over 20 letters and digits (the name and headings alone pass it), so the positive control passes at the default.

**PDF cases**
- **P1, planted positive.** `good.pdf` gives § 6's sample, exit 0.
- **P2, negative control.** `good.pdf` with `--name "Bo Example"` gives `DEAD  good.pdf: name not found; …`, then only the `text:` line, exit 2. P1 and P2 together show the guard can both pass and fire.
- **P3.** The name only on page 2 (`parse_name_page2_pdf`) gives `FAIL  <path>: 1 finding; fix them …`, `name: found on page 2, not page 1`, exit 1.
- **P4.** Page 2 empty (`parse_empty_page2_pdf`) gives `FAIL  <path>: 1 finding; …`, `text: 2 pages, 1 with text`, `page 2: little or no text (0 letters or digits)`, and the other checks run. Exit 1.
- **P5.** A one-page empty PDF gives `DEAD  <path>: no text; …`, the `text:` line and the page line, exit 2.
- **P6.** `pdftotext` removed from `PATH` gives `DEAD` with `barred`'s reason, exit 2.
- **P7.** A stand-in `pdftotext` that answers the default read and fails the layout read gives `DEAD` with `barred`'s failed reason, after the `text:` line. Exit 2. The same stand-in exiting 1 on the default read covers an encrypted file.
- **P8.** Three files (OK, FAIL, DEAD) give three blocks in order, exit 2.
- **P9.** `twocol_pdf` with `--name "Example Corp"` runs without error. Its result is pinned as found, so a later change to column handling shows up as a changed case.

**Text cases**
- **T1.** The name split by a line break inside it (`Ada\nExample`) is found on page 1.
- **T2.** A contact written with `ﬁ` (U+FB01) in the text, given with `fi`, is found.
- **T3.** `Zoë Example` in the text is found by `--name "Zoë Example"` (NFKC).
- **T4.** `--name Example` against a page holding only `ada@example.com` is found. This pins the boundary rule and its stated limit.
- **T5.** A contact on page 2 only gives `found on page 2, not page 1`, a finding. A contact absent everywhere gives `not found`. With no contacts, no contact line prints.
- **T6.** `What I use` in place of `Skills` gives `skills missing`, `FAIL  <path>: 1 finding; …`, and `What I use` is not reported.
- **T7.** `Work Experience:` counts as experience. `Experience at a glance` doesn't.
- **T8.** `--sections experience,education,skills` with no education heading gives `education missing`, a finding. The default `--sections` on the same text prints no education item and passes.
- **T9.** `Projects` present and not required prints `projects found (…)` after the required families, and is not a finding.
- **T10.** `Jan 2020 – Present`, `2017 - 2019` and `03/2014 to 02/2017` give `dates: 3 formats (MM/YYYY 2, YYYY 2, Mon YYYY 1)`, a finding.
- **T11.** `since 2015` in running text isn't counted. `2017-2019` counts two `YYYY` dates, not a `YYYY-MM`.
- **T12.** `Sept. 2019 \u2014 May 2021` (an em dash) counts two `Mon YYYY`. `2019-03 to 2021-11` counts two `YYYY-MM`.
- **T13.** `13/02/2019 - 14/03/2020` counts nothing. `03/02/2019 - 04/05/2020` counts two `MM/DD/YYYY`.
- **T14.** `Jan 2020 -` at a line end with `Present` on the next line counts nothing.
- **T15.** No ranges gives `dates: no date ranges found`, not a finding.
- **T16.** A two-page text with one trailing form feed counts 2 pages, not 3.
- **T17** (called with `min_page_chars=20`). A one-page text holding `Ada Example` and 9 more letters (19 in all) gives `page 1: little or no text (19 letters or digits)`, `FAIL  <path>: 1 finding; …`, and is not DEAD. With `min_page_chars=19` it passes. A page holding only U+FFFD characters counts 0, and a text whose only page holds nothing else is DEAD `no text`.
- **T18.** `L = "Ada Example\nThe well-\nknown results held.\n"`, `D = "Ada Example\nThe wellknown results held.\n"` give the `(finding)` hit line for `well-known` and `FAIL  <path>: 1 finding; …`, with no `next:` line. W7a's note texts, each page with `Ada Example` added at its top, give the note line and OK.
- **T19.** Layout and default texts with different page counts give spec (2)'s DEAD reason after the `text:` line.

**Usage and output**
- **U1.** Each usage error of § 2, in its order, gives its one `cannot run:` line and exit 2 with no file read. Where two errors hold at once, the earlier one is the line printed.
- **U2.** A file name holding a newline or an ESC prints escaped. A path starting with `-` reaches `pdftotext` as `./-…` and prints as given.
- **U3.** The command never writes a file: the folder listing and modification times are the same before and after.
- **U4.** A damaged section list (a line with no tab), swapped in by the test, gives usage error 9.
- **U5.** `-h` prints § 2's summary and exits 0. A failed write to standard output exits 2 with `cannot run: cannot write output`.

## 8. Keep (what does not change)

- **No claim about any hiring system.** The command reports what `pdftotext` extracts. The help and the guide's first paragraph say that it can't tell what any particular system will accept, and that a file can pass here and still be misread by one. The section list is "common English names", not "what systems recognise". No system has been measured, so nothing may imply one has.
- **Known limits, stated in the guide:** it can't tell a page header or footer region from the body; it doesn't check reading order in a multi-column page (P9 pins today's behaviour); it knows English section names only; ranges must sit on one line; day-first dates are misread (§ 4.5); phone numbers match only as written; a name split across a page break isn't found; and the default of 20 is a judgment, not a measurement.
- `pdf_text.py` is unchanged. The command starts no program other than `pdftotext`, writes no file and touches no network.
- No other command's output, exit status or spec changes. `--min-chars` keeps its one meaning, `barred`'s whole-file length.
- The name and contacts are the user's own arguments at run time. They are never shipped and never written to a file. The fixtures, the list and `examples/good.pdf` are invented.

## 9. Done when

- P1 to P9, T1 to T19 and U1 to U5 (33 cases) pass in CI on the supported Python versions, alongside spec (2)'s own W1 to W15 and W7a.
- `docs/specs/cli.md`'s next revision adds `parse` to sections 1, 2, 4 and 5 with the fixed help text of § 2 and the list line `- parse: check what a text extractor gets from your résumé PDF`, and its revision line says so. The command count in cli.md follows what ships.
- This spec is under `docs/specs/` with a revision line like `barred.md`'s.
- The tool count and list follow what ships (if spec (2) ships first, `wrapped-compounds` is the ninth tool and `parse` the tenth), everywhere they live: `AGENTS.md` ("Eight tools ship"), the README's opening line, tools table (row `track-record parse` | "What text comes out of my résumé PDF when a program reads it?" | `docs/guides/parse.md`) and exit-code lines, and the `CHANGELOG.md` entry. `data/section-names.txt` ships in the package: `setup.cfg`'s `[options.package_data]` gains `data/*.txt` beside `data/*.json`, and a packaging test asserts the file is in the built wheel. The package version is bumped in the release.
- `docs/guides/parse.md`: its first paragraph says the command can't tell what any particular system will accept. It opens with runs on the shipped `examples/good.pdf` showing OK, then FAIL, then DEAD, carries spec (2)'s `next:` advice, and lists every known limit of § 8.
- The release's usual reads have passed before the push.
<!-- signed spec ends -->
