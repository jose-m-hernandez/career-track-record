# Record check: behaviour spec

Status: accepted.
Date: 2026-11-14.
Revision: 1. The signed spec (sha256 faba1585b0407cf770b282276101c5f381bea78a419bb5c8ddd1706e95174a0a) is reproduced below verbatim. Its owner signed it on 2026-11-14.

## Signed spec

<!-- signed spec begins: sha256 faba1585b0407cf770b282276101c5f381bea78a419bb5c8ddd1706e95174a0a -->
# Record check: behaviour spec

Status: revision 1, drafted on 2026-11-14 for the owner's signature. The drafter of this design had read the specification of a private tool that does a similar job for the maintainer's own records. No code or data from that tool is in this spec. Its wording was checked against that tool's specification and redrafted where it echoed it; the plain-English terms the check left in common, such as the flag name `--report-only`, keep their ordinary meaning.
Date: 2026-11-14.
Revision: 1. The first revision.

The command is `<cli> record`.

Every example in this file and in the tool's fixtures is invented. None of it comes from a real person's records, employers or claims.

## 1. Purpose

A career record kept as tables (facts, sources, corrections, claims) holds together only while its rows keep pointing at each other: a fact names its source, a correction names the fact it corrects. Nothing stops those pointers from drifting: a source is renamed, a row is pasted twice, a date is mistyped, an old row is edited in place. This command checks the tables against rules the user declares and reports each break by file and line. It checks METHOD.md's rules 1 to 4 as far as a table can show them. It never edits a file.

## 2. Scope

In:
- one declaration file naming the tables, their key columns and the rules (section 3.1);
- tables in two formats: tab-separated text and CSV (section 3.2);
- seven checks: the table check (row width and keys), references, required cells, allowed values, dates, corrections, and an earlier copy (section 4);
- a self-test of every check before any file is read (section 5.2);
- a report that names files, lines and declared names, and never a cell value (section 6).

Out:
- judging whether a fact is true, or whether a resolution is honest;
- the "what did the record say on a given date" view of METHOD.md rule 4: it would have to print record values;
- writing, repairing, sorting or rewriting any file;
- tables in any other format (JSON, spreadsheets, Office files), keys made of more than one column, and dates coarser than a day;
- fetching anything over the network.

Limits a user can meet:
- Every table is read into memory whole, so memory use grows with the tables' size.
- A `pattern` rule runs the user's own regular expression as written (section 3.3).

## 3. Inputs

### 3.0 Options

| Option | Meaning |
|---|---|
| `DECLARATION` | The declaration file. Exactly one is required. |
| `--report-only` | Report every finding, but a finding no longer raises the exit status (section 6). Repeating it changes nothing. It takes no value, and it is never abbreviated. |
| `-h`, `--help` | Write the fixed summary of section 3.4 to standard output and exit `0`. It reads no file, and wins over every other argument; after `--`, every argument is a file name. |

`-` alone is a file name, not standard input.

### 3.1 The declaration

- UTF-8 text. A byte-order mark at the very start is dropped. It uses the plan-file syntax of reader-ab.md section 3.1: each line is `key: value`, a list value is one item per indented line under its key, blank lines and lines starting with `#` are ignored, and an unknown or repeated key is a problem.
- Every key is a list key. An item is fields separated by ` | ` (a space, a vertical bar, a space); each field is trimmed, and an empty field is a problem. An item that repeats an earlier item under the same key, field for field, is a problem.
- Paths in the declaration are relative to the declaration's folder. A path may also be absolute, or climb out of that folder with `..`; it is opened as written, so a declaration can name any file its user can read. Output prints each path as the declaration writes it.

| Key | Item | Meaning |
|---|---|---|
| `tables` | `name \| file \| format \| key column` | A table. `name` holds letters, digits and `-` only, and is unique. `format` is `tsv` or `csv`. Required: at least one table. |
| `references` | `table \| column \| table \| column \| rule` | Each reference in the first table's column must be held by the second table's column, in one of its whole rows. `rule` is a cell rule (section 3.3). |
| `required` | `table \| column` | The cell must not be empty. |
| `values` | `table \| column \| value \| value ...` | A cell that is not empty must be one of the values, exactly. At least one value. |
| `dates` | `table \| column` | A cell that is not empty must be a date written `YYYY-MM-DD`, four digits, two and two, that exists in the calendar. |
| `corrections` | `table \| column \| date column` | A row whose cell in `column` is not empty is a correction of the row whose key is that cell, in the same table (section 4.6). |
| `earlier` | `table \| file` | `file` is an earlier copy of the table's file, which must still be there, byte for byte, at its start (section 4.7). |

