# `track-record record`

Keep your record as tables: plain files, one row per line, tab-separated or CSV, where a fact names its source and a correction names the fact it corrects. Nothing stops those references from drifting apart: a source is renamed, a row is pasted twice, a date is mistyped, an old row is edited in place. The record check reads a declaration you write, the tables it names and the rules it sets, and reports each break by file and line. It never edits a file, and it never prints what a cell says: output holds only the tables, columns and paths your declaration names, line numbers and counts.

The declaration is a text file in the plan-file syntax of the reader commands: `key: value` lines, each item on its own indented line, fields separated by ` | `, and `#` comment lines. Paths are relative to the declaration's folder, may also be absolute or use `..`, and are opened as written. This one is invented:

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

`tables` names each table, its file, its format (`tsv` or `csv`) and its key column. `references` says that each reference in a column must be a key of a column in another table, and how a cell holds references: `single`, `list ,` (a list, split at the characters you name) or `pattern REGEX` (each match is one). `required` forbids an empty cell, `values` allows only the values you list (the `grade` column above: [grades](grades.md)), `dates` wants `YYYY-MM-DD` dates that exist, `corrections` checks that a correction points at one earlier row of the same table and is not dated before it, and `earlier` checks that an earlier copy of a file is still, byte for byte, the start of the file now. The rules are in [docs/specs/record-check.md](../specs/record-check.md), and the idea behind them in [docs/record-model.md](../record-model.md).

From a clone, in the repository's own test fixtures (`tests/fixtures/record/known/`), the check gives:

    cd tests/fixtures/record/known
    track-record record record.txt
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

The run exits 1 because checks FAIL. A line number is where the row starts. A row with the wrong number of fields is ragged: it is named but nothing else checks it, and a reference to it dangles. A whole row has as many fields as the header.

A check that looked at nothing is DEAD, never OK: its table file is missing, empty, not UTF-8 or not readable as CSV, a column it needs is missing or repeated in the header, no whole row is left, or it met nothing to check (every cell blank, no filled cell, no correction). A DEAD check vouches for nothing, and the run exits 2. An earlier copy that is the table's own file, by the same path or through a link, is DEAD too. Before it reads your declaration, the check also runs every kind of check, and each way a cell holds references, on built-in invented tables with one planted fault each, and stops with `cannot run: self-test failed` if one does not find exactly its fault.

Add `--report-only` to report every finding without letting a finding raise the exit status, for a record with known faults that you are repairing. A DEAD check still exits 2. Exit 0 means every check is OK (or, with `--report-only`, none is DEAD), 1 means a check found a problem, and 2 means a check is DEAD or the check couldn't run, for example because the declaration has a problem. Spec: [docs/specs/record-check.md](../specs/record-check.md).

Limits: every table is read into memory whole. A `pattern` rule runs your own regular expression as written, and one that backtracks heavily can run slowly.
