# Reader panel: behaviour spec

Status: accepted.
Date: 2026-11-05.
Revision: 2. The signed spec (sha256 30b42df506ccfe2054bd40aeee2d8fa47b0dc20e3475554bee7f3a913bc1c010) is reproduced below verbatim. Its owner signed it on 2026-11-05, with two amendments applied at its request (the anchor-gate sentence in section 6, and the unanimity sentence in section 6, whose figure is cut). It revises revision 1's signed text (sha256 ac82fffd00acf5929e7001ab2e67b6b0d38705982f2bb7e9c35da25e290e1d54), puts the evidence beside each verdict, and brings its inner status line and section 9 up to the signed state.

## Signed spec

<!-- signed spec begins: sha256 30b42df506ccfe2054bd40aeee2d8fa47b0dc20e3475554bee7f3a913bc1c010 -->
# Reader panel: behaviour spec

Status: revision 2, drafted on 2026-11-05 for the owner's signature. Revision 1 is draft 0.2 as its owner signed it on 2026-11-05, which settled every decision in § 9.
Date: 2026-11-05.
Revision: 2. Puts the evidence beside each verdict (sections 3.1, 5.5, 6, 7, 8, 9 and 10). Every verdict is decided as in revision 1; nothing in revision 2 changes a verdict, an exit status or the prompt. Revision 0.2: Draft 1, amended after review (the lens owns its scale; freeze rejects an unreachable pass bar; the `none` sentence is frozen). A revision below 1 is a draft; revision 1 is the spec the owner signs, reproduced verbatim with its hash, as docs/specs/reader-ab.md is.

The command is `track-record panel`.

Every example in this file and in the tool's fixtures is invented. None of it comes from a real person's résumés, postings, employers, prompts or results.

## 1. Purpose

Read one version of a career document through several named lenses, each a model reader in a stated role such as recruiter, hiring manager or peer, and report whether it passes a condition written before the first read, without letting the person running the test move the goalposts after seeing the answer, and without counting a lens that cannot tell a strong document from a weak one.

`track-record ab` compares two versions and asks which reads better. This command is the single-version cold read that docs/specs/reader-ab.md § 2 lists as out of scope and § 9.4 plans. It follows rule 6 of the method ("Test before you trust"): every lens carries its own control, so a lens that shows nothing also shows whether it was able to see something.

## 2. Scope

In scope:

- blind reads: a reader in a given role sees one posting, one lens file and one document, and scores the document alone;
- lenses: each is a plain-text prompt file the user writes, named in the plan and frozen with it;
- the anchored rubric: two planted documents the user supplies, a deliberately strong one and a deliberately weak one, read through every lens in every run;
- the anchor gate: a lens that does not put the strong anchor at or above one threshold and the weak anchor at or below another has its reads of the version reported INCONCLUSIVE and not counted;
- preregistration: the pass conditions, per lens and overall, frozen by hash before the first read;
- scoring the replies against the frozen rules, and writing a result;
- the evidence beside each verdict: an interval for each clause count, an exact p-value when a rule names a share to test against, the reads that are missing, and what the scores can and cannot show (§ 6.1).

Out of scope:

- writing or rewriting copy (readers may suggest rewrites; the tool never applies one);
- deciding what is true (a reader's doubt is a lead; the user's own record decides);
- comparing two versions (that is `ab`);
- recall tests (which of several versions a reader remembers), version ledgers, and any change to `claims`, `barred`, `tone` or `keywords`;
- supplying anchors: the tool ships invented anchors as test fixtures only, and a user writes their own, for their own posting;
- any network call from the test suite.

## 3. Inputs

### 3.1 The plan file

The plan is a plain-text file in the syntax of `ab` (reader-ab.md § 3.1 and its build interpretations): each line is `key: value`; a list value is one item per indented line under its key, with fields separated by ` | `; blank lines and lines starting with `#` are ignored; an unknown key, a repeated key or a field that holds ` | ` is an error (exit `2`). The plan names:

