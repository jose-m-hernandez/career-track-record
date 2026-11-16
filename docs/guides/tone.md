# `track-record tone`

Run the voice and tone check over your copy to find hype, hedges and filler:

    track-record tone resume.md letter.md

It checks each file against a rule file of phrasings to avoid, each set as an `error` or a `warn`; without `--rules`, the shipped default rules run. Every finding names the sentence and the rule's reason, and only `error` rules fail a run. The check never edits a file or suggests a replacement. A file whose name ends in `.pdf` (any case) is checked as the text `pdftotext` extracts from it, as written, so case-sensitive rules still apply.

To make your own rules, start from the defaults:

    track-record tone --print-defaults > tone-rules.json
    track-record tone --rules tone-rules.json resume.md letter.md

Before any file is read, each rule is tested against its own examples, so a broken rule stops the run instead of passing everything. An exemption lets one `error` rule pass a piece of wording you quote exactly, and the same wording anywhere else still fails.

Add `--warn-only` to run only the `warn` rules, and `--stale-check` to report exemptions whose wording appears in none of the files you name; a stale exemption counts as an error. Exit 0 means no errors (warnings allowed), 1 means at least one error, and 2 means the check couldn't run. Spec: [docs/specs/tone-and-tells.md](../specs/tone-and-tells.md).