Every table an item names must be declared under `tables`. Column names are not checked when the declaration is read: a column the table's header lacks makes that check DEAD (section 5.1).

### 3.2 Tables

- A table file is opened only if it is a regular file (a link to one is followed). It is read as bytes; a byte-order mark at the very start is dropped; the rest must be UTF-8 and must not hold a NUL character.
- **tsv**: LF, CRLF and a lone CR each end a line, and a line break at the end of the file does not start another line. Fields are separated by tabs. Nothing is quoted, and no line is a comment.
- **csv**: comma-separated, with double-quote quoting as Python's `csv` module reads it by default, in strict mode, with no limit on a field's length. A quoted field may hold a comma or a line break. A row starts on the line where its first character stands.
- Lines are numbered from 1. The first line is the header, which names the columns. Every later line that is not empty is a row. A row with exactly as many fields as the header is a **whole row**. A row with any other number of fields is a **ragged row**: the table check reports it, and nothing else looks at it, so none of its cells is checked and none can be the target of a reference.
- A column is found by its name in the header; the name must match exactly.

### 3.3 Cell rules

A reference's rule says how a cell holds references:

- `single`: the cell, exactly as written, is one reference. Nothing is trimmed, and case counts. An empty cell holds none.
- `list CHARACTERS`: the cell is cut at every one of the characters after `list ` (for example `list ,;`); each piece loses its leading and trailing plain spaces, and empty pieces are dropped. A space cannot be one of the characters. A cell left with no piece holds none.
- `pattern REGEX`: every non-overlapping match of the Python regular expression REGEX, read left to right, is one reference, and an empty match is not one. A cell with no match holds none. Known limit: the expression is run as written, and one that backtracks heavily can make a run very slow.

A reference is **dangling** when no whole row of the target table holds it, exactly, in the target column. Comparison is exact: two texts that look alike but differ in case, in Unicode form (a composed and a decomposed accented letter, say) or by an invisible character do not match.

### 3.4 The help summary

`<cli> record --help` writes exactly this, followed by a line break:

```text
usage: track-record record [--report-only] DECLARATION

Check the tables of your record against the rules you declare.

  --report-only  report findings but exit 0 for them
  -h, --help     show this summary and exit

exit: 0 all checks OK, 1 a check found a problem, 2 a DEAD check or cannot run
```

## 4. The checks

Each check counts over its table's whole rows, and writes one finding line per fault, in file order.

### 4.1 Table (one for every declared table)

A ragged row is a fault: `<file>:<line>: fields <n>, the header has <h>`. Among whole rows, an empty key is a fault (`<file>:<line>: empty key`), and so is each row whose key, not empty, already stood on an earlier whole row (`<file>:<line>: repeated key, first on line <m>`). `repeats` counts those rows; `keys with repeats` counts the different keys they repeat.

### 4.2 References

A row whose cell holds no reference is **blank**. A row holding one or more dangling references is a fault: `<file>:<line>: dangling <k>`, where `<k>` is how many of that row's references dangle.

### 4.3 Required

An empty cell is a fault: `<file>:<line>: empty`.

### 4.4 Values

A cell that is not empty and is not one of the values is a fault: `<file>:<line>: outside the set`. Empty cells are not checked; `filled` counts the cells that are.

### 4.5 Dates

A cell that is not empty and is not a real date written `YYYY-MM-DD` is a fault: `<file>:<line>: not a date`. Empty cells are not checked; `filled` counts the cells that are.

### 4.6 Corrections

Each correction row gets at most one finding, the first that applies, where `<m>` is the line of the row it corrects:

1. `<file>:<line>: corrects itself`: the cell equals the row's own key;
2. `<file>:<line>: corrects a ragged row, line <m>`: no whole row has that key, but a ragged row holds it where the key column stands (the first such row is named);
3. `<file>:<line>: corrects a missing row`: no row has that key;
4. `<file>:<line>: corrects a key that is not unique`: more than one whole row has that key;
5. `<file>:<line>: corrects a later row, line <m>`: the corrected row comes after the correction;
6. `<file>:<line>: dates cannot be compared, line <m>`: either row's date cell is not a real date (section 4.5);
7. `<file>:<line>: dated before the row it corrects, line <m>`: the correction's date is before the corrected row's date. The same date is not a fault.

