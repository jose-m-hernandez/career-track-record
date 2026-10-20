# The changelog follows Keep a Changelog and Semantic Versioning

Date: 2026-10-19

## The rule

> **`CHANGELOG.md` follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
> and releases follow [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).
> Every change adds a line under `## [Unreleased]`, in the group that fits
> (Added, Changed, Deprecated, Removed, Fixed, Security). A release moves those
> lines under a dated version heading and is tagged `vX.Y.Z` with an annotated tag.**

## Why

A reader should be able to see what changed and when without reading the
history. Adding the line in the same change keeps the log true; writing it at
release time from memory does not. Semantic Versioning tells a user whether an
upgrade can break them.

The cost is one line per change. A check that fails a pull request which does
not touch `CHANGELOG.md` is planned as its own change.
