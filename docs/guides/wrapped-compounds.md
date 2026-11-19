# `track-record wrapped-compounds`

A hyphenated word such as `well-known` can break at its hyphen when a line ends: `well-` on one line and `known` on the next. On screen the PDF looks right. But some programs that read the PDF's text, including the `pdftotext` program this check uses, drop the hyphen and the line break and join the halves into `wellknown`, a word that no reader or keyword search will match. This check finds each such word, so you can fix it before you send the file. It was measured with poppler 26.07.0: `pdftotext` joins at a wrapped hyphen there, and the check is built on that. Only `pdftotext` was measured. It stands in for the other programs that read a PDF's text, and none of them was tested.

Run it on the final PDF, after your last edit, and name text that must be in the file, such as your name, with `--control`:

    track-record wrapped-compounds --control "Your Name" resume.pdf

Every run needs a control, so a file read as blank or garbled can't pass as clean. If none of your controls is found in the file, it is reported DEAD, never OK. You can give `--control` more than once; finding any one is enough. A control that is empty after trimming is ignored; if every control is empty, the command stops with `cannot run: no usable --control given`.

If you then check text you took from a PDF with `track-record keywords`, run this check first. A word split at its hyphen can read as `crossfunctional` in that text, so a term whose pattern is `cross-functional` finds no use of it, and the scan reports a gap for it when your PDF does use it.

From a clone, in the repository's own test fixtures (`tests/fixtures/barred/`), the check gives:

    cd tests/fixtures/barred
    track-record wrapped-compounds --control Example\ Corp hyphmid.pdf sample.pdf
    FAIL  hyphmid.pdf: 1 finding(s); lines marked "finding" need a fix, other lines are for information
      wrapped compounds: page 1 line 13: "zebra-word" is split across lines; extracted text reads "zebraword" (finding)
      next: reword or change the layout so the word does not break at its hyphen, export the PDF again, and run this again
    OK    sample.pdf: 0 split compounds looked at, 0 findings (control found)
      wrapped compounds: none

`hyphmid.pdf` has `zebra-` at the end of a line and `word` at the start of the next, so it fails and the line says where. `sample.pdf` has no split hyphenated word, so it is OK. The run exits 1 because of the first file.

## What the three markers mean

Each line about a split word ends in one of three markers.

    wrapped compounds: page 1 line 14: "well-known" is split across lines; extracted text reads "wellknown" (finding)

A finding: the extracted text joined the halves into `wellknown`. Reword, or change the layout so the word does not break at its hyphen, then export the PDF again.

    wrapped compounds: page 2 line 3: "cross-team" is split across lines; extracted text does not join it (no join found, not a finding)

Not a finding: no word in the extracted text was free to match. The text kept the hyphen, or broke the line in a way this check does not model. Nothing to fix here, and the line is for your information.

    wrapped compounds: page 2 line 9: "manage-ment" is split across lines; extracted text reads "management" (note: "management" also appears unwrapped, nothing to fix)

A note: not a finding. A word your word processor broke at the end of a line, such as manage- / ment, looks the same as a wrapped compound. If the joined word also appears unbroken elsewhere in the file, the line is a note, not a finding. To clear both, turn off automatic hyphenation or widen the line so the word doesn't wrap.

A word that was broken and appears only once can't be told from a compound, so it stays a finding.

## Exit codes

Exit 0 means no split hyphenated word needs a fix. It checks nothing else about the file. Exit 1 means at least one finding. Exit 2 means no verdict: a file is DEAD, or the command could not run. 2 is not a pass: when one file is DEAD and another fails, read every status line, not only the exit code.

A DEAD line gives its reason after the path:

- `not a PDF; give the PDF file`: the name does not end in `.pdf` in any case.
- `cannot read`, `pdftotext not found` or `pdftotext failed`: the file could not be opened, `pdftotext` (part of poppler) is not installed, or it could not read the file. Check the path, install poppler, or export the PDF again.
- `no text; the PDF holds no selectable text (a scan?), so export it again from the document`, `no layout text; export the PDF again` and `page counts differ (default <a>, layout <b>); export the PDF again`: the file gave no usable text, or the two readings disagree. Export the PDF again.
- `control not found; check that the text in the PDF can be selected`: none of your controls is in the file.

## What it does not check

It checks only hyphenated words split at the end of a line, in PDFs. It does not check words broken without a hyphen, scanned images, spelling, tone or anything else about the file. The command reads no configuration file and writes nothing; its only inputs are its arguments, the files they name, and the `pdftotext` program that your `PATH` finds. Hit lines quote words from your own file, the compound and the word the text extraction made of it, which is the point of the check.

## Known limits

- **Columns.** In a page with two or more columns, one line of the layout text holds more than one column, so a hyphen at the end of a left-column line is not at the end of that line and is missed. The check reports what it finds and does not claim it found every wrap.
- Only the hyphen-minus is read, with its fullwidth and small forms. Other dashes are not.
- **Soft hyphens are invisible here.** A word broken at a soft hyphen (U+00AD) is not reported. This differs from `barred`, which reads a soft hyphen at the end of a line as a hyphen. Turn off automatic hyphenation to avoid both.
- A right half shorter than 3 letters joins on its whole length, so a short prefix can join the wrong word on a crowded page.

Spec: [docs/specs/wrapped-compounds.md](../specs/wrapped-compounds.md).