### 4.7 Earlier copy

The earlier copy's bytes must equal the start of the table file's bytes. Where the two differ at a byte that both files have, the first such byte gives `<file>:<line>: differs from the earlier copy`, where `<line>` is 1 plus the number of line breaks before that byte, counted as section 3.2 counts them (LF, CRLF or a lone CR). Where they do not, but the table file is shorter, the finding is `<file>: shorter than the earlier copy`. This check compares bytes only, so it needs no header and does not read the file as a table.

## 5. DEAD, and the self-test

### 5.1 A check is DEAD when

A DEAD check vouches for nothing. Its reason is the first that applies:

1. its table's file (for a reference, its own table's first, then the target's) is missing, is not a regular file, cannot be read, is not UTF-8, holds a NUL character, is empty, has an empty first line, or cannot be read as CSV. The reason names the file's state: `file missing`, `not a regular file`, `cannot be read`, `not UTF-8`, `holds a NUL character`, `empty file`, `no header`, `not readable as CSV`;
2. the header lacks a column the check needs (`no column <column>`), or names it more than once (`column <column> named twice`). A table check and a corrections check need the key column;
3. the table has no whole row (`no whole rows`);
4. the check met nothing to check: a reference check whose every cell is blank (`every cell blank`), a values or dates check with no cell filled (`no cell to check`), a corrections check with no correction row (`no correction rows`). A record that has no correction yet leaves the `corrections` item out of its declaration until it has one.

For a reference's target table, reasons 1 to 3 read `target <table>: <reason>`, for example `target origins: no column origin`.

An earlier-copy check is DEAD when its table's file is missing, is not a regular file or cannot be read, or when the earlier copy is missing (`earlier copy missing`), is not a regular file (`earlier copy not a regular file`), cannot be read (`earlier copy cannot be read`), is empty (`earlier copy empty`), or is the table's file itself, by the same path or through a link (`earlier copy is the table file itself`).

### 5.2 The self-test

Before the declaration is read, every check, and each of the three cell rules, runs on built-in invented tables, each with one planted fault. If any of them does not report exactly its planted fault, the run stops: exit `2`, nothing on standard output, and `cannot run: self-test failed: <check>` on standard error.

## 6. Output and exit status

One status line per check, in this order: the table checks in declaration order, then the references, required, values, dates, corrections and earlier checks, each in declaration order. Each status line is followed by its finding lines.

- `OK    <label>: <counts>`: the check ran and found no fault;
- `FAIL  <label>: <counts>`: the check ran and found at least one fault;
- `DEAD  <label>: <reason>` (section 5.1).

| Check | `<label>` | `<counts>` |
|---|---|---|
| table | `table <table>` | `whole rows <e>, ragged rows <n>, empty keys <k>, repeats <d>, keys with repeats <u>` |
| reference | `references <table>.<column> to <table>.<column>` | `whole rows <e>, blank <w>, references <r>, dangling <x>, rows with dangling <y>, distinct dangling <z>` |
| required | `required <table>.<column>` | `whole rows <e>, empty <k>` |
| values | `values <table>.<column>` | `whole rows <e>, filled <c>, outside the set <k>` |
| dates | `dates <table>.<column>` | `whole rows <e>, filled <c>, not a date <k>` |
| corrections | `corrections <table>.<column>` | `whole rows <e>, corrections <c>, faults <k>` |
| earlier | `earlier <table>` | `bytes earlier <b>, bytes now <B>` |

Then always one last line: `checks: OK <a>, FAIL <b>, DEAD <c>`. Counts are printed as numbers, `0` included. `<file>` is the table file's path as the declaration writes it. File paths and column names are escaped as printed paths are in barred.md section 6.

**Privacy.** Output never contains a cell value: no key, reference, date, value or header name that the declaration does not name. It names only declared tables, columns and paths, line numbers and counts. A test plants a sentinel string in every kind of cell of the fixtures, runs every known answer and every DEAD and cannot-run case, and finds it in neither standard output nor standard error.

**Exit status:** `0` when every check is OK; `1` when any check FAILs and none is DEAD; `2` when any check is DEAD or the run cannot go ahead. With `--report-only`, a FAIL does not raise the exit status, so the run exits `0` unless a check is DEAD or it cannot run. The highest applies.

