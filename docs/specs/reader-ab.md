# Reader A/B harness: behaviour spec

Status: accepted.
Date: 2026-11-05.
Revision: 2. The signed spec (sha256 9bb098e138a03df8ffbf6e077dde0868f3c71b2305050e831015113d57d840a6) is reproduced below verbatim. Its owner signed it on 2026-11-05, with its one-sided flag text applied at its request. It revises revision 1.2's signed text (sha256 a9e1b896030bd4fbc0c5c553b6f8394debfb403e3963d54b9587ba04fad18f53), puts the evidence beside each verdict and corrects section 1. The build interpretations of revision 1.1 follow it and still apply.

## Signed spec

<!-- signed spec begins: sha256 9bb098e138a03df8ffbf6e077dde0868f3c71b2305050e831015113d57d840a6 -->
# Reader A/B harness: behaviour spec

Status: revision 2, drafted on 2026-11-05 for the owner's signature. Revision 1 was accepted with all six decisions (§ 9) settled: 1 to 5 by the owner on 2026-10-28, and 6 by the owner on 2026-10-29.
Date: 2026-11-05.
Revision: 2. Puts the evidence beside each verdict and corrects what § 1 claims for the control (sections 1, 2, 3.1, 5.5, 6, 7, 8, 9 and 10). Every verdict is decided as in revision 1; nothing in revision 2 changes a verdict, an exit status or the prompt. Revision 1 was draft 3. It replaces draft 2 (2026-10-28). Draft 3 makes the fixtures' change a neutral one (a skills block moved above the experience section), uses neutral reader comments as the mechanism strings in 10.11 and 10.15, renames the versions in the tests to match, and settles decision 6. Draft 2's changes to draft 1 (2026-10-27) stand: the noise threshold becomes a plan field stated as a share; the fake reader's behaviour is defined on the A/A arm; slot alternation runs over the arm; failed reads leave the denominators; mechanism checks count replies per arm against the A/A floor; and the arms run in a fixed order. Tests 10.17 to 10.31 are new.

The command is `track-record ab`.

Every example in this file and in the tool's fixtures is invented. None of it comes from a real person's résumés, postings, employers, prompts or results.

## 1. Purpose

Compare two versions of the same career document by asking model readers, and report whether one reads better, without letting the person running the test move the goalposts after seeing the answer.

The tool exists because a tailored résumé changes many times in a day, and each change is judged by feel. The harness turns a change into a test with three parts: a hypothesis fixed in advance, a noise control, and a check that the two versions differ only where the change was meant to be.

It follows rule 6 of the method ("Test before you trust") for the comparison itself: the isolation check (§ 4.2) must find zero changed lines on the A/A arm and some on every comparison before any read. For the reads, every run carries one control, the A/A arm. It shows whether the readers pick a side when the two versions are the same. It does not show that they would see a real difference, so a run that finds no difference does not show that the readers could have found one.

## 2. Scope

In scope:

- paired reads: a reader sees one posting and two versions, A and B, and scores both;
- the A/A control: the same version in both slots, run in every run, before any comparison;
- preregistration: the hypotheses and decision rules, frozen by hash before the first read;
- the isolation check: the text that differs between the two versions, compared with what the plan says should differ;
- scoring the replies against the frozen rules, and writing a result;
- the evidence beside each verdict: an exact p-value, an interval, the reads that are missing, and what the readers' scores can and cannot show (§ 6.1).

Out of scope:

- writing or rewriting copy (readers may suggest rewrites; the tool never applies one);
- deciding what is true (a reader's suggestion is a lead; the user's own record decides);
- cold reads of a single version (planned for a later revision, § 9.4);
- any network call from the test suite.

## 3. Inputs

### 3.1 The plan file

The plan is a plain-text file the user writes before any read. Each line is `key: value`; a list value is one item per indented line under its key. Blank lines and lines starting with `#` are ignored, and an unknown key is an error (exit `2`). The plan names:

- `posting`: the posting file;
- `versions`: each version file, with a short name;
- `comparisons`: one or more comparisons, each written `X vs Y` in version names. The tool adds the A/A arm (below) when the plan leaves it out, and says so in the result;
- `aa-version`: the version used in both slots of the A/A arm (default: the second version of the first comparison);
- `readers`: each reader's name and command (§ 5.1), and whether it is `not-blind` (§ 5.5);
- `reads-per-reader`: reads per arm for each reader (default 3, which gives 6 reads per arm with two readers);
- `hypotheses`: each with its decision rule written as counts of valid reads. For example, "SUPPORTED if Y is preferred in 6 of 6; REFUTED if X is preferred in 4 or more; otherwise INCONCLUSIVE";
- `mechanisms` (optional): a case-insensitive pattern, the reply fields it is matched against, and the count of matching replies that supports it. The default fields are every free-text field: `DROVE-IT`, `DOUBTS`, `UNDERSOLD`, `OVEREXPLAINED`, `OWNED`, `FLAG-FIXES`, and the rationale part of `PREFER` (§ 5.4);
- `change-scope`: the line patterns where the two versions of each comparison may differ;
- `noise-threshold`: the share of valid A/A reads that are non-TIE and marked `clearly` or `strongly` at which every comparison is reported INCONCLUSIVE (default `1/2`, § 6);
- `sidedness` (optional): `two`, `greater` or `less`, the side of the sign test in § 6.1 (default `two`). `greater` tests whether the second-listed version of a comparison is preferred, and `less` whether it is not;
- `alpha` (optional): the level the disagreement flag in § 6.1 compares each p-value with (default `0.05`). It is written as `0.` followed by one or more digits, not all of them zero, and in no other form;
- `spend-ceiling`: the run's limit, in the reader's own units;
- `amends` (optional): the freeze file of the plan this one replaces (§ 3.2).

### 3.2 Freeze

`track-record ab freeze PLAN` hashes the plan and every input it names (sha256), writes the hashes to a freeze file beside the plan, and exits `0`.

- It refuses, with exit `2`, if any named input is missing, if a freeze file already exists, or if the run folder already holds a reply.
- After a freeze, neither the plan nor its inputs may change. A run checks every hash first and exits `2`, naming the file, if any one differs. That includes the plan itself.
- The run folder is the folder that holds the plan.
- An amendment is a new plan, in a new run folder, whose `amends` key names the earlier freeze file. It gets its own freeze. The result names both freezes, and the earlier freeze file and run folder are never edited.

