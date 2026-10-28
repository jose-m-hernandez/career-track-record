# CLAUDE.md is a one-line bridge to AGENTS.md

Date: 2026-10-19

> **Superseded 2026-10-27** by `2026-10-27-agents-md-is-the-only-instruction-file.md` (a `CLAUDE.md` anywhere in the folder chain turns off Claude Code's native `AGENTS.md` loading, so the bridge was removed).

## The rule

> **`AGENTS.md` is the only instruction file. `CLAUDE.md` holds exactly one
> line, `@AGENTS.md`, and nothing else.**

## Why

This repository is meant to be opened and used through the reader's own AI
agent, so `AGENTS.md` is its entry point. Some agents read `AGENTS.md` directly.
Claude Code reads `CLAUDE.md` instead, and the `@AGENTS.md` line makes it load
the same file. One source means the instructions cannot drift between agents.

The alternative, two full instruction files, was rejected: they would diverge.
The cost is one extra file at the root.
