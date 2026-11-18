# Recall tests

Two checks use memory in place of a score. One asks what you remember of your own record. The other asks what a reader remembers of your draft. Both are ways of working. No command runs either, and this guide says where the nearby shipped commands stop.

## Quiz yourself on your record

Before an interview, ask yourself questions about your own work and answer them aloud or on paper without looking: what the figure was, who the stakeholder was, what you decided and why, what went wrong. Then check each answer against the record. Where your answer and the record disagree, the record is the thing to read again, and, if the record is wrong, to correct as a new entry ([METHOD.md](../../METHOD.md), rule 1).

Keep each good answer as a case you can reuse: the question, the answer, and the entry it rests on. The next time a posting asks for something similar, the case is ready, and you know which fact supports it. Invented example: the question "What changed in the archive after your project?" and the answer "Retrieval time dropped from about nine minutes to about two, measured over the month after", with the entry that holds the measurement.

## Ask the reader what stuck

A reader who has finished your draft remembers some things and not others. After a cold read, ask the reader which version's content they remember: which jobs, which results, which figures. Do this before you tell them what the two versions are meant to do, and without showing the draft again.

Compare the versions by what stuck, not by what was liked. A reader may say they prefer the second version and then recall nothing from it. A version whose results are remembered has done a different job from one that was pleasant to read. The two answers can disagree, and when they do, both are worth a note.

How this fits with the tools:

- The readers of `panel` and `ab` are a command you name ([panel](panel.md); [ab](ab.md)). A command can be written to ask a recall question after a read. The tools don't ask one themselves: the `ab` reader scores one version against another, and the `panel` reader scores a document. The reply parts the panel reads are `READ` and `SCORE` and any fields the plan names ([docs/specs/reader-panel.md](../specs/reader-panel.md), line 122).
- Freeze your plan before any read, as `ab` does with its hashes ([ab](ab.md)). If you decide after you see the recall answers which question counts, the result is yours, not the reader's. Write the recall question down before any read, beside the frozen plan, and have the reader command ask it in a second step, after the read's reply, so the question is not in the prompt the reader reads with. Keep both replies as the record of what it said.

A reader that has been told the question can look for the answer. The method is meant for a cold reader. If a recall question appears in the prompt before the reading, it measures what the reader looked for.
