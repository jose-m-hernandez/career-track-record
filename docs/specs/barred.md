# Barred-wording check: behaviour spec

Status: draft. Revision 6.4 below is not signed; its owner signs the text between the draft markers as it stands.
Date: 2026-11-05.
Revision: 6.4. A draft: the text between the markers below (sha256 ab59c734e667a3308116a16136dcd8a1d3e42d6708a9d22ae5e0714d9543c243) is revision 6.4 in full. It is revision 6.3's text (sha256 3d1c088238215d69e7610986cd65aeecce451141587ad8abdb27310e0634551c, the whole of this file before this draft) with each PDF also read in layout mode.

## Draft spec (revision 6.4, not signed)

<!-- draft spec begins: sha256 ab59c734e667a3308116a16136dcd8a1d3e42d6708a9d22ae5e0714d9543c243 -->
# Barred-wording check: behaviour spec

Status: revision 6.4, drafted on 2026-11-05 for the owner's signature. Revision 6.4 reads each PDF in layout mode too, a port of a wrapped-compound check method that reads `pdftotext -layout` output; nothing in it comes from any private tool or record.
Date: 2026-11-05.
Revision: 6.4. Answers to the build questions are folded in (sections 3 to 7, 9 and 10). Revision 3 collapses whitespace inside entries, controls and file names (section 4). Revision 4 checks file names in both forms and escapes control characters in printed paths (section 6), and caps `--min-chars` at 18 significant digits (section 7, case 7). Revision 5 adds output that cannot be written and a closed standard error (section 7, case 8), with their known answers in 10.5. Revision 6 names the exact set of whitespace characters (section 4), and adds a third text form that keeps a line-end hyphen, so a hyphenated entry wrapped at its hyphen is caught (sections 4, 6 and 9.3), with known answers in 10.9. Revision 6.1 states the PDF limit inside a page (section 3.2), qualifies the hyphen-kept promise for PDFs to page breaks (sections 4 and 9.3), and pins the limit with a known answer in 10.9. Revision 6.2 adds `-h` and `--help`, with a fixed summary (sections 3.0, 3.4 and 7) and known answers in section 10. Revision 6.3 makes every argument after `--` a file name, so `-- --help` checks a file named `--help` (section 3.0). Revision 6.4 reads each PDF in layout mode too, so a hyphenated entry wrapped at its hyphen inside a page is matched (sections 3.2, 4, 5, 6, 7, 9.3 and 10).

The command is `<cli> barred`.

## 1. Purpose

Report every place a file uses wording from a list the user has barred, without ever printing the barred wording itself, and refuse to call a file clean when the read cannot be trusted.

## 2. Scope

In:
- one list file of barred entries;
- one or more named input files: plain text, Markdown, source files (with comments and note values stripped on request) and PDFs;
- each input file's name, which is checked as well as its text;
- text folding, so that a wrap, a ligature, a case difference or an invisible character cannot hide a match;
- a positive control on every file.

Out:
- rewriting, suggesting or ranking wording;
- fetching files over the network;
- any decision about what belongs on the list. The list is the user's data;
- scanning a whole repository, its history, commit messages, author identities or branch names. The repository's CI scanner keeps that job (section 9, decision 1).

## 3. Inputs

### 3.0 Options

