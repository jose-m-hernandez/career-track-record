# `track-record claims`

Keep a claims list: the sentences you have approved for your copy. The claim gate reads each file you name and fails on any sentence the list has not approved. A sentence you change is a new sentence, so it fails until you approve it again. The gate never decides whether a claim is true. Approving it is yours.

The list is a UTF-8 text file with one entry per line. Each entry has tab-separated fields: a status, the sentence, and, if you like, a source. The status is `approved`, `proposed` or `refused`. `proposed` lists a sentence you have not decided on, and it does not pass. `refused` records a claim you turned down, so the sentence fails with that reason if it comes back. A source can be anything you like: a file path, a URL or a record id. It is never printed, and only `--check-sources` reads it, as a file path relative to the folder that holds the list. Anything after a third tab is a note, which is never matched or printed. A line starting with `#` is a comment. This list is invented, with a tab between fields:

```text
# invented list
approved	Led a team of six engineers at Example Corp.	notes/offer-letter.txt
approved	Shipped the Example importer in 2021.
approved	Joined Example Corp. in 2019.	notes/start.txt	invented note
approved	Built an end-to-end import pipeline.
proposed	Cut build times by forty percent.	notes/draft.txt
refused	Increased revenue tenfold.
```

Every sentence is checked, short ones and contact lines included, because a short sentence can carry a claim. Each bullet and each heading starts a new sentence, with or without a final full stop. Matching is exact after folding, so case, ligatures, invisible characters, curly quotes, the hyphens U+2010 and U+2011 and one final full stop make no difference. An entry never matches part of a sentence, and a sentence that holds an entry plus more words is not covered by it.

Every run names a control phrase that must appear in each file. Give `--control` more than once and any one counts. A file without the control, or with no sentence to check, is reported DEAD, never OK. If a file you name is the list itself (a pattern such as `*.txt` can pick it up), it is also reported DEAD: the list is never checked as text, and the line names it by its position, such as `file #2`, never by its path.

    track-record claims --list claims.txt --control "Your Name" profile.md letter.md

Add `--stale-check` to also report approved entries that no file uses.

Add `--check-sources` to check your evidence too. Under an entry that has a source, write a `quote` line: `quote`, a tab, then a phrase that should appear word for word in that source. This check is a port of an evidence-check method in which a quote must appear in the source it cites. With the flag, each `approved` and `proposed` entry that has a quote is checked against its source, whether or not a file used it; `refused` entries are never checked. The quote is matched after the same folding as a sentence, and must start and end on word boundaries; a quote that ends in a number is not found inside a longer number, so `Version 2.` is not found in `Version 2.5`. Only UTF-8 text files and PDFs (through `pdftotext`) are read. A source that is not a local file at all, such as a URL, a record id, a missing path or a name too long for any file, is reported unverified and nothing is read. This invented entry has a quote, with a tab between fields:

```text
approved	Led a team of six engineers at Example Corp.	evidence/offer.txt
quote	will lead a group of six engineers
```

After the file lines and any stale lines, the gate prints one line for each checked quote that is not found (`approved, entry #1: quote not found`), whose source cannot be read (`source unreadable (not UTF-8)`, with the reason), or that is unverified (`source unverified`), then two count lines, one for approved entries and one for proposed ones, such as `quotes, approved: 1 found, 0 not found, 0 unreadable, 0 unverified`. These lines name an entry only by its number and status: they never print a quote, a source, its path or its text. An approved quote not found makes the run exit at least 1, and an approved source that cannot be read makes it exit 2. An unverified quote is printed and counted but does not change the exit code, and a proposed entry never changes it.

For each file the gate prints one line, OK, FAIL or DEAD. After a FAIL line comes one line for each unapproved sentence, or each run of sentences that one entry covers: the file, the line number, the reason (`unlisted`, or `proposed` or `refused` with the entry number) and the sentence as it stands in the file. A stale entry prints as `stale entry #N`. The output prints only text from the file you check. It never prints a source, a note, the path of your list or the sentence of an entry your files never used, and it names an entry only by its number. The gate knows your list by the file itself, not by what it holds: a copy of the list under another name is checked like any file, and its findings can print the sources, quotes and notes it holds.

Take the list above and a file `copy.txt` that holds one line, `Led a team of seven engineers at Example Corp.`:

    track-record claims --list claims.txt --control example copy.txt
    FAIL  copy.txt: 1 of 1 sentences not approved
    copy.txt:1: unlisted: Led a team of seven engineers at Example Corp.

The list approves a team of six, so the changed sentence is a new one and fails. The run exits 1.

Markdown marks such as `**` count as ordinary text. A word that layout split with a hyphen at a line end fails until you fix it or approve it with the hyphen.

Exit 0 means every file is OK. Exit 1 means a sentence is not approved, with `--stale-check` an approved entry no file uses, or with `--check-sources` an approved quote not found. Exit 2 means a file is DEAD, with `--check-sources` an approved entry's source cannot be read, or the gate couldn't run, for example because no file or control was named, or the list has an unknown status, two entries for one sentence, or a quote line it can't use (before the first entry, a second one for an entry, under an entry with no source, or with no quote). Spec: [docs/specs/claims.md](../specs/claims.md).
