# Keyword scan: behaviour spec (W1.2 parity release, W1.2b posting-line citation)

Status: accepted.
Date: 2026-10-20.

`<cli>` is the command name until it is settled.

## 1. Purpose

Show which terms a batch of job postings ask for that the user's own copy never uses, and, from W1.2b on, the posting line each one came from.

## 2. Scope

In:
- reading a folder of stored postings;
- reading a term table;
- reading one or more copy files (plain text, Markdown, or TypeScript source holding résumé text);
- three modes: `demand`, `coverage` and `report`;
- the posting file format, which the posting fetch tool (W1.4) writes and this tool reads;
- W1.2b: the posting-line citation, in text and machine-readable output.

Out:
- fetching postings (W1.4);
- rewriting, suggesting or ranking copy;
- any keyword density or score target;
- network access of any kind.

## 3. Releases

- **W1.2 (parity release).** Reproduces the behaviour in sections 4 to 9 exactly. The known answers in section 11 are its tests. It has no citation output.
- **W1.2b (next release, after parity passes).** Adds the citation (section 10). The citation is additive: it never changes a line that W1.2 prints, or its order. The parity comparison ignores it.

## 4. Inputs

### 4.1 Postings folder

Every file directly in the folder whose name ends in `.txt` is one posting. Sub-folders are not read. The suffix match is case-sensitive, so `.TXT` is not read. A name that starts with a dot is read like any other. Sidecar files (`.meta.json`) are never postings.

Postings are read in file-name order: plain character order by code point, case-sensitive, so `B.txt` comes before `a.txt`. A posting is either a headed file (4.2) or a raw file with a sidecar (4.3).

### 4.2 Headed posting file

A headed posting file has:
1. **Six header lines,** in this order, each written as `key: value` with exactly one colon-space separator and a non-empty value:
   - `source_url`
   - `api_endpoint`
   - `fetched_at`
   - `http_status`
   - `sha256`
   - `bytes`
2. **An optional seventh line**, the control line. A seventh line is a control line when it starts with the letters `control` and contains a colon-space anywhere. `control: x`, `controller: x` and `control: ` with an empty value all qualify. A seventh line that starts with `control` but has no colon-space, such as `control:x`, is body text, and the body's hash then has to cover it. When a control line is present, one blank line may follow it, and that blank line also belongs to the header.
3. **The body:** everything after the header.

The file is read as UTF-8 text, with every line ending translated to a single line feed. The `sha256` value must equal the SHA-256 of the body, encoded as UTF-8, with lines joined by single line feeds and nothing added at the end. The body must contain at least one character that is not whitespace. So a file of exactly seven lines whose seventh is a control line has an empty body (section 8, case 3). The `bytes` value must be present and non-empty, but W1.2 does not compare it to the body (section 12, decision 3).

Only the body is searched for terms. Header lines, including the control line and the blank line after it, never count toward hits, even when a value such as a `source_url` slug contains a term.

A file that is not valid UTF-8 cannot be read (section 8, case 8). A headed file that starts with a byte-order mark fails as a malformed header (section 8, case 2), because its first key is then not `source_url`.

Example. The body has no line feed after its last line:

```text
source_url: https://example.com/jobs/example-a
api_endpoint: https://example.com/api/jobs/example-a
fetched_at: 2026-01-15T09:00:00Z
http_status: 200
sha256: 7d2961bb63a0934815529950556722eac09f95910c6c0cf6e0391a6948adac7d
bytes: 114
Senior Engineer, Example A
You will build agents and evals in Python.
Experience with a knowledge graph is a plus.
```

### 4.3 Raw posting with a sidecar

When a file named `<posting>.txt.meta.json` sits beside `<posting>.txt`, the sidecar is used and the posting has no header. The sidecar is a JSON object:
- `format` is exactly `raw-posting-with-sidecar`;
- `source_url` is a string on the secure web scheme;
- `bytes` is an integer;
- `sha256` is a string.

The whole posting file, encoded as UTF-8, must have exactly `bytes` bytes and that SHA-256. Its text must contain a character that is not whitespace. The whole file is the body.

### 4.4 Term table

