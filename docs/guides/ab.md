# `track-record ab`

Compare two versions of a résumé, or any career document, by asking test readers which reads better. A reader is a command you name, such as one that calls a language model, or the built-in `fake`, which tests a plan. You write a plan first: the posting, the versions, where they may differ and what counts as a win. The tool hashes the plan and every file it names, and a run refuses anything that has changed since, so the rules can't quietly move after you see the answer. Every run also reads one version against itself, as a control, so you can see how often a reader picks a side when there is no difference. Each reader reads every pair of versions in both orders, and a pick counts only when both orders agree. Each comparison ends SUPPORTED, REFUTED or INCONCLUSIVE, by the rule you wrote. A plan that names `aa-band: on` can also end TIE: a SUPPORTED whose margin is no bigger than the A/A band, the count of pairs in which identical drafts picked a side, from this run and any run it pools or extends. This plan is invented:

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

Exit 0 means `freeze` wrote the freeze file, or `run` or `score` completed and scored its replies, whatever the verdicts, or `run` only printed the commands because `--live` was absent. Exit 1 means it finished but a read failed, or the spend ceiling cut it short. Exit 2 means it couldn't run: a plan error, a changed file, a failed check on the versions, or an interrupt. Spec: [docs/specs/reader-ab.md](../specs/reader-ab.md). How far to trust a score: [scoring](scoring.md).

**What a reader result means.** The readers are AI models standing in for the people who will read your draft, such as a recruiter or a hiring manager. How well they stand in for people hasn't been measured, so a result is evidence about these readers, not about people. Beside each verdict, a result shows:
- the exact p-value;
- the 95% interval for the share of paired picks that went to one version;
- how many reads, and how many pairs, were missing, and whether they could have changed the verdict;
- how many reads were left out because their reader was not blind.

A hypothesis is also scored a second time with every `slightly` pick counted as a TIE, and the result prints that second reading beside the verdict; when the two differ, the verdict line says it holds only when `slightly` counts as a pick. When a verdict favours a version that a model wrote and a reader of that model's family is among the readers, the readers of every other family must agree at the rule's share, on at least 3 pairs, or the verdict is INCONCLUSIVE. A mechanism needs a margin over its A/A floor (an A/A read gives the reader the same version twice, as a control). Revision 4 changes verdicts: rules count paired picks, and the default run makes 12 reads per arm, was 6. `run` and `score` refuse a plan frozen under an earlier release, with exit 2; score it with the release that froze it, or write a new plan.

It also prints one line on validity: reads from one model and prompt may not be independent, so the p-value may be too small. These lines never change a verdict. They help you judge how much to rely on it.

## Your first A/B test

This walks through one small test with an AI model as the reader. You need the `codex` command (Codex) installed and logged in. The test uses it unless you name the `claude` command (Claude Code), as the first argument on the reader line or in the `MODEL_READER_CLI` environment variable, and then you need that one installed and logged in instead. A run with `--live` asks that model, and your provider may bill you; the steps below show the cost first.

