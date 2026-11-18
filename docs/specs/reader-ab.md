# Reader A/B harness: behaviour spec

Status: accepted.
Date: 2026-11-15.
Revision: 4. The signed spec (sha256 ef5492839202bdaf53a9dbd523c4f9c080f5da9088cc50334b4025b14a306589) is reproduced below verbatim. Its owner signed it on 2026-11-14. It revises revision 3's signed text (sha256 3b581c40da031b943ae5280a6881235c5b5b6c27d8568db1d3d3e85851ee1f6f) with paired reads in both orders, paired-pick counting, the second reading, the family rule, the mechanism margin, amendments and extensions of the sample size, a pooled A/A gate, the refusal of plans frozen under an earlier revision, and the document key. The build interpretations of revision 1.1 follow it and still apply, except where the build interpretations of revision 4, at the end of this file, change them for this command. The build interpretations of revision 3 are restated there as build interpretations of revision 4.

## Signed spec

<!-- signed spec begins: sha256 ef5492839202bdaf53a9dbd523c4f9c080f5da9088cc50334b4025b14a306589 -->
# Reader A/B harness: behaviour spec

Status: revision 4, drafted on 2026-11-14 for the owner's signature, after revision 3. Revision 1 was accepted with all six decisions (§ 9) settled: 1 to 5 by the owner on 2026-10-28, and 6 by the owner on 2026-10-29.
Date: 2026-11-14.
Revision: 4. Reads each pair of a reader's reads in both orders and counts a reader's pick only when both orders agree (an order-split pair is a TIE), with an even read count per reader; counts every non-TIE A/A pick in the gate, `slightly` included; scores each hypothesis a second time with `slightly` counted as TIE; records every model that drafted or edited each version and each reader's model family, and asks readers of another family to agree before a verdict can favour a version that a model of a reader's own family drafted or edited; lets the A/A gate pool reads across runs; asks a mechanism for a margin over its A/A floor; lets a follow-up change the sample size, never a threshold; and lets a plan name the kind of document it compares (sections 3.1, 3.2, 4.1, 5.5, 6, 6.1, 7, 8, 9 and 10). **Revision 4 changes verdicts** of every plan: picks are counted per pair, `slightly` A/A picks now count toward the gate, a read floor (`min-valid-reads`) counts valid pairs, not reads, a mechanism needs a margin over its A/A floor, and the family rule can make a verdict INCONCLUSIVE. **Revision 4 changes an exit status at freeze:** a plan with an odd `reads-per-reader`, a plan without `drafted-by` on every version or `family` on every reader, and an amendment that changes a threshold froze under revision 3 and now exit `2`; and `run` and `score` refuse, exit `2`, a plan frozen under an earlier revision, which is never scored under revision 4's rules. The default run now makes twice the reads it did: 12 per arm, was 6. It changes the prompt only for a plan that names a `document` other than `résumé`. Revision 3 adds a second control on the reads, the sensitivity arm; replicate runs; an optional read floor; keeps reads from not-blind readers out of every verdict; and lets a settled completion lift an INCONCLUSIVE when the plan sets a read floor (sections 1, 2, 3.1, 3.2, 4, 5.2, 5.3, 5.5, 6, 6.1, 7, 8, 9 and 10). **Revision 3 changes verdicts** of plans with a not-blind reader, and adds verdict changes a plan opts into (a sensitivity arm, a read floor). It changes no exit status and no prompt. Revision 2 put the evidence beside each verdict and corrected § 1. Revision 1 was draft 3. It replaces draft 2 (2026-10-28). Draft 3 makes the fixtures' change a neutral one (a skills block moved above the experience section), uses neutral reader comments as the mechanism strings in 10.11 and 10.15, renames the versions in the tests to match, and settles decision 6. Draft 2's changes to draft 1 (2026-10-27) stand: the noise threshold becomes a plan field stated as a share; the fake reader's behaviour is defined on the A/A arm; slot alternation runs over the arm; failed reads leave the denominators; mechanism checks count replies per arm against the A/A floor; and the arms run in a fixed order. Tests 10.17 to 10.31 are new.

The command is `track-record ab`.

Every example in this file and in the tool's fixtures is invented. None of it comes from a real person's résumés, postings, employers, prompts or results.

## 1. Purpose

Compare two versions of the same career document by asking model readers, and report whether one reads better, without letting the person running the test move the goalposts after seeing the answer.

The tool exists because a tailored résumé changes many times in a day, and each change is judged by feel. The harness turns a change into a test with three parts: a hypothesis fixed in advance, a noise control, and a check that the two versions differ only where the change was meant to be.

It follows rule 6 of the method ("Test before you trust") for the comparison itself: the isolation check (§ 4.2) must find zero changed lines on the A/A arm and some on every comparison before any read. For the reads, every run carries one control, the A/A arm. It shows whether the readers pick a side when the two versions are the same. It does not show that they would see a real difference. A plan may add a second control, the sensitivity arm (§ 6): a version against a copy of it weakened on purpose. When the readers prefer the version, the run shows they could see that planted difference. Known limit: it does not show they could see one as small as the change under test. A run without a sensitivity arm that finds no difference does not show that the readers could have found one.

## 2. Scope

In scope:

- paired reads: a reader sees one posting and two versions, A and B, and scores both;
- the A/A control: the same version in both slots, run in every run, before any comparison;
- the sensitivity control, when the plan names one: a version against a copy of it weakened on purpose, run after the A/A arm and before any comparison;
- replicate runs: the same frozen plan run again in a new folder, compared with the first run;
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
- `document` (optional, revision 4): the kind of document the versions are, one of `résumé` (the default when the key is absent), `cover letter`, `essay` or `profile`, matched exactly. Any other value is refused at freeze, exit `2`, naming the plan line. It changes only the noun, with its article, where the reader prompt names the document (decision 26);
- `versions`: each version file, with a short name, and who drafted it, required for every version from revision 4 (§ 6, Family): `drafted-by user` when no model wrote or edited a word of it, `drafted-by model <family>` naming every model family that wrote or edited any wording in it, not only the last editor (more than one is written as a comma list, `drafted-by model <family>, model <family>`), `drafted-by third-party` when a person other than the user wrote it, or `drafted-by unknown`. For the family rule, a version `drafted-by unknown` is checked once with each reader family as its drafter, and must pass every time (§ 6, Family): stricter than a known drafter, and still passable;
- `comparisons`: one or more comparisons, each written `X vs Y` in version names. The tool adds the A/A arm (below) when the plan leaves it out, and says so in the result;
- `aa-version`: the version used in both slots of the A/A arm (default: the second version of the first comparison);
- `readers`: each reader's name and command (§ 5.1), its model `family` (required on every reader from revision 4, the fake reader included: one token, compared exactly after lower-casing, § 6, Family), whether it is `not-blind` (§ 5.5), and optionally the `reader-group` it belongs to, a name shared by readers that are alike (for example, one model behind two commands) (§ 5.5). A reader's `family` and its `reader-group` are separate: the family is required and the family rule reads it; the reader group stays optional and changes no verdict;
- `reads-per-reader`: reads per arm for each reader, an even number, read in pairs (§ 4.1) (default 6: 3 pairs per reader, and, with two readers, 6 paired picks and 12 reads per arm). The default run makes twice the reads that revision 3's default made: 12 per arm, was 6;
- `hypotheses`: each with its decision rule written as counts of valid paired picks, one per pair (§ 6). For example, "SUPPORTED if Y is preferred in 6 of 6; REFUTED if X is preferred in 4 or more; otherwise INCONCLUSIVE";
- `mechanisms` (optional): a case-insensitive pattern, the reply fields it is matched against, and the count of matching replies that supports it. The default fields are every free-text field: `DROVE-IT`, `DOUBTS`, `UNDERSOLD`, `OVEREXPLAINED`, `OWNED`, `FLAG-FIXES`, and the rationale part of `PREFER` (§ 5.4);
- `change-scope`: the line patterns where the two versions of each comparison may differ;
- `noise-threshold`: the share of valid A/A reads that are non-TIE, at any strength, at which every comparison is reported INCONCLUSIVE (default `1/2`, § 6). The default stays `1/2` now that `slightly` picks count: the gate trips more often, which fails closed, and no measurement supports another number;
- `aa-pool` (optional): the freeze files of earlier runs whose A/A reads this run's gate pools with its own (§ 6);
- `extends` (optional): the freeze file of a first run whose sample size this plan extends (§ 3.2);
- `sidedness` (optional): `two`, `greater` or `less`, the side of the sign test in § 6.1 (default `two`). `greater` tests whether the second-listed version of a comparison is preferred, and `less` whether it is not;
- `alpha` (optional): the level the disagreement flag in § 6.1 compares each p-value with (default `0.05`). It is written as `0.` followed by one or more digits, not all of them zero, and in no other form;
- `sensitivity` (optional): a pair written `X vs W`, where `X` is a version in `versions` and `W` is a copy of it weakened on purpose, also in `versions`. The plan should say in a comment what was weakened. Neither name may appear in a hypothesis, and the pair is not a comparison;
- `sensitivity-scope`: the line patterns where `X` and `W` may differ, under the rules of `change-scope`; required when `sensitivity` is given, and refused without it;
- `sensitivity-threshold` (optional): the share of valid sensitivity reads that must prefer `X`, written `<n>/<d>` (default `5/6`). It must be above 1/2 and at most 1;
- `min-valid-reads` (optional): the read floor, a whole number, 1 or more. A comparison arm with fewer valid reads from blind readers has its hypothesis and mechanism verdicts reported INCONCLUSIVE (§ 6). From revision 4 every comparison arm is paired, so the floor counts valid pairs: a floor written under revision 3 as a count of reads now asks for twice as many reads;
- `replicate-of` (optional): the freeze file of a first run of this same plan (§ 3.2);
- `spend-ceiling`: the run's limit, in the reader's own units;
- `amends` (optional): the freeze file of the plan this one replaces (§ 3.2).

### 3.2 Freeze

`track-record ab freeze PLAN` hashes the plan and every input it names (sha256), writes the hashes to a freeze file beside the plan, and exits `0`.

- It refuses, with exit `2`, if any named input is missing, if a freeze file already exists, or if the run folder already holds a reply.
- After a freeze, neither the plan nor its inputs may change. A run checks every hash first and exits `2`, naming the file, if any one differs. That includes the plan itself.
- The run folder is the folder that holds the plan.
- An amendment is a new plan, in a new run folder, whose `amends` key names the earlier freeze file. It gets its own freeze. The result names both freezes, and the earlier freeze file and run folder are never edited. From revision 4, an amendment may change the read count, never a decision threshold. A rule's count is part of its decision threshold, as a share: a clause's count `<n>`, in `<n> of <m>` or `<n> or more`, over the arm's planned paired picks. An amendment that changes the read count restates each count rule at the same share, and may change a rule's text in that way only: with the read count doubled, `6 of 6` becomes `12 of 12`, and `4 or more` of 6 becomes `8 or more` of 12. `freeze` compares the shares as exact fractions and refuses (exit `2`, naming the rule) a rule whose share differs from the rule it amends, or whose share gives no whole number at the new read count. It refuses (exit `2`, naming the changed setting) an amendment that changes `noise-threshold`, `sensitivity-threshold`, `alpha` or `min-valid-reads` from the plan it amends.
- An extension is a new plan, in a new run folder, whose `extends` key names the freeze file of a first run. It may change the sample size only: `reads-per-reader` and the number of readers of the models that already read. Everything else is not sample size and must be as the first plan has it: the decision rules, every threshold (`noise-threshold`, `sensitivity-threshold`), `alpha`, `min-valid-reads`, the versions, the prompts and which models read. `freeze` refuses any other difference: exit `2`, cannot run, naming the changed setting. A reader the extension adds is of a model that already read when it has the same command, byte for byte, the same `family` and the same `not-blind` marking as a reader of the first run; only its name differs. The same family alone is not enough, because another model of one family is another instrument. An extension's verdicts come from the first run's reads pooled with its own. Each count rule is read on the pooled pairs at its share, as for an amendment: the share is the threshold and does not change, and the count follows the pooled planned pairs. So `6 of 6` asks for every pooled pair, and `4 or more` of 6 for two thirds or more of them. `freeze` refuses (exit `2`, naming the rule) an extension whose pooled planned pairs give no whole number under a rule's share. Its result names the first freeze, says that the sample size changed after a result was seen, and prints the first run's verdict beside the pooled one. A first run can be extended once; a second extension needs a new plan. A plan may not carry `extends` together with `amends` or `replicate-of`. Replicates are the third way to add sample size (§ 6, Replicates).
- A replicate is a new plan, in a new run folder, whose `replicate-of` key names the freeze file of a first run. With that one line removed, the replicate's plan must be byte-identical to the plan the first freeze names, and every input it names must have the hash the first freeze recorded; `freeze` refuses it otherwise (exit `2`, naming the file). `replicate-of` must name a first run, not another replicate or an amendment, and a plan may not carry both `replicate-of` and `amends`. The first run folder is read, never written. A replicate's verdicts come from its own reads; its result also compares its counts with the first run's (§ 6).
- A plan frozen under an earlier revision is never scored under revision 4's rules: a verdict must not change because the tool was upgraded between the run and the score. A plan with no `family` on a reader or no `drafted-by` on a version is refused by `run` and by `score`, exit `2`, with a message that it was frozen under an earlier revision and must be scored with the release that froze it, or rewritten as a new plan.

