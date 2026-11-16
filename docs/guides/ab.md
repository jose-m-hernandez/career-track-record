# `track-record ab`

Compare two versions of a résumé, or any career document, by asking test readers which reads better. A reader is a command you name, such as one that calls a language model, or the built-in `fake`, which tests a plan. You write a plan first: the posting, the versions, where they may differ and what counts as a win. The tool hashes the plan and every file it names, and a run refuses anything that has changed since, so the rules can't quietly move after you see the answer. Every run also reads one version against itself, as a control, so you can see how often a reader picks a side when there is no difference. Each reader reads every pair of versions in both orders, and a pick counts only when both orders agree. Each comparison ends SUPPORTED, REFUTED or INCONCLUSIVE, by the rule you wrote. This plan is invented:

```
posting: posting.txt
versions:
  base | resume-base.txt | drafted-by user
  skills-top | resume-skills-top.txt | drafted-by user
comparisons:
  base vs skills-top
readers:
  reader-1 | fake | family m1
  reader-2 | /path/to/my-reader.sh | cost 3 | family m2
reads-per-reader: 6
hypotheses:
  SUPPORTED if skills-top preferred in 6 of 6; REFUTED if base preferred in 4 or more; otherwise INCONCLUSIVE
change-scope:
  ^Skills$
  ^At a glance$
  ^(Languages|Tools|Practices):
fake-reader:
  prefer containing "At a glance"
```

A reader's program is an absolute path, as here, or a program name found on your `PATH`. `freeze` refuses a relative path such as `./my-reader.sh`, because each read runs inside a folder of its own. Mark a reader `not-blind` when you know it gets your identity from its own setup: its reads are reported separately and never counted toward a verdict. `cost 3` is what one read costs, in a unit you choose; it feeds the spend estimate. A reader's reads come in pairs, the same two versions in opposite orders, so `reads-per-reader` is an even number (6 if you leave it out): three pairs per reader. Two readers at 6 reads each make 12 reads and six paired picks per comparison, and six paired picks is what `6 of 6` counts. When a reader prefers the same version in both orders the pair is a pick for it; when its two orders disagree, or one is a tie, the pair is a TIE. Each version says who wrote it with `drafted-by` (`user`, `third-party`, `unknown` or `model <family>`), and each reader names its model `family`. This plan has a live reader, so without `--live` it prints the commands and runs nothing, the fake reader included.

The tool has three subcommands:

    track-record ab freeze plan.txt
    track-record ab run plan.txt [--live]
    track-record ab score plan.txt

`freeze` finds every problem in the plan and writes a freeze file beside it. `run` checks the hashes and that the versions differ only where the plan says, runs the readers and writes a result. `score` scores the replies again into a new result and never overwrites an earlier one. The `fake` reader answers by the rules in the plan's `fake-reader` block, so it tests the plan and says nothing about your copy. A live reader is a command you name, run without a shell in a folder holding the two versions, the posting and the prompt; it inherits your whole environment, API keys included. A plan with a live reader prints its commands and a spend estimate, and starts nothing, until you add `--live`. What a live reader does with your files is up to that reader.

Exit 0 means `freeze` wrote the freeze file, or `run` or `score` completed and scored its replies, whatever the verdicts, or `run` only printed the commands because `--live` was absent. Exit 1 means it finished but a read failed, or the spend ceiling cut it short. Exit 2 means it couldn't run: a plan error, a changed file, a failed check on the versions, or an interrupt. Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md).

**What a reader result means.** The readers are AI models standing in for the people who will read your draft, such as a recruiter or a hiring manager. How well they stand in for people hasn't been measured, so a result is evidence about these readers, not about people. Beside each verdict, a result shows:
- the exact p-value;
- the 95% interval for the share of paired picks that went to one version;
- how many reads, and how many pairs, were missing, and whether they could have changed the verdict;
- how many reads were left out because their reader was not blind.

A hypothesis is also scored a second time with every `slightly` pick counted as a TIE, and the result prints that second reading beside the verdict; when the two differ, the verdict line says it holds only when `slightly` counts as a pick. When a verdict favours a version that a model wrote and a reader of that model's family is among the readers, the readers of every other family must agree at the rule's share, on at least 3 pairs, or the verdict is INCONCLUSIVE. A mechanism needs a margin over its A/A floor. Revision 4 changes verdicts: rules count paired picks, and the default run makes 12 reads per arm, was 6. `run` and `score` refuse a plan frozen under an earlier release, with exit 2; score it with the release that froze it, or write a new plan.

It also prints one line on validity: reads from one model and prompt may not be independent, so the p-value may be too small. These lines never change a verdict. They help you judge how much to rely on it.

## Plan keys added in 0.8.0

- `sensitivity: X vs W` (`ab`): a version `X` against a copy `W` of it weakened on purpose, run as its own arm before the comparisons. In the spec's words: "When the readers prefer the version, the run shows they could see that planted difference. Known limit: it does not show they could see one as small as the change under test." Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md) § 1, § 3.1 and § 6.
- `sensitivity-scope` (`ab`): the line patterns where `X` and `W` may differ, required with `sensitivity`. Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md) § 3.1 and § 4.2.
- `sensitivity-threshold` (`ab`): the share of valid sensitivity reads that must prefer `X`, above 1/2 and at most 1 (default 5/6). Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md) § 3.1 and § 6.
- `min-valid-reads` (`ab`, `panel`): the read floor. A comparison or rule with fewer valid reads from blind readers is INCONCLUSIVE. Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md) § 3.1 and § 6, [docs/specs/reader-panel.md](../specs/reader-panel.md) § 3.1 and § 6.
- `replicate-of` (`ab`, `panel`): the freeze file of a first run of the same plan, to run it again in a new folder and compare the two runs' counts. Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md) § 3.2, [docs/specs/reader-panel.md](../specs/reader-panel.md) § 3.2.
- `reader-group <name>` (`ab`, `panel`), a field on a reader's line: readers that are alike, such as one model behind two commands. The result counts each group's valid reads, and a group changes no verdict. Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md) § 5.5, [docs/specs/reader-panel.md](../specs/reader-panel.md) § 5.5.

## Plan keys added in revision 4

- `drafted-by <who>` (`ab`), a field on each version's line: `user`, `third-party`, `unknown`, or `model <family>` (more than one as a comma list). Required. Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md) § 3.1 and § 6.
- `family <name>` (`ab`), a field on each reader's line: the model family behind it. Required, and separate from `reader-group`. Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md) § 3.1 and § 6.
- `document` (`ab`): the kind of document the versions are, `résumé` (the default), `cover letter`, `essay` or `profile`. It changes only the noun in the reader prompt. Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md) § 3.1.
- `extends` (`ab`): the freeze file of a first run whose sample size this plan extends, once. Only `reads-per-reader` and the number of readers of the models that already read may change; the result pools the first run's reads with its own and prints the first run's verdict beside the pooled one. A first run that pools A/A reads cannot be extended. Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md) § 3.2.
- `aa-pool` (`ab`): freeze files of earlier runs whose control reads this run's noise gate counts with its own. A pooled run must share the prompt, the reader commands, the control version file and the posting. Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md) § 3.1 and § 6.
- `amends` (`ab`) may now change the read count, but never a threshold: each rule keeps its share of the planned pairs, so with twice the reads `6 of 6` becomes `12 of 12`. Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md) § 3.2.
