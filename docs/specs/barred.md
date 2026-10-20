# Barred-wording check: behaviour spec (W1.1)

Status: accepted.
Date: 2026-10-20.
Revision: 2. Answers to the build questions are folded in (sections 3 to 7, 9 and 10).

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
| `--min-chars N` | The minimum length (section 5). `N` is a whole number, 0 or more. Default 500. |

Every other argument is an input file. When `--list` is absent, the list is the file named by the environment variable `BARRED_STRINGS_PATH`. An unset or empty variable counts as absent. With neither, the run cannot go ahead (section 7, case 3).

### 3.1 The list file

- UTF-8 text. A byte-order mark at the very start of the file is dropped before anything else. A file that is not valid UTF-8 cannot be used (section 7, case 3).
- One entry per line. LF, CRLF and a lone CR each end a line. A CR is never part of an entry.
- A line that is blank, or whose first character that is not whitespace is `#`, is ignored. So an indented `#` line is a comment.
- An entry ends at the line's first tab. The text after that tab, up to the next tab or the end of the line, is the **flag field**. If the flag field is exactly `word`, in any case, the entry matches only as a whole word (section 4). Anything else after the first tab is a note. A note is never matched and never printed.
- An entry is trimmed of leading and trailing whitespace, then folded as in section 4. An entry that is empty after that cannot be used (section 7, case 3). This covers an entry made only of spaces, and an entry made only of characters that folding removes, such as a lone zero-width space.
- Entries are numbered from 1 in file order, counting only lines that are entries. Output names an entry only by this number.
- **The canary.** Entry 1 is a canary when, folded, it is `barred-strings-canary-` followed by at least 8 characters, each `a` to `z` or `0` to `9`, and nothing else. A canary is recognised but not required. It is entry 1 and is matched against input files like any other entry. A canary that carries the `word` flag cannot be used (section 7, case 3). A later entry that happens to start with the same prefix is an ordinary entry.

### 3.2 Input files

- A file whose name ends in `.pdf` (any case) is read as the text that `pdftotext` writes for it, in its default (non-layout) mode.
- Any other file is read as UTF-8. Each invalid byte sequence is replaced by U+FFFD and is not fatal. A replacement character is an ordinary character: it is counted in the length and it breaks a match that runs across it.
- **Line breaks.** Everywhere in this spec, for input files and PDF text alike, LF, CRLF and a lone CR each count as one line break. A form feed, which `pdftotext` writes between pages, is whitespace and not a line break. So are U+2028 and U+2029.
- Lines are numbered from 1. A byte-order mark is not a line break, so it never changes a line number.
- `--strip-comments` applies to every input file that is not a PDF, whatever its extension. It never applies to a PDF's text. It removes, in this order:
  1. every block comment, from `/*` to the next `*/`, across lines. This is a text rule, not a parser: a `/*` inside a string still opens a block. A `/*` with no later `*/` removes nothing;
  2. every line comment: `//` at the start of the file or after a whitespace character, through the end of that line. So the `//` in `"https://…"` does not start a comment;
  3. every `note:` field's string value. `note` must be at the start of the text or follow a character that is not a letter, digit or underscore, so `footnote:` and `my_note:` do not count. There is no whitespace before the colon. After the colon, any whitespace, line breaks included, may come before the value. The value is one or more double-quoted strings, honouring backslash escapes, joined by `+` with any whitespace around it. Single-quoted and backtick strings are not removed, and so are still checked.

  Text in other fields (a `value:` or `description:` string, for example) is still checked. Every removed character that is not part of a line break becomes a space, and line breaks are kept, so line numbers in the output still match the file on disk.

### 3.3 The control

- `--control TEXT` names a control string. It may be given more than once. A file passes its control when it contains any one of them.
- A control is folded as in section 4 and matched as a substring of the file's joined form, never with the `word` rule.
- With no `--control`, the run cannot go ahead (section 7, case 2). Control strings the user always wants can live in a config that the user's own wrapper passes in.

## 4. Folding and matching

**Folding** a text means, in order: Unicode NFKC normalisation, which folds ligatures such as "fi" into two letters and a no-break space into a space; full Unicode case folding, so that `ß` folds to `ss`; NFKC again; and removal of every format character (Unicode category Cf). That category includes the soft hyphen, the zero-width space, joiner and non-joiner, the word joiner, the byte-order mark and the direction marks. Entries, controls and file names are folded in the same way as text.

Each file's text is compared in two forms:
1. **Joined:** the folded text, with every run of whitespace, line breaks included, turned into one space. Nothing is trimmed from its ends.
2. **Rejoined:** the folded text, in which a hyphen-minus (U+002D, and no other dash) is removed whenever all of the following hold: the character before it is a word character; after it come only spaces or tabs, then one line break, then any whitespace; and the next character after that is a word character. The hyphen is removed together with all that whitespace. Then whitespace runs collapse as in the joined form. A word split across lines by hyphenation is matched whole. A **word character** is a letter, a number (any Unicode category starting with L or N) or the underscore.