### 3.3 Version and posting files

These are UTF-8 text, or PDF read through the same text extraction the barred check uses. File names are free; slots are not (§ 4).

## 4. Slots and isolation

### 4.1 Slot assignment

Within an arm, reads are numbered in the order they run: the first reader's reads, then the second reader's, and so on. Odd-numbered reads put the first-listed version in slot A, and even-numbered reads put the second-listed version there. With 6 reads, each version sits in slot A 3 times. With an odd count, the first-listed version gets the extra read in slot A, and the result shows each reader's slot split.

The key file is written before any read runs. Readers see only `A.txt` and `B.txt`.

### 4.2 The isolation check (before any read)

For each comparison, the tool compares the two versions line by line, after collapsing runs of spaces and dropping blank lines. It reports every changed line and marks each one as inside or outside the declared change scope.

- If every changed line is inside the scope, the check passes.
- If any changed line is outside the scope, the run stops before reading, exits `2` and prints those lines. The user then narrows the versions or widens the scope, in a new plan.
- If a comparison has no changed line at all, the run stops and exits `2`, because a file compared with itself is the control, not a test.
- A plan with no comparison exits `2` (no A/A arm is possible without a version to copy).

The A/A arm must show no changed line, and that is its own positive control. The check has to report zero on the A/A arm and nonzero on every real comparison, or the run does not start.

## 5. Readers

### 5.1 Pluggable

A reader is a command the tool runs once per read. The read folder is its only input and one reply file is its output. The tool ships one reader that needs no network, the fake reader (§ 5.3). Live readers are configured by the user and are never shipped with credentials.

### 5.2 Live runs and run order

The test suite and CI never start a live reader. For a live run, the tool prints the exact commands and the spend estimate. It runs them only when the user types the `--live` flag. Without `--live`, it prints, starts no reader, writes no reply and exits `0`. The fake reader never needs `--live`.

The A/A arm runs first, and then the comparisons in plan order. The spend ceiling stops the run between reads once it is reached. Reads that have already returned are kept, and the result says the run was cut.

### 5.3 The fake reader

The fake reader is a deterministic program for tests. Given a rule, it writes a reply in the reply format. Rules include:

- "prefer the version containing the string X";
- "always TIE";
- "prefer slot A" and "prefer slot B";
- "seeded pseudo-random", with the seed given in the plan;
- "write string S in field F" (for `PREFER`, S goes in the rationale);
- "omit field F";
- "on read k only", combined with another rule: that rule applies to read k, and every other read is TIE.

A rule applies to every comparison arm unless the plan names the arm it applies to, and it applies to the A/A arm only when the plan names it. On the A/A arm, the fake reader answers TIE unless the plan gives that arm its own rule. A non-TIE reply is marked `slightly` unless the rule names a strength. When the rules name no preference (for example, only "write S in F"), the reply is TIE. Each fake read costs 1 spend unit.

### 5.4 Reply format

Each reply starts with `READ: <read id>` and carries these fields, one per line or block:

- `PRIOR`;
- `SCORE-A` and `SCORE-B`;
- `PREFER`, written as `PREFER: <A|B|TIE>, <slightly|clearly|strongly>` with an optional rationale after it on the same line. TIE takes no strength. The rationale is the matchable text of `PREFER`;
- `DROVE-IT`, `DOUBTS`, `UNDERSOLD`, `OVEREXPLAINED`, `OWNED` and `FLAG-FIXES`.

A reply that is missing `READ`, `SCORE-A`, `SCORE-B` or `PREFER`, or whose `PREFER` choice cannot be read, is a failed read. Failed reads are counted and reported, never guessed.

### 5.5 Blindness

The prompt tells the reader that it knows nothing about the candidate, and the `PRIOR` field asks what it knew before reading. Any `PRIOR` other than `nothing` is flagged on that read in the result. A reader known to receive the user's identity from its own environment is marked `not-blind` in the plan. Its reads are reported separately, as well as together with the others, and every verdict line says how many of the reads behind it came from a reader marked `not-blind` (§ 6.1).

## 6. Scoring

Scoring reads only the replies, the key and the frozen plan. Failed reads are left out of every denominator below. A rule that needs N of N valid reads is INCONCLUSIVE when fewer than N reads are valid.

- **Preference.** Each read's preference is mapped through the key, from slot to version.
- **Hypotheses.** Each one gets SUPPORTED, REFUTED or INCONCLUSIVE from its frozen rule.
- **A/A gate.** If the share of valid A/A reads that are non-TIE and marked `clearly` or `strongly` is at or above the plan's noise threshold, every comparison is reported INCONCLUSIVE, whatever it showed, and the result says why. `Slightly` picks do not count toward the gate. If the A/A arm has fewer valid reads than planned (failed reads or a cut), the gate is "not evaluated", and every comparison is INCONCLUSIVE.
- **Position.** The share of non-TIE picks that went to slot A is reported per arm and overall. In an arm with two or more non-TIE picks, all in the same slot, position is INCONCLUSIVE whatever the version counts. Alternating slots then gives each version exactly the wins its slot gave it. With fewer than two non-TIE picks, position is "not assessable" and the verdict stands as the rule gave it.
- **Mechanisms.** A mechanism check counts the valid replies in each arm in which its pattern matches any named field (replies, not matches). It reports that count beside the same count on the A/A arm, which is the pattern's noise floor. Each count is shown as a share of the arm's valid reads. If the share in a comparison is no higher than the A/A share, the pattern is reported as unable to separate the versions, and its rule is INCONCLUSIVE.
- **Scores.** Scores are reported per version and per reader, with the A/A arm's score spread beside them.

### 6.1 Evidence beside the verdicts

Nothing in this section changes a verdict. Each line is reported beside the verdicts above, which come from the frozen rules alone (§ 8).

