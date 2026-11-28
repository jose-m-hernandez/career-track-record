# Provenance

This ledger lists every file in the repository once, with the harness and model recorded writing to it and the day (UTC) of the latest recorded write. A filled row names every harness and model that the maintainer's local session records show writing to the file. It does not say who created the file, or that nothing else wrote to it. `not recorded` means those records hold no write to the file; most files written before 2026-11-01 have none. A change that adds or edits a file updates that file's row in the same change. `tests/test_provenance.py` fails if a file has no row, a row has no file, or the table has any column other than these four. The ledger lists itself.

| path | harness | model | date |
| --- | --- | --- | --- |
| .github/CODEOWNERS | not recorded | not recorded | not recorded |
| .github/ISSUE_TEMPLATE/bug_report.md | claude-code | claude-sonnet-5-5 | 2026-11-21 |
| .github/ISSUE_TEMPLATE/feature_request.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| .github/pull_request_template.md | not recorded | not recorded | not recorded |
| .github/workflows/ci.yml | claude-code | claude-sonnet-5-5 | 2026-11-21 |
| .gitignore | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| AGENTS.md | claude-code | claude-fable-5-1, claude-sonnet-5-5 | 2026-11-20 |
| CHANGELOG.md | claude-code | claude-fable-5-1, claude-fable-5-2, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-27 |
| CODE_OF_CONDUCT.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| CONTRIBUTING.md | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| LICENSE | not recorded | not recorded | not recorded |
| LICENSE-COMMERCIAL.md | not recorded | not recorded | not recorded |
| METHOD.md | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| README.md | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| SECURITY.md | not recorded | not recorded | not recorded |
| SUPPORT.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| ci/__init__.py | not recorded | not recorded | not recorded |
| ci/barred_strings.py | not recorded | not recorded | not recorded |
| ci/forced_failures.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-23 |
| ci/hygiene.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-23 |
| ci/requirements-build.txt | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| docs/decisions/2026-10-19-claude-md-is-a-one-line-bridge-to-agents-md.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-19-the-changelog-follows-keep-a-changelog-and-semver.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-19-what-was-read-of-career-ops-and-how-it-reached-this-repo.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-27-a-test-modules-main-guard-is-last.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-27-agents-md-is-the-only-instruction-file.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-27-committed-files-are-utf-8.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-27-known-limits-sit-beside-their-tests.md | claude-code | claude-opus-5-5 | 2026-11-05 |
| docs/decisions/2026-10-27-one-module-per-outside-program.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-29-a-reader-command-is-the-one-outside-program-a-user-names.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-11-01-every-file-has-a-provenance-row.md | claude-code | claude-sonnet-5-5 | 2026-11-01 |
| docs/decisions/2026-11-05-the-reader-commands-share-one-harness.md | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-14 |
| docs/decisions/2026-11-14-every-date-a-change-writes-is-the-utc-day.md | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| docs/decisions/2026-11-14-no-file-ships-with-a-sentence-still-to-be-worded.md | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| docs/guides/ab.md | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| docs/guides/absence.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| docs/guides/barred.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| docs/guides/claims.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| docs/guides/drafts.md | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| docs/guides/grades.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| docs/guides/keywords.md | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| docs/guides/panel.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| docs/guides/parse.md | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| docs/guides/recall.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| docs/guides/record.md | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| docs/guides/scoring.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| docs/guides/setup.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| docs/guides/structure-read.md | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| docs/guides/tailoring.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| docs/guides/testing-a-review.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| docs/guides/tone.md | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| docs/guides/wrapped-compounds.md | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| docs/provenance.md | claude-code | claude-fable-5-1, claude-fable-5-2, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| docs/record-model.md | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| docs/review.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| docs/specs/absence.md | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| docs/specs/barred.md | claude-code | claude-fable-5-2, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-14 |
| docs/specs/claims.md | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| docs/specs/cli.md | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| docs/specs/drafts.md | claude-code | claude-sonnet-5-5 | 2026-11-17 |
| docs/specs/keyword-scan.md | claude-code | claude-sonnet-5-5 | 2026-11-17 |
| docs/specs/parse.md | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| docs/specs/reader-ab-aa-band.md | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| docs/specs/reader-ab.md | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-17 |
| docs/specs/reader-panel.md | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-19 |
| docs/specs/record-check.md | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| docs/specs/series.md | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| docs/specs/tone-and-tells.md | claude-code | claude-opus-5-5 | 2026-11-05 |
| docs/specs/wrapped-compounds.md | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| examples/ab-fake-plan.txt | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| examples/ab-first-plan.txt | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| examples/ab-first/posting.txt | claude-code | claude-sonnet-5-5 | 2026-11-17 |
| examples/ab-first/resume-base.txt | claude-code | claude-sonnet-5-5 | 2026-11-17 |
| examples/ab-first/resume-skills-top.txt | claude-code | claude-sonnet-5-5 | 2026-11-17 |
| examples/good.pdf | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| examples/keywords/postings/care-manager.txt | claude-code | claude-sonnet-5-5 | 2026-11-17 |
| examples/keywords/postings/care-manager.txt.meta.json | claude-code | claude-sonnet-5-5 | 2026-11-17 |
| examples/keywords/postings/support-lead.txt | claude-code | claude-sonnet-5-5 | 2026-11-17 |
| examples/keywords/resume.txt | claude-code | claude-sonnet-5-5 | 2026-11-17 |
| examples/keywords/terms.tsv | claude-code | claude-sonnet-5-5 | 2026-11-17 |
| examples/readers/model_reader.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-19 |
| pyproject.toml | not recorded | not recorded | not recorded |
| setup.cfg | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| src/career_track_record/__init__.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-23 |
| src/career_track_record/__main__.py | not recorded | not recorded | not recorded |
| src/career_track_record/ab.py | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-19 |
| src/career_track_record/ab_reader_command.py | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| src/career_track_record/absence.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| src/career_track_record/barred.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-14 |
| src/career_track_record/claims.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| src/career_track_record/cli.py | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| src/career_track_record/config.py | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| src/career_track_record/data/section-names.txt | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| src/career_track_record/data/tone-default.json | not recorded | not recorded | not recorded |
| src/career_track_record/drafts.py | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| src/career_track_record/keywords.py | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| src/career_track_record/panel.py | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-19 |
| src/career_track_record/parse.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| src/career_track_record/pdf_text.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-05 |
| src/career_track_record/posting_file.py | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| src/career_track_record/quote_check.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-05 |
| src/career_track_record/reader_harness.py | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-19 |
| src/career_track_record/record_check.py | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| src/career_track_record/record_folder.py | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| src/career_track_record/series.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| src/career_track_record/setup_cmd.py | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| src/career_track_record/stats.py | claude-code | claude-sonnet-5-5 | 2026-11-10 |
| src/career_track_record/tone.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| src/career_track_record/wrapped_compounds.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| src/career_track_record/write_guard.py | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| tests/__init__.py | not recorded | not recorded | not recorded |
| tests/fixtures/ab/base-weak.txt | claude-code | claude-sonnet-5-5 | 2026-11-10 |
| tests/fixtures/ab/base.txt | not recorded | not recorded | not recorded |
| tests/fixtures/ab/golden/10-1.txt | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/ab/golden/10-11.txt | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/ab/golden/10-8.txt | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/ab/golden/10-9.txt | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/ab/posting.txt | not recorded | not recorded | not recorded |
| tests/fixtures/ab/skills-top-short.txt | not recorded | not recorded | not recorded |
| tests/fixtures/ab/skills-top.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/bom.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/canary.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/case.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/clean.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/compound.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/decomp.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/early.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/emdash.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/endash.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/fold.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/footnote.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/hyph.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/hyphcr.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/hyphcrlf.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/hyphff1.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/hyphff2.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/hyphkeep.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/hyphkeepcrlf.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/hyphmid.pdf | not recorded | not recorded | not recorded |
| tests/fixtures/barred/hyphsp.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/lig.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/lines.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/list-l1.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/list-l2.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/list-l3.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/list-l4.txt | claude-code | claude-opus-5-5 | 2026-11-05 |
| tests/fixtures/barred/lrm.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/make_fixtures.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-19 |
| tests/fixtures/barred/moonshot-notes.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/moonshot-plain.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/moonshot-short.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/nbhyph.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/nbsp.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/nlnote.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/nocontrol.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/nokeep.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/note.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/page3wrap.pdf | claude-code | claude-opus-5-5 | 2026-11-05 |
| tests/fixtures/barred/pagewrap.pdf | claude-code | claude-opus-5-5 | 2026-11-05 |
| tests/fixtures/barred/plain.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/prefix-notes.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/sample.pdf | not recorded | not recorded | not recorded |
| tests/fixtures/barred/short.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/shyalone.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/barred/shycomment.ts | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/barred/shyend.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/barred/shyendcr.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/barred/shyendcrlf.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/barred/shyendsp.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/barred/shyline.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/barred/shymid.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/barred/shynonword.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/barred/shyspace.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/barred/single.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/soft.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/softhyph.pdf | claude-code | claude-opus-5-5 | 2026-11-05 |
| tests/fixtures/barred/spcolon.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/src.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/strblock.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/strip.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/substr.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/trim.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/two.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/twocol.pdf | claude-code | claude-opus-5-5 | 2026-11-05 |
| tests/fixtures/barred/unterm.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/url.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/value.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/word.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/word2.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/wrap.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/zw.txt | not recorded | not recorded | not recorded |
| tests/fixtures/drafts/README.md | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/drafts/letter-before.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/drafts/letter-edited.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/drafts/letter.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/keywords/copy.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/copy2.ts | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/copy3.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/copy4.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/make_fixtures.py | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-d/2026-01-15-example-d.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e10/2026-01-15-edge-01.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e10/2026-01-15-edge-02.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e10/2026-01-15-edge-03.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e10/2026-01-15-edge-04.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e10/2026-01-15-edge-05.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e10/2026-01-15-edge-06.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e10/2026-01-15-edge-07.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e10/2026-01-15-edge-08.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e10/2026-01-15-edge-09.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e10/2026-01-15-edge-10.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e7/2026-01-15-edge-01.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e7/2026-01-15-edge-02.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e7/2026-01-15-edge-03.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e7/2026-01-15-edge-04.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e7/2026-01-15-edge-05.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e7/2026-01-15-edge-06.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e7/2026-01-15-edge-07.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e8/2026-01-15-edge-01.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e8/2026-01-15-edge-02.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e8/2026-01-15-edge-03.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e8/2026-01-15-edge-04.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e8/2026-01-15-edge-05.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e8/2026-01-15-edge-06.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e8/2026-01-15-edge-07.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-e8/2026-01-15-edge-08.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-p1-ab/2026-01-15-example-a.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-p1-ab/2026-01-15-example-b.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-p1/2026-01-15-example-a.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-p1/2026-01-15-example-b.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-p1/2026-01-15-example-c.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-raw-crlf/2026-01-15-example-r.txt | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/postings-raw-crlf/2026-01-15-example-r.txt.meta.json | not recorded | not recorded | not recorded |
| tests/fixtures/keywords/terms-t1.tsv | not recorded | not recorded | not recorded |
| tests/fixtures/panel/anchor-strong.txt | claude-code | claude-fable-5-1 | 2026-11-05 |
| tests/fixtures/panel/anchor-weak.txt | claude-code | claude-fable-5-1 | 2026-11-05 |
| tests/fixtures/panel/golden/10-1.txt | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/fixtures/panel/golden/10-3.txt | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/fixtures/panel/hiring-manager.lens.txt | claude-code | claude-fable-5-1 | 2026-11-05 |
| tests/fixtures/panel/recruiter.lens.txt | claude-code | claude-fable-5-1 | 2026-11-05 |
| tests/fixtures/record/README.md | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/record/known/entry-table-before.tsv | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/record/known/entry-table.tsv | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/record/known/origin-table.csv | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/record/known/record.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/record/sentinel/entry-table-before.tsv | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/record/sentinel/entry-table.tsv | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/record/sentinel/origin-table.csv | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/record/sentinel/record.txt | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/fixtures/resolution/base-help.json | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/fixtures/resolution/base-outputs.json | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/fixtures/tone/case-11-01.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-03.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-04.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-05.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-06.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-07.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-08.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-09.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-10.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-11.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-12.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-23.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-24.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-25.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-26.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-27.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-28.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-29.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-30.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-31.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-32.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-33.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/case-11-37.txt | not recorded | not recorded | not recorded |
| tests/fixtures/tone/make_fixtures.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| tests/fixtures/tone/rules-r1.json | not recorded | not recorded | not recorded |
| tests/fixtures/tone/rules-r2.json | not recorded | not recorded | not recorded |
| tests/live_profile_check.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_ab.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-17 |
| tests/test_ab_document.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-14 |
| tests/test_ab_escape.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-17 |
| tests/test_ab_live.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-16 |
| tests/test_ab_reader_command.py | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| tests/test_ab_rev2.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-14 |
| tests/test_ab_rev3.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-17 |
| tests/test_ab_rev4.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-15 |
| tests/test_ab_rev4_runs.py | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| tests/test_ab_rev5_series.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_ab_rev5_series_recheck.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_ab_rev5_tie.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_ab_run_failures.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-14 |
| tests/test_ab_vr1.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-17 |
| tests/test_ab_vr2.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-16 |
| tests/test_absence.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/test_absence_pdf.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/test_barred.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-18 |
| tests/test_barred_pdf_layout.py | claude-code | claude-opus-5-5 | 2026-11-05 |
| tests/test_barred_soft_hyphen.py | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/test_barred_strings.py | claude-code | claude-sonnet-5-5 | 2026-11-21 |
| tests/test_claims.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| tests/test_claims_require_sources.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/test_claims_runs.py | claude-code | claude-sonnet-5-5 | 2026-11-04 |
| tests/test_claims_sources.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| tests/test_cli.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| tests/test_config.py | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| tests/test_doc_cites.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-23 |
| tests/test_docs_0_14_2.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/test_drafts.py | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/test_drafts_docs.py | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| tests/test_drafts_inputs.py | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/test_example_keywords.py | claude-code | claude-sonnet-5-5 | 2026-11-17 |
| tests/test_example_reader.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/test_forced_failures.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-23 |
| tests/test_freeze_reader_warning.py | claude-code | claude-sonnet-5-5 | 2026-11-17 |
| tests/test_help_lines.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/test_keywords.py | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| tests/test_live_profile_check.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_no_network.py | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| tests/test_output_failures.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/test_packaging.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_panel.py | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-19 |
| tests/test_panel_rev2.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_panel_rev3.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_panel_rev4.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_panel_rev4_runs.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_parse.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_parse_pdf.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_pdf_text.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| tests/test_placeholders.py | claude-code | claude-sonnet-5-5 | 2026-11-14 |
| tests/test_posting_file.py | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| tests/test_provenance.py | claude-code | claude-sonnet-5-5 | 2026-11-01 |
| tests/test_quote_check.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-05 |
| tests/test_reader_contract.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/test_reader_profile.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/test_readme_diagram.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/test_readme_truth.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| tests/test_record_check.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_record_check_inputs.py | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| tests/test_record_docs.py | claude-code | claude-sonnet-5-5 | 2026-11-16 |
| tests/test_record_folder.py | claude-code | claude-sonnet-5-5 | 2026-11-21 |
| tests/test_resolution.py | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| tests/test_review_method.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/test_setup.py | claude-code | claude-sonnet-5-5 | 2026-11-21 |
| tests/test_source_hygiene.py | not recorded | not recorded | not recorded |
| tests/test_spec_readings.py | claude-code | claude-sonnet-5-5 | 2026-11-20 |
| tests/test_spec_revisions.py | claude-code | claude-fable-5-1, claude-fable-5-2, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-20 |
| tests/test_stats.py | claude-code | claude-sonnet-5-5 | 2026-11-10 |
| tests/test_test_hygiene.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-23 |
| tests/test_tone.py | claude-code | claude-sonnet-5-5 | 2026-11-18 |
| tests/test_tone_pdf.py | not recorded | not recorded | not recorded |
| tests/test_wrapped_compounds.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_wrapped_compounds_pdf.py | claude-code | claude-sonnet-5-5 | 2026-11-19 |
| tests/test_write_recheck.py | claude-code | claude-sonnet-5-5 | 2026-11-18 |
