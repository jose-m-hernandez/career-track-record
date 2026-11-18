# Grading a source

Method rule 3 ([METHOD.md](../../METHOD.md)) asks that each fact carry a grade for its source. This guide is about how to choose that grade. It adds no command. The record check reads the grade column and holds you to your own list of allowed grades; it doesn't read a source or judge one ([docs/record-model.md](../record-model.md), lines 77-79 and 113).

## What a grade measures

A grade says how well a stranger could re-check the source. It doesn't say how sure you feel. You can be certain of a date and still hold a poor source for it, and a grade that followed your confidence would rise and fall with your mood while the evidence stayed put.

Four questions decide a grade:

1. **Can it be reopened?** Is there a file, a page or a document that the stranger could open today, without asking you?
2. **Can it be quoted?** Is there a phrase in it that supports the fact, so the stranger can find the words rather than take your reading of them?
3. **Can it be dated?** Does it say when it was written or signed, or can that be shown another way?
4. **Is it owned by someone other than you?** An offer letter was written by an employer. A note you made from memory was written by you.

The more of these a source answers with a plain yes, the higher it grades. The questions decide the order of your grades and nothing more. The letters, and what each one means, are your list to write: the record check takes the values you allow (`values: entries | grade | A | B | C | D` in the example at `docs/record-model.md:77-79`) and flags a grade outside them (`docs/record-model.md:113`). Your list sets their order too. This guide's examples read it as the example list does, `A` highest; the record check checks only that a grade is on your list (`docs/record-model.md:113`), not that one letter is above another.

Invented example. A fact says a team had six engineers. One source is a signed offer letter that you can reopen, that has a line saying "a group of six engineers", that carries a date and that an employer wrote: four yeses. Another source is your memory of a hallway conversation: none. They differ by a wide margin even if you feel equally sure of both.

## What someone tells you

What a person tells you goes in at a low grade, however much you trust them. A former colleague says your title was "Lead", and nothing you can reopen says so. The fact is worth entering, at the lowest grade your list has for a spoken word.

In this method, a grade rises when a source that can be reopened backs it. The record check doesn't enforce this; it sees only the rows you write. Say the colleague's message later turns up in your email, or a company page lists the title. The rise follows rule 1 ([METHOD.md](../../METHOD.md), "Never overwrite"): you add a new entry, at the higher grade, that points at the old one and says what backed it. The first entry stays where it was, at its low grade, so a reader can see what was believed and when it changed. The record check treats this as it treats any correction: the new row says which row it corrects, and sits after it (`docs/record-model.md:90-93`).

Invented example. Entry 14 says "title: Lead", grade D, source "a colleague's message, remembered". Entry 31 corrects entry 14. It says "title: Lead", grade B, source "company page, saved 2026-02-01", reason "the page lists the title". Entry 14 is unedited.

## A number has its own source

A figure inside a fact is a fact of its own. "Cut the backlog by forty percent" holds a claim about what happened and a number, and the number needs a source that shows forty, not a source that shows only that a backlog existed.

A well-sourced sentence doesn't lift a figure that has no source of its own. If the project page you can reopen says the team "cleared the backlog" and says nothing of forty percent, the sentence has a good source and the number has none. Grade the number by what backs it. If that is your own estimate, grade it as your own estimate, and enter it as a separate fact so that its grade shows. A résumé line built from it is only as firm as that weakest part.

## What this guide doesn't do

- It doesn't choose your letters or what they mean.
- No command computes a grade from the four questions. You answer them and enter the result.
- The record check confirms that a grade is present and is one of your allowed values. It doesn't confirm that the grade is right, because it doesn't read the source (`docs/record-model.md:120`).