- **Sign test.** For each hypothesis, over the valid reads of its comparison arm: `n` is the number of reads that pick a version, whatever their strength (a `slightly` pick counts), and `k` is the number of those that pick the second-listed version of the comparison (`Y` in `X vs Y`). TIEs are left out of `n` and reported as a count. The p-value is exact, from the binomial distribution with `n` trials and chance 1/2: under `greater`, the chance of `k` or more; under `less`, the chance of `k` or fewer; under `two`, twice the smaller of those two, and at most 1. Under `greater` or `less` the p-value measures one direction only. A SUPPORTED or REFUTED verdict for the other version is not compared with `alpha`; its flag line says that direction was not tested.
- **Interval.** The 95% Wilson score interval for `k/n`, with z = 1.959964, whatever `alpha` is.
- **No pick.** When `n` is 0, neither the p-value nor the interval is computed, and the line says so.
- **Disagreement flag.** A hypothesis whose verdict is SUPPORTED or REFUTED with a p-value at or above `alpha`, or INCONCLUSIVE with a p-value below `alpha`, is flagged. The exact p-value is compared, not the printed one. There is no flag when `n` is 0, or when the verdict is INCONCLUSIVE because of the A/A gate or position (its reason line already says why). Under a one-sided test, a SUPPORTED or REFUTED verdict whose deciding clause names the version the test does not look at (the first-listed under `greater`, the second-listed under `less`) is not compared with `alpha`: its flag line says `one-sided test: this direction not tested` instead. The flag never changes the verdict.
- **Missing reads.** For each arm, the result counts the planned reads that are missing: failed, and not run (a cut or a stopped run). For each hypothesis with missing reads in its arm, the frozen rule is evaluated again under every completion of those reads, each one counted as a pick for `X`, a pick for `Y`, or a TIE, as if every planned read were valid. The result says whether one verdict holds under every completion (settled) or which verdicts are possible (unsettled), and gives the range of the p-value over the completions. This reads the rule alone: it does not complete the A/A arm and does not apply the A/A gate or position. It never changes the verdict.
- **A dead run.** When no read in the run is valid, the result says so in one line. The exit status is `1`, as for any run with a failed read (§ 7).
- **The top of the scale.** The built-in prompt asks for scores from 1 to 10. For each arm, the result counts the valid reads that score both slots at 10 or more, and the valid reads that give both slots the same score. When every valid read of an arm scores both slots at 10 or more, the scores cannot show a difference in that arm, and the result says that preference is the only measure there.
- **Not-blind reads.** Each hypothesis and mechanism verdict line ends with the number of its valid reads that came from a reader marked `not-blind` (§ 5.5).
- **What the reads stand for.** Every result carries one validity line: the readers are models standing in for human screeners, that stand-in has not been checked against human ratings, and reads from one model and prompt may not be independent, so each p-value assumes an independence the reads may not have and may be too small. Each p-value carries a short form of the same caveat on the same line.

#### Printed forms

In the forms below, `<Y>` is the second-listed version, `<arm>` is `aa` or `c1`, `c2` and so on, and `<h>` is the hypothesis name. A p-value is printed rounded half up to 4 decimal places, or as `< 0.0001` when it rounds to 0. An interval's lower end is rounded down and its upper end rounded up, to 3 decimal places. `<side>` is `two-sided`, `one-sided greater` or `one-sided less`.

- `hypothesis <h> evidence: <Y> <k> of <n> non-TIE picks, <t> TIE; p = <p> <side> (reads may be correlated; may be too small); 95% interval <lo> to <hi>`
- With no pick: `hypothesis <h> evidence: no non-TIE pick, <t> TIE; p and interval not computed`
- `hypothesis <h> flag: evidence disagrees: <verdict> at p = <p>, at or above alpha <alpha>`, or `... below alpha <alpha>` for an INCONCLUSIVE verdict. `<alpha>` is printed as the plan wrote it, or `0.05` by default.
- Under a one-sided test, for a verdict in the direction the test does not look at: `hypothesis <h> flag: one-sided test: this direction not tested`.
- `missing <arm>: <m> of <planned> planned reads (failed <f>, not run <r>)`, one line per arm, `m` = `f` + `r`.
- `hypothesis <h> completions (missing reads: <m>): settled: <verdict>; p from <a> to <b>`, or `... unsettled: <verdicts> possible; p from <a> to <b>`, with the possible verdicts in the order SUPPORTED, REFUTED, INCONCLUSIVE and separated by `, `. When no completion has a pick, the part after the last `;` is `p not computed`. A hypothesis whose arm has no missing read gets no completions line.
- `DEAD: 0 of <N> planned reads are valid`, where `N` counts the planned reads of every arm.
- `scores <arm> ceiling: <c> of <v> valid reads score both slots at 10 or more`
- `scores <arm> separation: <s> of <v> valid reads give both slots the same score`
- When `c` equals `v` and `v` is 1 or more: `scores <arm>: at the ceiling; preference is the only measure`
- `A/A gate interval: <lo> to <hi> (95%, Wilson)`, the interval for the gate's own share (non-TIE `clearly` or `strongly` reads over valid A/A reads), or `A/A gate interval: not computed` when the A/A arm has no valid read.
- Every hypothesis verdict line and mechanism verdict line ends with ` [not blind: <b> of <v> valid reads]`.
- `validity: the readers are models standing in for human screeners, and that stand-in has not been checked against human ratings. Reads from one model and prompt may not be independent, so each p-value assumes independence and may be too small.`

## 7. Output and exit status

`track-record ab score` writes a result file containing:

- the plan and freeze hashes, and any amendment's;
- the key;
- one row per read: reader, slots, scores, preference and flags;
- each hypothesis, with its verdict and the counts behind it;
- the A/A gate;
- the position shares;
- failed reads and any cut;
- the evidence lines of § 6.1: each hypothesis's sign test, interval, flag and completions, the missing reads per arm, the A/A gate interval, the score ceiling and separation per arm, any `DEAD` line, and the validity line.

Every run writes a new result; an earlier result is never overwritten.

Exit status:

- `0`: the run completed and was scored, whatever the verdicts, or it was a print without `--live`.
- `1`: the run completed, but at least one read failed or the run was cut. A dead run (§ 6.1) is exit `1` too.
- `2`: the run could not run. Causes: a hash mismatch, a failed isolation check, a missing input, a freeze over an existing freeze or run, an unknown plan key, or a plan with no comparison.

When causes combine, the higher code wins: `2` over `1` over `0`.

## 8. Rules that hold in every run

