# `track-record panel`

Read one version of a résumé, or any career document, through several lenses: each a reader in a role you name, such as a recruiter or the hiring manager, given as a plain-text prompt file you write. Readers are the same as in `track-record ab`: a command you name, or the built-in `fake`. The plan is frozen by hash before the first read, lens files included.

Every lens also reads two anchors you supply: a document you wrote to be plainly strong for the posting, and one you wrote to be plainly weak. If a lens does not score the strong anchor at or above `anchor-strong-at-least` and the weak anchor at or below `anchor-weak-at-most`, on every anchor read, that lens's reads of your version are reported INCONCLUSIVE and not counted. The anchors do for the panel what the control read does for `ab`: a lens that shows nothing also shows whether it could see anything. This plan is invented:

```
posting: posting.txt
version: resume.txt
anchors:
  strong | anchor-strong.txt | written-by user
  weak | anchor-weak.txt | written-by user
lenses:
  recruiter | recruiter.lens.txt | author-edited-version no
  hiring-manager | hiring-manager.lens.txt | author-edited-version no
readers:
  reader-1 | fake
  reader-2 | /path/to/my-reader.sh | cost 3
anchor-reads-per-reader: 2
anchor-strong-at-least: 7
anchor-weak-at-most: 4
rules:
  recruiter | PASS if score at least 7 in 5 of 6; FAIL if score at most 4 in 2 or more; otherwise INCONCLUSIVE
  hiring-manager | FAIL if DOUBTS flagged in 3 or more; PASS if score at least 7 in 5 of 6; otherwise INCONCLUSIVE
  overall | PASS if score at least 7 in 10 or more; otherwise INCONCLUSIVE
fake-reader:
  strong | score 9
  weak | score 2
  version | score 7
```

Each reader reads the version three times per lens and each anchor twice, unless the plan says otherwise. A rule names its lens, or `overall` for every counted lens, and tests scores or flagged fields: a field such as `DOUBTS` is flagged when the reader wrote anything there but `none`. The reader sees the posting, the lens and one document, and nothing says whether that document is an anchor or your version.

The tool has the same three subcommands as `ab`:

    track-record panel freeze plan.txt
    track-record panel run plan.txt [--live]
    track-record panel score plan.txt

The `--live` rule, the spend ceiling, the `fake` reader and the exit codes are those of `ab`, and `run` and `score` also exit 2 for a plan frozen under an earlier revision. The spec is signed (revision 4). How far to trust a score: [scoring](scoring.md). Spec: [docs/specs/reader-panel.md](../specs/reader-panel.md).

## Five lenses and a confirming pass

This part is a way of using the panel. It adds no command and no plan key: the plan above already takes any number of lenses.

**Five viewpoints, one lens file each.** To read one draft as a hiring process would, write five lens files, name them in the plan under `lenses:`, and let each raise its own flags. A lens file is text you write, handed to the reader as it is ([docs/specs/reader-panel.md](../specs/reader-panel.md), § 3.3, lines 75-77). Give each file the same shape: a role, what that role looks for, and what it must quote when it flags something. This guide invents no roles; choose the five that match the posting. Invented example of the shape, for a records-clerk posting: "You are the person who will train the new hire. You look for evidence the candidate can follow a filing procedure without being reminded. When you doubt something, quote the line that made you doubt it." Have each lens report doubts in a field such as `DOUBTS`; the panel marks a field as flagged when the reader wrote anything there but `none` (the field rule above; spec, line 122).

The anchors still apply. Every lens reads your strong and weak anchors, and a lens that fails the anchor gate has its reads of your draft reported INCONCLUSIVE and not counted (spec, lines 32-33). Reads from a reader marked `not-blind` are left out of every verdict (spec, line 126). Five lenses at the default of three reads each make fifteen reads of your draft, plus the anchor reads, so look at the spend estimate before you add `--live`.

**The confirming pass.** A flag raised by one read is a suspicion. Take each flag from the five lenses and have a reader look at the draft again, with the flag and nothing else to go on, and answer one of two ways: confirmed, with a line quoted from the draft, or dropped. A confirmation that quotes no line counts as a dropped flag, the rule [scoring](scoring.md) uses for a rubric. Only confirmed flags go on your fix list.

Keep each dropped flag in your notes, with the reason. If the same flag comes up next round, you can see it was looked at and found unsupported, and you don't spend another pass on it.

What a command does here: `panel` runs the five lenses, applies the anchor gate and reports flagged fields. The confirming pass isn't a `panel` feature. Run it by hand, or as a second `panel` plan, which is frozen by hash like any other. Either way it is a choice you make; no command asks for it.

## Plan keys added in revision 4

- `written-by <who>`, a field on each anchor's line: `user`, `third-party`, `unknown`, or `model <family>` (more than one as a comma list, `model fam-a, model fam-b`), required, and it may be followed by `| note <text>`, free text that runs to the end of the line. Spec: [docs/specs/reader-panel.md](../specs/reader-panel.md) § 3.1.
- `author-edited-version yes` or `no`, a field on each lens's line: whether whoever wrote the lens's rubric also wrote or edited the version, required, printed in the result and changing no verdict. Spec: [docs/specs/reader-panel.md](../specs/reader-panel.md) § 3.1.
- `criteria <A>,<B>,...`, a field on a lens's line: the criteria its rubric scores, each read as `CRITERION-<name>` and summed by the tool, which ignores any `SCORE` field in such a reply. Spec: [docs/specs/reader-panel.md](../specs/reader-panel.md) § 3.1 and § 5.4.
- `calibration-only: yes`: reads only the anchors through every lens and no version, so a lens can be fixed before any version is read. Spec: [docs/specs/reader-panel.md](../specs/reader-panel.md) § 3.1 and § 6.
- `calibration: <freeze file>`: names a calibration run of the same lenses, and a lens that failed it is not counted; a run that reads the version and names none reports its scores as uncalibrated. Spec: [docs/specs/reader-panel.md](../specs/reader-panel.md) § 3.1 and § 6.
- `extends: <freeze file>`: a new run of a first run's plan that may change only the sample size, pools the first run's reads with its own and prints the first run's verdict beside the pooled one. Spec: [docs/specs/reader-panel.md](../specs/reader-panel.md) § 3.2.
- The headroom check: a rule's PASS through a `score at least` clause is INCONCLUSIVE when the strong anchor's median score is not above the version's, or when the lens has fewer than 3 valid strong-anchor reads to tell. Spec: [docs/specs/reader-panel.md](../specs/reader-panel.md) § 6.
- `anchor-reads-per-reader` now defaults to 2, where it was 1, so that two readers give the 4 reads of each anchor that the headroom check can use. Spec: [docs/specs/reader-panel.md](../specs/reader-panel.md) § 3.1.
