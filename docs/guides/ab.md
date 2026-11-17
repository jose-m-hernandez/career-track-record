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

**A worked example of `change-scope`.** Each `change-scope` line is a Python regular expression, tried with `re.search` against every line that differs between the two versions, so it matches anywhere in a line unless you anchor it with `^` and `$`. A changed line counts as a removal of the old text and an addition of the new, and both must match. Take an invented résumé, `base`, with the bullet `- Cut median first reply time from nine hours to three.`, and a second version, `rota`, whose only difference is that bullet reading `- Cut median first reply time from nine hours to three, by adding a weekend rota.` The scope `^- Cut median first reply time` lets the two versions differ on any line that begins with those words, and on no other line. `run` checks this before any read. Suppose `rota` also changes a line in the summary, from `plain language.` to `plain language, and weekend work.` No pattern matches that line, so `run` stops with exit 2 and runs no read, printing `cannot run: c1: changed line outside the change scope: - plain language.` and the same for the added line, marked `+`. `freeze` does not check this: in the same test it wrote the freeze file and exited 0, so a scope that is too narrow shows only at `run`. To go on, widen the scope, or make the versions differ only where it allows.

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

A hypothesis is also scored a second time with every `slightly` pick counted as a TIE, and the result prints that second reading beside the verdict; when the two differ, the verdict line says it holds only when `slightly` counts as a pick. When a verdict favours a version that a model wrote and a reader of that model's family is among the readers, the readers of every other family must agree at the rule's share, on at least 3 pairs, or the verdict is INCONCLUSIVE. A mechanism needs a margin over its A/A floor (an A/A read gives the reader the same version twice, as a control). Revision 4 changes verdicts: rules count paired picks, and the default run makes 12 reads per arm, was 6. `run` and `score` refuse a plan frozen under an earlier release, with exit 2; score it with the release that froze it, or write a new plan.

It also prints one line on validity: reads from one model and prompt may not be independent, so the p-value may be too small. These lines never change a verdict. They help you judge how much to rely on it.

## Your first A/B test

This walks through one small test with an AI model as the reader. You need the `codex` command (Codex) installed and logged in, or the `claude` command (Claude Code) as the fallback. A run with `--live` asks that model, and your provider may bill you; the steps below show the cost first.

**The files.** `examples/ab-first-plan.txt` is the plan, and `examples/ab-first/` holds an invented posting and two versions of an invented résumé. They differ only in where the skills sit: the second version moves them to the top, under "At a glance". The plan carries notes on every line, and the tool ignores lines that start with `#`. `examples/readers/model_reader.py` is the reader: an example script, not part of the installed package, that pastes the posting and both versions into one message, asks the model, and prints the reply. Read it before you run it; it is short. It uses `codex` unless you give it `claude`, either as an argument on the reader line (`... model_reader.py claude`, and then write `family claude` on that line) or in the environment variable `MODEL_READER_CLI`. The tool gives a reader no standard input and leaves the prompt in `PROMPT.txt` in the read folder, so the script reads that file (and `POSTING.txt`, `A.txt` and `B.txt`) and passes the text to the model. For Codex it runs `codex exec --sandbox read-only --skip-git-repo-check --ephemeral --ignore-user-config --disable apps --color never -c approval_policy="never" --output-last-message <temp file> -`: a read-only sandbox, no approval prompts, no saved session, your Codex `config.toml` skipped, and only the model's final message used as the reply (`--skip-git-repo-check` because the read folder is not a git repository). For Claude it runs `claude -p --tools "" --no-session-persistence`, which turns every built-in tool off, and adds `--bare` only when `ANTHROPIC_API_KEY` is set. For Claude every built-in tool is off; whether MCP servers or connectors from your setup load has not been measured. For Codex the sandbox is read-only, so it cannot change your files, and the reader passes `--disable apps`, which is meant to turn off Codex's apps and connectors feature. In one check of the Codex app-server, with `--disable apps` it offered 0 servers and 0 tools; without it, 431 tools, 21 of them with mail-like names. That check was of the app-server, not of a `codex exec` run, so whether a `codex exec` run is offered your account's apps has not been measured. If you have connected a mail app to the account you sign in to Codex with, use a reader of your own instead of this example. The reader line carries the argument, because the tool splits the line into a program and its arguments and runs it without a shell.