- No read before a freeze, and no plan edit after one.
- The A/A arm runs in every run, and it runs first.
- The isolation check runs before any read.
- Verdicts come from the frozen rules only. The tool has no option to change a rule at scoring time.
- The evidence of § 6.1 sits beside the verdicts and never changes one.
- A reader's suggested rewrite is reported as text and applied to nothing.

## 9. Decisions

Settled 2026-10-28:

1. Command name: `track-record ab`.
2. Default reads: 6 per arm (3 per reader, two readers). That is enough only for large, consistent effects, and a plan may ask for more.
3. Noise threshold default: `1/2`. Every comparison is reported INCONCLUSIVE when half or more of the valid A/A reads pick a side `clearly` or `strongly`.
4. Cold reads (one version, scored alone) are planned for a later revision, as a second instrument.
5. The plan format is plain text with `key: value` lines (§ 3.1).

6. Public examples: an example plan changes only a neutral part of a résumé, such as section order, a summary line, a skills block, or one bullet's wording, and uses invented companies only. No example changes how employers, roles, titles, dates or tenure are shown.

Settled 2026-11-05, for revision 2:

7. The sign test leaves TIEs out and reports them as a count, and a `slightly` pick counts as a pick. The default side is two-sided, set with `sidedness: two|greater|less`.
8. `alpha` defaults to 0.05. The disagreement flag works in both directions (SUPPORTED or REFUTED at p ≥ alpha, INCONCLUSIVE at p < alpha) and never changes a verdict. Under a one-sided test, a verdict in the direction the test does not look at says `one-sided test: this direction not tested` instead of being flagged.
9. The missing-read completions are reported only; they lift no INCONCLUSIVE. A dead run keeps exit `1` and gains the `DEAD` line.
10. Not-blind reads still count in the verdicts in revision 2, and every verdict line says how many there are.

## 10. Acceptance tests (known answers)

Every test uses the fake reader, except 10.13. That test uses a stub live-reader command that fails the test if it is ever executed.

The fixtures are invented:

- a two-page résumé for an invented engineer at invented companies, with a skills block, headed `Skills`, after the experience section;
- an invented posting;
- three versions, `base`, `skills-top` and `skills-top-short`. `skills-top` moves the skills block above the experience section and heads it `At a glance`; `skills-top-short` does the same and cuts the block to one line. Each pair differs only in the skills block, both changed versions contain `At a glance`, and the fixture plan's change scope names the skills heading and the skills lines (a moved block shows as removed and added lines, all inside the scope).

Unless a test says otherwise, the plan has one comparison (`base vs skills-top`), two readers with 3 reads each, the default noise threshold, and the fake reader's default TIE on the A/A arm.

- 10.1: The rule "prefer the version containing `At a glance`" on the comparison makes `skills-top` preferred in 6 of 6. The hypothesis "skills-top preferred in 6 of 6" is SUPPORTED, the A/A gate passes, and the run exits 0.
- 10.2: "Always TIE" makes the hypothesis INCONCLUSIVE, and position is "not assessable" (no non-TIE pick). Exit 0.
- 10.3: "Prefer slot A" on the comparison gives each version 3 wins. The arm's position share is 100% slot A, so position is INCONCLUSIVE and so is the hypothesis. The A/A gate passes.
- 10.4: Versions that also differ in a bullet outside the change scope stop the run before any read. It exits 2 and prints that line.
- 10.5: A comparison of a file with itself exits 2 before reading.
- 10.6: A version file edited after the freeze makes the run exit 2, naming the file. No reply is written.
- 10.7: A freeze in a folder that already holds a reply is refused, exit 2.
- 10.8: The A/A arm is given "seeded pseudo-random, seed 1, every reply non-TIE and strongly". 6 of 6 is at or above `1/2`, so the gate trips. The comparison is reported INCONCLUSIVE with the A/A reason, whatever its counts. Exit 0.
- 10.9: "Omit field `PREFER`" on read 1 of the comparison leaves one reply without `PREFER`. It is counted as failed and not guessed, leaving 5 valid reads, so the "6 of 6" rule is INCONCLUSIVE. Exit 1.
- 10.10: A reply whose `PRIOR` is not `nothing` is flagged on that read.
- 10.11: The rule "write `too long` in `DOUBTS`" applies to 4 of the 6 comparison reads and to no A/A read. The mechanism `too long` is reported as 4/6 against an A/A floor of 0/6. The rule "supported at 3 or more" is SUPPORTED.
- 10.12: The plan has two comparisons, `base vs skills-top` and `base vs skills-top-short` (18 reads), with a spend ceiling of 8 units. The A/A arm completes (6 reads), and the first comparison is cut at 2 reads. The A/A gate is evaluated, the first comparison is INCONCLUSIVE (2 valid reads), the second has no reads, and the result says the run was cut. Exit 1.
- 10.13: With a live reader configured and `--live` absent, the tool prints the commands and the spend estimate, never executes the stub, writes no reply and exits 0.
- 10.14: One run has two comparisons, `base vs skills-top` with "prefer slot B" and `base vs skills-top-short` with "prefer the version containing `At a glance`". The first arm is INCONCLUSIVE for position (each version wins 3, all in slot B). The second is SUPPORTED. The overall position share is 3 of 12 picks in slot A, reported beside both arms.
- 10.15: The rule "write `jargon` in `DOUBTS`" applies to every reply, A/A included. The mechanism `jargon` is reported at 6/6 against a floor of 6/6, as unable to separate the versions. INCONCLUSIVE.
- 10.16: A phrase written only in the `PREFER` rationale is matched under the default fields, and not matched when the plan names `DOUBTS` alone.
- 10.17: A freeze where a freeze file already exists is refused, exit 2.
- 10.18: An amendment (a new plan in a new run folder, with `amends` naming the first freeze file) is frozen and scored. Its result names both freezes, and the first run folder stays byte-identical. A second freeze in the first run folder is refused (10.7, 10.17).
- 10.19: A plan without an A/A arm gets one added, using `aa-version`, and the result says so. A plan with no comparison exits 2.
- 10.20: Versions that differ only in runs of spaces and in blank lines are treated as identical. Declared as a comparison, they exit 2.
- 10.21: Scoring twice writes two result files, and the first is unchanged.
- 10.22: "Prefer the version without `At a glance`" makes `base` preferred in 6 of 6, so the hypothesis is REFUTED (4 or more).
- 10.23: With the A/A arm given "prefer slot A, slightly", the gate passes because `slightly` picks don't count.
- 10.24: A reader marked `not-blind` has its reads reported separately as well as together.
- 10.25: The result shows scores per version and per reader, with the A/A score spread.
- 10.26: "Omit field `READ`", "omit field `SCORE-A`" and "omit field `SCORE-B`", each on a different read, give three failed reads, each counted and named.
- 10.27: "Prefer the version containing `At a glance`, on read 2 only" gives an arm with exactly one non-TIE pick. It reports position as "not assessable", and its verdict follows the rule.
- 10.28: Editing the plan file after the freeze makes the run exit 2, naming the plan.
- 10.29: A PDF version is read through text extraction. Its isolation check and scores match those of the same text given as a UTF-8 file.
- 10.30: A failed read together with a cut gives exit 1, and both are reported. A hash mismatch together with a failed isolation check gives exit 2, and both are reported (neither run reads anything).
- 10.31: With one reader and `reads-per-reader: 5`, the first-listed version is in slot A on reads 1, 3 and 5, and the result shows the slot split as 3 and 2.