**The files.** `examples/ab-first-plan.txt` is the plan, and `examples/ab-first/` holds an invented posting and two versions of an invented résumé. They differ only in where the skills sit: the second version moves them to the top, under "At a glance". The plan carries notes on every line, and the tool ignores lines that start with `#`. `examples/readers/model_reader.py` is the reader: an example script, not part of the installed package, that pastes the posting and both versions into one message, asks the model, and prints the reply. Read it before you run it; it is short. It asks `codex`. The tool gives a reader no standard input and leaves the prompt in `PROMPT.txt` in the read folder, so the script reads that file (and `POSTING.txt`, `A.txt` and `B.txt`) and passes the text to the model. For Codex it runs `codex exec --skip-git-repo-check --ephemeral --ignore-user-config --disable apps --color never -c approval_policy="never" -c default_permissions="reader" -c permissions.reader.filesystem=<profile> -c shell_environment_policy.inherit=none --output-last-message <temp file> -`, in a fresh folder that holds copies of the four files, not in the read folder: a permission profile, set by this example reader and not by the tool, that lets the commands the model runs read that folder, the system's own files and the folder Codex is installed in and grants no write, no approval prompts, no saved session, your Codex `config.toml` skipped, an environment of `PATH`, `HOME` and `TMPDIR` only for the Codex process itself, and only the model's final message used as the reply (`--skip-git-repo-check` because that folder is not a git repository). In checks with `codex sandbox` (Codex 0.156.1, no model call), a write in that folder was refused under that profile, so the commands the model runs are not meant to change your files; whether the commands a `codex exec` run issues get the same profile has not been measured in a live run. The reader also passes `--disable apps`, which is meant to turn off Codex's apps and connectors feature. In one check of the Codex app-server, with `--disable apps` it offered 0 servers and 0 tools; without it, 431 tools, 21 of them with mail-like names. That check was of the app-server, not of a `codex exec` run, so whether a `codex exec` run is offered your account's apps has not been measured. In a second check, of the app inventory that `codex app-server` returns (its `app/list` call, Codex 0.156.1), `--disable apps` returned 0 apps, and the same call without it returned 200 apps (the page size, so not a total). That check is not a measurement of the tools a `codex exec` run is offered, and it does not cover `--ignore-user-config`. For Claude it runs `claude -p --restricted --strict-mcp-config --tools "" --setting-sources "" --no-session-persistence`. The reader adds neither `--bare` nor an API key; it inherits your environment, so it uses whatever sign-in `claude` finds there. The check described below ran on a machine where the init event reported no API key (`apiKeySource` `none`). Before it sends your text, the reader starts `claude` on a fixed harmless prompt with the same restriction flags, plus `--output-format stream-json --verbose` to read the init event, and stops that process; if the event lists any MCP server or any tool, or it cannot read one, the reader stops with exit status 2 and sends none of the read folder's text. Each read therefore starts `claude` twice: first this preflight, then the real run on your text. The preflight and the real run each start in their own fresh empty folder that the reader creates, because a folder holding a project `.mcp.json` has not been measured. In one check of Claude Code 2.1.327, with one account and an empty folder, the init event listed 0 MCP servers and 0 tools under these flags; with `--tools ""` alone it listed 5 connector servers. If you have connected a mail app or any other connector to the account you sign in to Codex with, use a reader of your own instead of this example (see "Write a reader of your own" below). The reader line names the script, and the tool splits the line into a program and its arguments and runs it without a shell.

What that check left open: the hooks of the plugins that still load (the init event listed 4 or 5 plugins; whether their hooks run was not measured), `CLAUDE.md` and auto-memory (not measured), the skills and slash commands that remain, and that the run does not pass `--bare`, which would skip reading your sign-in. The `--bare` and API-key arm was not measured. This applies to the example reader's `claude` option; it is no evidence about any other reader. It also read only the start of one session; the reader's run on your text is a second session, and nothing after its start was checked.

**Four words the plan uses.**
- *A/A* is a control: the tool also has the reader read one version against itself. A fair reader should call that a tie, so the A/A reads show how often your reader picks a side when there is nothing to find.
- *Drafted by* says who wrote each version: `user` when no AI wrote or edited any of its words, or `model <family>` (for example `model codex`) when an AI did. It is there because a model may favour wording that a model of its own family wrote, so the tool checks such a win against readers of other families.
- *Family* is the model behind a reader (for example `codex`), one word that you choose consistently.
- *Paired picks*: each reader reads each pair of versions twice, once in each order, because readers lean towards whichever version comes first. The two reads of a pair make one pick only when they agree; if they disagree, the pair counts as a tie. The rule in the plan counts pairs: `3 of 3` means all three pairs.

**The steps.**