**Four words the plan uses.**
- *A/A* is a control: the tool also has the reader read one version against itself. A fair reader should call that a tie, so the A/A reads show how often your reader picks a side when there is nothing to find.
- *Drafted by* says who wrote each version: `user` when no AI wrote or edited any of its words, or `model <family>` (for example `model codex`) when an AI did. It is there because a model may favour wording that a model of its own family wrote, so the tool checks such a win against readers of other families.
- *Family* is the model behind a reader (`codex` or `claude`), one word that you choose consistently.
- *Paired picks*: each reader reads each pair of versions twice, once in each order, because readers lean towards whichever version comes first. The two reads of a pair make one pick only when they agree; if they disagree, the pair counts as a tie. The rule in the plan counts pairs: `3 of 3` means all three pairs.

**The steps.**

1. Copy the plan and its files to a new folder, because the tool writes its freeze file and results beside the plan, and a folder holds one plan only: `freeze` refuses a second plan in a folder that already has a freeze file, so each plan, including your own later, goes in its own folder. On macOS, Linux or Git Bash:

       mkdir my-first-test
       cp -r examples/ab-first examples/ab-first-plan.txt my-first-test/

   On Windows (Command Prompt):

       xcopy examples\ab-first my-first-test\ab-first /E /I
       copy examples\ab-first-plan.txt my-first-test\

2. Open `my-first-test/ab-first-plan.txt` and replace `/path/to/career-track-record` on the reader line with the full path to this repository's folder: run `pwd` on macOS or Linux, or `cd` on Windows, from the top folder of your clone. A reader program has to be named by its full path, not a relative one. On Windows write the path with forward slashes (`C:/Users/you/career-track-record/...`): the tool splits the line by shell rules, which eat a backslash, so `C:\Users\you\r.py` would become `C:Usersyour.py`. Use `python` where the line says `python3` if that is the command you have. If `track-record` is not found, the README's `PYTHONPATH=src python3 -m career_track_record` fallback is POSIX-only; in PowerShell write `$env:PYTHONPATH="src"; python -m career_track_record ab freeze my-first-test/ab-first-plan.txt`. `freeze` warns on standard error, one line per reader, when a reader's program or `.py` script cannot be found, but still writes the freeze; a wrong path you miss shows up only as failed reads, so check it first: `codex --version` (or `claude --version`) should print a version, and `python3 examples/readers/model_reader.py` run from a folder with no `PROMPT.txt` should stop with a one-line reason about that file, which shows the script runs. Before you freeze, read "Is the reader blind?" below: if the reader may know who you are, add `| not-blind` to its reader line now, because a frozen plan can't be changed.

3. Freeze the plan. This writes `my-first-test/ab-first-plan.txt.freeze` and exits 0:

       track-record ab freeze my-first-test/ab-first-plan.txt

4. Run it without `--live`. It prints the reader command, the number of reads (12: 6 for the comparison and 6 for the A/A control, because `reads-per-reader` is 6) and the estimated spend (12 units, one per read), starts nothing, and exits 0:

       track-record ab run my-first-test/ab-first-plan.txt

5. When you are ready to spend, add `--live`. The `run` above printed `planned reads: 12`: `--live` makes that many model calls, one at a time, each on your own Codex (or Claude) subscription or account, and it can take several minutes. Adding `--live` is your consent to that spend; the tool cannot see the real cost, only the units you declared in the plan:

       track-record ab run my-first-test/ab-first-plan.txt --live

The result is printed and saved as `result-1.txt` beside the plan. With only three pairs the test is small: a SUPPORTED verdict here means these readers preferred the change in all three pairs, and nothing more. Beside each verdict, check the A/A lines first. To test your own résumé, copy your two versions and a posting you saved yourself into the folder, change the file names and the `change-scope` patterns in the plan, and freeze it as a new plan. **Is the reader blind?** Not by default, for either reader: both load files from your own setup. For Codex, `--ignore-user-config` skips `config.toml` but not the `AGENTS.md` in your Codex home folder. This was checked without a live model, with `codex debug prompt-input` (Codex 0.156.1), which prints the input the model would see: an invented `AGENTS.md` in a throwaway Codex home appeared in it, and `-c project_doc_max_bytes=0`, `-c project_doc_fallback_filenames=[]` and `-c instructions=""` did not remove it. (`project_doc_max_bytes=0` does stop an `AGENTS.md` in the folder the reader runs in, which the read folder does not have.) None of the settings tried stops Codex loading that file, so the reader uses none. For Claude, without `--bare` the reader loads your `~/.claude` files (`CLAUDE.md` and memory), so it has the same gap, and `--bare` needs an API key, which is the only case where the example reader passes it. If your own instruction or memory files say who you are, add `| not-blind` to the reader line, so its reads are reported and never counted in a verdict. A model that does recall you should say so in the `PRIOR` field, and the result flags that read, but that catches only what the model admits.

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
