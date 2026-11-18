# Scoring a draft with readers

A reader gives a draft a score. This guide is about how far to trust a score, and what to put beside it so you can tell. The two tools that collect scores are described in [panel](panel.md) and [ab](ab.md). Where this page describes something they run, it cites the spec. Where it describes a way of working that no command runs, it says so.

## The anchors are the shipped check

Before you trust what a reader says about your draft, find out whether the reader can tell a strong draft from a weak one. The panel does this for you. Every lens also reads two documents you supply: one you wrote to be plainly strong for the posting, and one you wrote to be plainly weak. A lens that doesn't score the strong one at or above your threshold, and the weak one at or below yours, has its reads of your draft reported INCONCLUSIVE and left out of the count ([docs/specs/reader-panel.md](../specs/reader-panel.md), lines 32-33).

Invented example. You write a posting for a records clerk. Your strong anchor is a résumé that matches it line by line, and your weak anchor is a résumé for a pastry chef. A reader scores them 9 and 2, and the thresholds you set are 7 and 4. The reader can see a difference, so its reads of your real draft count. A reader that scores both at 7 can't see one, and what it says about your draft isn't evidence.

The panel reads the anchors through every lens in every run (spec lines 32-33). The rest of this page covers the case where the anchors pass and the scores still don't separate your draft's strengths from its weaknesses.

## A saturated scale

A scale is saturated when the scores bunch near the top and stop telling drafts apart. A reader that gives 8 to a good draft, 8 to a better one and 8 to a poor one is saturated, and no verdict built on those scores means much. Put a best draft and a worst draft that you invent through the same readers, as you do with anchors. If the scores don't separate them, treat the verdict on your real draft as untrusted. The panel's anchor gate runs this test for its own lenses (spec lines 32-33). For any other score you collect, you run it yourself: no command does.

## Read three times, take the middle score, and name a score gap

One read of one draft is a single sample, and a reader's score on the same draft can move from read to read. A way to steady it is to read the draft three times and take the middle score, the median. The panel reads a version three times per lens by default ([panel](panel.md), line 31). It then counts reads against the rules you froze in the plan. It doesn't compute a median or a gap, so this part is for you to do by hand.

Two versions whose middle scores sit within a gap you state in advance count as a tie. Call that gap the **score gap**. Invented example: you decide on a score gap of one point. Version A reads 7, 7, 8 (middle 7) and version B reads 6, 8, 8 (middle 8). They are one point apart, so they tie, and you don't call B the winner on one point. Write the gap down before you see the scores, as the plan's rules are written before any read.

The score gap is a different test from the A/A control. The A/A control puts one version in both slots and measures how often a reader picks a side when there is nothing to find ([docs/specs/reader-ab.md](../specs/reader-ab.md), section 2). It isn't a tolerance on scores. The two are used together. The A/A control tells you how noisy a reader is on identical drafts, and the score gap tells you how much of a score difference to ignore.

## A rubric is a set of gates

If you grade a draft against a list of criteria (a clear opening, a figure on each bullet, a stated result), treat each criterion as a gate that passes or fails, and ask the reader to cite the line it relied on. A pass that cites no line counts as a fail. A reader can say "the opening is clear" about any opening. It can't quote one that isn't there.

Invented example. Criterion 2 is "each role names a result". The reader answers "pass" and gives no line. That is a fail. Another reader answers "pass: 'Cut intake time from nine days to four'" and the line is on the page. That is a pass. No command applies this rule; you read the replies and mark them. [Testing a review](testing-a-review.md) uses the same rule to grade a reviewer.

## When scores bunch, count the line

When the scores sit close together near the top, they can't separate drafts, but the replies can. Ask each reader which line is weakest, or which would be cut first, and count how many reads name the same line, across readers and across passes. Three of three readers naming the bullet about "team lunches" is a signal that a score of 8 doesn't carry. Reads that scatter across the page are a different result: no line is the problem. The count of lines by read is positional, which scores are not. No command makes this count; it is a tally you keep.

## What is shipped and what isn't

| Part | Runs in a command? |
| --- | --- |
| Strong and weak anchors, and the anchor gate | Yes: the panel (`docs/specs/reader-panel.md:32-33`) |
| Reads of a reader marked `not-blind` left out of the verdicts | Yes: the panel (`docs/specs/reader-panel.md:126`) |
| A pick counts when both read orders agree | Yes: `ab` (`docs/specs/reader-ab.md`, section 6) |
| A/A control and sensitivity control | Yes: `ab` (`docs/specs/reader-ab.md`, section 2) |
| Median of three reads and the score gap | No |
| Best and worst draft through your own scores | No, outside the panel's anchors |
| Rubric gates with a cited line | No |
| Counting the line named weakest | No |