| Option | Meaning |
|---|---|
| `--list FILE` | The list file. Given at most once. |
| `--control TEXT` | A control string. May be given more than once (section 3.3). |
| `--strip-comments` | Strip comments and note values before matching (section 3.2). |
| `--min-chars N` | The minimum length (section 5). `N` is a whole number, 0 or more, with at most 18 significant digits (leading zeros don't count). Default 500. |
| `-h`, `--help` | Write the fixed summary of section 3.4 to standard output and exit `0`. It reads no list (neither `--list` nor `BARRED_STRINGS_PATH`), no control and no input file, and it wins over every other argument. An argument that is exactly `-h` or `--help` counts wherever it stands, even in the place of another option's value. After `--`, every argument is a file name, so `-- --help` checks a file named `--help`. The summary is fixed text, never built from the list. |

Every other argument is an input file. When `--list` is absent, the list is the file named by the environment variable `BARRED_STRINGS_PATH`. An unset or empty variable counts as absent. With neither, the run cannot go ahead (section 7, case 3).

### 3.1 The list file

- UTF-8 text. A byte-order mark at the very start of the file is dropped before anything else. A file that is not valid UTF-8 cannot be used (section 7, case 3).
- One entry per line. LF, CRLF and a lone CR each end a line. A CR is never part of an entry.
- A line that is blank, or whose first character that is not whitespace is `#`, is ignored. So an indented `#` line is a comment.
- An entry ends at the line's first tab. The text after that tab, up to the next tab or the end of the line, is the **flag field**. If the flag field is exactly `word`, in any case, the entry matches only as a whole word (section 4). Anything else after the first tab is a note. A note is never matched and never printed.
- An entry is prepared as section 4 says (folded, whitespace runs collapsed, trimmed). An entry that is empty after that cannot be used (section 7, case 3). This covers an entry made only of spaces, and an entry made only of characters that folding removes, such as a lone zero-width space.
- Entries are numbered from 1 in file order, counting only lines that are entries. Output names an entry only by this number.
- **The canary.** Entry 1 is a canary when, folded, it is `barred-strings-canary-` followed by at least 8 characters, each `a` to `z` or `0` to `9`, and nothing else. A canary is recognised but not required. It is entry 1 and is matched against input files like any other entry. A canary that carries the `word` flag cannot be used (section 7, case 3). A later entry that happens to start with the same prefix is an ordinary entry.

### 3.2 Input files

- **A PDF is read twice.** A file whose name ends in `.pdf` (any case) is read twice: once as the text that `pdftotext` writes for it in its default (non-layout) mode, the **default text**, and once as the text it writes with `-layout`, the **layout text**. The default text is the text revision 6.3 read, and it keeps every job it had then, so nothing matched before is missed. Both reads name the file the same way: a path that starts with `-` is passed as `./` followed by the path. The default read runs first. If either read cannot start or fails, the file is DEAD (section 7, case 6), with the reason `pdftotext not found` or `pdftotext failed`. Both reads happen before the length and control checks. A file that is not a PDF is read once.
- **Length and control.** A PDF's length (section 5) and its control (section 3.3) are taken from its default text only. So a PDF's OK line prints the same length as under revision 6.3.
- **Six forms.** The layout text is compared in the same three forms as any text (section 4: joined, rejoined and hyphen-kept), after the soft-hyphen rule below. So a PDF is compared in six forms, three of each text, and an entry's count in a PDF is the largest of its counts in the six.
- **Soft hyphens in the layout text.** Before folding, the layout text is split into lines at each line break (LF, CRLF or a lone CR). In each line, if the last character other than trailing spaces and tabs is a soft hyphen (U+00AD), and the character just before it is a word character (section 4), that one soft hyphen becomes a hyphen-minus (U+002D). Every line break is kept as it was, so no line number moves. Nothing else changes: a soft hyphen anywhere else is removed by folding, as before. The default text never gets this rule.
- **Line numbers in a PDF.** If an entry matches in any form of the default text, its line is the earliest line on which a match begins in the default text's forms, as before. Only if it matches in no form of the default text is its line the earliest line on which a match begins in the layout text's forms, counted in the layout text. The two texts can count lines differently: a line on a later page is numbered one lower in the layout text for each page before it, because default mode writes one more line at the end of each page (measured on poppler 26.07.0).
- **What layout mode changes.** In layout mode `pdftotext` keeps a line-end hyphen and the line break after it. So `zebra-`, a line break, then `word` reaches the hyphen-kept form as written, and an entry `zebra-word` wrapped at its hyphen inside a page is matched, as is a `word`-flagged entry that is one half of it (`zebra` or `word`) (10.11). A wrap kept this way makes the layout text 2 characters longer than the default text in the joined form: the hyphen, and the space that the kept line break becomes (`hyphmid.pdf` is 1193 characters in default mode and 1195 in layout mode). Layout mode also pads lines with spaces to keep their place on the page; whitespace runs collapse to one space in every form, so the padding changes no match. Neither change reaches the length or the control, which come from the default text.
- **Known limit: columns.** In layout mode `pdftotext` writes the lines of side-by-side columns on one line. So a wrap at a hyphen inside a column that has another column's text beside it is still missed: the layout line holds `a zebra-`, spaces, then the other column's text, so the hyphen does not end a line. And an entry can match across the gap between two columns, running from the end of a line in one column into the line beside it. The default text still finds everything it found before (10.11). This is a stated limit, not a deliberate difference.
- **Versions.** Measured on poppler 26.07.0. `-layout` is an option in poppler 0.62.0 and every later release, and in 0.62.0 layout mode keeps a line-end hyphen too (read in its source, not run). The check uses no option added after that release.
- Any other file is read as UTF-8. Each invalid byte sequence is replaced by U+FFFD and is not fatal. A replacement character is an ordinary character: it is counted in the length and it breaks a match that runs across it.
- **Line breaks.** Everywhere in this spec, for input files and PDF text alike, LF, CRLF and a lone CR each count as one line break. A form feed, which `pdftotext` writes between pages in both of its modes, is whitespace and not a line break. So are U+2028 and U+2029. No other character is a line break: the vertical tab, U+001C to U+001E and U+0085 are whitespace only, in input files and in the list file alike.
- Lines are numbered from 1. A byte-order mark is not a line break, so it never changes a line number.
- `--strip-comments` applies to every input file that is not a PDF, whatever its extension. It never applies to a PDF's text. It removes, in this order:
  1. every block comment, from `/*` to the next `*/`, across lines. This is a text rule, not a parser: a `/*` inside a string still opens a block. A `/*` with no later `*/` removes nothing;
  2. every line comment: `//` at the start of the file or after a whitespace character, through the end of that line. So the `//` in `"https://…"` does not start a comment;
  3. every `note:` field's string value. `note` must be at the start of the text or follow a character that is not a letter, digit or underscore, so `footnote:` and `my_note:` do not count. There is no whitespace before the colon. After the colon, any whitespace, line breaks included, may come before the value. The value is one or more double-quoted strings, honouring backslash escapes, joined by `+` with any whitespace around it. Single-quoted and backtick strings are not removed, and so are still checked.

  Text in other fields (a `value:` or `description:` string, for example) is still checked. Every removed character that is not part of a line break becomes a space, and line breaks are kept, so line numbers in the output still match the file on disk.

### 3.3 The control

- `--control TEXT` names a control string. It may be given more than once. A file passes its control when it contains any one of them.
- A control is prepared as section 4 says (folded, whitespace runs collapsed, trimmed) and matched as a substring of the file's joined form, never with the `word` rule. A control that is empty after that is not a control: if no usable control remains, the run cannot go ahead (section 7, case 2).
- With no `--control`, the run cannot go ahead (section 7, case 2). Control strings the user always wants can live in a config that the user's own wrapper passes in.

### 3.4 The help summary

The summary is the text below, byte for byte, ending in one line feed. `track-record` is the release's command name: if the name changes, the summary changes with it.

```text
usage: track-record barred [--list FILE] [--control TEXT]... [--strip-comments]
    [--min-chars N] FILE...

Report wording from your own barred list, by entry number only.

  --list FILE       the list file (default: $BARRED_STRINGS_PATH)
  --control TEXT    a string each file must hold (repeatable, any one counts)
  --strip-comments  strip comments and note values before matching
  --min-chars N     the minimum length of each file (default 500)
  -h, --help        show this summary and exit

exit: 0 all clean, 1 barred wording found, 2 a DEAD file or cannot run
```

## 4. Folding and matching

**Folding** a text means, in order: Unicode NFKC normalisation, which folds ligatures such as "fi" into two letters and a no-break space into a space; full Unicode case folding, so that `ß` folds to `ss`; NFKC again; and removal of every format character (Unicode category Cf). That category includes the soft hyphen, the zero-width space, joiner and non-joiner, the word joiner, the byte-order mark and the direction marks. Entries, controls and file names are folded in the same way as text. Each is then **prepared**: every run of whitespace inside it becomes one space, and leading and trailing whitespace is removed. So an entry written with a double space matches text with a single space or a line break, as the CI scanner does.

**Whitespace**, everywhere in this spec, means exactly the characters for which Python's `str.isspace()` is true. There are 29 of them (measured on Python 3.9 and 3.14): U+0009 to U+000D, U+001C to U+001F, U+0020, U+0085, U+00A0, U+1680, U+2000 to U+200A, U+2028, U+2029, U+202F, U+205F and U+3000. This includes some characters a reader might not expect: the vertical tab, the information separators U+001C to U+001F and the next-line character U+0085. A control character that is not on this list, such as U+0001, is not whitespace. The list is fixed by this spec, so a later Unicode version changes it only by a new revision. Where a rule names spaces or tabs, it means U+0020 and U+0009 only.

Each file's text is compared in three forms:
1. **Joined:** the folded text, with every run of whitespace, line breaks included, turned into one space. Nothing is trimmed from its ends.
2. **Rejoined:** the folded text, in which a hyphen-minus (U+002D, and no other dash) is removed whenever all of the following hold: the character before it is a word character; after it come only spaces or tabs, then one line break, then any whitespace; and the next character after that is a word character. The hyphen is removed together with all that whitespace. Then whitespace runs collapse as in the joined form. A word split across lines by hyphenation is matched whole. A **word character** is a letter, a number (any Unicode category starting with L or N) or the underscore.
3. **Hyphen-kept:** the folded text, in which a line-end hyphen-minus (U+002D, and no other dash) is kept and the whitespace after it is removed, whenever all of the following hold: the character before it is a word character; after it come only spaces, tabs or form feeds, then one line break, then any whitespace; and the next character after that is a word character. Then whitespace runs collapse as in the joined form. So `zebra-`, a line break, then `word` becomes `zebra-word`, and a hyphenated entry wrapped at its hyphen is matched whole (in a PDF, a wrap inside a page is matched through its layout text, section 3.2, except where the known limit for columns there applies). A form feed on either side of the line break (a page break, as `pdftotext` writes it) is removed in the same way. The joined and rejoined forms are unchanged by this form.

Matching rules:
- An entry matches wherever it occurs as a literal substring of any of the three forms. It is not limited to whole words: an entry `moonshot` also matches inside `moonshots`.
- An entry with the `word` flag matches only where the character before it and the character after it are each either absent (the start or end of the text) or a **boundary character**. A boundary character is anything that is not a letter (any Unicode category starting with L) and not a decimal digit (category Nd). So the underscore and punctuation are boundaries. This deliberately follows the repository's CI scanner, so one list means the same thing to both. It differs from the phrase boundary in the tone-and-tells check.
- Matches are counted left to right, without overlap. A candidate that fails the `word` rule does not use up any text, and the search goes on from the next character.
- A hyphen that is not at a line end is kept. `end-to-end` stays hyphenated and does not match an entry `end to end`.
- An en dash is a different character from an em dash. Barring one does not bar the other.
- The count for an entry in a file is the largest of its match counts in the three forms.

## 5. The minimum length

`<c>`, a file's length, is the number of Unicode code points in its joined form (section 4, form 1), after any stripping. A PDF's length is that of its default text (section 3.2). Nothing is trimmed, so a final line feed counts as one space. A file whose length is less than the minimum fails its read (section 7, case 4). A short text proves nothing: a zero from it looks the same as a real zero. The minimum is 500 unless `--min-chars N` sets it. `--min-chars 0` is allowed; the control check still applies.

## 6. Output and exit status

**File labels.** Each input file is named in the output by its **printed path**, unless its path matches any entry. A path matches when its folded path, in any of the three forms of section 4 (joined, rejoined or hyphen-kept), matches an entry under section 4's rules, `word` flag included. It also matches when its printed path, folded, matches an entry. Such a file is labelled `file #<i>` instead, where `<i>` is its 1-based position among the input files. Its path is never printed. The same rule keeps the list file's path out of every message. A finding from the name alone is reported on the `(file name)` line, whichever form matched.

**The printed path** is the path as given, with these characters escaped:
- the backslash, as `\\`;
- line feed, carriage return and tab, as `\n`, `\r` and `\t`;
- every other control character (U+0000 to U+001F, U+007F, U+0080 to U+009F), as `\x` and two lowercase hex digits;
- the line separator and paragraph separator (U+2028, U+2029) and every format character (Unicode category Cf, including the direction overrides), as `\u` and four lowercase hex digits. Format characters above U+FFFF take `\U` and eight lowercase hex digits. The next-line character U+0085 is a C1 control, so it takes the `\x85` form above.

A path with none of these characters is printed exactly as given. Escaping exists so that no file name can forge or reorder an output line. It changes only what is printed: matching (section 4) always uses the path as given.

One status line per input file, in argument order:
- `OK    <label>: 0 of <n> entries (control found; <c> chars)`, where `<n>` is the number of entries and `<c>` the length (section 5);
- `FAIL  <label>: <k> entries`, where `<k>` is the number of distinct entries matched in the file's name or text. Next come the finding lines. First, one line per entry matched in the name, in entry order: `<label>:0: entry #<N> (file name)`. Then one line per entry matched in the text, in entry order: `<label>:<line>: entry #<N> (<count> x)`. An entry matched in both appears once in each group;
- `DEAD  <label>: <reason>`, where the reason names the case from section 7, never an entry. A DEAD file gets no finding lines, even when its name matches.

**The line number** of a text finding is the line on which that entry's earliest match begins, taking the earliest across all three forms. A match begins at the character in the file (or in the PDF's text) from which its first folded character came. For a match that runs across a line break, that is the line where it starts. For a PDF, section 3.2 says which of its two texts the line is counted in.