1. Copy the plan and its files to a new folder, because the tool writes its freeze file and results beside the plan, and a folder holds one plan only: `freeze` refuses a second plan in a folder that already has a freeze file, so each plan, including your own later, goes in its own folder. On macOS, Linux or Git Bash:

       mkdir my-first-test
       cp -r examples/ab-first examples/ab-first-plan.txt my-first-test/

   On Windows (Command Prompt):

       xcopy examples\ab-first my-first-test\ab-first /E /I
       copy examples\ab-first-plan.txt my-first-test\

2. Open `my-first-test/ab-first-plan.txt` and replace `/path/to/career-track-record` on the reader line with the full path to this repository's folder: run `pwd` on macOS or Linux, or `cd` on Windows, from the top folder of your clone. A reader program has to be named by its full path, not a relative one. On Windows write the path with forward slashes (`C:/Users/you/career-track-record/...`): the tool splits the line by shell rules, which eat a backslash, so `C:\Users\you\r.py` would become `C:Usersyour.py`. Use `python` where the line says `python3` if that is the command you have. If `track-record` is not found, the README's `PYTHONPATH=src python3 -m career_track_record` fallback is POSIX-only; in PowerShell write `$env:PYTHONPATH="src"; python -m career_track_record ab freeze my-first-test/ab-first-plan.txt`. `freeze` warns on standard error, one line per reader, when a reader's program or `.py` script cannot be found, but still writes the freeze; a wrong path you miss shows up as failed reads, so check it first: `codex --version` should print a version, and `python3 examples/readers/model_reader.py` run from a folder with no `PROMPT.txt` should stop with a one-line reason about that file, which shows the script runs. Before you freeze, read "Is the reader blind?" below: if the reader may know who you are, add `| not-blind` to its reader line now, because a frozen plan can't be changed.

3. Freeze the plan. This writes `my-first-test/ab-first-plan.txt.freeze` and exits 0:

       track-record ab freeze my-first-test/ab-first-plan.txt

4. Run it without `--live`. It prints the reader command, the number of reads (12: 6 for the comparison and 6 for the A/A control, because `reads-per-reader` is 6) and the estimated spend (12 units, one per read), starts nothing, and exits 0:

       track-record ab run my-first-test/ab-first-plan.txt

5. When you are ready to spend, add `--live`. The `run` above printed `planned reads: 12`: `--live` makes that many model calls, one at a time, each on your own Codex subscription or account, and it can take several minutes. Adding `--live` is your consent to that spend; the tool cannot see the real cost; it tallies the units you declared in the plan:

       track-record ab run my-first-test/ab-first-plan.txt --live

**Is the reader blind?** Not by default: the reader loads files from your own setup. For Codex, `--ignore-user-config` skips `config.toml` but not the `AGENTS.md` in your Codex home folder. This was checked without a live model, with `codex debug prompt-input` (Codex 0.156.1), which prints the input the model would see: an invented `AGENTS.md` in a throwaway Codex home appeared in it, and `-c project_doc_max_bytes=0`, `-c project_doc_fallback_filenames=[]` and `-c instructions=""` did not remove it. (`project_doc_max_bytes=0` does stop an `AGENTS.md` in the folder the reader runs in, which the read folder does not have.) None of the settings tried stops Codex loading that file, so the reader uses none. If your own instruction or memory files say who you are, add `| not-blind` to the reader line, so its reads are reported and never counted in a verdict. A model that does recall you should say so in the `PRIOR` field, and the result flags that read, but that catches only what the model admits. For the claude option, whether `CLAUDE.md` or auto-memory reach the reader has not been measured.

The result is printed and saved as `result-1.txt` beside the plan. With only three pairs the test is small: a SUPPORTED verdict here means these readers preferred the change in all three pairs, and nothing more. Beside each verdict, check the A/A lines first. If the plan names `aa-band: on`, the `A/A band` line and each `margin` line sit beside the verdict too, and the A/A lines are still what to read first. The band is only as good as the reader's blindness, which the example `codex` reader does not establish; do not cite a band from its reads as evidence of noise level. When a verdict is TIE, the margin was inside the band, and the result says the versions are not shown to differ. One way to learn more is an `extends` run with more reads: the pooled count is read at the same share, and the band is measured again from the pooled A/A pairs. The result says that the sample size changed after a result was seen, and a first run can be extended only once. To test your own résumé, copy your two versions and a posting you saved yourself into the folder, change the file names and the `change-scope` patterns in the plan, and freeze it as a new plan.