### 3.3 Version and posting files

These are UTF-8 text, or PDF read through the same text extraction the barred check uses. File names are free; slots are not (§ 4).

## 4. Slots and isolation

### 4.1 Slot assignment

The arms are the A/A arm (`aa`), the sensitivity arm (`s`), when the plan names one, and the comparisons (`c1`, `c2` and so on). Within an arm, reads are numbered in the order they run: the first reader's reads, then the second reader's, and so on. From revision 4, each reader's reads come in pairs, counted within that reader: its first and second read, its third and fourth, and so on. The first read of a pair puts the first-listed version in slot A and the second read puts the second-listed version there, so each reader sees each order equally often. `freeze` refuses an odd `reads-per-reader` (exit `2`, naming the plan line). The result shows each reader's slot split.

The key file is written before any read runs. Readers see only `A.txt` and `B.txt`.

### 4.2 The isolation check (before any read)

For each comparison, the tool compares the two versions line by line, after collapsing runs of spaces and dropping blank lines. It reports every changed line and marks each one as inside or outside the declared change scope.

- If every changed line is inside the scope, the check passes.
- If any changed line is outside the scope, the run stops before reading, exits `2` and prints those lines. The user then narrows the versions or widens the scope, in a new plan.
- If a comparison has no changed line at all, the run stops and exits `2`, because a file compared with itself is the control, not a test.
- A plan with no comparison exits `2` (no A/A arm is possible without a version to copy).

The sensitivity pair gets the same check as a comparison, against `sensitivity-scope`: at least one changed line, and every changed line inside the scope, or the run stops before reading and exits `2`.

The A/A arm must show no changed line, and that is its own positive control. The check has to report zero on the A/A arm and nonzero on every real comparison, or the run does not start.

## 5. Readers

### 5.1 Pluggable

A reader is a command the tool runs once per read. The read folder is its only input and one reply file is its output. The tool ships one reader that needs no network, the fake reader (§ 5.3). Live readers are configured by the user and are never shipped with credentials.

### 5.2 Live runs and run order

The test suite and CI never start a live reader. For a live run, the tool prints the exact commands and the spend estimate. It runs them only when the user types the `--live` flag. Without `--live`, it prints, starts no reader, writes no reply and exits `0`. The fake reader never needs `--live`.

The A/A arm runs first, then the sensitivity arm when the plan names one, and then the comparisons in plan order. The spend ceiling stops the run between reads once it is reached. Reads that have already returned are kept, and the result says the run was cut.

### 5.3 The fake reader

The fake reader is a deterministic program for tests. Given a rule, it writes a reply in the reply format. Rules include:

- "prefer the version containing the string X";
- "always TIE";
- "prefer slot A" and "prefer slot B";
- "seeded pseudo-random", with the seed given in the plan;
- "write string S in field F" (for `PREFER`, S goes in the rationale);
- "omit field F";
- "on read k only", combined with another rule: that rule applies to read k, and every other read is TIE.

A rule applies to every comparison arm unless the plan names the arm it applies to, and it applies to the A/A arm or the sensitivity arm only when the plan names that arm (`aa` or `s`). On the A/A arm, the fake reader answers TIE unless the plan gives that arm its own rule. A non-TIE reply is marked `slightly` unless the rule names a strength. When the rules name no preference (for example, only "write S in F"), the reply is TIE. Each fake read costs 1 spend unit.

### 5.4 Reply format

Each reply starts with `READ: <read id>` and carries these fields, one per line or block:

- `PRIOR`;
- `SCORE-A` and `SCORE-B`;
- `PREFER`, written as `PREFER: <A|B|TIE>, <slightly|clearly|strongly>` with an optional rationale after it on the same line. TIE takes no strength. The rationale is the matchable text of `PREFER`;
- `DROVE-IT`, `DOUBTS`, `UNDERSOLD`, `OVEREXPLAINED`, `OWNED` and `FLAG-FIXES`.

A reply that is missing `READ`, `SCORE-A`, `SCORE-B` or `PREFER`, or whose `PREFER` choice cannot be read, is a failed read. Failed reads are counted and reported, never guessed.

### 5.5 Blindness

The prompt tells the reader that it knows nothing about the candidate, and the `PRIOR` field asks what it knew before reading. Any `PRIOR` other than `nothing` is flagged on that read in the result. A reader known to receive the user's identity from its own environment is marked `not-blind` in the plan. Its reads are reported separately and are never counted in a verdict, a gate or a mechanism count: from revision 3, everything in § 6 counts reads from blind readers only. Every verdict line says how many reads it left out because their reader is marked `not-blind` (§ 6.1). A reader's `reader-group`, when given, is reported with its reads, and the result counts valid reads per reader group; a reader group changes no verdict.

## 6. Scoring

Scoring reads only the replies, the key and the frozen plan, and, for a replicate, the first run's replies and key. Failed reads, and reads from readers marked `not-blind`, are left out of every denominator below. A rule that needs N of N valid reads is INCONCLUSIVE when fewer than N reads are valid, unless a settled completion lifts it (§ 6.1).

- **Preference.** Each read's preference is mapped through the key, from slot to version.
- **Paired picks** (revision 4). On a comparison arm and on the sensitivity arm, the two reads of a pair give one paired pick. When both prefer the same version, at any strength, the pair is one pick for that version. When they prefer different versions (an order-split pair), the pair is a TIE. A pair with one pick and one TIE is a TIE: a pick counts only when both orders agree. A pair with a failed read is a failed pair: it leaves the denominators, and it counts as one missing pair. Hypotheses, the sensitivity gate, the sign test, the completions and the read floor count paired picks: in their rules and lines, a valid read means a valid pair. The A/A arm is not paired: both slots hold the same version, so its gate counts single reads. Position, mechanisms, scores, the `missing` lines and the not-blind suffix count reads.
- **Hypotheses.** Each one gets SUPPORTED, REFUTED or INCONCLUSIVE from its frozen rule.
- **A/A gate.** If the share of valid A/A reads that are non-TIE is at or above the plan's noise threshold, every comparison is reported INCONCLUSIVE, whatever it showed, and the result says why. From revision 4, `slightly` picks count toward the gate. With `aa-pool`, the gate counts this run's valid A/A reads together with those of each pooled run. A pooled run must share with this run, by hash, the prompt, the reader command, the A/A version file and the posting. Its freeze must exist before this plan is frozen, and this plan's freeze records the pooled freeze file's hash as an input. `freeze` refuses any other pooled run (exit `2`, naming the file). Only valid A/A reads from blind readers are pooled. If the A/A arm has fewer valid reads than planned (failed reads or a cut), the gate is "not evaluated", and every comparison is INCONCLUSIVE.
- **Position.** The share of non-TIE reads that went to slot A is reported per arm and overall. In an arm with two or more non-TIE reads, all in the same slot, position is INCONCLUSIVE whatever the version counts. Alternating slots then gives each version exactly the wins its slot gave it. With fewer than two non-TIE reads, position is "not assessable" and the verdict stands as the rule gave it. From revision 4 the result also gives each reader's order consistency per arm: of its pairs in which both reads pick a version, how many pick the same version in both orders.
- **Mechanisms.** A mechanism check counts the valid replies in each arm in which its pattern matches any named field (replies, not matches). It reports that count beside the same count on the A/A arm, which is the pattern's noise floor. Each count is shown as a share of the arm's valid reads. If the share in a comparison is no higher than the A/A share, the pattern is reported as unable to separate the versions, and its rule is INCONCLUSIVE. From revision 4, a mechanism also needs a margin over its floor: its rule is INCONCLUSIVE, with the reason `no margin over the A/A floor`, unless the two-sided Fisher exact p-value for the comparison's count against the A/A count is below `alpha`. The test is two-sided, the stricter choice; the direction is already set by the rule above, under which a comparison share no higher than the A/A share cannot separate the versions. A mechanism verdict reports what readers wrote, not what caused their preference, and its line says so.
- **Sensitivity gate.** When the plan names a sensitivity pair: if the share of valid sensitivity reads that prefer `X` is below `sensitivity-threshold`, every comparison is reported INCONCLUSIVE, whatever it showed, and the result says the readers did not detect the planted difference. `Slightly` picks count toward this gate. If the sensitivity arm has fewer valid reads than planned (failed reads or a cut), the gate is "not evaluated", and every comparison is INCONCLUSIVE. A failed or unevaluated sensitivity gate voids mechanism verdicts as well as hypotheses, as the A/A gate does. Mechanisms are not counted on the sensitivity arm. Without a sensitivity pair, the result says the gate was not tested, and verdicts stand as the other rules give them.
- **Second reading** (revision 4). Each hypothesis is scored a second time, by the same frozen rule, with every `slightly` read counted as a TIE before pairing. The first reading, with `slightly` counted as a pick, gives the verdict; the result prints the second reading's verdict beside it. The gates (the A/A gate and the sensitivity gate) are computed once, by their own definitions, and apply to both readings. The lift (§ 6.1) acts on the first reading only, since that is the verdict: the second reading is the frozen rule with `slightly` counted as a TIE, under the same gates, with no lift. Position, the read floor and the family rule act on the first reading only, as the lift does; the second reading is a printed comparison and never changes a verdict. When the two differ and the verdict is SUPPORTED or REFUTED, the verdict line itself says that the verdict holds only one way; when the verdict is INCONCLUSIVE, the second reading's verdict is printed beside it, with no such sentence.
- **Family** (revision 4). The rule is stated by the version a verdict favours, the version its deciding clause names, so it covers SUPPORTED and REFUTED alike. When a SUPPORTED or REFUTED verdict favours a version drafted or edited by a model (`drafted-by model <family>`), and any blind reader is of that model's family, the verdict also needs the blind readers of every other family, taken together, to agree. With three or more families, the families that did not draft the version are pooled for this check. They agree when the deciding clause's share of their valid pairs, rounded up, pick the version. The share is the one § 3.2 defines: `6 of 6` asks for all of their valid pairs, and `4 or more` of 6 for two thirds or more of them. The check needs at least 3 valid pairs from the other families. When it fails, the verdict is INCONCLUSIVE, with the reason `the other family did not agree`; with fewer than 3 valid pairs from the other families, `too few pairs from another family`; and with no blind reader of another family, `no reader of another family`. The check is a guard on the verdict: 3 pairs alone would not carry one. For a favoured version `drafted-by unknown`, the check is run once for each blind reader family, each time treating that family as the drafter, and every run must pass. With two families, each family's readers, alone, must agree at the deciding clause's share, with at least 3 valid pairs; with one family, the verdict is INCONCLUSIVE, `no reader of another family`. Not-blind readers stay out of every count, as § 5.5 says. The result gives each family's counts beside the pooled count for every hypothesis; the reader-group lines stay as § 6.1 has them.
- **Read floor.** When the plan sets `min-valid-reads`, a comparison arm with fewer valid reads than the floor (from revision 4, valid pairs) has its hypothesis and mechanism verdicts reported INCONCLUSIVE, with the reason "below the read floor".
- **Scores.** Scores are reported per version and per reader, with the A/A arm's score spread beside them. When the plan names a sensitivity pair, the result also gives, per reader, the sensitivity arm's score gap: the mean score that reader gave `X` minus the mean it gave `W`.
- **Replicates.** A replicate's result gives, for each hypothesis, the first run's and this run's counts (`k` of `n` non-TIE paired picks for the second-listed version, blind reads only) and the two-sided Fisher exact p-value for the difference between them. Two runs of one frozen plan should differ only by chance; a small p-value suggests they differ by more than chance. Known limit: each replicate is compared with the first run only, so spread across three or more runs is not measured.

