# Method: keeping a career record you can trust

A career record is assembled from sources that disagree: two résumés with different start dates, a title that changed mid-year, a number remembered one way and printed another. The method is how the record stays useful when that happens. It's six rules.

Status: the barred-wording check, the keyword scan, the voice and tone check, the claim gate and the reader panel run rule 6. Reader A/B runs rule 6's fixed cases, and its isolation check runs on every plan. Its reads always carry an A/A control (a read of one draft against itself), which measures how often readers pick a side on identical drafts. A plan may add a control that must be found: a copy of a draft weakened on purpose, which readers should rank below the draft. Each result reports both, and the evidence beside each verdict. A run without that second control that finds no difference does not show the readers could have found one. On request (`--check-sources`), the claim gate checks that each quote on an approved or proposed entry appears word for word in the local file the entry cites; it does not yet flag a claim with no source. The record check (`track-record record`) checks rules 1 to 4 as far as a table can show them; [docs/record-model.md](docs/record-model.md) says what it checks and what it can't.

## 1. Never overwrite

Every fact (an entry in the record) is appended with its source and the date it was recorded. A correction is a new entry that points at the entry it corrects and says why. Nothing is edited in place, so the history of a fact is always there to read: what was believed, what replaced it, and on what evidence.

How a correction is stored and checked: [docs/record-model.md](docs/record-model.md).

Example (invented): a fact says a role started in March 2019. A later entry corrects it to April 2019, citing the offer letter, and the March entry stays where it was.

## 2. Don't force one answer

When sources disagree, the record holds a resolution: the value it settles on, the basis for it, and how firm it is. Some conflicts settle cleanly. Others don't, and the honest resolution is a range or a coarser value.

Example (invented): one résumé says a job started 2014-03-01, another says June 2014, and a reference letter says "spring 2014". The resolution is "2014, spring", with all three sources attached. A precise date the evidence doesn't support is worse than a coarse one it does.

Keep the argument apart from the answer. The resolution is short and machine-readable; the reasoning behind it lives in its own note.

## 3. Grade every source

A signed offer letter, an old résumé, a colleague's memory and a model's summary aren't equally strong. Each fact carries a grade for its source, and the grade travels with the fact into every output, so that a later tool, or you, can leave out a claim below a chosen grade and list the weakest claims first.

How to choose a grade: [docs/guides/grades.md](docs/guides/grades.md).

## 4. Keep two clocks

A record answers two different questions:

- **What is true?** Apply every correction, whenever it was made.
- **What did the record say on a given date?** Apply only the corrections made by that date.

Both come up. The first is what you publish. The second lets anyone check an earlier report against the record as it stood that day.

## 5. Point every claim to its source

A claim is a fact as it appears on a résumé or a profile. Each claim links back to the facts behind it. A quoted phrase only counts as verified once a check has found it, word for word, in the source it cites. A claim with no link is flagged, not trusted.

How far a claim stands, and what a suggested link is worth: [docs/guides/claims.md](docs/guides/claims.md). Tailoring a draft to a posting from approved claims: [docs/guides/tailoring.md](docs/guides/tailoring.md). Reading a draft for order before editing it, without inventing a fact to fill a gap: [docs/guides/structure-read.md](docs/guides/structure-read.md).

## 6. Test before you trust

Changes to a tool are measured against a fixed set of invented cases with known answers: planted conflicts, missing sources, a quote that doesn't appear in its source. A change that misses a case it used to catch doesn't ship. A check that finds nothing also has to show it was looking: every run includes a control that must be found, so a silent tool can't pass for a clean result.

Testing a reviewer on planted flaws: [docs/guides/testing-a-review.md](docs/guides/testing-a-review.md). How far to trust a reader's score: [docs/guides/scoring.md](docs/guides/scoring.md). Reading a draft through five hiring viewpoints and confirming each flag: [docs/guides/panel.md](docs/guides/panel.md). Memory as a test, of your record and of a reader: [docs/guides/recall.md](docs/guides/recall.md).

## What this method doesn't do

It doesn't decide for you. When the evidence won't settle a conflict, the record says so and shows each candidate with its sources. Picking one is yours.