## Write a reader of your own

A reader is a program that the plan's reader line names, run once per read. The spec says how, in [docs/specs/reader-ab.md](../specs/reader-ab.md), section "Live readers". The command "runs with its read folder as the working folder and gets no argument from the tool". When it starts, the folder holds "exactly `A.txt` and `B.txt`", the two versions as text, and `POSTING.txt` and `PROMPT.txt`. "The command's standard output is the reply", and a nonzero exit status is a failed read. "The command is split into a program and its arguments by POSIX shell-word rules and run without a shell", so the first word is an absolute path or a name found on `PATH`, and a relative path is refused at freeze. `read-timeout` is in seconds (default 600); a read that reaches it is a failed read. A `panel` read folder holds different files; see [the panel guide](panel.md#write-a-reader-of-your-own).

The reply has the fields in the spec's section 5.4, "Reply format": `READ`, `PRIOR`, `SCORE-A`, `SCORE-B`, `PREFER`, `DROVE-IT`, `DOUBTS`, `UNDERSOLD`, `OVEREXPLAINED`, `OWNED` and `FLAG-FIXES`, written as `FIELD: value` at the start of a line. `PREFER` is `PREFER: <A|B>, <slightly|clearly|strongly>`, or `PREFER: TIE`, which takes no strength (spec section 5.4). A reply that is missing `READ`, `SCORE-A`, `SCORE-B` or `PREFER`, or whose `PREFER` choice cannot be read, is a failed read. For what goes after `READ:` and what form the scores take, the prompt in `PROMPT.txt` says; the skeleton below writes a placeholder after `READ:` and keeps its scores between 1 and 10.

This skeleton is a placeholder, and your own judgement goes where it counts the posting's words. It uses the Python 3.9 standard library, which suits a repository written in standard-library Python, and a script is a way to run several steps from one command when the line has no shell. It reads the four files from its working folder, calls no model, opens no network connection and prints a reply in the section 5.4 format. Save it as `my_reader.py`:

```python
#!/usr/bin/env python3
"""A placeholder reader: put your own judgement where the marked lines are."""
import re


def read(name):
    with open(name, encoding="utf-8") as handle:
        return handle.read()


prompt = read("PROMPT.txt")  # the instructions the tool wrote; read them, then match their format
posting, a, b = read("POSTING.txt"), read("A.txt"), read("B.txt")

# Placeholder judgement: count the posting's words that each version repeats.
words = set(re.findall(r"[a-z]+", posting.lower()))
count_a = len(words & set(re.findall(r"[a-z]+", a.lower())))
count_b = len(words & set(re.findall(r"[a-z]+", b.lower())))
score_a, score_b = (max(1, min(10, n)) for n in (count_a, count_b))  # the prompt asks for 1 to 10

choice = "B, slightly" if count_b > count_a else "A, slightly" if count_a > count_b else "TIE"
print("READ: placeholder")
print("PRIOR: nothing")
print("SCORE-A: %d" % score_a)
print("SCORE-B: %d" % score_b)
print("PREFER: " + choice)
for field in ("DROVE-IT", "DOUBTS", "UNDERSOLD", "OVEREXPLAINED", "OWNED", "FLAG-FIXES"):
    print(field + ": none")
```

The reader line has the shape of the one in `examples/ab-first-plan.txt`, with the skeleton's full path:

    reader-1 | python3 /full/path/to/my_reader.py | cost 1 | family mine

