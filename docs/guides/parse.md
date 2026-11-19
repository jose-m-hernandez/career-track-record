# `track-record parse`

This command cannot tell what any particular hiring system will accept. It shows what the program `pdftotext` gets out of your résumé PDF, and a file can pass here and still be misread by one system. A pass means the checks below found nothing to fix. It does not mean a given system will read the file the way you expect.

Run it on the final PDF, after your last edit. Give your full name as it appears in the PDF with `--name`; every run needs it, so a file read as blank or garbled can't pass as clean. Give each email, phone number or link that should be on page 1 with `--contact`, written as it appears in the PDF. You can give `--contact` more than once.

What it checks, in this order:

- Text on every page: a page with fewer letters or digits than `--min-page-chars` (20 by default) is reported as having little or no text, as a scanned page would.
- Your name: it must be on page 1.
- Each contact: it should be on page 1.
- Section headings: it looks for common English names such as Experience or Skills. By default `experience` and `skills` must be there; `--sections` changes that to any of `experience`, `education`, `skills`, `summary`, `projects` and `certifications`, separated by commas.
- Date formats: it counts the formats your date ranges use, and more than one format is a finding.
- Wrapped compounds: a hyphenated word split across two lines, as the [wrapped-compounds](wrapped-compounds.md) check finds it.

The command reads no configuration and writes nothing. Its only inputs are its arguments and the files they name. The runs below use `examples/good.pdf`, a made-up résumé that ships with the repository, and are run from the repository root.

An OK run:

    track-record parse --name "Ada Example" --contact ada@example.com examples/good.pdf
    OK    examples/good.pdf
      text: 2 pages, 2 with text
      name: page 1
      contact "ada@example.com": page 1
      sections: experience found (page 1 line 3: Experience), skills found (page 1 line 12: Skills), education found (page 1 line 9: Education)
      dates: 1 format (Mon YYYY 5)
      wrapped compounds: none

A run with a finding, here a contact that is not in the file:

    track-record parse --name "Ada Example" --contact ada@example.com --contact nobody@example.com examples/good.pdf
    FAIL  examples/good.pdf: 1 finding; fix them in the document the PDF was made from, make the PDF again, and run this again
      text: 2 pages, 2 with text
      name: page 1
      contact "ada@example.com": page 1
      contact "nobody@example.com": not found
      sections: experience found (page 1 line 3: Experience), skills found (page 1 line 12: Skills), education found (page 1 line 9: Education)
      dates: 1 format (Mon YYYY 5)
      wrapped compounds: none

A run with no verdict, here a name that is not in the file:

    track-record parse --name "Bo Example" examples/good.pdf
    DEAD  examples/good.pdf: name not found; check that the name you gave matches the PDF, and that its text can be selected
      text: 2 pages, 2 with text

When a wrapped-compounds line is marked `(finding)`, this is the next step:

    next: reword or change the layout so the word does not break at its hyphen, export the PDF again, and run this again

`parse` does not print that line inside its block, so it is given here. It applies only when a wrapped-compounds line is marked `(finding)`. A line marked `(note: ...)` or `(no join found, not a finding)` needs nothing.

## Exit codes

Exit 0 means every file is OK. Exit 1 means at least one file has a finding and no file is DEAD. Exit 2 means no verdict: a file is DEAD, or the command could not run. 2 is not a pass: when one file is DEAD and another is OK, read every block, not only the exit code.

A DEAD line gives its reason after the path:

- `not a PDF; give the PDF file`: the name does not end in `.pdf`. Give the PDF file.
- `cannot read`, `pdftotext not found` or `pdftotext failed`: the file could not be opened, `pdftotext` (part of poppler) is not installed, or it could not read the file. An encrypted PDF, or one that takes `pdftotext` more than 60 seconds, ends as `pdftotext failed`. Check the path, install poppler, or export the PDF again without a password.
- `no text; the PDF holds no selectable text (a scan?), so export it again from the document`: not one page holds a letter or digit. Export the PDF again from the document it was made from, not from a scan or a picture.
- `no layout text; export the PDF again` and `page counts differ (default <a>, layout <b>); export the PDF again`: the file gave no usable layout reading, or the two readings disagree. Export the PDF again.
- `name not found; check that the name you gave matches the PDF, and that its text can be selected`: your name is on no page. Check the spelling against the PDF, give the full name, and make sure the text can be selected.

## Known limits

- It cannot tell a page header or footer region from the body of the page.
- It does not check reading order in a page with several columns. It reports what `pdftotext` gives and says nothing about the order.
- It knows English section names only.
- A date range must sit on one line. A range whose two dates are on different lines is not counted.
- Day-first dates are misread: `03/02/2019` meant as 3 February is read as March 2, and `13/02/2019` is not counted at all.
- Phone numbers match only as written: `(555) 010-0000` does not match `555-010-0000`.
- A name split across a page break is not found on either page.
- The default of 20 letters or digits for a page is a judgment, not a measurement on a sample of résumés.
- Give the full name. A one-word name can be found inside an email address, since `Example` is found in `ada@example.com`.

Spec: [docs/specs/parse.md](../specs/parse.md).