A tab-separated file with a header row and these columns:
- `family`: the name the output prints;
- `pattern`: a pattern in Python's regular-expression syntax, matched without regard to case;
- `note`: may be empty.

A family can have several rows; each row adds one variant. Families keep the order in which they first appear.

Two note values carry meaning:
- `chosen`: the family is a term the user has chosen. The report labels it, and the scan never treats it as something to replace (6.6).
- `must-find`: the family is the run's check that it sees the postings (8, case 4). In the modes that read postings, a table needs at least one `must-find` family.

A note applies to its whole family. A family is `chosen` when any of its rows carries `chosen`, and `must-find` when any of its rows carries `must-find`. When rows of one family carry different notes, each meaning applies on its own, so a family can be both. Any other note value is allowed and has no effect, no label and no error; today's behaviour is unchanged.

Every pattern is compiled when the table is read. A pattern that is not a valid regular expression stops the run (section 8, case 9).

The fixtures use only plain words as patterns.

### 4.5 Copy files

Any text file. A file whose name ends in `.ts` is cleaned before counting, unless `--keep-notes` is given:
1. **Note strings.** Every `note` property whose value is a quoted string (double quote, single quote or backtick; backslash escapes in the first two) is rewritten as `note: ''`.
   - The key is the lower-case word `note` standing alone: `footnote:` and `notes:` don't count, and neither does `Note:`. A key after a non-word character, as in `my-note:`, does count.
   - Any whitespace, line feeds included, may sit on either side of the colon.
2. **Blocks.** Every `/* … */` block is then removed and replaced by nothing, so `aa/* x */bb` becomes `aabb`. A block can span lines.
3. **Comment lines.** Every line whose first non-blank characters are `//` is then removed, together with its line feed, so no blank line is left behind.

The cleanings run in that order, each on the result of the one before:
- a `/*` inside a note string goes with that string;
- a `//` line inside a block goes with the block;
- a `/*` inside a `//` line still opens a block that runs to the next `*/`, even on a later line, and that block is removed before the comment-line step.

`--keep-notes` turns off all three. Files with other names are used as they are.

A copy file is read as UTF-8. One that is not valid UTF-8 stops the run (section 8, case 8). A byte-order mark is read as an ordinary character and doesn't affect counting.

## 5. Counting

- **Hits.** A variant's hits in a text are its non-overlapping matches, found left to right, without regard to case. A family's hits are the sum over its variants. A pattern of plain letters also matches inside longer words: `agent` counts once in `agents`.
- **Demand.** A family's demand is the number of postings in which it has at least one hit, out of all the postings read.
- **Share.** A family's share is its demand divided by the posting count.
- **Percent.** The percent printed is the share times 100, rounded to the nearest whole number, with exact halves rounded to the even neighbour: 12.5 prints as 12.

## 6. Modes and output

Exit status for every mode: **0** means the run worked, whether or not it found gaps; **2** means it cannot run (section 8). In W1.2 no mode exits 1 (section 12, decision 1).

### 6.1 `demand`

`<cli> keywords demand --postings DIR --terms FILE` prints a heading line, a blank line, then a table. The heading line is `# Demand, <YYYY-MM-DD> (<N> postings)` with today's date. The table has one row per family:
- **Columns:** family, demand as `n/N`, percent, total hits across postings, and the top three variants.
- **Top variants:** up to three, each written as the variant pattern in backticks with its hit count in brackets, with any `|` in a pattern escaped with a backslash, separated by commas.
  - The variants are ordered by hits, high to low. On a tie, the variant that had a hit first comes first: postings in file-name order, then term-table row order within a posting.
  - A variant with zero hits is never listed. The cell is a dash exactly when no variant of the family has a hit, that is, when its demand is 0.
- **Row order:** demand first (high to low), then total hits (high to low), then family name (A to Z).
- **"A to Z"** everywhere in this spec means plain character order by code point, case-sensitive, so `Zeta` comes before `alpha`. It compares the family name, never the printed label.
- Standard output ends with one blank line after the table.
- `--out FILE` also writes the text to that file, ending with a single line feed after the table, so without that final blank line.