- `posting`: the posting file;
- `version`: the one document under test;
- `anchors`: two items, `strong | <file>` and `weak | <file>`, each exactly once;
- `lenses`: each lens's name and its prompt file (§ 3.3), `<name> | <file>`, and optionally `max <n>`, the top of the lens's own scale, a whole number at or above `anchor-strong-at-least` (§ 6.1). Names are letters, digits and `-`, unique, and not one of the words `all`, `overall`, `strong`, `weak` or `version`. The result names lenses `l1`, `l2` and so on in plan order;
- `readers`: each reader's name and command, and optionally `not-blind` and `cost <n>`, exactly as in `ab` (§ 5.1, § 5.5);
- `reads-per-reader`: reads of the version per lens for each reader (default 3);
- `anchor-reads-per-reader`: reads of each anchor per lens for each reader (default 1);
- `anchor-strong-at-least` and `anchor-weak-at-most`: the gate's thresholds, whole numbers of any sign, both required, with the first greater than the second (§ 6);
- `rules`: each a pass condition for one lens or for the panel, `<lens> | <rule>` or `overall | <rule>`, in the clause language of § 6, and optionally `| null-share <n>/<d>`, the share of reads expected to pass each of its tests by chance, strictly between 0 and 1 and written as a fraction in no other form (§ 6.1). For example, `recruiter | PASS if score at least 7 in 5 of 6; FAIL if score at most 4 in 2 or more; otherwise INCONCLUSIVE`;
- `sidedness` (optional): `two`, `greater` or `less`, the side of the exact test against a rule's `null-share` (default `two`);
- `spend-ceiling`: the run's limit, in the plan's one spend unit (absent means no ceiling);
- `read-timeout`: seconds per live read (default 600);
- `fake-reader` (optional): the fake reader's rules (§ 5.3);
- `amends` (optional): the freeze file of the plan this one replaces (§ 3.2).

### 3.2 Freeze

`track-record panel freeze PLAN` hashes the plan and every input it names (sha256): the posting, the version, both anchors, every lens file and any amended freeze, plus the built-in prompt. It writes the hashes to a freeze file beside the plan and exits `0`. The rules of reader-ab.md § 3.2 hold unchanged: it refuses (exit `2`) a missing input, an existing freeze file or a run folder that already holds a reply; a run checks every hash first and exits `2`, naming the file, if any one differs, the plan and the lens files included; the run folder is the folder that holds the plan; an amendment is a new plan in a new run folder whose `amends` names the earlier freeze file, and the earlier folder is never edited.

### 3.3 Documents and lens files

The posting, the version and the anchors are UTF-8 text, or PDF read through the same text extraction the barred check uses. A lens file is UTF-8 text that is not blank. It is given to the reader as it is, as `LENS.txt`; the tool reads nothing into it and substitutes nothing in it. File names are free. **The lens owns its scale.** A lens may define its own scale and criteria, for example five criteria each scored 0 to 2 and summed to 0 to 10; the plan's thresholds and rules are written on that scale. The tool fixes no scale: any whole number is a valid `SCORE` (§ 5.4), 0 included.

## 4. Documents and the document check

### 4.1 What a reader sees

Each read is of one document. Within a lens, reads are numbered in the order they run: every reader's reads of the strong anchor, then of the weak anchor, then of the version. The reader sees `DOCUMENT.txt`, never the document's name or role: nothing in its folder says whether it is reading an anchor or the version. The key file, written before any read runs, maps each read to its document.

### 4.2 The document check (before any read)

The three documents are compared line by line after collapsing runs of spaces and dropping blank lines, as in reader-ab.md § 4.2. If any two of them show no changed line, the run stops before reading and exits `2`, naming the pair, because a gate between two copies of one text can tell nothing. A lens file that cannot be read, or is blank, stops the run the same way.

## 5. Readers

### 5.1 Pluggable

As in `ab`: a reader is a command the tool runs once per read; the read folder is its only input and one reply file is its output. The tool ships one reader that needs no network, the fake reader (§ 5.3). Live readers are configured by the user and are never shipped with credentials.

### 5.2 Live runs and run order

The test suite and CI never start a live reader. The `--live` rule of reader-ab.md § 5.2 holds unchanged: for a live run the tool prints the exact commands and the spend estimate, runs them only when the user types `--live`, and without it prints, starts nothing, writes no reply and exits `0`. A plan with any live reader and no `--live` runs nothing, fake reads included; a plan whose readers are all `fake` never needs `--live`.

Lenses run in plan order. Within a lens the anchors run first, strong then weak, and the version last, so that a run cut by the spend ceiling keeps its gate. The ceiling stops the run between reads once the tally of declared costs reaches it; reads already returned are kept, and the result says the run was cut.

### 5.3 The fake reader

The fake reader is a deterministic program for tests, run inside the tool, that applies to every reader whose command is the word `fake`. Its rules are `fake-reader` items, `[<lens> |] [<document> |] <rule> [| read <k>]`, where `<lens>` is a lens name or `all`, `<document>` is `strong`, `weak`, `version` or `all`, and leaving either out means every one. The rules are:

