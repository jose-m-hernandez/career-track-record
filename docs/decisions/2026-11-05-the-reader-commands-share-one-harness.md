# The reader commands share one harness

Date: 2026-11-05

Status: proposed with the reader panel draft (docs/specs/reader-panel.md); the maintainer settles it with that spec.

## The rule

> **What `track-record ab` and `track-record panel` share lives in one module,
> `reader_harness.py`: the plan-file syntax, the freeze and its checks, the run
> folder and its errors, the live-reader preview and read, the read loop with
> its spend ceiling and run log, the reply-field splitter and the tail of every
> result. Each command keeps its own plan meaning, fake reader and scoring.
> The harness starts no program: `ab_reader_command.py` stays the only module
> that starts a reader command, in its one call.**

## Why

The panel needs the same freeze-by-hash, the same `--live` rule, the same spend
ceiling and the same reply parsing as `ab`. Copying them would give two places
for one rule to drift, and the no-network test's one excused module would have
to become two. Moving them into a module both import keeps one place for each
rule and leaves `ab_reader_command.py` as the one call site.

The cost is that a change to the harness changes both commands, so a change
there runs both commands' tests.