### 6.1 Evidence beside the verdicts

Nothing in this section changes a verdict, except the lift (under Missing reads). Each line is reported beside the verdicts above, which come from the frozen rules alone (§ 8).

- **Sign test.** For each hypothesis, over the valid reads of its comparison arm: `n` is the number of reads that pick a version, whatever their strength (a `slightly` pick counts), and `k` is the number of those that pick the second-listed version of the comparison (`Y` in `X vs Y`). TIEs are left out of `n` and reported as a count. The p-value is exact, from the binomial distribution with `n` trials and chance 1/2: under `greater`, the chance of `k` or more; under `less`, the chance of `k` or fewer; under `two`, twice the smaller of those two, and at most 1. Under `greater` or `less` the p-value measures one direction only. A SUPPORTED or REFUTED verdict for the other version is not compared with `alpha`; its flag line says that direction was not tested.
- **Interval.** The 95% Wilson score interval for `k/n`, with z = 1.959964, whatever `alpha` is.
- **No pick.** When `n` is 0, neither the p-value nor the interval is computed, and the line says so.
- **Disagreement flag.** A hypothesis whose verdict is SUPPORTED or REFUTED with a p-value at or above `alpha`, or INCONCLUSIVE with a p-value below `alpha`, is flagged. The exact p-value is compared, not the printed one. There is no flag when `n` is 0, or when the verdict is INCONCLUSIVE because of the A/A gate, the sensitivity gate, position, the read floor or the family rule (its reason line already says why). Under a one-sided test, a SUPPORTED or REFUTED verdict whose deciding clause names the version the test does not look at (the first-listed under `greater`, the second-listed under `less`) is not compared with `alpha`: its flag line says `one-sided test: this direction not tested` instead. The flag never changes the verdict.
- **Missing reads.** For each arm, the result counts the planned reads that are missing: failed, and not run (a cut or a stopped run). For each hypothesis with missing reads in its arm, the frozen rule is evaluated again under every completion of those reads, each one counted as a pick for `X`, a pick for `Y`, or a TIE, as if every planned read were valid. From revision 4 the completions work per pair. A pair with both reads missing completes as a pick for `X`, a pick for `Y` or a TIE. A pair with one valid read (a half-read pair) completes only in the ways that read allows: a valid pick for one version completes as a pick for that version or a TIE, never for the other, and a valid TIE completes only as a TIE. The result says whether one verdict holds under every completion (settled) or which verdicts are possible (unsettled), and gives the range of the p-value over the completions. This reads the rule alone: it does not complete the A/A arm or the sensitivity arm, and does not apply a gate, position, the read floor or the family rule. **The lift.** It changes a verdict in one case only: when the plan sets `min-valid-reads`, the arm's valid reads meet it, the verdict is INCONCLUSIVE because of the rule alone (not a gate, position, the floor or the family rule), and one verdict holds under every completion, that verdict replaces INCONCLUSIVE, and the result says it was lifted. Without a read floor nothing is lifted.
- **A dead run.** When no read in the run is valid, the result says so in one line. The exit status is `1`, as for any run with a failed read (§ 7).
- **The top of the scale.** The built-in prompt asks for scores from 1 to 10. For each arm, the result counts the valid reads that score both slots at 10 or more, and the valid reads that give both slots the same score. When every valid read of an arm scores both slots at 10 or more, the scores cannot show a difference in that arm, and the result says that preference is the only measure there.
- **Not-blind reads.** Each hypothesis and mechanism verdict line ends with the number of valid reads it left out because their reader is marked `not-blind` (§ 5.5).
- **Sensitivity gate evidence.** The gate's share gets the exact one-sided p-value against 1/2 (the chance that `k` or more of `n` valid sensitivity pairs prefer `X` if readers picked at random, TIE pairs counted as pairs that do not prefer `X`) and its 95% Wilson interval. Here `k` counts picks for the first-listed version `X`, the one not weakened; the sign test's convention of counting the second-listed version does not apply to the gate.
- **What the reads stand for.** Every result carries one validity line: the readers are models standing in for human screeners, that stand-in has not been checked against human ratings, and reads from one model and prompt may not be independent, so each p-value assumes an independence the reads may not have and may be too small. Each p-value carries a short form of the same caveat on the same line.

#### Printed forms

Every line names the unit it counts: on a paired arm, a line that counts pairs says pairs. In the forms below, `<Y>` is the second-listed version, `<arm>` is `aa` or `c1`, `c2` and so on, and `<h>` is the hypothesis name. A p-value is printed rounded half up to 4 decimal places, or as `< 0.0001` when it rounds to 0. An interval's lower end is rounded down and its upper end rounded up, to 3 decimal places. `<side>` is `two-sided`, `one-sided greater` or `one-sided less`.