### 6.2 `coverage`

`<cli> keywords coverage --terms FILE [--keep-notes] FILE…` prints a table:
- one column per copy file, headed by the file's base name;
- one row per family, in term-table order;
- each cell is the family's hits in that file.

It reads no postings, so the `must-find` rule (section 8, case 4) never applies to it. A table without a `must-find` family runs normally in `coverage`.

### 6.3 `report`

`<cli> keywords report --postings DIR --terms FILE [--keep-notes] --copy FILE…` prints:
1. **A table.** The columns are family, demand, one column per copy file, and gap.
   - **Family:** a `chosen` family is printed with ` (chosen)` after its name.
   - **Demand:** written `n/N (p%)`.
   - **Copy cells:** the family's hits in that file.
   - **Gap:** `GAP` or empty.
   - **Row order:** demand (high to low), then family name (A to Z).
2. **A blank line.**
3. **One summary line.**

A family is a **gap** when both are true:
- its share is at least 30 percent, compared exactly: 3 of 10 is a gap, 2 of 7 is not;
- it has zero hits across all the copy files given.

The summary line is `Keywords: ` followed by the gaps in table order, separated by `; `. Each gap is written as `<family> (<p>% of postings, 0 in copy)`. With no gaps, the line is `Keywords: none`.

### 6.4 Rules that hold in every mode

- It never edits a copy file, a posting or the term table.
- It never suggests wording, synonyms or replacements, and never prints a score.
- There is no density target and no minimum count beyond the 30 percent gap rule.

### 6.5 Table format

Tables are Markdown pipe tables: a header row, a separator row of `---` cells, then the data rows.

### 6.6 Chosen terms

A `chosen` family is reported like any other family, with its label. The scan never marks a chosen term the user's copy uses as unused, unneeded or replaceable, even when no posting uses it. Test 11.9 pins this.

## 7. Machine-readable output (W1.2b)

`--json` replaces the text output with a single JSON object containing:
- `mode`;
- `postings` (the count);
- `families`: an array in the text table's order. Each item holds `family`, `chosen` (true or false), `demand`, `percent`, `copy` (an object of file base name to hits), `gap` (true or false), and, for gaps only, `cites` (section 10).

The exit status is unchanged.

## 8. When it cannot run

It exits 2 with one line on standard error. It never prints an empty or all-zero table in place of a result. The cases:

1. The postings folder has no `.txt` files.
2. A header is malformed: wrong key, wrong order, missing separator, empty value, or fewer than seven lines.
3. A body does not match its `sha256`, a raw posting does not match its sidecar's `bytes` or `sha256`, or a body is blank.
4. In `demand` and `report`: every `must-find` family has zero demand across the postings read, which shows the run is not seeing the postings. The same applies when no family is marked `must-find`. `coverage` never checks this.
5. The term table is missing or has no rows.
6. A copy file named on the command line does not exist.
7. W1.2b: the stored posting a citation is about to quote no longer matches its recorded hash (section 9).
8. A posting, copy file or term table is not valid UTF-8.
9. A term pattern is not a valid regular expression.

## 9. Verbatim guarantee (W1.2b)

Every cited line is the posting's own text. The guarantee works in three steps:
- **Check first.** Before printing citations, the tool re-reads each cited posting from disk and re-checks its hash (4.2 or 4.3). A posting that fails is case 7: it exits 2 and cites nothing.
- **Exact text.** A cited line is the exact text of that line in the stored file, after line endings are translated to line feeds as in 4.2. Nothing is trimmed, re-cased or re-encoded.
- **Line numbers.** Line numbers count from 1 at the first line of the file, header included, so a reader can open the file and find the line.

This is the same promise the README makes for every quote the tools show: it can be checked word for word against the saved copy it came from, for as long as the user keeps that copy. Stored postings are covered.

## 10. The posting-line citation (W1.2b)

For each gap family, `report` cites the postings behind its demand.

**What is cited:** for every posting with a hit in that family, the line holding the first hit, in file-name order. The number of cited postings therefore equals the demand count `n`. When a hit runs across a line feed, every line it touches is cited.

