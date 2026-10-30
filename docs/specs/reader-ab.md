# Reader A/B harness: behaviour spec

Status: accepted.
Date: 2026-10-29.
Revision: 1. The signed spec (sha256 810a739956b054d5df05c9d3cd421b17816b00c2c4ce2f7be3def7a11226e1a1) is reproduced below verbatim, and the build interpretations follow it.

## Signed spec

<!-- signed spec begins: sha256 810a739956b054d5df05c9d3cd421b17816b00c2c4ce2f7be3def7a11226e1a1 -->
# Reader A/B harness: behaviour spec

Status: accepted. All six decisions (§ 9) are settled: 1 to 5 by the owner on 2026-10-28, and 6 by legal review on 2026-10-28.
Date: 2026-10-29.
Revision: draft 3. It replaces draft 2 (2026-10-28). Draft 3 makes the fixtures' change a neutral one (a skills block moved above the experience section), uses neutral reader comments as the mechanism strings in 10.11 and 10.15, renames the versions in the tests to match, and settles decision 6. Draft 2's changes to draft 1 (2026-10-27) stand: the noise threshold becomes a plan field stated as a share; the fake reader's behaviour is defined on the A/A arm; slot alternation runs over the arm; failed reads leave the denominators; mechanism checks count replies per arm against the A/A floor; and the arms run in a fixed order. Tests 10.17 to 10.31 are new.

The command is `track-record ab`.

Every example in this file and in the tool's fixtures is invented. None of it comes from a real person's résumés, postings, employers, prompts or results.

## 1. Purpose

Compare two versions of the same career document by asking model readers, and report whether one reads better, without letting the person running the test move the goalposts after seeing the answer.

The tool exists because a tailored résumé changes many times in a day, and each change is judged by feel. The harness turns a change into a test with three parts: a hypothesis fixed in advance, a noise control, and a check that the two versions differ only where the change was meant to be.

It follows rule 6 of the method ("Test before you trust"). Every run carries a control, so a run that shows nothing also shows that it was able to see something.

## 2. Scope

In scope:

- paired reads: a reader sees one posting and two versions, A and B, and scores both;
- the A/A control: the same version in both slots, run in every run, before any comparison;
- preregistration: the hypotheses and decision rules, frozen by hash before the first read;
- the isolation check: the text that differs between the two versions, compared with what the plan says should differ;
- scoring the replies against the frozen rules, and writing a result.

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

The prompt tells the reader that it knows nothing about the candidate, and the `PRIOR` field asks what it knew before reading. Any `PRIOR` other than `nothing` is flagged on that read in the result. A reader known to receive the user's identity from its own environment is marked `not-blind` in the plan. Its reads are reported separately, as well as together with the others.

## 6. Scoring

Scoring reads only the replies, the key and the frozen plan. Failed reads are left out of every denominator below. A rule that needs N of N valid reads is INCONCLUSIVE when fewer than N reads are valid.

- **Preference.** Each read's preference is mapped through the key, from slot to version.
- **Hypotheses.** Each one gets SUPPORTED, REFUTED or INCONCLUSIVE from its frozen rule.
- **A/A gate.** If the share of valid A/A reads that are non-TIE and marked `clearly` or `strongly` is at or above the plan's noise threshold, every comparison is reported INCONCLUSIVE, whatever it showed, and the result says why. `Slightly` picks do not count toward the gate. If the A/A arm has fewer valid reads than planned (failed reads or a cut), the gate is "not evaluated", and every comparison is INCONCLUSIVE.
- **Position.** The share of non-TIE picks that went to slot A is reported per arm and overall. In an arm with two or more non-TIE picks, all in the same slot, position is INCONCLUSIVE whatever the version counts. Alternating slots then gives each version exactly the wins its slot gave it. With fewer than two non-TIE picks, position is "not assessable" and the verdict stands as the rule gave it.
- **Mechanisms.** A mechanism check counts the valid replies in each arm in which its pattern matches any named field (replies, not matches). It reports that count beside the same count on the A/A arm, which is the pattern's noise floor. Each count is shown as a share of the arm's valid reads. If the share in a comparison is no higher than the A/A share, the pattern is reported as unable to separate the versions, and its rule is INCONCLUSIVE.
- **Scores.** Scores are reported per version and per reader, with the A/A arm's score spread beside them.

## 7. Output and exit status

`track-record ab score` writes a result file containing:

- the plan and freeze hashes, and any amendment's;
- the key;
- one row per read: reader, slots, scores, preference and flags;
- each hypothesis, with its verdict and the counts behind it;
- the A/A gate;
- the position shares;
- failed reads and any cut.

Every run writes a new result; an earlier result is never overwritten.

Exit status:

- `0`: the run completed and was scored, whatever the verdicts, or it was a print without `--live`.
- `1`: the run completed, but at least one read failed or the run was cut.
- `2`: the run could not run. Causes: a hash mismatch, a failed isolation check, a missing input, a freeze over an existing freeze or run, an unknown plan key, or a plan with no comparison.

When causes combine, the higher code wins: `2` over `1` over `0`.

## 8. Rules that hold in every run

- No read before a freeze, and no plan edit after one.
- The A/A arm runs in every run, and it runs first.
- The isolation check runs before any read.
- Verdicts come from the frozen rules only. The tool has no option to change a rule at scoring time.
- A reader's suggested rewrite is reported as text and applied to nothing.

## 9. Decisions

Settled 2026-10-28:

1. Command name: `track-record ab`.
2. Default reads: 6 per arm (3 per reader, two readers). That is enough only for large, consistent effects, and a plan may ask for more.
3. Noise threshold default: `1/2`. Every comparison is reported INCONCLUSIVE when half or more of the valid A/A reads pick a side `clearly` or `strongly`.
4. Cold reads (one version, scored alone) are planned for a later revision, as a second instrument.
5. The plan format is plain text with `key: value` lines (§ 3.1).

6. Public examples: an example plan changes only a neutral part of a résumé, such as section order, a summary line, a skills block, or one bullet's wording, and uses invented companies only. No example changes how employers, roles, titles, dates or tenure are shown.

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
<!-- signed spec ends -->

## Build interpretations (maintainer, 2026-10-29)

Revision 1.1 completes the signed spec, which is not edited. It adds plan keys, fake-reader rules, live-reader rules, the reply format and causes of exit `2`, and it reads three sentences of the signed spec as stated in "Readings of signed sentences" below. This section states those rules, then the tests that revision 1.1 adds.

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