- `score <n>`: the reply's score;
- `score containing "<S>" <n>`: the score, only when the document's text contains S. This lets a test rank the anchors blind, by their text, and not by the key;
- `write "<S>" in <FIELD>`, where FIELD is any reply field;
- `omit <FIELD>`.

The score is 5 unless a score rule fires; when several fire, the last in plan order wins. `PRIOR` is `nothing` unless written. Every free-text field is `none` unless written. `read <k>` makes an item apply only to read k of its lens, numbered as in § 4.1. Each fake read costs 1 spend unit, and a `cost` on a fake reader is ignored.

### 5.4 Reply format

Each reply starts with `READ: <read id>` and carries these fields, one per line or block, in the same form as reader-ab.md § 5.4 and its build interpretations (a field starts a line as `FIELD: value`, case-sensitive, and runs to the next field; text before the first field is ignored; a field that appears twice is a failed read):

- `PRIOR`;
- `SCORE`: one integer, of any size and sign, on the scale the lens gives (§ 3.3);
- `STRENGTHS`, `DOUBTS`, `UNDERSOLD`, `OVEREXPLAINED`, `OWNED` and `FLAG-FIXES`, the free-text fields.

The built-in `PROMPT.txt` fixes only this envelope: the `READ`, `PRIOR` and `SCORE` fields and the free-text fields. It states no scale. It tells the reader, for each free-text field, "write exactly `none` if you have nothing material"; that sentence is part of the frozen prompt, so it is covered by the prompt's hash like the rest of the text, and a field that says anything but `none` is flagged (below).

A reply missing `READ` or `SCORE`, or whose `SCORE` is not an integer, is a failed read. Failed reads are counted and reported, never guessed. A free-text field is **flagged** when it is present and its value, trimmed, is anything but exactly `none`. A missing or empty field is not flagged.

### 5.5 Blindness

As in reader-ab.md § 5.5: the prompt tells the reader that it knows nothing about the candidate, any `PRIOR` other than `nothing` is flagged on that read, and a reader marked `not-blind` has its reads of the version reported separately as well as together with the others. The clause language of § 6 tests a score or a flagged field over a lens's reads and cannot select reads by reader, so there is no rule for keeping not-blind readers out of `overall` in draft 1; leave not-blind readers out of the plan. Every verdict line says how many of the reads behind it came from a reader marked `not-blind` (§ 6.1).

## 6. Scoring

Scoring reads only the replies, the key and the frozen plan. Failed reads are left out of every denominator below. A rule that needs N of N valid reads is INCONCLUSIVE when the count of valid reads is not exactly N.

- **The anchor gate**, per lens. It is evaluated only when every planned anchor read of the lens is valid; otherwise it is "not evaluated". It passes when every valid read of the strong anchor scores at or above `anchor-strong-at-least` and every valid read of the weak anchor scores at or below `anchor-weak-at-most`; one read on the wrong side fails it, and the result names each such read with its score. The anchors check that a lens can tell strong from weak; a passed gate doesn't show it could see this version's difference.
- **Counted lenses.** A lens whose gate passed is counted. A lens whose gate failed or was not evaluated is not counted: every rule on it is INCONCLUSIVE with that reason, and its reads of the version are shown but not counted anywhere. One lens's gate voids that lens only.
- **Rules.** A rule's clauses are `PASS if <test> in <k> of <m>`, `PASS if <test> in <k> or more`, and the same with `FAIL`, separated by `; `, ending with `otherwise INCONCLUSIVE`. A test is `score at least <n>`, `score at most <n>`, `<FIELD> flagged` or `<FIELD> not flagged`, where FIELD is a free-text field. A rule on a lens counts that lens's valid reads of the version; an `overall` rule counts the valid reads of the version across every counted lens, and is INCONCLUSIVE when no lens is counted. `<k> of <m>` holds when exactly `<m>` reads are counted and at least `<k>` of them pass the test; `<k> or more` holds when at least `<k>` pass it, however many are counted. Clauses are tried in order, and the first that holds decides. A version cannot be required to beat a score the gate did not show the lens can give: `freeze` rejects (exit `2`, naming the plan line) any `PASS` clause `score at least <n>` where `<n>` is greater than `anchor-strong-at-least`. A `<n>` equal to or below it is accepted, as is any `FAIL` clause. Prefer `<k> of <m>` with slack to unanimity: a unanimity rule (`6 of 6`) fails on one stray read, so it is brittle. The result names rules `r1`, `r2` and so on in plan order, and shows each clause's count.
- **Scores** are reported per lens for each document, and for the version per reader as well, with the lowest and highest beside the mean.
- **Flags.** For each lens and free-text field, the result reports how many valid reads of the version flagged it.