**Text layout:** the citations come after the `Keywords:` line, under a line reading `Posting lines:`. Each gap family starts with a line naming the family, followed by one line per citation:

```text
  <posting file name>:<line number>: <line text>
```

Each family's citations end with a line giving the posting's `sha256`, or one line per posting when there are several.

**JSON layout:** each gap family's `cites` is an array of `{"posting": <file name>, "line": <number>, "text": <line text>, "sha256": <posting sha256>}`.

**Limit:** `--max-cites K` keeps the first K postings per family and prints `(and M more)` when more remain. The default is 3, and `--max-cites 0` cites every posting (section 12, decision 4).

## 11. Acceptance tests (known answers)

The fixtures are invented. They live under `tests/fixtures/keywords/`. The generator writes:
- each posting body exactly as listed, with no line feed after its last line, then the header around it, with `sha256` and `bytes` computed from the body;
- the copy files exactly as listed, each ending with one line feed.

Every posting uses `fetched_at: 2026-01-15T09:00:00Z` and `http_status: 200`. Each `source_url` is `https://example.com/jobs/<slug>`, and each `api_endpoint` is `https://example.com/api/jobs/<slug>`.

**Term table T1** (columns `family`, `pattern`, `note`):

```text
family	pattern	note
agents	agents	must-find
evals	evals
python	python
knowledge-graph	knowledge graph
field-notes	field notes	chosen
```

**Postings P1.** The files are `2026-01-15-example-a.txt`, `-example-b.txt` and `-example-c.txt`. Their bodies:

```text
example-a:
Senior Engineer, Example A
You will build agents and evals in Python.
Experience with a knowledge graph is a plus.

example-b:
Staff Engineer, Example B
We ship agents to customers.
Python is required.

example-c:
Lead Engineer, Example C
Build evals for our agents.
Field notes from customers guide the roadmap.
```

**The copy files:**
- `copy.txt` is the single line `I build agents and write evals.`
- `copy2.ts` is:
  ```text
  // python appears only in this comment line
  export default { text: "Python services in production", note: "knowledge graph" };
  /* field notes appear only in this block */
  ```
- `copy3.txt` is the single line `Field notes shape everything I write. I build agents.`
- `copy4.txt` is the single line `I build agents.`

### 11.1 `demand` on P1 (the date line shows the run date)

```text
| family | postings | % | hits | top variants |
|---|---|---|---|---|
| agents | 3/3 | 100% | 3 | `agents` (3) |
| evals | 2/3 | 67% | 2 | `evals` (2) |
| python | 2/3 | 67% | 2 | `python` (2) |
| field-notes | 1/3 | 33% | 1 | `field notes` (1) |
| knowledge-graph | 1/3 | 33% | 1 | `knowledge graph` (1) |
```

Exit 0.

### 11.2 `coverage copy.txt copy2.ts`

```text
| family | copy.txt | copy2.ts |
|---|---|---|
| agents | 1 | 0 |
| evals | 1 | 0 |
| python | 0 | 1 |
| knowledge-graph | 0 | 0 |
| field-notes | 0 | 0 |
```

Exit 0. The comment line, the `note:` string and the block are not counted.

### 11.3 `coverage --keep-notes copy2.ts`

The rows give: agents 0, evals 0, python 2, knowledge-graph 1, field-notes 1. Exit 0.

### 11.4 `report --copy copy.txt` on P1

```text
| family | demand | copy.txt | gap |
|---|---|---|---|
| agents | 3/3 (100%) | 1 |  |
| evals | 2/3 (67%) | 1 |  |
| python | 2/3 (67%) | 0 | GAP |
| field-notes (chosen) | 1/3 (33%) | 0 | GAP |
| knowledge-graph | 1/3 (33%) | 0 | GAP |

Keywords: python (67% of postings, 0 in copy); field-notes (33% of postings, 0 in copy); knowledge-graph (33% of postings, 0 in copy)
```

Exit 0.

### 11.5 `report --copy copy.txt copy2.ts` on P1

The python row is no longer a gap. The summary line reads:

```text
Keywords: field-notes (33% of postings, 0 in copy); knowledge-graph (33% of postings, 0 in copy)
```

