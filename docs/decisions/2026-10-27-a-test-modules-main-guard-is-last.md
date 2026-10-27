# A test module's main guard is last

Date: 2026-10-27

## The rule

> **A test module's `if __name__ == "__main__":` guard is its last statement.**

## Why

Run as a script, a test module's `unittest.main()` runs, and exits, at the
guard. A test class defined after the guard never runs that way, while test
discovery still runs it.

`LayoutCase` checks `tests/test_barred.py`. The other test modules hold the rule
by review.