### 6.1 Evidence beside the verdicts

Nothing in this section changes a verdict. Each line is reported beside the verdicts above, which come from the frozen rules alone (§ 8).

- **Interval.** For each clause of each rule, `n` is the number of reads the rule counts and `k` the number that pass the clause's test. The result gives the 95% Wilson score interval for `k/n`, with z = 1.959964. When `n` is 0, no interval is computed, and the line says so.
- **Against a declared share.** When a rule names a `null-share` q, each clause also gets an exact p-value from the binomial distribution with `n` trials and chance q: under `greater`, the chance of `k` or more; under `less`, of `k` or fewer; under `two`, twice the smaller of the two, and at most 1. Without a `null-share`, no p-value is printed: a single version has no natural share to test against.
- **Missing reads.** For each lens, the result counts the planned reads of the version that are missing: failed, and not run. For each rule with missing reads among the reads it would count, the rule is evaluated again under every completion of those reads, each missing read taking any score and any set of flagged fields, as if every planned read of the version were valid. The result says whether one verdict holds under every completion (settled) or which verdicts are possible (unsettled). Missing anchor reads are not completed: the gate stays "not evaluated", and a lens that is not counted adds no reads to complete. This never changes the verdict.
- **A dead run.** When no read in the run is valid, the result says so in one line. The exit status is `1`, as for any run with a failed read (§ 7).
- **The top of the scale.** For each lens, the result gives the version's lowest valid score beside the strong anchor's highest valid score, and the version's spread (highest minus lowest). When the version's lowest score is at or above the strong anchor's highest, the lens cannot rank the version above the strong anchor, and the result says so. When every valid read gives the version the same score, the result says so. When the lens names `max`, the result gives the room between the strong anchor's highest score and that maximum.
- **Not-blind reads.** Each rule's verdict line ends with the number of the reads it counts that came from a reader marked `not-blind` (§ 5.5).
- **What the reads stand for.** Every result carries one validity line: the readers are models standing in for human screeners, that stand-in has not been checked against human ratings, and reads from one model and prompt may not be independent, so each p-value assumes independence and may be too small. Each p-value carries a short form of the same caveat on the same line.

#### Printed forms

`<rule>` is the rule's name (`r1`, `r2` and so on), `<arm>` is the lens's arm (`l1`, `l2` and so on), and `<test>` is the clause's test as written. A p-value is printed rounded half up to 4 decimal places, or as `< 0.0001` when it rounds to 0. An interval's lower end is rounded down and its upper end rounded up, to 3 decimal places. `<side>` is `two-sided`, `one-sided greater` or `one-sided less`.

- `rule <rule> evidence: <test>: <k> of <n> counted reads; 95% interval <lo> to <hi>`, one line per clause, or `... <k> of <n> counted reads; interval not computed` when `n` is 0.
- With a `null-share` q, written as the plan wrote it, the same line gains, before the interval: `; p = <p> <side> against <q> (reads may be correlated; may be too small)`.
- `missing <arm> version: <m> of <planned> planned reads (failed <f>, not run <r>)`, one line per lens.
- `rule <rule> completions (missing reads: <m>): settled: <verdict>`, or `... unsettled: <verdicts> possible`, in the order PASS, FAIL, INCONCLUSIVE, separated by `, `. A rule with no missing read among those it would count gets no completions line.
- `DEAD: 0 of <N> planned reads are valid`, where `N` counts every planned read of every lens.
- `scores <arm> version against strong anchor: lowest version score <a>, highest strong-anchor score <b>`, or `... not assessable` when either has no valid read.
- `scores <arm> version spread: <s> (highest <h>, lowest <l>)`, or `scores <arm> version spread: not assessable` with no valid read of the version.
- When `a` is at or above `b`: `scores <arm>: the version scores at or above the strong anchor; this lens cannot rank it higher`.
- When the version has two or more valid reads and its spread is 0: `scores <arm>: every read gives the version the same score`.
- When the lens names `max`: `scores <arm> room above the strong anchor: <max minus b> (scale maximum <max>)`.
- Every rule verdict line ends with ` [not blind: <b> of <v> counted reads]`.
- `validity: the readers are models standing in for human screeners, and that stand-in has not been checked against human ratings. Reads from one model and prompt may not be independent, so each p-value assumes independence and may be too small.`

## 7. Output and exit status

`track-record panel score` writes a result file containing:

- the plan and freeze hashes, any amendment's, the prompt hash, and each lens's name, file and hash;
- the version, the anchors and the thresholds;
- the key;
- one row per read: reader, document, score, flagged fields and flags;
- per lens: its read counts, its anchor gate with the scores or the reads that failed it, whether it is counted, its scores and its flag counts;
- the counted lenses;
- each rule, with its clause counts, its verdict and any reason;
- the spend tally, failed reads and any cut;
- the evidence lines of § 6.1: each clause's interval and any p-value, the missing reads per lens and each rule's completions, the score lines per lens, any `DEAD` line, and the validity line.

Every run writes a new result; an earlier result is never overwritten.

Exit status, as in `ab`:

- `0`: the run completed and was scored, whatever the verdicts, or it was a print without `--live`.
- `1`: the run completed, but at least one read failed or the run was cut.
- `2`: the run could not run: a hash mismatch, a failed document check, a missing input, a freeze over an existing freeze or run, a plan error, or a run that stopped early.

When causes combine, the higher code wins.

## 8. Rules that hold in every run

- No read before a freeze, and no plan or lens edit after one.
- Every lens reads both anchors in every run, before it reads the version.
- The document check runs before any read.
- A reader never learns which document it is reading.
- Verdicts come from the frozen rules only. The tool has no option to change a rule, a threshold or a lens at scoring time.
- The evidence of § 6.1 sits beside the verdicts and never changes one.
- A reader's suggested rewrite is reported as text and applied to nothing.

## 9. Decisions

Decisions 1 to 10 were settled as written when the owner signed revision 1 on 2026-11-05; each "Default" below is the settled choice. Decisions 11 to 13 were settled on 2026-11-05 for revision 2.

1. **Command name.** Default: `track-record panel`, with `freeze`, `run` and `score`, as `ab` has.
2. **How a lens is defined.** Default: a plain-text prompt file per lens, named in the plan, its sha256 frozen with the plan, handed to the reader unchanged as `LENS.txt` beside the built-in `PROMPT.txt`. Alternative considered: lens text written inline in the plan. The file keeps a lens reusable across plans and keeps the plan short.
3. **The anchor thresholds.** Default: two required plan fields, `anchor-strong-at-least` and `anchor-weak-at-most`, whole numbers with the first greater than the second. Every valid anchor read must land on its side; the mean is not used, because a mean can hide one read that got an anchor backwards.
4. **One failed anchor voids what.** Default: that lens only. The other lenses keep their own gates and verdicts; an overall rule counts only counted lenses.
5. **How a pass condition is written.** Default: per-lens and overall rules in `ab`'s clause language, with `PASS` and `FAIL` in place of `SUPPORTED` and `REFUTED`, over scores and flagged fields (§ 6). Alternative considered: keeping `SUPPORTED` and `REFUTED`; `PASS` and `FAIL` were chosen because a single version has a pass condition, not a hypothesis about a difference.
6. **Anchor read counts.** Default: `anchor-reads-per-reader` is its own field, default 1, so that anchors cost one read per reader per lens while the version keeps `reads-per-reader` (default 3).
7. **Read order within a lens.** Default: strong anchor, weak anchor, then the version, each reader in turn, so that a cut by the spend ceiling leaves the gate evaluable.
8. **What "flagged" means.** Default: a free-text field is flagged when it says anything but exactly `none`; a missing or empty field is not flagged. No pattern matching over fields in draft 1 (the `mechanisms` of `ab` could be added later as a rule test).
9. **Reserved lens names.** Default: `all`, `overall`, `strong`, `weak` and `version` may not name a lens, because the plan's `rules` and `fake-reader` items use them.
10. **Not-blind readers.** Default: reported as in `ab`, flagged on each read and counted separately on the version; the gate does not treat them apart. No rule can leave them out of `overall` in draft 1 (§ 5.5).
11. **Evidence.** Each clause count gets a Wilson interval. A rule may name a `null-share` at freeze, and then each clause gets an exact p-value against it; without one, no p-value is printed.
12. **Missing reads and the top of the scale.** The completions are reported only; they lift no INCONCLUSIVE. A dead run keeps exit `1` and gains the `DEAD` line. The score lines report a version at or above the strong anchor, a version with no spread, and, when a lens names its maximum, the room above the strong anchor.
13. **Not-blind reads** still count in revision 2, and every verdict line says how many there are.

## 10. Acceptance tests (known answers)

Every test uses the fake reader, except those that name a local stub script, as reader-ab.md's build interpretations read "live" for 10.13 and 10.35 to 10.37. The fixtures are invented: the version and posting are `ab`'s (`base.txt`, an invented résumé at invented companies, and its posting); a strong anchor, a résumé for a second invented engineer that meets the posting plainly with numbers and named systems; a weak anchor, a résumé of adjectives and vague duties; and two lens files, a recruiter and a hiring manager.

