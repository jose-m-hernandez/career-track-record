# Command line: behaviour spec

Status: accepted.
Date: 2026-10-22.
Revision: 12. Adds `<cli> absence`, with its fixed help text (sections 1, 2, 4 and 5). Revision 11. Notes that `<cli> claims` takes `--require-local-sources` and lists it in its fixed help text (sections 2 and 5). Revision 10 added `<cli> parse`, with its fixed help text (sections 1, 2, 4 and 5). Revision 9 lists `setup` in the help list and fixes the command count (sections 1, 2, 4 and 5). Revision 8 added `<cli> wrapped-compounds`, with its fixed help text (sections 1, 2, 4 and 5). Revision 7 added `<cli> drafts` and its subcommands `check` and `extract`, with its fixed help text (sections 1, 2, 4 and 5). Revision 6 added `<cli> record`, with its fixed help text (sections 1, 2, 4 and 5). Revision 5 noted that `<cli> claims` takes `--check-sources` and lists it in its fixed help text (sections 2 and 5). Revision 4 added `<cli> panel`, with its fixed help text (sections 2, 4 and 5). Revision 3 added `<cli> claims`.

`<cli>` is the command name until it is settled. This release names it `track-record`.

## 1. Scope

The top-level command, and the help rule every command shares. Each command's own spec governs everything else: keywords (keyword-scan.md), barred (barred.md), tone (tone-and-tells.md), ab (reader-ab.md), claims (claims.md), panel (reader-panel.md), record (record-check.md), absence (absence.md), drafts (drafts.md), wrapped-compounds (wrapped-compounds.md), parse (parse.md). `setup` has no spec of its own.

## 2. Running a command

`<cli> keywords`, `<cli> barred`, `<cli> tone`, `<cli> ab`, `<cli> claims`, `<cli> panel`, `<cli> record`, `<cli> absence`, `<cli> drafts`, `<cli> wrapped-compounds` and `<cli> parse` run that command under its own spec. `<cli> setup` chooses your record folder; it takes `--folder PATH` or `--show`. `ab` has three subcommands: `<cli> ab freeze PLAN`, `<cli> ab run PLAN [--live]` and `<cli> ab score PLAN`. `panel` has the same three: `<cli> panel freeze PLAN`, `<cli> panel run PLAN [--live]` and `<cli> panel score PLAN`. `claims` takes `--check-sources`, which also checks each quote in the claims list against the source its entry cites, and `--require-local-sources`, which runs that check and also fails an approved quote it could not check and an approved entry with no source (claims.md). `drafts` has two subcommands: `<cli> drafts check FILE [--earlier COPY]` and `<cli> drafts extract FILE ID --out OUT [--earlier COPY]` (drafts.md). `wrapped-compounds` takes `--control TEXT` (repeatable) and one or more PDF files, and reads no configuration (wrapped-compounds.md). `parse` takes `--name TEXT`, `--contact TEXT` (repeatable), `--sections LIST`, `--min-page-chars N` and one or more PDF files, and reads no configuration (parse.md). `absence` takes one DECLARATION file, runs as `<cli> absence DECLARATION`, and reads no configuration (absence.md).

## 3. Usage errors

`<cli>` with no command, or with a command it does not know, exits `2`, writes nothing to standard output, and writes a usage message to standard error.

## 4. Help

`-h` and `--help` are accepted at every level: `<cli>`, `<cli> keywords`, each keywords mode, `<cli> barred`, `<cli> tone`, `<cli> ab`, `<cli> claims`, `<cli> panel`, `<cli> record`, `<cli> absence`, `<cli> drafts`, `<cli> wrapped-compounds`, `<cli> parse`, `<cli> setup`, each `drafts` subcommand and each `ab` and `panel` subcommand. Help goes to standard output, nothing goes to standard error, and the run exits `0`. Help reads no input file, list or rule file.

`<cli> --help` names the command in its usage line and lists the twelve commands, each with its one-line description:

- keywords: scan saved job postings for terms
- barred: report wording from your own barred list
- tone: flag hype, hedges and filler in your copy
- ab: compare two versions of your copy with test readers
- claims: fail on sentences your claims list hasn't approved
- panel: read one version blind through named lenses
- record: check your record's tables against rules you declare
- absence: show that your listed terms appear nowhere in the files you declare
- drafts: check a file of a document's versions, or extract one
- wrapped-compounds: find hyphenated words split across two lines in a PDF
- parse: check what a text extractor gets from your résumé PDF
- setup: choose your record folder

If help cannot be written (standard output closed, or a write fails), the run stops, exits `2` and writes one line to standard error, `cannot run: cannot write output`, with no traceback. This is the same rule each command's spec states for its own output.

## 5. What this spec does not promise

The exact layout of the help and usage messages from `<cli>` and `<cli> keywords` is not promised. That includes section headings and line wrapping, which come from Python's argument parser and differ between Python versions. Only barred, tone, ab, claims, panel, record, absence, drafts, wrapped-compounds and parse promise fixed help text. Barred, tone, claims, record, absence, drafts, wrapped-compounds and parse state theirs in their own specs. Claims' summary lists `--check-sources` from claims.md revision 2 and `--require-local-sources` from claims.md revision 3. For `ab` and `panel`, the help of the command and of each of its subcommands is fixed text, pinned by the command's tests. A missing or unknown subcommand, a missing PLAN, an extra argument or an unknown option exits `2` with one `cannot run: ...` line on standard error and nothing on standard output.