- `hypothesis <h> evidence: <Y> <k> of <n> non-TIE paired picks, <t> TIE; p = <p> <side> (reads may be correlated; may be too small); 95% interval <lo> to <hi>`
- With no pick: `hypothesis <h> evidence: no non-TIE paired pick, <t> TIE; p and interval not computed`
- `hypothesis <h> flag: evidence disagrees: <verdict> at p = <p>, at or above alpha <alpha>`, or `... below alpha <alpha>` for an INCONCLUSIVE verdict. `<alpha>` is printed as the plan wrote it, or `0.05` by default.
- Under a one-sided test, for a verdict in the direction the test does not look at: `hypothesis <h> flag: one-sided test: this direction not tested`.
- `missing <arm>: <m> of <planned> planned reads (failed <f>, not run <r>)`, one line per arm, `m` = `f` + `r`. On a paired arm the line adds the pairs those reads cost: `missing <arm>: <m> of <planned> planned reads (failed <f>, not run <r>), costing <q> of <P> planned pairs`, so the two counts can be reconciled on the page.
- `hypothesis <h> completions (missing pairs: <m>): settled: <verdict>; p from <a> to <b>`, or `... unsettled: <verdicts> possible; p from <a> to <b>`, with the possible verdicts in the order SUPPORTED, REFUTED, INCONCLUSIVE and separated by `, `. When no completion has a pick, the part after the last `;` is `p not computed`. A hypothesis whose arm has no missing read gets no completions line.
- `DEAD: 0 of <N> planned reads are valid`, where `N` counts the planned reads of every arm.
- `scores <arm> ceiling: <c> of <v> valid reads score both slots at 10 or more`
- `scores <arm> separation: <s> of <v> valid reads give both slots the same score`
- When `c` equals `v` and `v` is 1 or more: `scores <arm>: at the ceiling; preference is the only measure`
- `A/A gate interval: <lo> to <hi> (95%, Wilson)`, the interval for the gate's own share (from revision 4, every non-TIE read, `slightly` included, over valid A/A reads, pooled ones included), or `A/A gate interval: not computed` when the A/A arm has no valid read.
- Every hypothesis verdict line and mechanism verdict line ends with ` [not blind: <b> reads left out]`.
- `sensitivity gate: passed (<k> of <n> valid sensitivity pairs prefer <X>; threshold <t>)`, `sensitivity gate: failed (...)` with the same parentheses, `sensitivity gate: not evaluated (<v> valid pairs of <p> planned)`, or `sensitivity gate: not tested`, on the line after the A/A gate line.
- `sensitivity gate evidence: p = <p> one-sided greater (reads may be correlated; may be too small); 95% interval <lo> to <hi>`, when the gate was evaluated.
- `sensitivity score gap <reader>: <gap>`, one line per reader with a valid sensitivity read, with `<gap>` printed as the score lines print a mean.
- A hypothesis reason line `hypothesis <h> reason: below the read floor (<v> valid pairs, floor <f>)`, and a mechanism reason line of the same form.
- After a lift, the verdict line gives the lifted verdict, and the reason line reads `hypothesis <h> reason: lifted from INCONCLUSIVE: settled under every completion of <m> missing pairs; read floor of <f> pairs met`.
- In a replicate: `replicate of: <first freeze sha256>`, and per hypothesis `hypothesis <h> replicate: first run <Y> <k1> of <n1> paired picks, this run <k2> of <n2>; Fisher exact p = <p> two-sided`.
- `reader-group <name>: <v> valid reads`, one line per reader group named in the plan, counting its valid reads across every arm.
- From revision 4:
  - `order consistency <reader> <arm>: <a> of <p> pairs pick the same version in both orders`, one line per reader and paired arm, where `<p>` counts the reader's pairs in which both reads pick a version;
  - `A/A slightly rate: <s> of <v> valid A/A reads are slightly`;
  - `hypothesis <h> second reading (slightly as TIE): <verdict>`; when it differs from a SUPPORTED or REFUTED verdict, the verdict line itself carries `; the verdict holds only when slightly counts as a pick` after the verdict and before the not-blind suffix (an INCONCLUSIVE verdict's line carries no such sentence), for example `hypothesis h1 verdict: SUPPORTED; the verdict holds only when slightly counts as a pick [not blind: 0 reads left out]`;
  - `hypothesis <h> family <name>: <Y> <k> of <n> paired picks`, one line per family, where `<n>` counts the family's valid pairs and `<k>` those that pick `<Y>`;
  - a hypothesis reason line `hypothesis <h> reason: the other family did not agree`, `hypothesis <h> reason: too few pairs from another family` or `hypothesis <h> reason: no reader of another family`, and a mechanism reason line `mechanism <m> reason: no margin over the A/A floor`;
  - `mechanism <m> margin: Fisher exact p = <p> two-sided against the A/A floor`, and on every mechanism verdict line, before the not-blind suffix, ` (what readers wrote, not a cause)`;
  - `A/A pool: <r> earlier runs, <v> valid A/A reads in the gate`;
  - `document: <kind>`, only when the plan's `document` is not `résumé`;
  - in an extension, `extends: <first freeze sha256>; the sample size changed after a result was seen`, and per hypothesis `hypothesis <h> extension: first run <verdict>, pooled <verdict>`.
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
- the evidence lines of § 6.1: each hypothesis's sign test, interval, flag and completions, the missing reads per arm, the A/A gate interval, the score ceiling and separation per arm, any `DEAD` line, and the validity line;
- the sensitivity gate, its counts, evidence and score gaps; any read-floor or lift reason; the counts per reader group; and, in a replicate, the comparison with the first run;
- from revision 4: each reader's order consistency, the A/A slightly rate and any A/A pool, each hypothesis's second reading and counts per family, any family reason, each mechanism's margin, the `document` line when the kind is not `résumé`, and, in an extension, the first run's verdicts beside the pooled ones.

Every run writes a new result; an earlier result is never overwritten.

Exit status:

- `0`: the run completed and was scored, whatever the verdicts, or it was a print without `--live`.
- `1`: the run completed, but at least one read failed or the run was cut. A dead run (§ 6.1) is exit `1` too.
- `2`: the run could not run. Causes: a hash mismatch, a failed isolation check, a missing input, a freeze over an existing freeze or run, an unknown plan key, a plan with no comparison, or (from revision 4) a plan frozen under an earlier revision, at `run` and at `score` (§ 3.2).

When causes combine, the higher code wins: `2` over `1` over `0`.

## 8. Rules that hold in every run

- No read before a freeze, and no plan edit after one.
- The A/A arm runs in every run, and it runs first.
- The isolation check runs before any read.
- Verdicts come from the frozen rules only. The tool has no option to change a rule at scoring time.
- A plan is scored only under the revision that froze it: `run` and `score` refuse a plan frozen under an earlier revision (§ 3.2).
- An amendment may change the read count, never a decision threshold; an extension may change the sample size only (§ 3.2).
- The evidence of § 6.1 sits beside the verdicts and never changes one, except the lift, which only a plan with a read floor allows.
- When a plan names a sensitivity pair, the sensitivity arm runs in every run of that plan, after the A/A arm and before any comparison.
- Reads from a reader marked `not-blind` are never counted in a verdict or a gate.
- A reader's suggested rewrite is reported as text and applied to nothing.

## 9. Decisions

Settled 2026-10-28:

1. Command name: `track-record ab`.
2. Default reads: 6 per arm (3 per reader, two readers). That is enough only for large, consistent effects, and a plan may ask for more. (Its "6 per arm (3 per reader)" is superseded in revision 4 by decision 21: 12 reads per arm, 6 per reader.)
3. Noise threshold default: `1/2`. Every comparison is reported INCONCLUSIVE when half or more of the valid A/A reads pick a side `clearly` or `strongly` (superseded in revision 4 by decision 18).
4. Cold reads (one version, scored alone) are planned for a later revision, as a second instrument.
5. The plan format is plain text with `key: value` lines (§ 3.1).

6. Public examples: an example plan changes only a neutral part of a résumé, such as section order, a summary line, a skills block, or one bullet's wording, and uses invented companies only. No example changes how employers, roles, titles, dates or tenure are shown.

Settled 2026-11-05, for revision 2:

7. The sign test leaves TIEs out and reports them as a count, and a `slightly` pick counts as a pick. The default side is two-sided, set with `sidedness: two|greater|less`.
8. `alpha` defaults to 0.05. The disagreement flag works in both directions (SUPPORTED or REFUTED at p ≥ alpha, INCONCLUSIVE at p < alpha) and never changes a verdict. Under a one-sided test, a verdict in the direction the test does not look at says `one-sided test: this direction not tested` instead of being flagged.
9. The missing-read completions are reported only; they lift no INCONCLUSIVE (superseded in revision 3 by decision 16, the lift). A dead run keeps exit `1` and gains the `DEAD` line.
10. Not-blind reads still count in the verdicts in revision 2, and every verdict line says how many there are.

Proposed for revision 3, settled when the owner signs it:

11. The sensitivity arm is optional, and a run without one says "sensitivity gate: not tested".
12. The sensitivity threshold defaults to 5/6, and `freeze` refuses one at or below 1/2.
13. `Slightly` picks count toward the sensitivity gate.
14. A replicate is a new run folder that names the first run's freeze; repeat reads inside one folder are not offered.
15. From revision 3, reads from not-blind readers are never counted in a verdict, which changes the verdicts of plans that have one.
16. A settled completion lifts an INCONCLUSIVE only when the plan sets a read floor and the arm meets it.

Proposed for revision 4, settled when the owner signs it:

17. **Position.** Each reader reads every pair in both orders, with an even read count and the orders balanced within the reader. A reader's pick counts only when both orders agree; an order-split pair, and a pair with one pick and one TIE, is a TIE, and a pair with a failed read is a failed pair. Rules count paired picks, one per pair. The result reports each reader's order consistency.
18. **The A/A gate counts every non-TIE pick**, `slightly` included, and the noise threshold default stays `1/2`. A/A reads may be pooled across runs that share, by hash, the prompt, the reader command, the A/A version file and the posting, when the pooled run was frozen first; only blind readers' valid A/A reads are pooled.
19. **`Slightly`.** The result reports the A/A arm's `slightly` rate, and each rule is also read with `slightly` counted as TIE, frozen with the plan. The first reading, with `slightly` counted as a pick, gives the verdict; the second, under the same gates and without position, the read floor, the family rule or the lift, is printed beside it and never changes a verdict; a SUPPORTED or REFUTED verdict that holds only one way says so on its verdict line.
20. **Same family.** The not-blind exclusion stays. The plan records every model family that drafted or edited each version (`drafted-by`), and each reader's family; a version of `unknown` origin is checked once with each reader family as its drafter, and must pass each time. Counts per family sit beside the pooled count. When a SUPPORTED or REFUTED verdict favours a version drafted or edited by a model of a blind reader's family, the readers of every other family, taken together, must agree at the deciding clause's share, on at least 3 valid pairs. That is a guard on the verdict: 3 pairs alone would not carry one.
21. **Read counts.** The default `reads-per-reader` is 6: 3 pairs per reader, and, with two readers, 6 paired picks and 12 reads per arm, twice the reads of revision 3's default. 6 of 6, in paired picks, stays the default for large effects. A plan for a modest change uses 12 to 20 paired picks per arm, which is 24 to 40 reads, at least four times the 6 reads per arm that revision 3's default made, or replicates. The README gives the effect each read count can detect.
22. **Mechanisms.** A mechanism claim needs a margin over its A/A floor, tested with the two-sided Fisher exact test the tool already has, and is labelled as what readers said, not what caused their preference.
23. **Scores.** No change: preference stays the only basis for a verdict.
24. **Amendments and extensions.** An amendment may change the read count, never a decision threshold; a rule's count is part of its threshold, as a share, so an amendment restates each count rule at the same share, and an extension reads each count rule at its share over the pooled pairs. An extension pools the first run's reads, names its freeze, may change the sample size only, says that the sample size changed after a result was seen, and prints the first run's verdict beside the pooled one; one extension per first run, an added reader has the same command, family and `not-blind` marking as a reader of the first run, and a changed setting is refused at freeze.
25. **Sources.** This spec cites no paper. The README names the papers behind decisions 17 to 22 once each cited figure has been checked against its paper.
26. **The document key.** A plan may name the kind of document its versions are with the optional scalar key `document`. Its four values are `résumé`, the default when the key is absent, `cover letter`, `essay` and `profile`, matched exactly; any other value refuses the plan at freeze, exit `2`, as any invalid scalar does. The reader prompt changes only the noun, with its article, in three phrases: "reading a résumé for", "one version of the résumé" and "another version of the same résumé" (for an essay: "reading an essay for", "one version of the essay" and "another version of the same essay"). With the key absent or `résumé`, the prompt and its recorded sha256 are byte-identical to revision 3's. With it set to another kind, the rendered prompt is what each read folder's `PROMPT.txt` holds and what the freeze and the result record as the prompt sha256, and the result prints `document: <kind>`. A change to the key after freeze is refused, as any plan edit is.

## 10. Acceptance tests (known answers)

Every test uses the fake reader, except 10.13. That test uses a stub live-reader command that fails the test if it is ever executed.

The fixtures are invented:

- a two-page résumé for an invented engineer at invented companies, with a skills block, headed `Skills`, after the experience section;
- an invented posting;
- three versions, `base`, `skills-top` and `skills-top-short`. `skills-top` moves the skills block above the experience section and heads it `At a glance`; `skills-top-short` does the same and cuts the block to one line. Each pair differs only in the skills block, both changed versions contain `At a glance`, and the fixture plan's change scope names the skills heading and the skills lines (a moved block shows as removed and added lines, all inside the scope).

Unless a test says otherwise, the plan has one comparison (`base vs skills-top`), every version `drafted-by user`, two readers with 6 reads each (`reader-1`, of family `m1`, and `reader-2`, of family `m2`), the default noise threshold, and the fake reader's default TIE on the A/A arm. Each arm has 12 reads: reader-1's reads 1 to 6, then reader-2's reads 7 to 12. Its pairs are reads 1 and 2, 3 and 4, and so on to 11 and 12, so a comparison arm or the sensitivity arm gives 6 paired picks. This default makes twice the reads of revision 3's, which had two readers with 3 reads each.

- 10.1: The rule "prefer the version containing `At a glance`" on the comparison makes `skills-top` preferred in all 12 reads, so in 6 of 6 paired picks. The hypothesis "skills-top preferred in 6 of 6" is SUPPORTED, the A/A gate passes, and the run exits 0.
- 10.2: "Always TIE" makes the hypothesis INCONCLUSIVE, and position is "not assessable" (no non-TIE pick). Exit 0.
- 10.3: "Prefer slot A" on the comparison gives each version 6 of the 12 reads, and every pair is order-split, so all 6 paired picks are TIE. The arm's position share is 100% slot A (12 of 12 non-TIE reads), so position is INCONCLUSIVE and so is the hypothesis. The A/A gate passes.
- 10.4: Versions that also differ in a bullet outside the change scope stop the run before any read. It exits 2 and prints that line.
- 10.5: A comparison of a file with itself exits 2 before reading.
- 10.6: A version file edited after the freeze makes the run exit 2, naming the file. No reply is written.
- 10.7: A freeze in a folder that already holds a reply is refused, exit 2.
- 10.8: The A/A arm is given "seeded pseudo-random, seed 1, every reply non-TIE and strongly". 12 of 12 is at or above `1/2`, so the gate trips. The comparison is reported INCONCLUSIVE with the A/A reason, whatever its counts. Exit 0.
- 10.9: "Omit field `PREFER`" on read 1 of the comparison leaves one reply without `PREFER`. It is counted as failed and not guessed. Its pair (reads 1 and 2) is a failed pair, leaving 11 valid reads and 5 valid pairs, so the "6 of 6" rule is INCONCLUSIVE. Exit 1.
- 10.10: A reply whose `PRIOR` is not `nothing` is flagged on that read.
- 10.11: The rule "write `too long` in `DOUBTS`" applies to 8 of the 12 comparison reads (revision 3's 4 of 6, at the same share) and to no A/A read. The mechanism `too long` is reported as 8/12 against an A/A floor of 0/12, with a margin p of 0.0013 (10.85). The rule "supported at 3 or more" is SUPPORTED.
- 10.12: The plan has two comparisons, `base vs skills-top` and `base vs skills-top-short` (36 reads), with a spend ceiling of 16 units. The A/A arm completes (12 reads), and the first comparison is cut at 4 reads. The A/A gate is evaluated, the first comparison is INCONCLUSIVE (4 valid reads, 2 valid pairs), the second has no reads, and the result says the run was cut. Exit 1.
- 10.13: With a live reader configured and `--live` absent, the tool prints the commands and the spend estimate, never executes the stub, writes no reply and exits 0.
- 10.14: One run has two comparisons, `base vs skills-top` with "prefer slot B" and `base vs skills-top-short` with "prefer the version containing `At a glance`". The first arm is INCONCLUSIVE for position (each version wins 6 reads, all in slot B, and every pair is order-split). The second is SUPPORTED. The overall position share is 6 of 24 non-TIE reads in slot A (the second arm's even reads), reported beside both arms.
- 10.15: The rule "write `jargon` in `DOUBTS`" applies to every reply, A/A included. The mechanism `jargon` is reported at 12/12 against a floor of 12/12, as unable to separate the versions. INCONCLUSIVE.
- 10.16: A phrase written only in the `PREFER` rationale is matched under the default fields, and not matched when the plan names `DOUBTS` alone.
- 10.17: A freeze where a freeze file already exists is refused, exit 2.
- 10.18: An amendment (a new plan in a new run folder, with `amends` naming the first freeze file) is frozen and scored. Its result names both freezes, and the first run folder stays byte-identical. A second freeze in the first run folder is refused (10.7, 10.17).
- 10.19: A plan without an A/A arm gets one added, using `aa-version`, and the result says so. A plan with no comparison exits 2.
- 10.20: Versions that differ only in runs of spaces and in blank lines are treated as identical. Declared as a comparison, they exit 2.
- 10.21: Scoring twice writes two result files, and the first is unchanged.
- 10.22: "Prefer the version without `At a glance`" makes `base` preferred in 6 of 6, so the hypothesis is REFUTED (4 or more).
- 10.23: With the A/A arm given "prefer slot A, slightly", the gate passed under revision 3, because `slightly` picks did not count. From revision 4 it trips (10.80).
- 10.24: A reader marked `not-blind` has its reads reported separately, and from revision 3 never counted with the others (§ 5.5).
- 10.25: The result shows scores per version and per reader, with the A/A score spread.
- 10.26: "Omit field `READ`", "omit field `SCORE-A`" and "omit field `SCORE-B`", each on a different read, give three failed reads, each counted and named.
- 10.27: "Prefer the version containing `At a glance`, on read 2 only" gives an arm with exactly one non-TIE pick. It reports position as "not assessable", and its verdict follows the rule.
- 10.28: Editing the plan file after the freeze makes the run exit 2, naming the plan.
- 10.29: A PDF version is read through text extraction. Its isolation check and scores match those of the same text given as a UTF-8 file.
- 10.30: A failed read together with a cut gives exit 1, and both are reported. A hash mismatch together with a failed isolation check gives exit 2, and both are reported (neither run reads anything).
- 10.31: With one reader and `reads-per-reader: 6`, the first-listed version is in slot A on reads 1, 3 and 5, and the result shows the slot split as 3 and 3. With the default two readers, it is in slot A on reads 1, 3, 5, 7, 9 and 11, so each reader's split is 3 and 3. (Revision 3 alternated over the arm and allowed `reads-per-reader: 5`, a split of 3 and 2; revision 4 refuses an odd count, 10.77.)

Tests 10.42 to 10.57 are new in revision 2 (10.32 to 10.41 are the build interpretations' tests, below). Where a test names "the example rule", the hypothesis is `SUPPORTED if skills-top preferred in 6 of 6; REFUTED if base preferred in 4 or more; otherwise INCONCLUSIVE`.

- 10.42: 10.1 with the example rule. The result has `hypothesis h1 evidence: skills-top 6 of 6 non-TIE paired picks, 0 TIE; p = 0.0313 two-sided (reads may be correlated; may be too small); 95% interval 0.609 to 1.000`, the verdict line `hypothesis h1 verdict: SUPPORTED; the verdict holds only when slightly counts as a pick [not blind: 0 reads left out]` (every pick is `slightly`, 10.82), and no flag line. (The exact p-value is 1/32 = 0.03125, so rounding half to even would print 0.0312.)
- 10.43: 10.42 with `sidedness: greater` prints `p = 0.0156 one-sided greater`. With `sidedness: less` it prints `p = 1.0000 one-sided less` and the flag line `hypothesis h1 flag: one-sided test: this direction not tested`, because the deciding clause names `skills-top`, the version `less` does not look at. The verdict is SUPPORTED in both.
- 10.44: Reads 1 to 8 of the comparison `prefer containing "At a glance"`, reads 9 to 12 `prefer without "At a glance"` (so 4 pairs pick `skills-top` and 2 pick `base`), and the hypothesis is `SUPPORTED if skills-top preferred in 4 or more; otherwise INCONCLUSIVE`. It is SUPPORTED, with `skills-top 4 of 6 non-TIE paired picks, 0 TIE; p = 0.6875 two-sided` and `95% interval 0.299 to 0.904` (the exact lower end, 0.29999…, is rounded down), and the flag line `hypothesis h1 flag: evidence disagrees: SUPPORTED at p = 0.6875, at or above alpha 0.05`.
- 10.45: `reads-per-reader: 8` (16 reads and 8 pairs per arm), `prefer containing "At a glance"` on the comparison, `omit PREFER | read 16`, and the hypothesis `SUPPORTED if skills-top preferred in 8 of 8; otherwise INCONCLUSIVE`. Seven pairs are valid, so the verdict is INCONCLUSIVE. The result has `skills-top 7 of 7 non-TIE paired picks, 0 TIE; p = 0.0156 two-sided`, `95% interval 0.645 to 1.000`, the flag line `hypothesis h1 flag: evidence disagrees: INCONCLUSIVE at p = 0.0156, below alpha 0.05`, `missing c1: 1 of 16 planned reads (failed 1, not run 0), costing 1 of 8 planned pairs`, `missing aa: 0 of 16 planned reads (failed 0, not run 0)` (the A/A arm is not paired) and `hypothesis h1 completions (missing pairs: 1): unsettled: SUPPORTED, INCONCLUSIVE possible; p from 0.0078 to 0.0156`. The failed read's pair is half-read: its valid read 15 picks `skills-top`, so it completes as a pick for `skills-top` or a TIE, never for `base` (under revision 3, a `base` completion made the upper end 0.0703). Exit 1.
- 10.46: `prefer without "At a glance"` on the comparison, `omit PREFER | read 1`, the example rule. Five pairs are valid, all for `base`, so the verdict is REFUTED, with `skills-top 0 of 5 non-TIE paired picks, 0 TIE; p = 0.0625 two-sided`, `95% interval 0.000 to 0.435`, the flag line `hypothesis h1 flag: evidence disagrees: REFUTED at p = 0.0625, at or above alpha 0.05`, and `hypothesis h1 completions (missing pairs: 1): settled: REFUTED; p from 0.0313 to 0.0625`. The half-read pair's valid read 2 picks `base`, so it completes as `base` or TIE, never `skills-top` (under revision 3 the upper end was 0.2188). Exit 1.
- 10.47: `aa | omit PREFER` and `all | omit PREFER`, the example rule. Every read fails. The result has `DEAD: 0 of 24 planned reads are valid`, `missing aa: 12 of 12 planned reads (failed 12, not run 0)`, `missing c1: 12 of 12 planned reads (failed 12, not run 0), costing 6 of 6 planned pairs`, the gate "not evaluated", `A/A gate interval: not computed`, `hypothesis h1 evidence: no non-TIE paired pick, 0 TIE; p and interval not computed`, verdict INCONCLUSIVE with no flag line, and `hypothesis h1 completions (missing pairs: 6): unsettled: SUPPORTED, REFUTED, INCONCLUSIVE possible; p from 0.0313 to 1.0000`. Exit 1, as 10.9 is.
- 10.48: 10.1 plus `all | score 10 10` and `aa | score 10 10`. For both `aa` and `c1`: `scores <arm> ceiling: 12 of 12 valid reads score both slots at 10 or more`, `scores <arm> separation: 12 of 12 valid reads give both slots the same score` and `scores <arm>: at the ceiling; preference is the only measure`.
- 10.49: With no `score` rule (every score 5), each arm has `ceiling: 0 of 12` and `separation: 12 of 12`, and no "at the ceiling" line. With `all | score 10 12`, `c1` has `ceiling: 12 of 12`, `separation: 0 of 12` and the "at the ceiling" line, and `aa` has none.
- 10.50: 10.11's plan with reader-2 marked `not-blind`. The hypothesis verdict line ends ` [not blind: 6 reads left out]`, and so does the `too long` mechanism verdict line.
- 10.51: Every result has exactly one validity line, with the text in § 6.1, including those of 10.2, 10.8 and 10.47.
- 10.52: 10.42 with `alpha: 0.01` has the flag line `hypothesis h1 flag: evidence disagrees: SUPPORTED at p = 0.0313, at or above alpha 0.01`. The verdict is SUPPORTED.
- 10.53: `freeze` refuses each of `alpha: 0`, `alpha: 0.0`, `alpha: 1`, `alpha: 1/20`, `alpha: .05`, `sidedness: both` and `sidedness: Two`, with exit 2, naming the plan line, and writes no freeze file. `alpha: 0.05` and `sidedness: less` freeze.
- 10.54: 10.8 has `A/A gate interval: 0.757 to 1.000 (95%, Wilson)` (12 of 12). With the default TIE on the A/A arm (10.1), it is `A/A gate interval: 0.000 to 0.243 (95%, Wilson)` (0 of 12).
- 10.55: 10.2 (always TIE) has `hypothesis h1 evidence: no non-TIE paired pick, 6 TIE; p and interval not computed` and no flag line.
- 10.56: 10.8 with `prefer containing "At a glance"` on the comparison and the example rule. The rule alone would give SUPPORTED at p = 0.0313. The gate trips, so the verdict is INCONCLUSIVE with the A/A reason, the evidence line is printed in full, and there is no flag line.
- 10.57: Revision 2 changed no prompt: the built-in prompt's sha256 equals the one the previous release recorded, and from revision 4 it still does when the plan names no `document` (10.92). A plan frozen before revision 4 is no longer run or scored: it has no `family` and no `drafted-by`, so `run` and `score` refuse it, exit 2 (10.94).

Tests 10.58 to 10.76 are new in revision 3. They add a fixture, `base-weak`: the `base` résumé with one bullet's specific phrase, here called P, replaced by a vague one, so that P appears only in `base`. Tests 10.58 to 10.70 are the sensitivity-arm proposal's S.1 to S.13, in order: S.1 to S.9 are 10.58 to 10.66, S.10 is 10.67, S.11 is 10.68, S.12 is 10.69 and S.13 is 10.70. Where a test names "the sensitivity plan", the plan adds `sensitivity: base vs base-weak` and a `sensitivity-scope` naming that bullet's line.

- 10.58: The sensitivity plan with `s | prefer containing "P"` and the comparison as 10.1: `sensitivity gate: passed (6 of 6 valid sensitivity pairs prefer base; threshold 5/6)`, `sensitivity gate evidence: p = 0.0156 one-sided greater (reads may be correlated; may be too small); 95% interval 0.609 to 1.000`, the comparison SUPPORTED, exit 0.
- 10.59: The sensitivity plan with `s | tie`: the gate fails (0 of 6), and the comparison is INCONCLUSIVE with a reason naming the sensitivity gate, and no flag line, though its p-value (0.0313) is below alpha. Exit 0.
- 10.60: `sensitivity: base vs base` exits 2 before reading.
- 10.61: A `base-weak` that also differs from `base` outside `sensitivity-scope` exits 2 before reading and prints the line.
- 10.62: Every earlier acceptance test, with no `sensitivity` key, gives the result it gave under revision 2 plus the line `sensitivity gate: not tested`, with two exceptions: every verdict line's not-blind suffix takes the revision 3 form ` [not blind: <b> reads left out]` (as 10.42 shows), and the tests with a reader marked `not-blind` (10.24 and 10.50) leave those reads out of every count (decision 15, as 10.71 shows).
- 10.63: The sensitivity plan with `s | omit PREFER | read 1`: the gate is "not evaluated", the comparison is INCONCLUSIVE, exit 1.
- 10.64: The sensitivity plan with a spend ceiling of 18: the A/A arm completes (12 reads), the sensitivity arm is cut at 6 reads, the gate is "not evaluated", the run is reported cut, exit 1.
- 10.65: The sensitivity plan with `s | prefer slot A`: `base` is preferred on the odd reads only, so every pair is order-split, the gate fails (0 of 6 pairs prefer `base`, below 5/6), and position on `s` is INCONCLUSIVE (12 of 12 non-TIE reads in slot A).
- 10.66: The sensitivity plan with `s | score 8 5`. The score rule follows the slots, so reader-1 (reads 1 to 6; `base` in slot A on reads 1, 3 and 5) gives `base` 8, 5, 8, 5, 8, 5 and `base-weak` 5, 8, 5, 8, 5, 8, a gap of 0, and reader-2 (reads 7 to 12; `base` in slot A on reads 7, 9 and 11) gives a gap of 0 too: each reader's orders are balanced. (Under revision 3, reads alternated over the arm, and the gaps were 1 and -1.)
- 10.67: `all | prefer slot B` with the sensitivity plan and no `s` rule: the sensitivity reads are TIE (the `all` arm does not reach `s`), so the gate fails.
- 10.68: `freeze` refuses `sensitivity-threshold: 1/2`, `sensitivity-threshold: 2/5` and `sensitivity` without `sensitivity-scope`, naming the plan line; `sensitivity-threshold: 4/6` freezes.
- 10.69: 10.11's plan made the sensitivity plan with `s | tie`: the gate fails, the `too long` mechanism is INCONCLUSIVE, and its 8/12 count is still shown.
- 10.70: A hypothesis that names `base-weak` is refused by `freeze`, naming the plan line.
- 10.71: 10.1 with reader-2 marked `not-blind`: reader-1's 6 blind reads remain, 3 pairs, so "skills-top preferred in 6 of 6" is INCONCLUSIVE (it was SUPPORTED under revision 2), and the verdict line ends ` [not blind: 6 reads left out]`. This is the verdict change of decision 15.
- 10.72: 10.9's plan (one failed read, 5 valid) with `min-valid-reads: 6`: the hypothesis reason is `below the read floor (5 valid pairs, floor 6)`. With `min-valid-reads: 5` the reason is the rule's own, and the verdict is INCONCLUSIVE.
- 10.73: The rule `SUPPORTED if skills-top preferred in 5 of 6; otherwise INCONCLUSIVE`, `prefer containing "At a glance"`, `omit PREFER | read 1`: five valid pairs, so the rule gives INCONCLUSIVE, and every completion gives SUPPORTED. Without a read floor the verdict stays INCONCLUSIVE, with `completions (missing pairs: 1): settled: SUPPORTED`. With `min-valid-reads: 5` the verdict is SUPPORTED, with the reason `lifted from INCONCLUSIVE: settled under every completion of 1 missing pairs; read floor of 5 pairs met`; its second reading, which is not lifted, is INCONCLUSIVE, so the verdict line says that the verdict holds only when slightly counts as a pick. Exit 1 in both.
- 10.74: 10.73's plan with `min-valid-reads: 5` and the A/A gate tripped as in 10.8: the verdict stays INCONCLUSIVE with the A/A reason; nothing is lifted.
- 10.75: A replicate of 10.1 (a second folder whose plan adds only `replicate-of`) gives `replicate of: <the first freeze's sha256>` and `hypothesis h1 replicate: first run skills-top 6 of 6 paired picks, this run 6 of 6; Fisher exact p = 1.0000 two-sided`, and the first run folder stays byte-identical. A replicate whose plan differs from the first in any other line, or whose version file has changed since the first freeze, is refused by `freeze`, naming the file.
- 10.76: Readers `reader-1 | fake | reader-group f1` and `reader-2 | fake | reader-group f1`: the result has `reader-group f1: 24 valid reads` (every valid read of every arm), and every verdict is as in 10.1.

Revision 4 restates the default plan above. Revision 3's had two readers with 3 reads each, 6 reads per arm, and an odd count that revision 4 refuses; revision 4's has two readers with 6 reads each, 12 reads per arm, twice as many. Tests 10.1 to 10.76 are stated for the new default plan. In it, a count of paired picks, such as the 6 of 6 of 10.1, is the number revision 3 gave as a count of reads, and the counts of A/A reads, mechanism replies, scores and the `missing` lines are twice revision 3's. Every plan in those tests gives each version a `drafted-by` and each reader a `family`, as the default plan does. The fake reader marks a pick `slightly` unless its rule names a strength, so each SUPPORTED or REFUTED verdict in 10.1 to 10.76 whose picks are all `slightly` has an INCONCLUSIVE second reading, and its verdict line says that the verdict holds only when slightly counts as a pick (10.82); a test that means a verdict that holds both ways names a strength in its rule. Each result also has, for each hypothesis, one `family` line per reader family (10.78). Tests 10.77 to 10.94 are new in revision 4:

- 10.77: `reads-per-reader: 3` and `reads-per-reader: 5` are each refused at freeze, exit 2, naming the plan line, and no freeze file is written. `reads-per-reader: 6` freezes.
- 10.78: 10.1: every pair picks `skills-top` in both orders, so the hypothesis counts 6 paired picks from 12 reads, one per pair. The result has `order consistency reader-1 c1: 3 of 3 pairs pick the same version in both orders`, the same line for reader-2, `hypothesis h1 family m1: skills-top 3 of 3 paired picks` and `hypothesis h1 family m2: skills-top 3 of 3 paired picks`.
- 10.79: 10.3 (`prefer slot A` on the comparison): every pair is order-split, so every paired pick is a TIE. The result has `hypothesis h1 evidence: no non-TIE paired pick, 6 TIE; p and interval not computed` and `order consistency reader-1 c1: 0 of 3 pairs pick the same version in both orders`, and the same line for reader-2.
- 10.80: 10.1 with `aa | prefer slot A | slightly`: 12 of 12 valid A/A reads are non-TIE, at or above `1/2`, so the gate trips, and the hypothesis is INCONCLUSIVE with the A/A reason: `slightly` picks count from revision 4 (under revision 3, 10.23 passed this gate). The result has `A/A slightly rate: 12 of 12 valid A/A reads are slightly` and `A/A gate interval: 0.757 to 1.000 (95%, Wilson)`.
- 10.81: 10.1 with `aa | prefer slot A | slightly | read 1` and `aa | prefer slot B | clearly | read 2`: `A/A slightly rate: 1 of 12 valid A/A reads are slightly`. 2 of 12 valid A/A reads are non-TIE, below `1/2`, so the gate passes, with `A/A gate interval: 0.046 to 0.449 (95%, Wilson)`.
- 10.82: 10.42, where every pick is `slightly`: the first reading is SUPPORTED, and the second is INCONCLUSIVE, because no pick is left once `slightly` counts as a TIE. The result has `hypothesis h1 verdict: SUPPORTED; the verdict holds only when slightly counts as a pick [not blind: 0 reads left out]` and `hypothesis h1 second reading (slightly as TIE): INCONCLUSIVE`. With `prefer containing "At a glance" | clearly`, both readings are SUPPORTED, the verdict line is `hypothesis h1 verdict: SUPPORTED [not blind: 0 reads left out]`, and the second reading line gives SUPPORTED. With `clearly` on reads 1 to 11 and `slightly` on read 12, the first reading is SUPPORTED (6 of 6); on the second, reads 11 and 12 are one pick and one TIE, so that pair is a TIE, the count is 5 of 6, and the second reading is INCONCLUSIVE.
- 10.83: `skills-top` is `drafted-by model m1`, and the readers are the default plan's (reader-1 of `m1`, reader-2 of `m2`). (a) With 10.42's reads and the example rule, reader-2's 3 valid pairs all pick `skills-top`; the share of `6 of 6` asks for all of them, so the other family agrees, and the verdict is SUPPORTED. (b) With `prefer containing "At a glance"` on reads 1 to 6 only (reader-1's) and the hypothesis `SUPPORTED if skills-top preferred in 3 or more; otherwise INCONCLUSIVE`, the rule holds on the pooled count (3 of 6). Its share is 3 of 6, so reader-2's 3 valid pairs need 2 picks (half of 3, rounded up), and they have none: the verdict is INCONCLUSIVE, with `hypothesis h1 reason: the other family did not agree`, `hypothesis h1 family m1: skills-top 3 of 3 paired picks` and `hypothesis h1 family m2: skills-top 0 of 3 paired picks`. (c) With 10.42's reads, `omit PREFER | read 7` and the hypothesis `SUPPORTED if skills-top preferred in 5 or more; otherwise INCONCLUSIVE`, the 5 valid pairs all pick `skills-top`, so the rule holds, but reader-2 has 2 valid pairs: INCONCLUSIVE, with `hypothesis h1 reason: too few pairs from another family`. Exit 1.
- 10.84: (a) 10.83 (a) with both readers of family `m1`: INCONCLUSIVE, with `hypothesis h1 reason: no reader of another family`. (b) 10.83 (a) with `skills-top` `drafted-by unknown`: the check runs twice. With `m1` as the drafter, reader-2's 3 valid pairs all pick `skills-top`; with `m2` as the drafter, reader-1's 3 do; both runs pass, and the verdict is SUPPORTED. 10.83 (b)'s reads and rule with `skills-top` `drafted-by unknown`: the run with `m1` as the drafter fails (reader-2 has 0 of the 2 picks it needs), so the verdict is INCONCLUSIVE, with `the other family did not agree`. 10.83 (a) with `skills-top` `drafted-by unknown` and both readers of family `m1`: INCONCLUSIVE, with `no reader of another family`. (c) 10.22 (every read prefers `base`) with `base` `drafted-by model m1`: the REFUTED verdict favours `base`, so the rule applies. With the default readers it stays REFUTED: the share of `4 or more` of 6 is two thirds, so reader-2's 3 valid pairs need 2, and all 3 pick `base`. With both readers of family `m1` it is INCONCLUSIVE, with `no reader of another family`.
- 10.85: 10.11 has `mechanism too long margin: Fisher exact p = 0.0013 two-sided against the A/A floor` (8 of 12 against 0 of 12; the exact p-value is 10/7429), below alpha 0.05, so the mechanism is SUPPORTED, and its verdict line carries ` (what readers wrote, not a cause)` before the not-blind suffix. With `too long` written in 4 of the 12 comparison reads, revision 3's count, the share 4/12 is above the floor 0/12 and "supported at 3 or more" holds, but the margin line gives `p = 0.0932` (exactly 15/161), not below alpha: INCONCLUSIVE, with `mechanism too long reason: no margin over the A/A floor`. (Under revision 3, 10.11's 4 of 6 was SUPPORTED with no margin asked; its margin would have been 2/33, 0.0606.)
- 10.86: An amendment of 10.42's plan that sets `reads-per-reader: 12` and restates the example rule as `SUPPORTED if skills-top preferred in 12 of 12; REFUTED if base preferred in 8 or more; otherwise INCONCLUSIVE` freezes. Each of these is refused at freeze, exit 2, naming the rule: the same amendment with the rule kept as written (`6 of 6` over 12 planned pairs is a share of 1/2, not 1), and an amendment that sets `reads-per-reader: 8`, at which `4 or more` of 6 gives no whole number (two thirds of 8 pairs). An amendment that also changes `noise-threshold` or `alpha` is refused, exit 2, naming the setting.
- 10.87: An extension of 10.1 that changes only `reads-per-reader` (to 4), or that adds `reader-3 | fake | family m2`, freezes and pools the first run's reads. Its result has `extends: <the first freeze's sha256>; the sample size changed after a result was seen`. With `reads-per-reader: 4`, the pooled arm has 10 planned pairs (6 and 4); 10.1's rule `6 of 6` is read at its share as all 10 of them, every pooled pair picks `skills-top`, and the result has `hypothesis h1 extension: first run SUPPORTED, pooled SUPPORTED` and `skills-top 10 of 10 non-TIE paired picks, 0 TIE; p = 0.0020 two-sided` (exactly 1/512) with `95% interval 0.722 to 1.000`. An extension of 10.42's plan (the example rule) with `reads-per-reader: 4` is refused at freeze, exit 2, naming the rule: two thirds of 10 pooled pairs is no whole number. With `reads-per-reader: 6` it freezes: over 12 pooled pairs its rule is read as `12 of 12` for `skills-top` and `8 or more` for `base`. Each of these is refused at freeze, exit 2, naming the setting: an extension that changes `alpha`, a version or the posting; one that adds a reader of family `m3`, or `reader-3 | fake | family m2 | not-blind`; a second extension of the same first run; and a plan that carries `extends` with `amends` or `replicate-of`.
- 10.88: 10.1 is run in one folder. A second plan in a new folder, 10.1's plus `aa-pool` naming the first freeze file, gates on the A/A reads of both: `A/A pool: 1 earlier runs, 24 valid A/A reads in the gate`, 0 of 24 non-TIE, so the gate passes, and its freeze file records the first freeze file's hash. `freeze` refuses, exit 2, naming the file, an `aa-pool` whose freeze file records another prompt hash, another reader command, another A/A version file or another posting, and one that names a freeze file that does not exist yet.
- 10.89: `freeze` refuses, exit 2, naming the plan line, a version without `drafted-by`, a `drafted-by` value in none of its four forms, and a reader without `family`. `drafted-by model M1, model m3` on `skills-top` freezes. Families compare after lower-casing, so with 10.83 (a)'s reads, reader-1 is of a drafting family and reader-2 is not, and the verdict is SUPPORTED, as in 10.83 (a).
- 10.90: The read floor counts pairs. 10.72 is unchanged (10.9's plan has 5 valid pairs, below `min-valid-reads: 6`). 10.1 with `min-valid-reads: 12`, a floor that 12 reads would meet, is below it, because the arm has 6 valid pairs: the hypothesis is INCONCLUSIVE with `hypothesis h1 reason: below the read floor (6 valid pairs, floor 12)`.
- 10.91: With `document: essay`, each read folder's `PROMPT.txt` is the built-in prompt with "reading a résumé for", "one version of the résumé" and "another version of the same résumé" read as "reading an essay for", "one version of the essay" and "another version of the same essay". It differs from the built-in prompt in those three lines only, has the same number of lines, and holds no "résumé". The freeze file and the result's `prompt sha256:` line give its sha256, and the result has `document: essay`. The same holds for `cover letter` ("reading a cover letter for") and `profile` ("reading a profile for"). The four kinds give four different prompt hashes.
- 10.92: Without `document`, and with `document: résumé`, the prompt is the built-in prompt byte for byte, its sha256 is `567b9bc16d86abfe4af935a844e28a1b6d2d257aa4f93b6ab3de8e97ce1fdd14`, the one the previous releases recorded, and the result has no `document:` line.
- 10.93: `freeze` refuses each of `document: resume`, `document: letter`, `document: Essay` and `document: poem`, exit 2, naming the plan line, and writes no freeze file. A plan frozen with `document: essay` and then changed to `document: cover letter`, or with the line removed, makes the run exit 2 with `changed since the freeze: plan.txt`, and no read runs, as for any other plan edit.
- 10.94: A plan frozen by the previous release, with no `family` and no `drafted-by`, is refused by `run`, exit 2, before any read, with the message that it was frozen under an earlier revision and must be scored with the release that froze it, or rewritten as a new plan. A run folder whose plan was frozen and run by the previous release is refused by `score` with the same message, exit 2, and no result is written.
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

- **Item:** `[<arm> |] <rule> [| <strength>] [| read <k>]`. The arm is `all` (every comparison arm, never the A/A arm or the sensitivity arm), `aa` (the A/A arm), `s` (the sensitivity arm, revision 3), or a comparison written as in `comparisons`. Leaving the arm out means `all`.
- **Rules:**
  - `prefer containing "<S>"`: prefers the slot whose text contains S, and is TIE when both or neither do.
  - `prefer without "<S>"`: prefers the slot whose text does not contain S, and is TIE when both or neither do.
  - `tie`: it takes no strength, and `tie` with a strength is an error.
  - `prefer slot A` and `prefer slot B`.
  - `random seed <n> [non-tie]`: deterministic from the seed, the arm and the read number. The pick comes from the first byte of the sha256 of the text `<seed>:<arm>:<k>`, where the arm is `aa`, `s`, `c1`, `c2` and so on, and `<k>` is the read number. With `non-tie` the pick is A when the byte is even and B when it is odd. Without it the pick is A, B or TIE for a byte mod 3 of 0, 1 or 2. Seeds live in the rule, so different arms may use different seeds.
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
7. **Layout.** Read k of an arm is at `reads/<arm>/<k>/` in the run folder, where `<arm>` is `aa` for the A/A arm, `s` for the sensitivity arm (revision 3), and `c1`, `c2` and so on for the comparisons in plan order. The key file is `key.txt`. A folder holds a reply (sections 3.2 and 10.7) when any `reads/*/*/REPLY.txt` exists. Results name a read as `<arm>/<k>`, for example `c1/3`.

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

## Build interpretations of revision 4 (maintainer, 2026-11-15)

Revision 4 completes signed revision 4 and does not edit it. It restates the build interpretations of revision 3 (points 1 to 17), each as unchanged, amended or dropped, then reads the points the signed text leaves open (points 18 to 41), then restates four statements of revision 1.1 for `ab`, gives an example plan and restates tests 10.40 and 10.41. The build interpretations of revision 1.1 above still apply, except where this section changes them for `ab`; `track-record panel` keeps them as they are. The message strings below are the strings the tool prints, after `plan line <n>: ` where a plan line is named.

### Revision 3's points, restated

1. **No flag beside a reason line (amended).** Section 6.1 says there is no disagreement flag when a verdict is INCONCLUSIVE because of a gate or position. Whenever a hypothesis prints a reason line for the A/A gate, the sensitivity gate, position, the read floor or, from revision 4, the family rule, it gets no flag line, even when its rule alone would also have given INCONCLUSIVE. A lift reason does not suppress the flag: after a lift, the flag is computed on the lifted verdict.
2. **The A/A gate interval (amended).** It is printed whenever the A/A arm has at least one valid read, including when the gate is "not evaluated"; `not computed` means the arm has no valid read. Its share counts every non-TIE A/A read, `slightly` included, over the valid A/A reads, the reads of pooled runs included.
3. **The completions (amended).** Every split of an arm's missing pairs into picks for `X`, picks for `Y` and TIE pairs is tried, and so is every number of the half-read pairs completing as their one valid read allows. With `a` pairs fully missing, `bx` half-read pairs whose valid read picks the first-listed version, `by` whose valid read picks the second and `bt` whose valid read is a TIE, every split of the `a` pairs is tried together with every number from 0 to `bx` of the first kind completing as that pick (the rest TIE) and 0 to `by` of the second, and the `bt` pairs complete as TIE; the completions line says `missing pairs: <m>`, `m` being `a + bx + by + bt`. Only blind readers' missing pairs are completed. Each completion counts every planned pair of blind readers in the arm as valid, which is how a rule's `<n> of <m>` is read there. The p-value range uses the plan's `sidedness`.
4. **Where the lines go (amended).** The `missing` lines (and, for an extension, the `extension pool` lines) and any `DEAD` line follow the per-arm read counts. `A/A pool: …` comes directly before `A/A gate: …`, and `sensitivity gate: …` follows `A/A gate: …` directly, then `sensitivity gate evidence: …` when the gate was evaluated, then the A/A gate interval, then the `A/A slightly rate` line. `position overall: …` is followed by the `order consistency` lines, one per blind reader and paired arm, arms in run order and readers in plan order. For each hypothesis the lines are: the rule (and, for an extension, the rule at the pooled pairs), the pair counts, the verdict, its reason lines (A/A gate, sensitivity gate, position, read floor, then the family rule; after a lift the lift reason is the only reason line), the second reading, the `family` lines, the evidence, the flag, the completions, the `replicate` line and the `extension` line. `document: …`, then `extends: …`, then `replicate of: …` follow `prompt sha256:`. The score ceiling and separation lines follow the A/A score spread; the `sensitivity score gap` lines follow the last of them, then the `reader-group` lines. The validity line is the last line before the result's tail. The arms run in the order `aa`, `s`, `c1`, `c2` and on, and `position overall` includes `s`.
5. **What counts as blind (unchanged, with two lines added).** In sections 6 and 6.1 every count counts blind readers only: valid, failed, not-run and planned reads alike. `DEAD` is the exception: it counts every reader's reads. The key, the per-read rows, the slot split lines, the `not-blind readers` lines and the `reader-group` lines are reporting, and stay unchanged. The two lines revision 4 adds follow the same rule: the A/A slightly rate counts this run's valid blind A/A reads (pooled reads are not in it), and the order consistency lines are printed for blind readers only.
6. **The per-arm count lines (unchanged).** In a plan with a not-blind reader, `reads all readers <arm>: …` prints as `reads blind readers <arm>: …` and counts the blind readers' reads only, the `aa` arm's line included. In a plan without one the lines are unchanged.
7. **Sensitivity reasons (unchanged).** A reason line reads `the sensitivity gate failed: the readers did not detect the planted difference` or `the sensitivity gate was not evaluated`.
8. **The threshold prints reduced (unchanged).** `sensitivity-threshold` prints as `noise-threshold` does, as a reduced fraction: `4/6` prints `2/3`.
9. **The sensitivity pair (unchanged).** "Neither name may appear in a hypothesis" bars `W`, the weakened copy, and no more (`a hypothesis may not name the weakened copy of the sensitivity pair: <name>`); `X` may appear in one. `X` and `W` may appear in `comparisons`. `sensitivity-scope` follows `change-scope`'s item rules, minus the comparison prefix. `sensitivity: base vs base` freezes, and `run` stops before any read with exit `2`.
10. **The sensitivity gate's counts (amended).** The gate's `n` counts the valid sensitivity pairs of blind readers, TIE pairs included, and `not evaluated (<v> valid pairs of <p> planned)` counts pairs. At exactly the threshold the gate passes; only "below" fails.
11. **Score gaps (unchanged).** One `sensitivity score gap` line per blind reader with a valid sensitivity read, in reader order, computed exactly and printed with the mean's `%.2f`; a zero gap prints 0.00, never -0.00.
12. **The lift (amended).** The lift needs a completions line (at least one missing pair) and a settled SUPPORTED or REFUTED. A settled INCONCLUSIVE lifts nothing and prints no lift reason. Its reason line counts missing pairs: `lifted from INCONCLUSIVE: settled under every completion of <m> missing pairs; read floor of <f> pairs met`.
13. **The one-sided flag after a lift (unchanged).** The deciding clause of a lifted verdict is the first clause of the lifted kind, in rule order. This matters only for a rule with two clauses of the same kind that name different versions, under `sidedness` `greater` or `less`, and changes a flag line, never a verdict.
14. **The read floor (amended).** `<v>` counts the arm's valid pairs of blind readers, TIE pairs included, and a `v` equal to the floor is not below it. The floor applies to comparison arms only.
15. **Replicates (unchanged).** `replicate-of` is a path relative to the plan's folder and names a `.freeze` file; the first plan is that name without `.freeze`, in the same folder. The replicate's freeze records the first freeze file as an input, and the replicate's plan, minus its whole `replicate-of` line, must be byte-identical to the first plan. Every refusal exits `2` and names the plan line or the file. `run` and `score` stop with `the first run has not been run yet: …` when the first folder holds no key. Nothing under the first folder is ever written. Known limits, not built: the first run's key is not checked against its run log, and the prompt hash is not compared with the first freeze.
16. **Fisher exact p (unchanged).** The replicate line's p, and the margin of a mechanism (point 30), are two-sided: the sum of the hypergeometric probability of every table with the observed margins whose probability is at most the observed table's, computed exactly with `Fraction` and capped at 1. A side with n = 0 gives 1.0000.
17. **Reader groups (amended).** `reader-group <name>` takes a name of letters, digits and `-`, once per reader, in any order among `not-blind`, `cost` and `family`. There is one line per group, in order of first appearance, counting all readers' valid reads across every arm. A reader's extra field that is none of these stops the plan with `a reader's extra fields may be not-blind, cost <n>, reader-group <name> and family <name>, each at most once: …`.

### Readings of revision 4

18. **How a version names who wrote it.** A version item is `<name> | <file> | drafted-by <who>`. `<who>` is `user`, `third-party`, `unknown`, or one or more `model <family>` joined by `, `. A family is one token of letters, digits and `-`, stored lower-cased, and a family named twice in one list counts once. A version item with two fields gives `a version needs drafted-by (revision 4): <name>`; any other third field, or a fourth, gives `drafted-by is user, third-party, unknown or model <family>, with more models as a comma list: <text>`.
19. **How a reader names its family.** `family <token>` is one more extra field of a reader item, at most once, in any order among the others; the token is letters, digits and `-`, stored lower-cased. A reader without one gives `a reader needs a family (revision 4): <name>`; a bad token gives `a family is one token of letters, digits and -: <text>`. `track-record panel` reads readers as it did, and `family` there is an unknown extra field.
20. **A plan frozen under an earlier revision.** `run` and `score` check the freeze hashes first. When the plan's hash matches and the plan lacks `family` on a reader or `drafted-by` on a version, the only problem printed is `frozen under an earlier revision: <plan file> has no family on a reader or no drafted-by on a version; score it with the release that froze it, or rewrite it as a new plan`, exit `2`, before any read and before any result is written. A plan edited since its freeze is still named as changed and never read.
21. **The read count.** An absent `reads-per-reader` means 6. An odd one is refused at freeze with `reads-per-reader must be an even number, read in pairs (revision 4)`.
22. **Which reads form a pair.** In each arm, a reader's reads in read-number order pair as first and second, third and fourth. `read <k>` in a fake-reader item still counts across the arm.
23. **Units on the lines revision 4 did not name.** The hypothesis counts line is `hypothesis <h> pair counts: valid=<v> <X>=<x> <Y>=<y> tie=<t>` and counts pairs. The position lines say `non-TIE reads in slot A` and count reads. The `reads <who> <arm>: …` lines count reads.
24. **The A/A gate line.** `A/A gate: passed (<s> of <v> valid A/A reads non-TIE, at any strength; threshold <t>)` and `A/A gate: tripped (<s> of <v> valid A/A reads non-TIE, at any strength, <percent>; threshold <t>)`. With `aa-pool`, `<s>` and `<v>` are totals over this run and the pooled runs.
25. **What the second reading is compared with.** The printed verdict, after position, the read floor, the family rule and the lift. The second reading takes every valid `slightly` read as a TIE before pairing, applies the frozen rule to the valid pairs, and is INCONCLUSIVE when a gate is tripped, failed or not evaluated, each by its own definition. Position, the read floor, the family rule and the lift never act on it. It prints for every hypothesis, and an INCONCLUSIVE verdict never carries the sentence `; the verdict holds only when slightly counts as a pick`.
26. **The family lines.** One line per distinct family of the plan's blind readers, in order of first appearance among the readers, printed lower-cased. `<n>` counts that family's valid pairs in the hypothesis's arm, TIE pairs included, and `<k>` those that pick `<Y>`. A family whose readers are all not-blind gets no line.
27. **When the family rule applies, and its share.** The families that wrote the favoured version are the families in its `drafted-by model …` list; the rule applies when a blind reader's family is one of them, and always for `unknown`. The other families are the blind readers' families that are not among them, pooled. The share is the deciding clause's `<n>` over the arm's planned pairs of blind readers, an exact fraction, and the other families agree when at least that share of their valid pairs, taken up to the next whole number, with TIE pairs counted as valid, pick the favoured version. The reasons, in order of precedence, are `no reader of another family`, `too few pairs from another family` (fewer than 3 valid pairs) and `the other family did not agree`. For `unknown` there is one run per blind family, in order of first appearance, each with that family as the only one that wrote it; the first run that fails gives the reason. A version `drafted-by user` or `third-party` never meets the rule.
28. **The family rule and the lift.** A lifted verdict meets the family rule, so the lift can never carry a verdict the rule would stop. Its deciding clause is the one point 13 names, used with its share and the observed valid pairs of the other families. When the check fails the verdict is INCONCLUSIVE, the family reason is the only reason line, and no lift reason is printed.
29. **A rule needing more pairs than the arm plans.** `freeze` does not refuse it, as in revision 3; the README's example plans are checked against their planned pairs by a test.
30. **The mechanism margin and its label.** A mechanism keeps its label, `<pattern> in <arm>`. The margin is the two-sided Fisher exact p-value of the arm's count of valid reads against the A/A floor's count, compared with the plan's `alpha`; the floor never uses reads pooled with `aa-pool`. When either arm has no valid read the line is `… margin: not computed (an arm has no valid read)`. The reason `no margin over the A/A floor` prints when the share separates the versions and the p-value is at or above `alpha`, and it is the first of the mechanism's reason lines. Every mechanism verdict line carries ` (what readers wrote, not a cause)` after `(SUPPORTED at <n> or more)` and before the not-blind suffix.
31. **What a missing read costs.** `missing <arm>: … costing <q> of <P> planned pairs`: `q` counts the planned pairs of blind readers with at least one read missing, failed or not run, and a pair with both reads missing counts once. The A/A line keeps its revision 3 form.
32. **Amending a rule.** The amended plan is the amended freeze's name without `.freeze`, in that freeze's folder; it must exist, match its freeze and read under revision 4, else exit `2` with `the amended plan is missing: …`, `changed since the freeze: …` or `the amended plan cannot be read under revision 4: …`. Hypotheses are matched in order and must have the same comparison and the same clauses (kind, version, form) in the same order; only the counts may differ. A clause's `<n>`, and an `<n> of <m>` clause's `<m>`, must keep the same share over the arm's planned pairs of blind readers, compared as exact fractions, and a mechanism's `supported at <n> or more` the same share over the arm's planned reads of blind readers. Any other difference in a rule, a different number of hypotheses or mechanisms, or a share that gives no whole number at the new read count, is refused naming the rule: `an amendment may restate a rule's counts at the same share, and change nothing else: <h or mechanism pattern>`. A rule written under the amended plan's own read count, unchanged, passes.
33. **Amending a threshold.** The effective values are compared, so `noise-threshold: 1/2` written against an absent one is no change; fractions and `alpha` compare by value. The message is `an amendment may not change <setting> from the plan it amends`.
34. **What an extension may change.** `extends` names a `.freeze` file; the first plan is its name without `.freeze`. Every plan key other than `reads-per-reader`, `readers` and `extends` must be written exactly as in the first plan, `spend-ceiling`, `read-timeout` and `fake-reader` included. A reader's model is everything in its item except its name: command, family, `not-blind`, cost and reader group. The extension's set of models must equal the first plan's, and a reader name both plans use must name the same model. Every input the first freeze recorded must have that hash now. The messages are `an extension may change only reads-per-reader and the number of readers of each model: <setting>`, `changed since the first freeze: <file>`, `the first plan is missing: …`, `extends must name a first run, not an amendment, a replicate or an extension: …`, `extends must name a .freeze file` and, on the `extends` line, `a plan may not carry extends with amends, replicate-of or aa-pool`.
35. **Reading a count rule on an extension's pooled pairs.** A clause's `<n>` and, for `<n> of <m>`, `<m>` are each multiplied by the pooled planned pairs over the first plan's planned pairs, and a mechanism's count by the pooled planned reads over the first plan's. A result that is not whole is refused at freeze: `an extension's pooled pairs give no whole number for <h or mechanism pattern>`. The result prints `hypothesis <h> rule at the pooled pairs: <rule>` after the rule line, and a mechanism verdict line shows the scaled count.
36. **A second extension.** The first folder is never written, so `freeze` reads every freeze file in each folder beside the extension's run folder and refuses when the plan of any of them carries `extends` naming the same first freeze file (same real path): `the first run already has an extension: <folder>`. Known limit: an extension kept anywhere else is not seen, and the scan reads every folder beside the run folder.
37. **What an extension's result pools and prints.** Every arm pools the first run's reads with this run's, blind readers only; pairs are formed within each run, never across them. Planned reads and pairs are the sums. The gates, the rules, the mechanisms, position, order consistency, the completions and the floor read the pooled reads. The key, the per-read rows, the `reads`, `missing` and score lines show this run's reads, and one line per arm, `extension pool <arm>: first run <v1> valid reads of <p1> planned, this run <v2> of <p2>`, follows the `missing` lines. `hypothesis <h> extension: first run <verdict>, pooled <verdict>` gives the first run's verdict as its own result would give it, from its reads alone under its own plan. `run` and `score` stop with `the first run has not been run yet: …` when the first folder holds no key.
38. **Which runs `aa-pool` accepts.** Each item is the path of a `.freeze` file relative to the plan's folder, outside this run's folder, named once (`aa-pool names .freeze files: …`, `aa-pool names <item> twice`, `aa-pool names a run in this folder: …`). Each pooled plan must exist, match its freeze and read under revision 4 (`the pooled plan is missing: …`, `changed since the freeze: …`, `the pooled plan cannot be read under revision 4: …`). Compared by hash: the prompt each freeze recorded, the posting, the A/A version file, and the readers' commands as the ordered list of every reader's command, byte for byte. The refusal is `the pooled run differs in <the prompt, the reader commands, the A/A version file or the posting>: <file>`. A freeze file that does not exist is `missing input: …`. `run` and `score` stop with `the pooled run has not been run yet: …` when a pooled folder holds no key. Only each pooled run's own A/A reads are pooled, never reads it pooled itself.
39. **The pooled gate when a run's A/A arm is incomplete.** The gate is "not evaluated" when this run's A/A arm, or any pooled run's, has fewer valid blind reads than its planned blind reads, and its line counts this run and the pooled runs together. `A/A pool: <r> earlier runs, <v> valid A/A reads in the gate` counts this run's valid A/A reads plus the pooled ones.
40. **Where the checks of a relation between runs are made.** The checks of points 32 to 38 are made by `freeze` before anything is written, and when any of them finds a problem those problems are all that is printed (exit `2`, no freeze file); the checks of the harness itself (a missing input, an existing freeze file, a reply in the folder) follow when none does. They do not change what `run` and `score` verify.
41. **Test 10.62 and the 0.7.0 results.** The four results of the 0.7.0 tests came from three-read plans that revision 4 refuses, so a byte comparison with them cannot hold. Test 10.62 is read as: each of 10.1, 10.8, 10.9 and 10.11, under the revision 4 default plan and with no `sensitivity` key, prints `sensitivity gate: not tested` directly after its `A/A gate:` line, and every verdict line ends in the ` [not blind: <b> reads left out]` form. The four golden files hold revision 4 results of the same four tests. Test 10.32's version case, `odd | my | file.txt`, is refused with the message of point 18, since its third field is now read as the `drafted-by` field.

### Revision 1.1's statements, for `ab`

Four statements of the revision 1.1 section above are not true of `ab` under revision 4. It stays as written because `docs/specs/reader-panel.md` points to it for the panel's own rules. For `ab`:

- `reads-per-reader` is an even number, 2 or more, and defaults to 6.
- `<n> of <m>` holds when the arm has exactly `<m>` valid pairs and at least `<n>` of them pick the version; `<n> or more` holds when at least `<n>` valid pairs pick it.
- A reader item may also carry `family <name>`, and must.
- A version item is `<name> | <file> | drafted-by <who>`.

This example plan, whose texts are invented, freezes under revision 4:

```
posting: posting.txt
versions:
  base | base.txt | drafted-by user
  skills-top | skills-top.txt | drafted-by model m1
comparisons:
  base vs skills-top
readers:
  reader-1 | fake | family m1
  reader-2 | /path/to/my-reader.sh --model small | family m2 | cost 3
hypotheses:
  base vs skills-top | SUPPORTED if skills-top preferred in 6 of 6; REFUTED if base preferred in 4 or more; otherwise INCONCLUSIVE
mechanisms:
  too long | default | supported at 3 or more
change-scope:
  ^(Skills|At a glance)
reads-per-reader: 6
fake-reader:
  aa | prefer slot A | slightly
```

### Tests 10.40 and 10.41 under revision 4

- 10.40: 10.11's plan with one A/A read made to fail (`aa | omit PREFER | read 1`): the gate is "not evaluated", and both the hypothesis and the `too long` mechanism are INCONCLUSIVE, with the mechanism's 8 of 12 count still shown. Exit `1`.
- 10.41: 10.11's plan plus `base vs skills-top | prefer slot B`: position is INCONCLUSIVE and so is the hypothesis, but the `too long` mechanism is still SUPPORTED (8 of 12 against a floor of 0 of 12, margin p = 0.0013).

## Errata (maintainer, 2026-11-17)

**E2. Section 3.2.** The signed text reads: "A reader the extension adds is of a model that already read when it has the same command, byte for byte, the same `family` and the same `not-blind` marking as a reader of the first run; only its name differs."

Correction: add after that sentence: "A reader's name is a label; an extension may name every reader anew."

**E4. Section 9, decision 21.** The signed text ends decision 21 with: "The README gives the effect each read count can detect."

Correction: delete the sentence.

**E5. Build interpretation 29.** The build interpretation reads: "**A rule needing more pairs than the arm plans.** `freeze` does not refuse it, as in revision 3; the README's example plans are checked against their planned pairs by a test."

Correction: "**A rule needing more pairs than the arm plans.** `freeze` does not refuse it, as in revision 3."