Unless a test says otherwise, the plan has two lenses (`recruiter`, `manager`), two fake readers with 3 version reads and 1 anchor read each, and thresholds 7 and 4. A lens then has 10 reads: 1 to 4 on the anchors, 5 to 10 on the version. "The control lenses" are fake rules that score the strong anchor 9 (or 8), the weak anchor 2 (or 3) and the version 7 through both lenses. Each test below maps to a named test in `tests/test_panel.py`.

- 10.1: The control lenses pass their gates, are counted, and the rule `PASS if score at least 7 in 6 of 6; FAIL if score at most 4 in 2 or more` on the recruiter is PASS. Exit 0. (`test_10_1_a_lens_that_ranks_the_anchors_is_counted_and_its_rule_passes`)
- 10.2: The manager lens scores every document 5. Its gate fails, naming its four anchor reads; its reads of the version are reported INCONCLUSIVE and not counted. The recruiter lens in the same run is counted and its rule is PASS. (`test_10_2_a_flat_lens_is_inconclusive_and_the_control_lens_is_counted`)
- 10.3: A lens that scores the strong anchor 2 and the weak anchor 9 fails its gate, naming every anchor read. (`test_10_3_a_lens_that_ranks_the_anchors_backwards_fails_the_gate`)
- 10.4: One anchor read made to fail (`manager | omit SCORE | read 1`) leaves the manager gate "not evaluated" and the lens not counted; the recruiter is unaffected. Exit 1. (`test_10_4_a_failed_anchor_read_leaves_the_gate_not_evaluated`)
- 10.5: With both lenses counted, `overall | PASS if score at least 7 in 12 of 12` is PASS. With the manager voided, the same rule counts 6 of 6 and is INCONCLUSIVE, while `6 or more` is PASS. (`test_10_5_overall_rules_count_only_counted_lenses`)
- 10.6: With no lens counted, an overall rule is INCONCLUSIVE with the reason "no lens is counted". (`test_10_6_no_counted_lens_makes_overall_rules_inconclusive`)
- 10.7: `write "too long" in DOUBTS` on 4 of the recruiter's 6 version reads makes `FAIL if DOUBTS flagged in 3 or more` FAIL; a field written `none` is not flagged. (`test_10_7_a_flagged_field_rule_counts_fields_that_say_more_than_none`)
- 10.8: A read folder holds exactly `DOCUMENT.txt`, `LENS.txt`, `POSTING.txt` and `PROMPT.txt` (and the reply); `DOCUMENT.txt` is the anchor or version the key names, and the key has 20 rows in run order. (`test_10_8_a_read_folder_holds_the_document_posting_lens_and_prompt`)
- 10.9: The freeze holds one hash per input, lens files included, and the prompt's; a lens file edited after the freeze makes the run exit 2, naming it, with nothing written. (`test_10_9_freeze_hashes_every_input_and_a_changed_lens_stops_the_run`)
- 10.10: Two anchors that are the same file, or a version that differs from an anchor only in spaces and blank lines, stop the run before any read, exit 2, naming the pair. (`test_10_10_documents_that_do_not_differ_stop_the_run_before_reading`)
- 10.11: With a live reader configured and `--live` absent, the tool prints the commands and the spend estimate, never executes the stub, writes no reply and exits 0. (`test_10_11_live_reader_without_live_flag_only_prints`)
- 10.12: A spend ceiling of 6 cuts the run after the recruiter's anchors and two version reads: its gate is evaluated, its rule INCONCLUSIVE (2 valid reads), the manager's gate is not evaluated, and the result says the run was cut. Exit 1. (`test_10_12_the_spend_ceiling_cuts_between_reads_after_the_anchors`)
- 10.13: Every plan error is found by `freeze`, which names the plan line and writes no freeze file: thresholds that are not whole numbers or not in order, a third anchor, a reserved or repeated lens name, a rule on an unknown lens, a clause in another language, `k of m` with k above m, a field a rule cannot test, a fake rule with a field it cannot name, a read outside the lens's reads, and fake rules with no fake reader. (`test_10_13_every_plan_error_is_found_by_freeze_with_its_line`)
- 10.14: Scoring twice writes two result files, and the first is unchanged. (`test_10_14_scoring_twice_keeps_the_first_result`)
- 10.15: `score containing "<S>" <n>` scores by the document's text, so a fake rule can rank the anchors without the key; a text in no document leaves the score at 5. (`test_10_15_the_fake_reader_can_score_by_the_document_text`)
- 10.16: A reply's `READ` value is not checked; a missing or non-integer `SCORE` is a failed read; a free-text field is flagged unless it is exactly `none`, absent or empty. (`test_10_16_a_good_reply`, `test_10_16_the_read_value_is_not_checked`, `test_10_16_a_missing_or_non_integer_score_is_a_failed_read`, `test_10_16_a_field_is_flagged_unless_it_is_none_or_absent`)
- 10.17: A stub that lists its working folder sees exactly the four files, and the sha256 of `LENS.txt` equals the lens file's in the freeze; a stub that exits nonzero gives a failed read on each of its reads, reported with the status, so the gate is not evaluated. (`test_10_17_a_live_stub_sees_four_files_and_the_frozen_lens`, `test_10_17_a_stub_that_exits_nonzero_is_a_failed_read`)
- 10.18: With one reader, `reads-per-reader: 2` and `anchor-reads-per-reader: 2`, a lens has 6 reads in the order strong, strong, weak, weak, version, version. (`test_10_18_read_counts_follow_the_plan`)
- 10.19: An amendment is frozen and scored; its result names both freezes, and the first run folder stays byte-identical. (`test_10_19_an_amendment_names_both_freezes`)
- 10.20: `-h` and `--help` at `panel` and at each subcommand print fixed text and exit 0; a missing or unknown subcommand, a missing PLAN or an unknown option exits 2 with one line. (`test_10_20_help_at_panel_and_at_each_subcommand`, `test_10_20_usage_errors_exit_2_with_one_line_and_no_output`)
- 10.21: A reader marked `not-blind` has its reads flagged and its version reads counted separately as well as together. (`test_10_21_not_blind_reads_are_flagged_and_counted_separately`)
- 10.22: When two clauses hold, the first in the rule decides. (`test_10_22_the_first_clause_that_holds_decides`)
- 10.23: The fake reader starts no program. (`test_10_23_the_fake_reader_starts_no_program`)
- 10.24: A second `run` in a folder that holds a run is refused, and `run` and `score` without a freeze exit 2. (`test_10_24_a_second_run_is_refused_and_a_run_needs_a_freeze`)
- 10.25: The example plan below is read as written. (`test_10_25_the_example_of_the_spec_is_read_as_written`)
- 10.26: A lens whose file defines a 0 to 10 scale is gated and scored on it, and a score of 0 is accepted; the built-in prompt states no scale. (`test_the_lens_owns_its_scale`, `test_the_built_in_prompt_fixes_no_scale`)
- 10.27: `freeze` refuses a `PASS` clause `score at least <n>` with `<n>` above `anchor-strong-at-least`, naming the plan line; equal and below are accepted. (`test_a_pass_bar_above_the_strong_threshold_is_refused_by_freeze`)
- 10.28: The frozen prompt holds the sentence "write exactly `none` if you have nothing material" once per free-text field. (`test_the_frozen_prompt_tells_each_free_text_field_to_write_none`)