Tests 10.42 to 10.57 are new in revision 2 (10.32 to 10.41 are the build interpretations' tests, below). Where a test names "the example rule", the hypothesis is `SUPPORTED if skills-top preferred in 6 of 6; REFUTED if base preferred in 4 or more; otherwise INCONCLUSIVE`.

- 10.42: 10.1 with the example rule. The result has `hypothesis h1 evidence: skills-top 6 of 6 non-TIE picks, 0 TIE; p = 0.0313 two-sided (reads may be correlated; may be too small); 95% interval 0.609 to 1.000`, the verdict line `hypothesis h1 verdict: SUPPORTED [not blind: 0 of 6 valid reads]`, and no flag line. (The exact p-value is 1/32 = 0.03125, so rounding half to even would print 0.0312.)
- 10.43: 10.42 with `sidedness: greater` prints `p = 0.0156 one-sided greater`. With `sidedness: less` it prints `p = 1.0000 one-sided less` and the flag line `hypothesis h1 flag: one-sided test: this direction not tested`, because the deciding clause names `skills-top`, the version `less` does not look at. The verdict is SUPPORTED in both.
- 10.44: Reads 1 to 4 of the comparison `prefer containing "At a glance"`, reads 5 and 6 `prefer without "At a glance"`, and the hypothesis is `SUPPORTED if skills-top preferred in 4 or more; otherwise INCONCLUSIVE`. It is SUPPORTED, with `skills-top 4 of 6 non-TIE picks, 0 TIE; p = 0.6875 two-sided` and `95% interval 0.299 to 0.904` (the exact lower end, 0.29999…, is rounded down), and the flag line `hypothesis h1 flag: evidence disagrees: SUPPORTED at p = 0.6875, at or above alpha 0.05`.
- 10.45: `reads-per-reader: 4`, `prefer containing "At a glance"` on the comparison, `omit PREFER | read 8`, and the hypothesis `SUPPORTED if skills-top preferred in 8 of 8; otherwise INCONCLUSIVE`. Seven reads are valid, so the verdict is INCONCLUSIVE. The result has `skills-top 7 of 7 non-TIE picks, 0 TIE; p = 0.0156 two-sided`, `95% interval 0.645 to 1.000`, the flag line `hypothesis h1 flag: evidence disagrees: INCONCLUSIVE at p = 0.0156, below alpha 0.05`, `missing c1: 1 of 8 planned reads (failed 1, not run 0)`, `missing aa: 0 of 8 planned reads (failed 0, not run 0)` and `hypothesis h1 completions (missing reads: 1): unsettled: SUPPORTED, INCONCLUSIVE possible; p from 0.0078 to 0.0703`. Exit 1.
- 10.46: `prefer without "At a glance"` on the comparison, `omit PREFER | read 1`, the example rule. Five reads are valid, all for `base`, so the verdict is REFUTED, with `skills-top 0 of 5 non-TIE picks, 0 TIE; p = 0.0625 two-sided`, `95% interval 0.000 to 0.435`, the flag line `hypothesis h1 flag: evidence disagrees: REFUTED at p = 0.0625, at or above alpha 0.05`, and `hypothesis h1 completions (missing reads: 1): settled: REFUTED; p from 0.0313 to 0.2188`. Exit 1.
- 10.47: `aa | omit PREFER` and `all | omit PREFER`, the example rule. Every read fails. The result has `DEAD: 0 of 12 planned reads are valid`, `missing aa: 6 of 6 planned reads (failed 6, not run 0)`, the same for `c1`, the gate "not evaluated", `A/A gate interval: not computed`, `hypothesis h1 evidence: no non-TIE pick, 0 TIE; p and interval not computed`, verdict INCONCLUSIVE with no flag line, and `hypothesis h1 completions (missing reads: 6): unsettled: SUPPORTED, REFUTED, INCONCLUSIVE possible; p from 0.0313 to 1.0000`. Exit 1, as 10.9 is.
- 10.48: 10.1 plus `all | score 10 10` and `aa | score 10 10`. For both `aa` and `c1`: `scores <arm> ceiling: 6 of 6 valid reads score both slots at 10 or more`, `scores <arm> separation: 6 of 6 valid reads give both slots the same score` and `scores <arm>: at the ceiling; preference is the only measure`.
- 10.49: With no `score` rule (every score 5), each arm has `ceiling: 0 of 6` and `separation: 6 of 6`, and no "at the ceiling" line. With `all | score 10 12`, `c1` has `ceiling: 6 of 6`, `separation: 0 of 6` and the "at the ceiling" line, and `aa` has none.
- 10.50: 10.11's plan with reader-2 marked `not-blind`. The hypothesis verdict line ends ` [not blind: 3 of 6 valid reads]`, and so does the `too long` mechanism verdict line.
- 10.51: Every result has exactly one validity line, with the text in § 6.1, including those of 10.2, 10.8 and 10.47.
- 10.52: 10.42 with `alpha: 0.01` has the flag line `hypothesis h1 flag: evidence disagrees: SUPPORTED at p = 0.0313, at or above alpha 0.01`. The verdict is SUPPORTED.
- 10.53: `freeze` refuses each of `alpha: 0`, `alpha: 0.0`, `alpha: 1`, `alpha: 1/20`, `alpha: .05`, `sidedness: both` and `sidedness: Two`, with exit 2, naming the plan line, and writes no freeze file. `alpha: 0.05` and `sidedness: less` freeze.
- 10.54: 10.8 has `A/A gate interval: 0.609 to 1.000 (95%, Wilson)`. With the default TIE on the A/A arm (10.1), it is `A/A gate interval: 0.000 to 0.391 (95%, Wilson)`.
- 10.55: 10.2 (always TIE) has `hypothesis h1 evidence: no non-TIE pick, 6 TIE; p and interval not computed` and no flag line.
- 10.56: 10.8 with `prefer containing "At a glance"` on the comparison and the example rule. The rule alone would give SUPPORTED at p = 0.0313. The gate trips, so the verdict is INCONCLUSIVE with the A/A reason, the evidence line is printed in full, and there is no flag line.
- 10.57: Revision 2 changes no prompt: the built-in prompt's sha256 equals the one the previous release recorded, so a plan frozen before revision 2 without `sidedness` or `alpha` still runs.
<!-- signed spec ends -->

## Build interpretations (maintainer, 2026-10-29)

Revision 1.1 completes the signed spec and does not edit it. It adds plan keys, fake-reader rules, live-reader rules, the reply format and causes of exit `2`, and it reads three sentences of the signed spec as stated in "Readings of signed sentences" below. This section states those rules, then the tests that revision 1.1 adds.

### Readings of signed sentences

1. **Section 4.1, "Readers see only `A.txt` and `B.txt`."** Of the versions, a reader sees only the two slot files, never version names or the key. The posting and the prompt are given as well (section 2: a reader sees one posting and two versions; section 5.5: the prompt).
2. **Section 3.1, `spend-ceiling` "in the reader's own units".** Section 3.1 could mean each reader's own unit or one shared unit; this takes one shared unit, chosen by the user. With one reader the two readings coincide.
3. **Section 5.2, "The test suite and CI never start a live reader."** In section 5.2, a live reader means one that reaches a network or uses credentials; a local stub script is not one. Elsewhere in this section, "live" means any command other than `fake`. Tests 10.35 to 10.37 run a local stub script with `--live`, and with 10.13 they are the only tests that name a non-fake command.

### The plan file

A list item is one indented line, and its fields are separated by ` | ` (space, bar, space). No field may contain ` | `: a line that would need one is an error (exit `2`). Spaces around a field are trimmed. This example is invented:

```
versions:
  base | base.txt
  skills-top | skills-top.txt
comparisons:
  base vs skills-top
readers:
  reader-1 | fake
  reader-2 | /path/to/my-reader.sh --model small | not-blind | cost 3
hypotheses:
  base vs skills-top | SUPPORTED if skills-top preferred in 6 of 6; REFUTED if base preferred in 4 or more; otherwise INCONCLUSIVE
mechanisms:
  too long | default | supported at 3 or more
change-scope:
  ^(Skills|At a glance)
fake-reader:
  aa | prefer slot A | slightly
```

- **Items.** `versions`: `<name> | <file>`. `comparisons`: `<X> vs <Y>`, in version names. `readers`: `<name> | <command>`, then optionally `not-blind` and `cost <n>`, in either order, each recognised by its word.
- **Mechanisms.** `[<comparison> |] <pattern> | <fields> | supported at <n> or more`. **Change-scope.** `[<comparison> |] <pattern>`.
- **Which comparison.** A hypothesis, mechanism or change-scope item may start with its comparison, written exactly as in `comparisons`. With one comparison the field may be left out. With more than one, a hypothesis or mechanism without it is an error, and a change-scope item without it applies to every comparison.
- **Hypothesis rules.** Clauses are separated by `; `. Each is `SUPPORTED if <version> [is] preferred in <n> of <m>` or `... preferred in <n> or more`, and the same with `REFUTED`. The last clause must be `otherwise INCONCLUSIVE`. `<n> of <m>` holds when the arm has exactly `<m>` valid reads and at least `<n>` of them prefer the version. `<n> or more` holds when at least `<n>` valid reads prefer it, however many reads are valid. Clauses are tried in order, and the first that holds decides. The result names the hypotheses `h1`, `h2` and so on, in plan order.
- **Patterns.** In `mechanisms` and `change-scope` they are Python regular expressions, matched with `re.search`, so they are not anchored unless the pattern anchors itself. The result names a mechanism by its pattern. A space-bar-space inside a pattern is read as a field separator, so write alternation as `a|b`.
- **Mechanism patterns** are case-insensitive and are matched against field text.
- **Change-scope patterns** are case-sensitive and are matched against each changed line after the space collapsing of section 4.2. A pattern that matches empty text is refused at freeze (exit `2`, naming the plan line), because it would let every changed line through. That covers an empty branch such as `^Skills |`, a group with an empty branch such as `^(Skills|)`, an optional-only pattern such as `x?`, and `^$` (blank lines are dropped before the isolation check, so `^$` could never match a changed line). A pattern written to match every line, such as `.+`, is accepted as the user's own explicit scope.
- **Mechanism fields.** `default` (the list in section 3.1) or a comma-separated list of reply field names, for example `DOUBTS, PREFER`.
- **Names** (versions and readers) are letters, digits and `-`, and unique within their key.
- **Scalars.** An absent `spend-ceiling` means no ceiling. File paths are relative to the plan's folder. `noise-threshold` is written as a fraction `<n>/<d>` and in no other form. `cost`, `spend-ceiling` and `read-timeout` are whole numbers, 0 or more. `reads-per-reader` is a whole number, 1 or more. `read-timeout` is in seconds and defaults to `600`.
- **The A/A arm is always added.** `aa-version` only picks its version (the default of section 3.1 otherwise), and the result says the arm was added (10.19).
- **Where errors are found.** Every plan error is found by `freeze`, which exits `2`, names the plan line number where there is one, and writes no freeze file. Besides syntax, `freeze` refuses a `read <k>` outside the arm's reads, a hypothesis that names a version not in its comparison, an `<n>` greater than `<m>`, and `fake-reader` items when the plan has no fake reader. `run` re-checks the hashes (section 3.2), compares the sha256 of the built-in prompt with the one in the freeze file (exit `2`, naming `PROMPT.txt`, if they differ), and runs the isolation check (section 4.2) before any read. It finds no syntax error, because it relies on the freeze: a plan edited after the freeze is named as changed and is not read.
- **One run to a folder.** A run folder holds one run. A second `run` there exits `2` while `reads/`, `key.txt` or `run-log.txt` exists. An amendment goes in a new folder (section 3.2).
- **The run log is always written.** Once `run` has written `key.txt`, it writes `run-log.txt`, however the read loop ends. If the loop ends early for any reason other than the spend ceiling, the run log gains a last line, `stopped: <reason>`. `score` then scores the reads that exist (the reads that never started are shown as not run), reports the `stopped:` line, and exits `2`, as does the `run` that stopped. No folder is left with `reads/` or `key.txt` and no `run-log.txt`, short of a process killed outright.

### The fake reader

The fake reader runs inside the tool, not through the read folder, and it applies to every reader whose command is the word `fake`. The read folder is still written, so results and the layout are the same as for a live reader. The `fake-reader` key is a list, and a live reader ignores it.

- **Item:** `[<arm> |] <rule> [| <strength>] [| read <k>]`. The arm is `all` (every comparison arm, never the A/A arm), `aa` (the A/A arm), or a comparison written as in `comparisons`. Leaving the arm out means `all`.
- **Rules:**
  - `prefer containing "<S>"`: prefers the slot whose text contains S, and is TIE when both or neither do.
  - `prefer without "<S>"`: prefers the slot whose text does not contain S, and is TIE when both or neither do.
  - `tie`: it takes no strength, and `tie` with a strength is an error.
  - `prefer slot A` and `prefer slot B`.
  - `random seed <n> [non-tie]`: deterministic from the seed, the arm and the read number. The pick comes from the first byte of the sha256 of the text `<seed>:<arm>:<k>`, where the arm is `aa`, `c1`, `c2` and so on, and `<k>` is the read number. With `non-tie` the pick is A when the byte is even and B when it is odd. Without it the pick is A, B or TIE for a byte mod 3 of 0, 1 or 2. Seeds live in the rule, so different arms may use different seeds.
  - `write "<S>" in <FIELD>`, where FIELD is any reply field. For `PREFER`, S goes in the rationale.
  - `omit <FIELD>`, where FIELD is any reply field.
  - `score <a> <b>`: writes `SCORE-A: <a>` and `SCORE-B: <b>`. Without it the fake reader writes `SCORE-A: 5` and `SCORE-B: 5`.
- **Strength.** `slightly` (the default), `clearly` or `strongly`, applied to the item's non-TIE picks. A strength on a `write`, `omit` or `score` item is ignored.
- **PRIOR** is `nothing` unless a `write ... in PRIOR` item applies.
- **`read <k>`** makes the item apply only to read k of its arm, numbered as in section 4.1 (the number counts across the arm, not within each reader).
- **Combining.** On each read, the items for that arm that apply to that read are combined. At most one preference rule (`prefer ...`, `tie`, `random ...`) may apply to one read, and two is an error found at freeze. Any number of `write`, `omit` and `score` items may apply. A read with no preference rule is TIE. When `omit F` and anything that writes F apply to the same read, the field is omitted. When more than one `score` item applies, the last one wins. So section 5.3's "on read k only, every other read is TIE" holds when the `read k` item is the arm's only preference rule (10.27), and `omit PREFER | read 1` makes read 1 a failed read whatever else applies (10.9).
- A `cost` on the fake reader is ignored: it always costs 1.

### Live readers

A reader whose command is not the word `fake` is live.

1. **Folder.** The command runs with its read folder as the working folder and gets no argument from the tool. It inherits the tool's environment, which is why section 5.5 marks some readers `not-blind`.
2. **Read folder contents.** When the command starts, the folder holds exactly `A.txt` and `B.txt` (the two versions as text, PDFs already extracted per section 3.3), `POSTING.txt` and `PROMPT.txt`. The prompt is built into the tool and fixed per tool version. Its sha256 goes into the freeze file and into the result.
3. **Reply.** The command's standard output is the reply, and the tool writes it to `REPLY.txt` in the read folder. Standard error goes to `STDERR.txt`, a log that is never scored. A nonzero exit status is a failed read, reported with the status, and its standard output is not scored. A reader that has itself written `REPLY.txt` or `STDERR.txt` into its folder by the time the command returns makes a failed read, reported as `the reader wrote <name> into its folder` (`REPLY.txt` is named first if both exist). The tool overwrites nothing, leaves the reader's file as it is, writes neither file for that read, and counts the read's declared cost as spent. Known limit: the tool holds the command's standard output and standard error in memory until the command returns, and sets no size limit on them. `read-timeout` limits how long a read takes, not how much it prints.
4. **No shell.** The command is split into a program and its arguments by POSIX shell-word rules and run without a shell: no pipes, redirection, globbing or variable expansion. A user who needs those writes a script and names it as the command. The first word is the program: an absolute path, or a name with no `/` that is looked up on `PATH`. A relative path such as `./my-reader.sh` is refused at freeze (exit `2`, naming the plan line), because the command runs in its read folder, where no such program exists.
5. **Time limit.** `read-timeout` is in seconds (default `600`). When it is reached, the tool stops the process. The read is a failed read reported as `timed out`, and its declared cost counts as spent. Known limit: the tool stops the reader's own process, not processes the reader started. A reader that starts helpers must stop them itself.
6. **Cost.** A reader item may carry `cost <n>`, what one read costs in the plan's one spend unit (default `1`). `spend-ceiling` is in that same unit; readers that bill in different units are converted into one unit by the user when the plan is written, and the tool does no conversion. The estimate printed without `--live` is the sum of the planned reads' costs. The tool cannot see real spend: the ceiling stops the run on a tally of declared costs between reads, and the result says so.
7. **Layout.** Read k of an arm is at `reads/<arm>/<k>/` in the run folder, where `<arm>` is `aa` for the A/A arm and `c1`, `c2` and so on for the comparisons in plan order. The key file is `key.txt`. A folder holds a reply (sections 3.2 and 10.7) when any `reads/*/*/REPLY.txt` exists. Results name a read as `<arm>/<k>`, for example `c1/3`.

Without `--live`, a plan with a live reader prints each live command and the estimate, starts no reader, writes nothing and exits `0`. The print comes after the hash and isolation checks, so a plan that could not run exits `2` instead.

### The reply format

- **Fields.** Each field starts a line as `FIELD: value`, where FIELD is one of the section 5.4 names, case-sensitive, at the start of the line. A field's value runs to the next line that starts with a field name, so block values are allowed. Text before the first field is ignored.
- **`READ:`** must be present. Its value is not checked: a live reader cannot know its read number, and the tool identifies the read by its folder.
- **`SCORE-A:` and `SCORE-B:`** each hold one integer, of any size and sign. A missing or non-integer score is a failed read.
- **`PREFER:`** is `A`, `B` or `TIE`, case-sensitive, and so are the strengths. Only the first line of `PREFER` is its value and rationale. After `A` or `B` comes a comma and a strength (`slightly`, `clearly` or `strongly`); an `A` or `B` without a readable strength is a failed read. The rationale is the rest of the line after the strength, or after `TIE`, with leading spaces and the characters `,` `;` `:` `-` and the en and em dashes (U+2013, U+2014) stripped. So `PREFER: TIE, slightly` is a TIE whose rationale is `slightly`.
- **Duplicates.** A field that appears twice is a failed read.
- **The other fields** (`PRIOR`, `DROVE-IT`, `DOUBTS`, `UNDERSOLD`, `OVEREXPLAINED`, `OWNED`, `FLAG-FIXES`) are optional, and a missing one is empty for matching. A `PRIOR` is unflagged only when its value, trimmed, is exactly `nothing` (case-sensitive, no punctuation). A missing `PRIOR` is flagged (section 5.5).

### What the A/A gate and position cover

- **The A/A gate covers every verdict of every comparison,** hypotheses and mechanisms alike. When it trips, or is "not evaluated", each comparison's hypothesis and mechanism verdicts are INCONCLUSIVE, and the result says why. The counts and shares are still reported. Section 6 says "every comparison is reported INCONCLUSIVE, whatever it showed". A gate that is "not evaluated" means the A/A arm is incomplete, and that arm is also the mechanisms' noise floor, so the same rule applies.
- **Position covers hypotheses only.** An arm whose position is INCONCLUSIVE keeps its mechanism verdicts as the section 6 mechanism rule gives them. The position rule is about version counts ("whatever the version counts"), and mechanisms count reader comments against their own A/A floor.

### Other rulings

- **Errors on files in the run folder exit `2`.** Any error in reading or writing a file in the run folder (the freeze file, `key.txt`, the read folders and their files, `run-log.txt`, a result file) ends the command with exit `2` and one line on standard error: `cannot run: cannot write <name>: <reason>` or `cannot run: cannot read <name>: <reason>`, where `<name>` is relative to the run folder. A `key.txt` that `score` cannot parse gives `cannot run: cannot parse key.txt: <reason>`. The command never ends in a traceback for these.
- **A stopped run says so on standard error.** When `run` or `score` exits `2` because the run stopped early (the `stopped:` line in the result), standard error gets exactly one line, `cannot run: stopped: <reason>`. Standard output is unchanged: the scored reads and the `stopped:` line. Every other exit `2` already writes its own `cannot run:` line.
- **An interrupt ends any `ab` command with exit `2`** and one line on standard error, `cannot run: stopped: interrupted`, with no traceback. When an interrupt comes during the reads, the run log ends with `stopped: interrupted`.
- **Printed text is escaped.** Every text `ab` prints that comes from an argument, a file name or a file's contents is escaped the same way as the barred check's printed paths: `\`, line breaks, tabs, control and format characters, and U+2028 and U+2029 are written as escapes. So input cannot split or forge an output line.
- **Known limit: a plan file whose own name contains a line break.** It can be frozen but not run: `run` exits `2`, because the freeze file lists names one to a line.
- **The key is checked by its hash.** `run` records `key sha256: <hex>` in `run-log.txt`. `score` compares it with the current `key.txt` and, if they differ, exits `2` with `cannot run: changed since the run: key.txt`. A run log with no `key sha256` line is exit `2` too, naming `run-log.txt`.

### Tests that revision 1.1 adds

- 10.32: A plan field containing ` | `: `freeze` exits `2`, naming the plan line number, and writes no freeze file.
- 10.33: Two comparisons and a hypothesis with no comparison field: `freeze` exits `2`, naming the line, and writes no freeze file.
- 10.34: `all | prefer slot A` and `base vs skills-top | tie` together: `freeze` exits `2` (two preference rules on read 1), and writes no freeze file.
- 10.35: A stub reader script that exits nonzero gives a failed read, reported with its status; the run exits `1`, and the stub's standard output is not scored.
- 10.36: A stub that sleeps past `read-timeout: 1` is stopped and reported as `timed out`. The tally of declared costs includes it, and the run exits `1`.
- 10.37: A stub that lists its working folder sees exactly `A.txt`, `B.txt`, `POSTING.txt` and `PROMPT.txt`, and that `PROMPT.txt`'s sha256 equals the one in the freeze file.
- 10.38: A reply whose `READ:` value is any text is scored normally. A reply with `PREFER: A` and no strength is a failed read.
- 10.39: With no `score` rule, the result shows every fake read's scores as 5 and 5. With `score 7 4`, SCORE-A is 7 and SCORE-B is 4.
- 10.40: 10.11's plan with one A/A read made to fail (`aa | omit PREFER | read 1`): the gate is "not evaluated", and both the hypothesis and the `too long` mechanism are INCONCLUSIVE, with the mechanism's 4/6 count still shown. Exit `1`.
- 10.41: 10.11's plan plus `base vs skills-top | prefer slot B`: position is INCONCLUSIVE and the hypothesis is INCONCLUSIVE, but the `too long` mechanism is still SUPPORTED (4/6 against a floor of 0/6).

### Known limit: moved blocks

Changed lines are found with Python's `difflib.SequenceMatcher` (`autojunk=False`) over the collapsed, non-blank lines. A moved block shows as removed and added lines only when the text it moves past is longer than the block itself. A long block moved past a short one shows the short one as changed instead. If those lines fall outside the change scope, the run stops at the isolation check (exit `2`) before any read; if they are inside it, only in-scope lines differ and the run goes ahead. Either way the limit can stop a run. It cannot let through a line whose text changed, but it can report a moved block as a change to the block it moved past.