The output never contains a list entry, a note, a matching path, the list file's path, or text quoted from the input. A test greps the captured output for each entry and finds none.

Exit status: `0` when every file is OK; `1` when at least one file FAILs and none is DEAD; `2` when any file is DEAD or the run cannot go ahead. The highest applies.

## 7. When it cannot run

The run exits `2` and says why, on one line, without printing any entry or the list's path, when:
1. No input file is named.
2. No usable control is given (none, or each one empty after preparing).
3. The list cannot be used: no list is named (no `--list` and no `BARRED_STRINGS_PATH`); the file is missing or unreadable; it is not valid UTF-8; it holds no entries once comments and blank lines are removed; an entry is empty after trimming and folding (the message gives its number); or entry 1 is a canary carrying the `word` flag. An empty list cannot prove anything clean.

A single file is DEAD, while the other files are still checked, when:

4. its length is less than the minimum (section 5);
5. none of its control strings is found;
6. it cannot be read, or it is a PDF and `pdftotext` is missing or fails on either of its two reads (section 3.2).

The run also exits `2`, before any file is read, when:

7. an option is unknown (`-h` and `--help` are known options, section 3.0), lacks its value, is given twice where only once is allowed (`--list`, `--min-chars`), or has a value out of range (`--min-chars` that is not a whole number of 0 or more, or that has more than 18 significant digits; leading zeros don't count). The digit cap keeps the parse inside what every supported Python converts without error.

At any point in the run:

8. Its output cannot be written: standard output is closed, or a write to it fails (for example, a full disk, or a reader that closed the pipe). The run stops at once, exits `2` and writes one line to standard error, `cannot run: cannot write output`, with no traceback. Lines already written stay written, but the exit status is `2` whatever they said. This includes the help summary: a help write that fails exits `2` with this line.

A closed or failing standard error never changes the exit status. When a message can't be written there, it is dropped, and the run exits exactly as it would have with the message written.

## 8. Rules that hold in every run

- It never edits an input or the list.
- It never prints an entry, a note, matched text, a matching path or the list's path.
- It never reports a file clean that it did not read in full.
- A closed or failing standard error never changes the exit status (section 7).

## 9. Decisions

1. **One list format; CI keeps its own scanner.** The product reads the CI scanner's list format: the canary as entry 1 and the `word` flag, exactly as section 3.1 states. One list file serves both. The product has no whole-repository mode. The CI scanner checks history, commit messages, identities and branch names, which a current-tree mode could not replace, so the CI scanner stays. Retiring it would need a history-wide mode with its own spec, in a later wave if ever.
2. **Line numbers, new in this release.** The prior tool printed no line. This one does, as stated in section 6, so the parity comparison takes the line from this tool and checks the rest.
3. **Deliberate differences from the prior tool**, which the parity run should expect:
   - No `--control` exits `2`. Before, a built-in set of control strings applied. The user's wrapper now passes them in.
   - An empty list exits `2`. Before, it reported every file OK.
   - A missing list exits `2` with a message. Before, it crashed with exit `1`. A list that is not valid UTF-8 now exits `2` the same way.
   - Entries are folded. Before, an entry written with a ligature or a no-break space could never match.
   - Case folding is full Unicode case folding, so `ß` matches `ss`. Before, matching ignored only simple case.
   - Every format character is removed. Before, six named ones were.
   - Entries are trimmed, an indented `#` line is a comment, a CR at a line end is never part of an entry, a leading byte-order mark is dropped, and the canary and the `word` flag are read. Before, edge spaces and a trailing CR stayed in the entry (so it could not match), an indented `#` line was an entry, and a `word` note was only a note.
   - A file name that matches an entry is a finding, and that name is never printed. Before, names were not checked and every path was printed. Names are checked in all three forms of section 4, so a name hyphenated across a line break is matched whole, with or without its hyphen.
   - A printed path has its backslashes, control characters, line and paragraph separators and format characters escaped (section 6). Before, every path was printed raw, so a line break in a file name could forge an output line.
   - The prior tool's line-break handling, rejoin rule and comment stripping are kept as they were, including the text-rule limit in section 3.2, with one deliberate exception: the hyphen-kept form (section 4, form 3) is new. The prior tool turned `zebra-`, a line break, then `word` into `zebraword` and `zebra- word`, so it missed an entry `zebra-word` wrapped at its hyphen. This tool catches it (10.9). In a PDF this holds inside a page too, through the layout text (section 3.2), except where the known limit for columns applies.
   - A PDF is also read in layout mode (section 3.2), so a hyphenated entry wrapped at its hyphen inside a page is matched, and so is a `word`-flagged half of it. The prior tool read PDFs in default mode only and missed both.

## 10. Acceptance tests (known answers)

The fixtures are invented. They live under `tests/fixtures/barred/`, and the generator writes them, except the two that are not valid UTF-8: `badutf8.txt` and the list in section 10.5 that is not valid UTF-8. The tests write those two at run time, because the repository's history scan refuses a file that isn't UTF-8. Every text file except `short.txt` and `nocontrol.txt` is wrapped in padding, the line `Example Corp shipped a reporting tool for teams.` repeated twelve times, before and after the test line, so it passes the length and control checks. The test line is therefore line 13. Every file ends each line with LF unless stated. Every run uses `--control "Example Corp"` and `--list` naming L1 unless stated.

**List L1:**

```text
# an invented list

turnkey synergy	note: entry one
rockstar ninja	note: entry two
—	note: the em dash
moonshot
fix it
```

L1 has five entries: 1 `turnkey synergy`, 2 `rockstar ninja`, 3 the em dash, 4 `moonshot` and 5 `fix it`.

**List L2:**

```text
# a second invented list, in the CI format
barred-strings-canary-example0001
grossweg
   padded phrase   	note: trimmed
fix	WORD
café
```

L2 has five entries: 1 the canary, 2 `grossweg`, 3 `padded phrase`, 4 `fix` with the `word` flag, and 5 `café`, written with a precomposed `é`.

**List L3:**

```text
# a third invented list
zebra-word
```

L3 has one entry: 1 `zebra-word`.

**List L4:**

```text
# a fourth invented list
zebra	word
word	word
```

L4 has two entries: 1 `zebra` and 2 `word`, each with the `word` flag.

### 10.1 Each evasion still matches (exit 1, entry 1, count 1)

| File | Test line |
|---|---|
| `plain.txt` | `We delivered a turnkey synergy for the team.` |
| `case.txt` | `TURNKEY SYNERGY was the pitch.` |
| `wrap.txt` | `turnkey` and `synergy across lines` on two lines |
| `hyph.txt` | `a turnkey syn-` and `ergy plan` on two lines |
| `hyphcrlf.txt` | as `hyph.txt`, with CRLF line endings throughout |
| `hyphcr.txt` | as `hyph.txt`, with a lone CR ending the `syn-` line |
| `hyphsp.txt` | `a turnkey syn-`, two spaces, then a line break and `ergy plan` |
| `soft.txt` | `turnkey syn`, a soft hyphen, then `ergy` |
| `zw.txt` | `turnkey`, a zero-width space, then ` synergy` |
| `nbsp.txt` | `turnkey`, a no-break space, then `synergy` |

Each reports line 13.

`lig.txt`, with the test line `we`, the "fi" ligature, then `x it fast`, matches entry 5 once.
`emdash.txt`, with the test line `fast — and more`, matches entry 3 once.

### 10.2 Must pass (exit 0)

| File | Test line | Why |
|---|---|---|
| `clean.txt` | `We wrote tests for the importer.` | nothing listed |
| `endash.txt` | `from 2017–2026` (an en dash) | an en dash is not the listed em dash |
| `compound.txt` | `end-to-end tests and moon-shot ideas` | a mid-line hyphen is kept, so `moon-shot` is not `moonshot` |
| `note.txt` | `note: entry one` | notes are never matched |
| `nbhyph.txt` | `a turnkey syn`, a non-breaking hyphen (U+2011), then a line break and `ergy plan` | only U+002D is rejoined |
| `badutf8.txt` | `turnkey syn`, the byte 0xFF, then `ergy` | the replacement character breaks the match |

`clean.txt` prints `OK    clean.txt: 0 of 5 entries (control found; <c> chars)`.

### 10.3 Counts, order and line numbers

`two.txt`, with the test line `a turnkey synergy and a rockstar ninja and another turnkey synergy`, prints `FAIL  two.txt: 2 entries`, then `two.txt:13: entry #1 (2 x)` and `two.txt:13: entry #2 (1 x)`, in that order. Exit 1.

`substr.txt`, with the test line `the moonshots were many`, matches entry 4 once, because matching is by substring. Exit 1.

`early.txt` has three test lines: `turnkey syn-`, then `ergy and later turnkey`, then `synergy`. The joined form matches entry 1 once, starting on line 14. The rejoined form matches it twice, the first starting on line 13. It prints `early.txt:13: entry #1 (2 x)`. Exit 1.

`bom.txt` is a byte-order mark followed by `plain.txt`'s content: `bom.txt:13: entry #1 (1 x)`. Exit 1.

### 10.4 Source files (each with `--strip-comments` unless stated)

`src.ts` is the padding, then:

```text
// turnkey synergy in a comment
export default { value: "clean text", note: "rockstar ninja" + "more" };
/* moonshot in a block */
```

then the padding again.
- Without `--strip-comments`: FAIL, with entries 1, 2 and 4, one each, on lines 13, 14 and 15. Exit 1.
- With `--strip-comments`: OK. Exit 0.

The other source fixtures each have one test block between the paddings:

| File | Test block | Result |
|---|---|---|
| `lines.ts` | `/* a block`, then `that spans */`, then `rockstar ninja here` | FAIL, entry 2 on line 15: line numbers survive stripping |
| `nlnote.ts` | `x = { note:`, then `  "moonshot" +`, then `  "more" };` | OK: a line break may follow the colon |
| `url.ts` | `x = "https://moonshot.example";` | FAIL, entry 4: `//` after a quote is not a comment |
| `footnote.ts` | `x = { footnote: "moonshot" };` | FAIL, entry 4: `footnote:` is not `note:` |
| `spcolon.ts` | `x = { note : "moonshot" };` | FAIL, entry 4: no space before the colon |
| `single.ts` | `x = { note: 'moonshot' };` | FAIL, entry 4: only double-quoted values are removed |
| `unterm.ts` | `/* moonshot never closed` | FAIL, entry 4: an unclosed block removes nothing |
| `strblock.ts` | `x = "a/*b"; moonshot; y = "*/";` | OK: the known limit of the text rule in section 3.2 |
| `strip.txt` | `// turnkey synergy` | OK: stripping applies whatever the extension |

A PDF whose text holds `// turnkey synergy` FAILs with `--strip-comments`: stripping never applies to a PDF.

### 10.5 Cannot run, and DEAD files

- `short.txt` is the single line `turnkey synergy here but no anchor word`: DEAD, too short. Exit 2.
- `nocontrol.txt` is `A turnkey synergy line. ` repeated 40 times: DEAD, control not found, never FAIL. Exit 2.
- A joined form of exactly 499 characters is DEAD, and one of exactly 500 is OK. The count includes the space that the file's final line feed becomes: `clean.txt` (25 lines, each ending in LF) counts one more than the same text with no final line feed. With `--min-chars 499`, both are OK.
- `clean.txt plain.txt short.txt` in one run prints OK, FAIL and DEAD lines, in that order, and exits 2.
- A missing input file is DEAD, while the other files still run. Exit 2.
- The control is matched after folding: `--control "EXAMPLE CORP"` passes `clean.txt`.
- No file named: exit 2. No `--control`: exit 2. A list holding only comments and blank lines: exit 2. A missing list: exit 2. A list that is not valid UTF-8: exit 2.
- No `--list`, with `BARRED_STRINGS_PATH` naming L1: the same results as `--list` naming L1. No `--list` and the variable unset, or set but empty: exit 2.
- `--list` given twice, `--min-chars -1`, `--min-chars x`, and an unknown option: each exits 2 before any file is read.
- `clean.txt` with standard output closed: exit 2, and standard error is exactly `cannot run: cannot write output`.
- No file named, with standard error closed: exit 2. `clean.txt` with standard error closed: exit 0.
- `--min-chars 1000000000000000000` (19 digits) exits 2 before any file is read, with a one-line reason naming the 18-digit cap. `--min-chars 999999999999999999` (18 digits) is in range: `clean.txt` is DEAD, too short. Exit 2. `--min-chars 0000000000000000000500` (22 digits, 3 significant) is in range and means 500: `clean.txt` is OK. Exit 0.
- A list whose only entry line is three spaces, a tab and a note: exit 2. A list whose only entry is a zero-width space: exit 2.
- L2 with the flag field `word` added to the canary's line: exit 2.
- A list whose only entry is `turnkey  synergy`, with two spaces, matches `plain.txt` and `wrap.txt` once each. Exit 1.
- `--control "Example  Corp"`, with two spaces, passes `clean.txt`. `--control "   "` as the only control exits 2.
- A PDF with `pdftotext` absent from `PATH`: DEAD. Exit 2.
- A PDF whose text has a form feed between pages: a match on the first line after the form feed reports the line number counted by line breaks alone.

### 10.6 The list format (runs use `--list` naming L2)

| File | Test line | Result |
|---|---|---|
| `fold.txt` | `the Großweg plan` | entry 2, once: full case folding |
| `trim.txt` | `a padded phrase here` | entry 3, once: the entry was trimmed |
| `word.txt` | `we fix bugs; prefix and fixes do not count; fix.` | entry 4, 2 x |
| `word2.txt` | `fix_it and fix2` | entry 4, once: the underscore is a boundary, a digit is not |
| `decomp.txt` | `cafe`, a combining acute accent, then ` menu` | entry 5, once: NFKC composes it |
| `lrm.txt` | `gross`, a left-to-right mark, then `weg` | entry 2, once: every format character is removed |
| `canary.txt` | `barred-strings-canary-example0001` | entry 1, once: the canary is matched like any entry |

`clean.txt` against L2 prints `OK    clean.txt: 0 of 5 entries (control found; <c> chars)`.

L1 written with CRLF line endings, with a byte-order mark before its first line, and with its comment line indented by two spaces, gives the same results on `plain.txt` and `clean.txt` as L1 itself, with five entries.

### 10.7 File names

- `moonshot-notes.txt` holds `clean.txt`'s content. Run alone, it prints `FAIL  file #1: 1 entries`, then `file #1:0: entry #4 (file name)`. Exit 1.
- `clean.txt moonshot-notes.txt` prints the OK line for `clean.txt`, then `FAIL  file #2: 1 entries`. Exit 1.
- `moonshot-plain.txt` holds `substr.txt`'s content. It prints `FAIL  file #1: 1 entries`, then `file #1:0: entry #4 (file name)`, then `file #1:13: entry #4 (1 x)`. Exit 1.
- `moonshot-short.txt` holds `short.txt`'s content. It prints only `DEAD  file #1: ` and the reason. Exit 2.
- `prefix-notes.txt`, run against L2, holding `clean.txt`'s content: OK, because `fix` carries the `word` flag.
- A file named `moon-`, a line feed, then `shot.txt`, holding `clean.txt`'s content: the rejoined form of its name matches. It prints `FAIL  file #1: 1 entries`, then `file #1:0: entry #4 (file name)`. Exit 1.
- A file named `clean`, a line feed, then `OK    forged.txt`, holding `clean.txt`'s content, prints one line: `OK    clean\nOK    forged.txt: 0 of 5 entries (control found; <c> chars)`, with a literal backslash and `n`. Exit 0.
- A file named `a\b.txt` (one backslash), holding `clean.txt`'s content, prints `OK    a\\b.txt: 0 of 5 entries (control found; <c> chars)`. Exit 0.
- A file named `notes`, a right-to-left override (U+202E), then `txt.md`, holding `clean.txt`'s content, prints `OK    notes\u202etxt.md: 0 of 5 entries (control found; <c> chars)`. Exit 0.

### 10.8 Nothing barred is ever printed

Every run in 10.1 to 10.7, 10.9 and 10.11 is captured. For each L1, L2, L3 and L4 entry, and for each fixture name that contains an entry, a search of the captured output finds nothing. The search uses section 4's matching rules, so an entry with the `word` flag is searched as a whole word: `prefix-notes.txt` in an OK line is not a hit for `fix`. The same search on the list files finds each entry, which shows the search works.

### 10.9 The hyphen-kept form (runs use `--list` naming L3)

Each file is the padding, the test lines, then the padding again, so the first test line is line 13. LF ends each line unless stated.

| File | Test lines | Result |
|---|---|---|
| `hyphkeep.txt` | `a zebra-`, then a line break and `word here` | FAIL, entry 1 on line 13, once |
| `hyphff1.txt` | `a zebra-`, then a line break, a form feed and `word here` | FAIL, entry 1 on line 13, once: a page break after the line break |
| `hyphff2.txt` | `a zebra-`, then a form feed, a line break and `word here` | FAIL, entry 1 on line 13, once: a page break before the line break |
| `hyphkeepcrlf.txt` | as `hyphkeep.txt`, with CRLF line endings throughout | FAIL, entry 1 on line 13, once |
| `nokeep.txt` | `a zebra -`, then a line break and `word here` | OK: the hyphen must follow a word character |
| `hyphmid.pdf` | an invented PDF, padded to the minimum, whose text wraps `a zebra-` / `word here` inside a page | FAIL, entry 1 on line 13, once: the layout text keeps the wrap (section 3.2). This is the positive control for PDF reading, skipped where `pdftotext` is absent except in the repository's CI, where its absence fails the run. |

`hyphkeep.txt` prints `FAIL  hyphkeep.txt: 1 entries`, then `hyphkeep.txt:13: entry #1 (1 x)`. Exit 1. `hyphff1.txt`, `hyphff2.txt` and `hyphkeepcrlf.txt` print the same two lines with their own names. Exit 1 each.

`nokeep.txt` prints `OK    nokeep.txt: 0 of 1 entries (control found; <c> chars)`. Exit 0.

A file named `zebra-`, a line feed, then `word.txt`, holding `clean.txt`'s content, run against L3: the hyphen-kept form of its name matches. It prints `FAIL  file #1: 1 entries`, then `file #1:0: entry #1 (file name)`. Exit 1.

Against L1, the hyphen-kept form changes no result in 10.1 to 10.7: `hyph.txt` still counts entry 1 once, and `early.txt` still prints `early.txt:13: entry #1 (2 x)`.

### 10.10 Help

- `--help` alone, and `-h` alone: exit 0, standard output is exactly the summary of section 3.4, standard error is empty.
- `--help` with `--list` naming a missing file: exit 0, the summary. This proves no list is read.
- `--help` with no list, no control and no input file: exit 0, the summary.
- `--help` with an unknown option: exit 0, the summary.
- `--list --help`: exit 0, the summary (help in a value's place).
- `--help` with standard output closed: exit 2, and one line on standard error, `cannot run: cannot write output`.

### 10.11 PDFs in layout mode

Each PDF fixture is an invented PDF that the generator writes: Helvetica, 11 points, one line every 13 points, a text block starting 40 points from the left. Its padding is the padding line repeated twelve times, as in the text fixtures. Every run uses `--control "Example Corp"`. The tests that need the real `pdftotext` are skipped where it is absent, except in the repository's CI, where its absence fails the run. Measured on poppler 26.07.0.

| File | Content |
|---|---|
| `twocol.pdf` | one page in two columns. The left column is `Example Corp wrote it.` twelve times, then `a turnkey`, `synergy plan`, `a zebra-` and `word here`, then `Example Corp wrote it.` twelve times. The right column starts 330 points from the left, beside it: `Right column text line 1.` to `Right column text line 28.` |
| `softhyph.pdf` | one page: the padding, `a turnkey syn` and a soft hyphen (the font's encoding maps byte 0xAD to it), then `ergy plan`, then the padding |
| `pagewrap.pdf` | two pages: page 1 is the padding, then `a zebra-`; page 2 is `word here`, then the padding |
| `page3wrap.pdf` | three pages: the padding; the padding; then `a zebra-`, `word here` and the padding |

The committed fixtures:

| Run | Result |
|---|---|
| `hyphmid.pdf`, read by `pdftotext` itself | the default text holds `a zebraword here` and no `zebra-`; the layout text has a line ending `a zebra-`, followed by a line starting `word here`. This shows the positive control of 10.9 is a wrap inside a page |
| `hyphmid.pdf`, L4 | `FAIL  hyphmid.pdf: 2 entries`, then `hyphmid.pdf:13: entry #1 (1 x)` and `hyphmid.pdf:14: entry #2 (1 x)`. Exit 1 |
| `twocol.pdf`, L1 | `FAIL  twocol.pdf: 1 entries`, then `twocol.pdf:13: entry #1 (1 x)`. Exit 1. Found in the default text only: the layout text, with its whitespace collapsed, does not hold `turnkey synergy` |
| `twocol.pdf`, L3 | `OK    twocol.pdf: 0 of 1 entries (control found; <c> chars)`. Exit 0: the known limit for columns (section 3.2) |
| `twocol.pdf`, a list whose only entry is `turnkey right column` | `FAIL  twocol.pdf: 1 entries`, then `twocol.pdf:13: entry #1 (1 x)`. Exit 1: the known limit for columns, a match across the gap |
| `softhyph.pdf`, L1 | `FAIL  softhyph.pdf: 1 entries`, then `softhyph.pdf:13: entry #1 (1 x)`. Exit 1 |
| `pagewrap.pdf`, L3 | `FAIL  pagewrap.pdf: 1 entries`, then `pagewrap.pdf:13: entry #1 (1 x)`. Exit 1 |
| `page3wrap.pdf`, L3 | FAIL, entry 1, once. Exit 1. The line is the line of the layout text that ends `a zebra-` (line 25), not the line of the default text that holds `zebraword` (line 27): the match is in the layout text only. The test takes both numbers from `pdftotext` itself, since another poppler release may count page ends differently |

The layout run of 10.1 to 10.9. For each row below, a one-page PDF is built from the fixture's lines, named after the fixture with `.pdf` for `.txt`, and run with the same list:
- its layout text, saved as the fixture's name, prints exactly what the fixture prints (exit status, standard output and standard error);
- the PDF itself prints what the fixture prints, with `.pdf` for `.txt`, except `nokeep.pdf` against L3, which prints `OK    nokeep.pdf: 0 of 1 entries (control found; 1194 chars)`. Default mode removes that line-end hyphen and the line break, so the length is 2 less than the fixture's 1196.

The rows are, against L1: `plain`, `case`, `wrap`, `hyph`, `hyphcrlf`, `hyphcr`, `hyphsp`, `clean`, `compound`, `note`, `two`, `substr`, `early` and `short`; against L2: `trim`, `word`, `word2`, `canary` and `clean`; against L3: `hyphkeep`, `hyphkeepcrlf`, `nokeep` and `clean`. Left out: the fixtures with characters the generator, which writes ASCII only, cannot carry (`soft`, `zw`, `nbsp`, `lig`, `emdash`, `endash`, `nbhyph`, `decomp`, `lrm`, `fold` and `bom`); `badutf8`, which is not UTF-8; `nocontrol`, whose one line is longer than the page; `hyphff1` and `hyphff2`, whose form feeds are page breaks in a PDF (`pagewrap.pdf` covers that); the source files and `strip.txt`, since stripping never applies to a PDF (10.4); the file-name cases (10.7); and the option and list cases with no text to extract (10.5, and the list-format runs of 10.6).

A stand-in `pdftotext` answers the default read and the layout read with different texts, for a file `x.pdf`, against L1. Below, a block in brackets stands for the padding, the block's lines, then the padding, each line ending in a line feed, so the block's first line is line 13.

| Default read | Layout read | Result |
|---|---|---|
| [`nothing listed`] | exits 1 | `DEAD  x.pdf: pdftotext failed`. Exit 2 |
| exits 1 | [`a turnkey synergy here`] | `DEAD  x.pdf: pdftotext failed`. Exit 2 |
| [`nothing listed`] | [`a turnkey syn-`, `ergy plan`] | `FAIL  x.pdf: 1 entries`, then `x.pdf:13: entry #1 (1 x)`. Exit 1: found in the layout text only |
| [`a turnkey synergy here`] | [`nothing listed`] | `x.pdf:13: entry #1 (1 x)`. Exit 1: found in the default text only |
| [`a turnkey synergy here`] | the padding line four times, `a turnkey synergy here`, then the padding line twenty times | `x.pdf:13: entry #1 (1 x)`. Exit 1: the default text's line wins over the layout text's line 5 |
| [`a turnkey synergy here`] | [`a turnkey synergy and a turnkey synergy`] | `x.pdf:13: entry #1 (2 x)`. Exit 1: the larger count |
| [`a turnkey synergy and a turnkey synergy`] | [`a turnkey synergy here`] | `x.pdf:13: entry #1 (2 x)`. Exit 1: the larger count, here the default text's |
| [`nothing listed`] | [`nothing listed`], or the same with ten more padding lines | the same OK line both times. Exit 0: the length is the default text's |
| [`nothing listed`], padded with `Another firm shipped a reporting tool for teams.` | [`nothing listed`] | `DEAD  x.pdf: control not found`. Exit 2: the control is the default text's |
| [`nothing listed`] | [`a turnkey syn` and a soft hyphen, with or without spaces after it, then `ergy plan`] | `x.pdf:13: entry #1 (1 x)`. Exit 1: a line-end soft hyphen in the layout text is a hyphen |
| [`nothing listed`] | [`a turnkey syn`, a space and a soft hyphen, then `ergy plan`] | OK. Exit 0: the soft hyphen does not follow a word character, so folding removes it, and `syn ergy` is not the entry |
| [`nothing listed`] | [`a turnkey syn`, a space and a soft hyphen, then `ergy plan`] | not against L1 but against a list whose only entry is `syn - ergy`: `OK    x.pdf: 0 of 1 entries (control found; <c> chars)`. Exit 0: that soft hyphen is not turned into a hyphen, so no form holds `syn - ergy` |
| [`a turnkey syn` and a soft hyphen, then `ergy plan`] | [`nothing listed`] | OK. Exit 0: the default text never gets the soft-hyphen rule |
| [`nothing listed`] | [`a turnkey syn-`, `ergy plan`] | for a file named `X.PDF` instead of `x.pdf`: `FAIL  X.PDF: 1 entries`, then `X.PDF:13: entry #1 (1 x)`. Exit 1: the layout read runs whatever the case of `.pdf` |
| [`nothing listed`] | [`a turnkey synergy here`] | for a file named `-x.pdf` instead of `x.pdf`, given after `--`, against a stand-in that fails when its first argument starts with `-`: `FAIL  -x.pdf: 1 entries`, then `-x.pdf:13: entry #1 (1 x)`. Exit 1: the layout read passes the path as `./-x.pdf` |
| [`nothing listed`] | [a soft hyphen alone on its line] | OK. Exit 0: a soft hyphen with nothing before it is not turned into a hyphen |
| [`nothing listed`] | [`x abc1` and a soft hyphen, `def y`, `x ab_` and a soft hyphen, `cd y`] | not against L1 but against a list whose entries are 1 `abc1-def` and 2 `ab_-cd`: `FAIL  x.pdf: 2 entries`, then `x.pdf:13: entry #1 (1 x)` and `x.pdf:15: entry #2 (1 x)`. Exit 1: a digit and an underscore are word characters, so each soft hyphen is a hyphen |
| [`nothing listed`] | [`x a.` and a soft hyphen, then `b y`] | not against L1 but against a list whose only entry is `a.- b`: `OK    x.pdf: 0 of 1 entries (control found; <c> chars)`. Exit 0: a `.` is not a word character, so the soft hyphen is not turned into a hyphen |
| [`nothing listed`] | [`// turnkey synergy here`] | run with `--strip-comments`: `FAIL  x.pdf: 1 entries`, then `x.pdf:13: entry #1 (1 x)`. Exit 1: stripping never applies to the layout text |
| [`nothing listed`] | [`a turnkey syn` and a soft hyphen, then `ergy plan`], each line ending in CRLF, or each in a lone CR | `FAIL  x.pdf: 1 entries`, then `x.pdf:13: entry #1 (1 x)`, both times. Exit 1: the soft-hyphen rule splits lines on CRLF and on a lone CR too |
| [`nothing listed`] | [`a turnkey syn-`, `ergy plan`] | for a file named `doc.PdF` instead of `x.pdf`: `FAIL  doc.PdF: 1 entries`, then `doc.PdF:13: entry #1 (1 x)`. Exit 1: the layout read runs for a mixed-case `.pdf` |
| [`nothing listed`], after which the stand-in removes itself | never reached | with `PATH` holding only the stand-in's folder: `DEAD  x.pdf: pdftotext not found`. Exit 2: the layout read finds no `pdftotext` and gives its own reason |
| [`nothing listed`] | [`a turnkey syn-`, `ergy plan`] | not against L1 but against a list whose only entry is `syn- ergy`: `FAIL  x.pdf: 1 entries`, then `x.pdf:13: entry #1 (1 x)`. Exit 1: only the layout text's joined form holds `syn- ergy` |

One run against that stand-in, logging its arguments, shows exactly two calls, in this order: `x.pdf -`, then `x.pdf - -layout`.
<!-- draft spec ends -->