Tests 10.29 to 10.38 are new in revision 2. They use the defaults above and the control lenses unless they say otherwise.

- 10.29: 10.1's rule on the recruiter gives `rule r1 evidence: score at least 7: 6 of 6 counted reads; 95% interval 0.609 to 1.000` and `rule r1 evidence: score at most 4: 0 of 6 counted reads; 95% interval 0.000 to 0.391`, no p-value, and the verdict line `rule r1 verdict: PASS [not blind: 0 of 6 counted reads]`.
- 10.30: The same rule with `| null-share 1/2` prints `; p = 0.0313 two-sided against 1/2 (reads may be correlated; may be too small)` on both clause lines. With `| null-share 3/4` the first clause prints `p = 0.3560 two-sided against 3/4` and the second `p = 0.0005 two-sided against 3/4`. With `sidedness: greater` and `null-share 1/2`, the first clause prints `p = 0.0156 one-sided greater against 1/2`. The verdict is PASS in every case.
- 10.31: With the control lenses scoring the strong anchor 9 through both lenses (10.32 assumes the same), each lens has `scores <arm> version against strong anchor: lowest version score 7, highest strong-anchor score 9`, `scores <arm> version spread: 0 (highest 7, lowest 7)` and `scores <arm>: every read gives the version the same score`, and no "at or above the strong anchor" line. With `version | score 9` in place of 7, each lens also has `scores <arm>: the version scores at or above the strong anchor; this lens cannot rank it higher`.
- 10.32: `recruiter | recruiter.lens.txt | max 10` gives `scores l1 room above the strong anchor: 1 (scale maximum 10)`, and the manager lens has no such line. `max 6` (below `anchor-strong-at-least`, 7) is refused by `freeze`, naming the plan line.
- 10.33: `recruiter | version | omit SCORE | read 5` leaves the recruiter 5 valid reads of the version, so 10.1's rule is INCONCLUSIVE. The result has `missing l1 version: 1 of 6 planned reads (failed 1, not run 0)`, `missing l2 version: 0 of 6 planned reads (failed 0, not run 0)` and `rule r1 completions (missing reads: 1): unsettled: PASS, INCONCLUSIVE possible`. Exit 1.
- 10.34: `omit SCORE` on every read makes every read fail: `DEAD: 0 of 20 planned reads are valid`, both gates "not evaluated", every rule INCONCLUSIVE, exit 1.
- 10.35: With reader-2 marked `not-blind`, the recruiter rule's verdict line ends ` [not blind: 3 of 6 counted reads]`, and `overall | PASS if score at least 7 in 12 of 12` ends ` [not blind: 6 of 12 counted reads]`.
- 10.36: Every result has exactly one validity line, with the text in § 6.1, including those of 10.2 and 10.34.
- 10.37: `freeze` refuses each of `null-share 0/4`, `null-share 4/4`, `null-share 0.5`, `max x`, `max 7.5` and `sidedness: both`, naming the plan line, and writes no freeze file.
- 10.38: Revision 2 changes no prompt: the built-in prompt's sha256 equals the one the previous release recorded, so a plan frozen before revision 2 without the new fields still runs.