It carries a `family`, as every reader line does. Add `| not-blind` if the reader may know who you are; the paragraph that begins "Is the reader" says when. The spec says a reader "inherits the tool's environment"; what else a reader can reach has not been measured. A reader of your own that runs `claude -p` must exclude connectors: in one check of Claude Code 2.1.327, the flags the example reader passes (`--restricted --strict-mcp-config --tools "" --setting-sources ""`) gave an init event listing 0 MCP servers and 0 tools, and `--tools ""` alone listed 5 connector servers; the `--bare` and API-key arm was not measured.

## Keep a series of drafts

A series file records, for each draft, which draft it was read against and what the round said. Three words in it: a *draft* is the plan's version, so the version name in the plan is the draft's id; a *round* is the run folder; and an empty `parent` is what the `drafts` file writes `none`. The `drafts` file keeps a document's versions by hand, with their text, parents and your notes; the series file records, from the tool, which draft was read against which parent and what each round said. Both name parents today, and no command compares them.

You make the series file by hand; the tool never creates it. It is a tab-separated file whose first line is exactly this, and whose later lines each have nine fields:

    draft	parent	file_sha256	posting_sha256	round	plan_sha256	result	date	note

Add the row of the starting draft yourself, with an empty `parent` and `file_sha256` set to the sha256 of its file (`shasum -a 256` prints it); leave `posting_sha256`, `round`, `plan_sha256` and `result` empty, but keep their tabs. Date a row you write by hand with the UTC day, as the tool does for its own rows: `date -u +%F`. Keep the file in a folder above the plans: each plan's folder must lie below the series file's folder, and its path from there is the `round`. A folder name with `;`, `@` or a control character is refused.

A plan joins a series with the `series` key, a path to the file relative to the plan's folder, and an optional `series-note` for the row's `note`. A plan with `series` must also name at least one hypothesis, and `series-note` needs `series`; `freeze` refuses either fault with exit 2, before any read. It must hold exactly one comparison: the second version is the draft, and the first is its parent, so name the versions as the series names them. When `run` or `score` writes a result, the tool adds the draft's row under a lock and prints `series: added row <draft> to <file>`. Plans that extend, amend or replicate that run each add one item to the end of the row's `result` cell instead, and print `series: added result of <round> to row <draft> in <file>`; a TIE is written there as `h1 TIE`, with none of the result's sentences. The `series:` lines are printed after the result and are not in the result file. Scoring the same plan again changes nothing and says `series: no change: plan <12 digits> is already recorded in row <draft> (line <n>)`. If the write fails, the result stays, the series file stays, and `series: not written: <reason>` is printed with exit status 1; scoring the plan again writes it.

`freeze`, `run` and `score` each check the series file before any read and before any result, and exit 2 if it breaks the format, if the parent's file is not the one the series records, or if the series already holds the draft in a plan that is not a follow-up. A plan that names `series` needs a POSIX file lock, so it cannot be frozen on Windows. Spec: [docs/specs/series.md](../specs/series.md).

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

## Plan keys added in revision 5

- `aa-band` (`ab`): the only value is `on`. A SUPPORTED whose margin (pairs for the version the rule names, minus pairs for the other) is no bigger than the A/A band becomes TIE; REFUTED and INCONCLUSIVE are unchanged. The result gains an `A/A band` line and a `margin` line for each SUPPORTED hypothesis. A plan without the key is scored as before. An amendment may not add, drop or change it. Spec: [docs/specs/reader-ab-aa-band.md](../specs/reader-ab-aa-band.md) § 2, § 3 and § 4.
- `series` (`ab`): a series file, as a path relative to the plan's folder; the plan must hold exactly one comparison and at least one hypothesis. When the result is written, the tool adds a row, or an item to a row's `result` cell, to that file. See "Keep a series of drafts". Spec: [docs/specs/series.md](../specs/series.md) § 4, § 5 and § 6.
- `series-note` (`ab`): one line, without a tab, for the `note` column of the row the plan adds; it needs `series`. Spec: [docs/specs/series.md](../specs/series.md) § 4.