## 7. When it cannot run

The run exits `2`, writes nothing to standard output, and writes `cannot run: <reason>` lines to standard error, when: no DECLARATION is named, or more than one (`record needs a DECLARATION file`, `record takes one DECLARATION file, not several`); an option is unknown, an abbreviation such as `--report` included (`unknown option <option>`), or `--report-only` is given a value (`--report-only takes no value`); the declaration is not a regular file or cannot be read (`cannot read the declaration: <name>`), or is not UTF-8 (`the declaration is not valid UTF-8: <name>`); the declaration has problems, one line each (`declaration line <n>: <problem>`), or names no table (`the declaration names no table`); or the self-test fails (section 5.2). `<name>` is the file's name without its folder, escaped. When the output cannot be written, it follows cli.md section 4: exit `2`, one line `cannot run: cannot write output`, and no traceback. The run never shows a traceback.

## 8. Decisions, with reasons

- **Fail by default.** A checker that exits 0 on a broken record would be read as a pass; `barred` and `claims` fail on a finding too. `--report-only` is for a record that has known faults and is being repaired.
- **DEAD exits 2 in both modes.** A check that examined nothing has not checked anything. It is never reported as passed, as METHOD.md rule 6 asks.
- **No cell value in the output.** Output ends up in terminals, logs and an AI agent's context. Line numbers are enough to find a fault in your own file.
- **One syntax.** The declaration uses the plan-file syntax the reader commands already use, so there is one way to write a file for this tool.
- **A self-test first.** A check that cannot find its own planted fault would report a clean record falsely.
- **The earlier copy is compared as bytes.** "Never overwrite" means the old bytes are still there, exactly; any rewrite, even of a single character, shows.

## 9. Known answers

An invented declaration, `record.txt`:

```text
# invented example
tables:
  entries | entry-table.tsv | tsv | entry
  origins | origin-table.csv | csv | origin
references:
  entries | cites | origins | origin | list ,
required:
  entries | grade
values:
  entries | grade | A | B | C | D
dates:
  entries | recorded
corrections:
  entries | corrects | recorded
earlier:
  entries | entry-table-before.tsv
```

`entry-table.tsv`, with `→` standing for a tab:

```text
entry→cites→grade→recorded→corrects
e-01→o-01→A→2026-01-05→
e-02→o-01, o-02→B→2026-01-06→
e-03→o-09→E→2026-02-30→
e-04→→C→2026-01-07→e-01
e-02→o-02→D→2026-01-08→
e-06→o-02→→2026-01-03→e-04
e-07→o-01→B
```

`origin-table.csv`:

```text
origin,kind
o-01,offer letter
o-02,"old resume, 2019"
```

`entry-table-before.tsv` is the first three lines of `entry-table.tsv`. Every line of the three tables ends with LF. `<cli> record record.txt` writes:

```text
FAIL  table entries: whole rows 6, ragged rows 1, empty keys 0, repeats 1, keys with repeats 1
entry-table.tsv:6: repeated key, first on line 3
entry-table.tsv:8: fields 3, the header has 5
OK    table origins: whole rows 2, ragged rows 0, empty keys 0, repeats 0, keys with repeats 0
FAIL  references entries.cites to origins.origin: whole rows 6, blank 1, references 6, dangling 1, rows with dangling 1, distinct dangling 1
entry-table.tsv:4: dangling 1
FAIL  required entries.grade: whole rows 6, empty 1
entry-table.tsv:7: empty
FAIL  values entries.grade: whole rows 6, filled 5, outside the set 1
entry-table.tsv:4: outside the set
FAIL  dates entries.recorded: whole rows 6, filled 6, not a date 1
entry-table.tsv:4: not a date
FAIL  corrections entries.corrects: whole rows 6, corrections 2, faults 1
entry-table.tsv:7: dated before the row it corrects, line 5
OK    earlier entries: bytes earlier 90, bytes now 201
checks: OK 2, FAIL 6, DEAD 0
```

It exits `1`; with `--report-only`, `0`. With `entry-table.tsv` removed, every check on `entries` is DEAD with `file missing`, the earlier check included, and the run exits `2` in both modes.

## 10. Command line (cli.md, Revision 6)

cli.md names `<cli> record` among the commands, with the one-line description `check your record's tables against rules you declare`, and lists `record` among the commands whose fixed help text is stated in their own spec.
<!-- signed spec ends -->