## Build notes (draft 1)

### The plan file

This example is invented:

```
posting: posting.txt
version: resume.txt
anchors:
  strong | anchor-strong.txt
  weak | anchor-weak.txt
lenses:
  recruiter | recruiter.lens.txt
  hiring-manager | hiring-manager.lens.txt
readers:
  reader-1 | fake
  reader-2 | /path/to/my-reader.sh --model small | not-blind | cost 3
reads-per-reader: 3
anchor-reads-per-reader: 1
anchor-strong-at-least: 7
anchor-weak-at-most: 4
rules:
  recruiter | PASS if score at least 7 in 5 of 6; FAIL if score at most 4 in 2 or more; otherwise INCONCLUSIVE
  hiring-manager | FAIL if DOUBTS flagged in 3 or more; PASS if score at least 7 in 5 of 6; otherwise INCONCLUSIVE
  overall | PASS if score at least 7 in 10 or more; otherwise INCONCLUSIVE
spend-ceiling: 40
fake-reader:
  strong | score 9
  weak | score 2
  version | score 7
  hiring-manager | version | write "no numbers" in DOUBTS | read 5
```

- **Readers, scalars and paths** follow reader-ab.md's build interpretations: `cost`, `spend-ceiling` and `read-timeout` are whole numbers, 0 or more; `reads-per-reader` and `anchor-reads-per-reader` are 1 or more; a live command is split by POSIX shell-word rules and its program is an absolute path or a name on `PATH`; file paths are relative to the plan's folder.
- **Rules** always start with their lens or `overall`, even with one lens.
- **Where errors are found.** Every plan error is found by `freeze`, which names the plan line number where there is one and writes no freeze file. `run` re-checks the hashes, compares the built-in prompt's sha256 with the frozen one, and runs the document check, before any read.
- **One run to a folder, the run log, the key's hash, errors on files in the run folder, a stopped run, an interrupt and escaped output** all follow reader-ab.md's build interpretations and other rulings, unchanged. The key file has three tab-separated fields: the read id, the reader and the document.

### Live readers

As in reader-ab.md's build interpretations, with the read folder holding exactly `DOCUMENT.txt`, `LENS.txt`, `POSTING.txt` and `PROMPT.txt` when the command starts. Read k of a lens is at `reads/<arm>/<k>/`, where `<arm>` is `l1`, `l2` and so on. Results name a read as `<arm>/<k>`, for example `l2/5`. The prompt is built into the tool and fixed per tool version; it is not the `ab` prompt, and its sha256 goes into the freeze file and the result.

### Known limits

- The known limits of `ab`'s live readers hold here: a reader's standard output and standard error are held in memory with no size limit, and a timeout stops the reader's own process only.
- A lens is handed to the reader as text. Whether the reader takes the role is up to the reader; the gate measures only whether it ranked the anchors.
- Two anchors fix two points on a scale. A lens that ranks them correctly can still be wrong about the version; the gate rules out a lens that cannot see, not one that sees badly. More anchors, or anchors closer to the version, are a change for a later revision.
- Set the strong threshold at or above the score the version must reach.
- The ceiling stops reads once the tally reaches it, so one costly read can overshoot it, the same as in `ab`.
<!-- signed spec ends -->
