# `track-record panel`

Read one version of a résumé, or any career document, through several lenses: each a reader in a role you name, such as a recruiter or the hiring manager, given as a plain-text prompt file you write. Readers are the same as in `track-record ab`: a command you name, or the built-in `fake`. The plan is frozen by hash before the first read, lens files included.

Every lens also reads two anchors you supply: a document you wrote to be plainly strong for the posting, and one you wrote to be plainly weak. If a lens does not score the strong anchor at or above `anchor-strong-at-least` and the weak anchor at or below `anchor-weak-at-most`, on every anchor read, that lens's reads of your version are reported INCONCLUSIVE and not counted. The anchors do for the panel what the control read does for `ab`: a lens that shows nothing also shows whether it could see anything. This plan is invented:

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
  reader-2 | /path/to/my-reader.sh | cost 3
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

Each reader reads the version three times per lens and each anchor once, unless the plan says otherwise. A rule names its lens, or `overall` for every counted lens, and tests scores or flagged fields: a field such as `DOUBTS` is flagged when the reader wrote anything there but `none`. The reader sees the posting, the lens and one document, and nothing says whether that document is an anchor or your version.

The tool has the same three subcommands as `ab`:

    track-record panel freeze plan.txt
    track-record panel run plan.txt [--live]
    track-record panel score plan.txt

The `--live` rule, the spend ceiling, the `fake` reader and the exit codes are those of `ab`. The spec is signed (revision 3). Spec: [docs/specs/reader-panel.md](../specs/reader-panel.md).