Matching rules:
- An entry matches wherever it occurs as a literal substring of either form. It is not limited to whole words: an entry `moonshot` also matches inside `moonshots`.
- An entry with the `word` flag matches only where the character before it and the character after it are each either absent (the start or end of the text) or a **boundary character**. A boundary character is anything that is not a letter (any Unicode category starting with L) and not a decimal digit (category Nd). So the underscore and punctuation are boundaries. This deliberately follows the repository's CI scanner, so one list means the same thing to both. It differs from the phrase boundary in the tone-and-tells check.
- Matches are counted left to right, without overlap. A candidate that fails the `word` rule does not use up any text, and the search goes on from the next character.
- A hyphen that is not at a line end is kept. `end-to-end` stays hyphenated and does not match an entry `end to end`.
- An en dash is a different character from an em dash. Barring one does not bar the other.
- The count for an entry in a file is the larger of its match counts in the two forms.

## 5. The minimum length

`<c>`, a file's length, is the number of Unicode code points in its joined form (section 4, form 1), after any stripping. Nothing is trimmed, so a final line feed counts as one space. A file whose length is less than the minimum fails its read (section 7, case 4). A short text proves nothing: a zero from it looks the same as a real zero. The minimum is 500 unless `--min-chars N` sets it. `--min-chars 0` is allowed; the control check still applies.

## 6. Output and exit status

**File labels.** Each input file is named in the output by its path exactly as given, unless its folded path matches any entry under the rules of section 4, `word` flag included. Such a file is labelled `file #<i>` instead, where `<i>` is its 1-based position among the input files. Its path is never printed. The same rule keeps the list file's path out of every message.

One status line per input file, in argument order:
- `OK    <label>: 0 of <n> entries (control found; <c> chars)`, where `<n>` is the number of entries and `<c>` the length (section 5);
- `FAIL  <label>: <k> entries`, where `<k>` is the number of distinct entries matched in the file's name or text. Next come the finding lines. First, one line per entry matched in the name, in entry order: `<label>:0: entry #<N> (file name)`. Then one line per entry matched in the text, in entry order: `<label>:<line>: entry #<N> (<count> x)`. An entry matched in both appears once in each group;
- `DEAD  <label>: <reason>`, where the reason names the case from section 7, never an entry. A DEAD file gets no finding lines, even when its name matches.

**The line number** of a text finding is the line on which that entry's earliest match begins, taking the earliest across both forms. A match begins at the character in the file (or in the PDF's text) from which its first folded character came. For a match that runs across a line break, that is the line where it starts.

The output never contains a list entry, a note, a matching path, the list file's path, or text quoted from the input. A test greps the captured output for each entry and finds none.

Exit status: `0` when every file is OK; `1` when at least one file FAILs and none is DEAD; `2` when any file is DEAD or the run cannot go ahead. The highest applies.

## 7. When it cannot run

The run exits `2` and says why, on one line, without printing any entry or the list's path, when:
1. No input file is named.
2. No control is given.
3. The list cannot be used: no list is named (no `--list` and no `BARRED_STRINGS_PATH`); the file is missing or unreadable; it is not valid UTF-8; it holds no entries once comments and blank lines are removed; an entry is empty after trimming and folding (the message gives its number); or entry 1 is a canary carrying the `word` flag. An empty list cannot prove anything clean.

A single file is DEAD, while the other files are still checked, when:

4. its length is less than the minimum (section 5);
5. none of its control strings is found;
6. it cannot be read, or it is a PDF and `pdftotext` is missing or fails.

The run also exits `2`, before any file is read, when:

7. an option is unknown, lacks its value, is given twice where only once is allowed (`--list`, `--min-chars`), or has a value out of range (`--min-chars` that is not a whole number of 0 or more).

## 8. Rules that hold in every run

- It never edits an input or the list.
- It never prints an entry, a note, matched text, a matching path or the list's path.
- It never reports a file clean that it did not read in full.

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
   - A file name that matches an entry is a finding, and that name is never printed. Before, names were not checked and every path was printed.
   - The prior tool's line-break handling, rejoin rule and comment stripping are kept as they were, including the text-rule limit in section 3.2.

## 10. Acceptance tests (known answers)

The fixtures are invented. They live under `tests/fixtures/barred/`, and the generator writes them. Every text file except `short.txt` and `nocontrol.txt` is wrapped in padding, the line `Example Corp shipped a reporting tool for teams.` repeated twelve times, before and after the test line, so it passes the length and control checks. The test line is therefore line 13. Every file ends each line with LF unless stated. Every run uses `--control "Example Corp"` and `--list` naming L1 unless stated.

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
- A list whose only entry line is three spaces, a tab and a note: exit 2. A list whose only entry is a zero-width space: exit 2.
- L2 with the flag field `word` added to the canary's line: exit 2.
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

### 10.8 Nothing barred is ever printed

Every run in 10.1 to 10.7 is captured. For each L1 and L2 entry, and for each fixture name that contains an entry, a search of the captured output finds nothing. The same search on the list files finds each entry, which shows the search works.
