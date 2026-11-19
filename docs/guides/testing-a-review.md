# Testing a review

A review is anything that reads a draft and tells you what is wrong with it: a person, a prompt to a language model, a checklist. Method rule 6 ([METHOD.md](../../METHOD.md)) asks that a tool be measured on cases with known answers, and that a check that finds nothing show it was looking. This guide applies that to a reviewer. It describes a way of working. No command in this repository grades a reviewer. Where a shipped command does part of the job, the page cites its spec.

## Plant the flaws

Take a draft and put flaws in it on purpose: a figure with no source, a verb stronger than the record allows, a title that differs from the offer letter, a paragraph that repeats another. Keep a list of what you planted. This is the answer key. Also keep a few cases with nothing planted, because a reviewer that finds a problem in a clean draft is wrong in a different way.

Then run the reviewer and score three things:

- **Found.** How many of the planted flaws it named.
- **Invented.** How many problems it named that aren't in the draft, or quoted a line that isn't there.
- **Complete.** Whether its output has each part you asked for. A reviewer told to give a finding, a quoted line and a fix has missed a part when a finding has no quoted line.

Invented example. A draft for a records clerk has three planted flaws: "managed 40 files a day" with no source, "supervised" where the record says "assisted", and a start date a month off. The reviewer names the first and third, and adds a fourth problem, "the summary is too long", which isn't a flaw you planted but is arguable. You score two found, one missed and one claim to look at by hand. Add a column for arguable findings so you decide them the same way each time.

Fix the case set before you run it, and fix how it divides: one half to tune the reviewer on, one half held out. Hash the case files so a later change shows. The tool already works this way for its own plans: `ab` and `panel` hash the plan and each file it names before the first read, and a run refuses a changed file ([ab](ab.md), [panel](panel.md)). Don't tune on the held-out half. If you do, it's no longer held out, and the score on it tells you about your tuning.

For a tool that drafts text, add a stricter rule: any sentence whose fact isn't in the facts you supplied fails that case. A drafter that adds a fact has failed, whatever else it did well. This matches the record's rule for a claim: a claim without a link is flagged, not trusted ([METHOD.md](../../METHOD.md), rule 5).

## The rubric

Grade the reviewer on a table. A pass on a row needs a cited line, as in [scoring](scoring.md): a pass that points at no line counts as a fail.

| Row | The question |
| --- | --- |
| Grounded in the text | Does each finding point at words in the draft? |
| Nothing invented | Is each quoted line on the page, and each fact in the supplied facts? |
| Stays in its own lane | Does it do the job it was given and not another? A fact check isn't a style edit. |
| Follows its stated output | Does the reply have the parts you asked for, in the form you asked for? |
| Calibrated | Does it say the draft is clean when it is, and report findings when they're real? |

## The judge is not the author

If a model scores or reviews drafts, don't let the model that wrote a draft be the one that judges it. A model can prefer wording of its own family. The shipped tools address part of this. `ab` records which model family drafted each version and which family each reader is. When a verdict would favour a version that a model of a reader's own family drafted or edited, readers of another family have to agree before the verdict stands ([docs/specs/reader-ab.md](../specs/reader-ab.md), lines 14 and 59). The rule asks for agreement from another family. It doesn't bar a reader from reading its own family's work.

Before a judge scores anything that counts, run it on outputs whose answers you know. Include a case where the right answer is "cannot tell": two drafts that are the same, or a draft that you can't judge without a document the reader wasn't given. A judge that picks a winner there is overconfident, and you want to learn that before it scores your real draft. The control that must be found ([METHOD.md](../../METHOD.md), rule 6) is the shipped form of the same idea: `ab` puts one version in both slots, and a plan may add a copy weakened on purpose ([docs/specs/reader-ab.md](../specs/reader-ab.md), lines 33-34). Running a judge on cases with known answers, and the "cannot tell" case, are for you to do by hand.

## What is shipped and what isn't

| Part | Runs in a command? |
| --- | --- |
| A plan and its files hashed before the first read | Yes: `ab`, `panel` |
| A planted strong and weak document read through each lens | Yes: `panel` (`docs/specs/reader-panel.md:32-33`) |
| A reader's model family declared; another family to agree | Yes: `ab` (`docs/specs/reader-ab.md`, sections 3.1 and 6) |
| A control that must be found | Yes: `ab` and `panel` (`METHOD.md`, rule 6) |
| Planted flaws in your own draft, found/invented/complete scoring | No |
| A held-out half of the cases | No |
| A judge run on known answers, including "cannot tell" | No |
