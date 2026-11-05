# Command line: behaviour spec

Status: accepted.
Date: 2026-10-22.
Revision: 4. Adds `<cli> panel`, with its fixed help text (sections 2, 4 and 5). Revision 3 added `<cli> claims`.

`<cli>` is the command name until it is settled. This release names it `track-record`.

## 1. Scope

The top-level command, and the help rule every command shares. Each command's own spec governs everything else: keywords (keyword-scan.md), barred (barred.md), tone (tone-and-tells.md), ab (reader-ab.md), claims (claims.md), panel (reader-panel.md).

## 2. Running a command

`<cli> keywords`, `<cli> barred`, `<cli> tone`, `<cli> ab`, `<cli> claims` and `<cli> panel` run that command under its own spec. `ab` has three subcommands: `<cli> ab freeze PLAN`, `<cli> ab run PLAN [--live]` and `<cli> ab score PLAN`. `panel` has the same three: `<cli> panel freeze PLAN`, `<cli> panel run PLAN [--live]` and `<cli> panel score PLAN`.

## 3. Usage errors

`<cli>` with no command, or with a command it does not know, exits `2`, writes nothing to standard output, and writes a usage message to standard error.

## 4. Help

`-h` and `--help` are accepted at every level: `<cli>`, `<cli> keywords`, each keywords mode, `<cli> barred`, `<cli> tone`, `<cli> ab`, `<cli> claims`, `<cli> panel` and each `ab` and `panel` subcommand. Help goes to standard output, nothing goes to standard error, and the run exits `0`. Help reads no input file, list or rule file.

`<cli> --help` names the command in its usage line and lists the six commands, each with its one-line description:

- keywords: scan saved job postings for terms
- barred: report wording from your own barred list
- tone: flag hype, hedges and filler in your copy
- ab: compare two versions of your copy with test readers
- claims: fail on sentences your claims list hasn't approved
- panel: read one version blind through named lenses

If help cannot be written (standard output closed, or a write fails), the run stops, exits `2` and writes one line to standard error, `cannot run: cannot write output`, with no traceback. This is the same rule each command's spec states for its own output.

## 5. What this spec does not promise

The exact layout of the help and usage messages from `<cli>` and `<cli> keywords` is not promised. That includes section headings and line wrapping, which come from Python's argument parser and differ between Python versions. Only barred, tone, ab, claims and panel promise fixed help text. Barred, tone and claims state theirs in their own specs. For `ab` and `panel`, the help of the command and of each of its subcommands is fixed text, pinned by the command's tests. A missing or unknown subcommand, a missing PLAN, an extra argument or an unknown option exits `2` with one `cannot run: ...` line on standard error and nothing on standard output.