Exit 0.

### 11.6 The 30 percent edge and rounding

Postings E10, E7 and E8 are generated sets of 10, 7 and 8 postings. Posting `i` has these two body lines:
- `Engineer <i>, Example Edge`
- `We build agents. Python helps.` for the first k postings, and `We build agents. Go helps.` for the rest. k is 3, 2 and 1 respectively.

The file names are `2026-01-15-edge-<ii>.txt`, where `<ii>` is two-digit and the slug is `edge-<ii>`. With `report --copy copy4.txt`:
- E10 gives the python row `3/10 (30%)`, marked GAP, and `Keywords: python (30% of postings, 0 in copy)`.
- E7 gives `2/7 (29%)`, no gap, and `Keywords: none`.
- E8 gives `1/8 (12%)`, no gap, and `Keywords: none`.

### 11.7 Cannot run

Each case exits 2, prints nothing on standard output, and prints one line on standard error that names the problem:
1. an empty postings folder;
2. example-a with `a plus.` changed to `a must.` in the body, so the hash fails;
3. example-b with its key `http_status` changed to `status`;
4. a single posting whose body is `Data Engineer, Example D` and `Python and evals.`, so the `must-find` family has zero demand;
5. `report --copy` naming a file that does not exist.

### 11.8 Posting file round trip

Write a posting with the posting-file writer, then read it back:
- the body is unchanged;
- the recorded `sha256` matches;
- changing one body character makes the read fail (case 3).

### 11.9 A chosen term is never something to replace

Run `report --copy copy3.txt` on example-a and example-b only:
- field-notes is `0/2 (0%)` and labelled ` (chosen)`, with copy hits 1 and no GAP;
- the summary line names only python, evals and knowledge-graph;
- no output anywhere suggests removing, replacing or reconsidering field-notes.

### 11.10 Citation (W1.2b)

`report --copy copy.txt` on P1 prints, after the summary line:
- under `Posting lines:` for python: `2026-01-15-example-a.txt:8: You will build agents and evals in Python.` and `2026-01-15-example-b.txt:9: Python is required.`;
- for field-notes: `2026-01-15-example-c.txt:9: Field notes from customers guide the roadmap.`;
- for knowledge-graph: `2026-01-15-example-a.txt:9: Experience with a knowledge graph is a plus.`;
- each posting's sha256, as in its header.

In every case the count of cited postings equals the family's demand count. A test re-reads each cited file and asserts that the cited text is exactly that line. With the same output in `--json`, the parsed `cites` arrays hold the same posting, line, text and hash.

### 11.11 Citation against a changed posting (W1.2b)

Edit example-a on disk after its header is written, without fixing the hash, then run 11.10. It exits 2 (case 7), prints nothing on standard output, and quotes no line.

## 12. Decisions

1. **Exit status.** W1.2 exits 0 when it finds gaps, matching today's behaviour, and 2 when it cannot run (section 8). From W1.2b, a run that finds gaps exits 1. That change ships as its own dated decision, after the parity release, so no parity comparison spans it.
2. **Note values.** The tool has one vocabulary, `chosen` and `must-find`, with no aliases. A term file that uses other labels is translated before it reaches the tool.
3. **`bytes` in a headed posting.** The posting writer (W1.4) always writes it correctly. W1.2 requires it and does not check it. From W1.2b it is checked, and a mismatch is section 8 case 3.
4. **`--max-cites`.** The default is 3 cited postings per gap family, followed by `(and M more)` when there are more. `--max-cites 0` cites every posting.
5. **The `demand` report.** It is written to stdout, and to the file named by `--out` when given. There is no default write location.
6. **Copy files that share a base name** in `coverage` and `report` are labelled by the shortest path suffix that tells them apart, and only when names collide. With no collision, output is byte-identical to the base-name form.
   - A **path suffix** is the last k components of the path as given, after `~` expansion and after removing `./` components and repeated slashes, joined by `/`.
   - k is chosen separately for each group of colliding names: the smallest k that makes the labels in that group distinct. Files outside any collision keep their base names.
   - The same path given more than once, after that normalisation, is read once and gets one column, as today.
