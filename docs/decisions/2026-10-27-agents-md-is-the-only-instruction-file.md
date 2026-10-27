# AGENTS.md is the only instruction file

Date: 2026-10-27

## The rule

> **`AGENTS.md` is the only instruction file. The repository has no
> `CLAUDE.md`.**

## Why

This repository is meant to be opened through the reader's own AI agent, so
`AGENTS.md` is its entry point. Claude Code loads `AGENTS.md` itself, but only
when no `CLAUDE.md` sits anywhere in the folder chain: one such file turns
native loading off for the whole chain (measured with /context on Claude Code
2.1.309). The one-line `CLAUDE.md` that bridged to `AGENTS.md` was therefore
removed. It held no instructions of its own, so no instruction text changed.

This supersedes the 2026-10-19 record that kept that one-line file.
