# Provenance

This ledger lists every file in the repository once, with the harness and model recorded writing to it and the day (UTC) of the latest recorded write. A filled row names every harness and model that the maintainer's local session records show writing to the file. It does not say who created the file, or that nothing else wrote to it. `not recorded` means those records hold no write to the file; most files written before 2026-11-01 have none. A change that adds or edits a file updates that file's row in the same change. `tests/test_provenance.py` fails if a file has no row, a row has no file, or the table has any column other than these four. The ledger lists itself.

| path | harness | model | date |
| --- | --- | --- | --- |
| .github/CODEOWNERS | not recorded | not recorded | not recorded |
| .github/pull_request_template.md | not recorded | not recorded | not recorded |
| .github/workflows/ci.yml | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| .gitignore | not recorded | not recorded | not recorded |
| AGENTS.md | claude-code | claude-fable-5-1, claude-sonnet-5-5 | 2026-11-05 |
| CHANGELOG.md | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-05 |
| CONTRIBUTING.md | claude-code | claude-sonnet-5-5 | 2026-11-01 |
| LICENSE | not recorded | not recorded | not recorded |
| LICENSE-COMMERCIAL.md | not recorded | not recorded | not recorded |
| METHOD.md | claude-code | claude-fable-5-1, claude-sonnet-5-5 | 2026-11-05 |
| README.md | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-05 |
| SECURITY.md | not recorded | not recorded | not recorded |
| ci/__init__.py | not recorded | not recorded | not recorded |
| ci/barred_strings.py | not recorded | not recorded | not recorded |
| ci/requirements-build.txt | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-19-claude-md-is-a-one-line-bridge-to-agents-md.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-19-the-changelog-follows-keep-a-changelog-and-semver.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-19-what-was-read-of-career-ops-and-how-it-reached-this-repo.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-27-a-test-modules-main-guard-is-last.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-27-agents-md-is-the-only-instruction-file.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-27-committed-files-are-utf-8.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-27-known-limits-sit-beside-their-tests.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-27-one-module-per-outside-program.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-10-29-a-reader-command-is-the-one-outside-program-a-user-names.md | not recorded | not recorded | not recorded |
| docs/decisions/2026-11-01-every-file-has-a-provenance-row.md | claude-code | claude-sonnet-5-5 | 2026-11-01 |
| docs/decisions/2026-11-05-the-reader-commands-share-one-harness.md | claude-code | claude-fable-5-1, claude-opus-5-5 | 2026-11-05 |
| docs/provenance.md | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-05 |
| docs/specs/barred.md | not recorded | not recorded | not recorded |
| docs/specs/claims.md | claude-code | claude-sonnet-5-5 | 2026-11-02 |
| docs/specs/cli.md | claude-code | claude-fable-5-1, claude-sonnet-5-5 | 2026-11-05 |
| docs/specs/keyword-scan.md | not recorded | not recorded | not recorded |
| docs/specs/reader-ab.md | claude-code | claude-sonnet-5-5 | 2026-11-01 |
| docs/specs/reader-panel.md | claude-code | claude-fable-5-1, claude-opus-5-5 | 2026-11-05 |
| docs/specs/tone-and-tells.md | not recorded | not recorded | not recorded |
| pyproject.toml | not recorded | not recorded | not recorded |
| setup.cfg | not recorded | not recorded | not recorded |
| src/career_track_record/__init__.py | claude-code | claude-opus-5-5, claude-sonnet-5-5 | 2026-11-02 |
| src/career_track_record/__main__.py | not recorded | not recorded | not recorded |
| src/career_track_record/ab.py | claude-code | claude-fable-5-1, claude-sonnet-5-5 | 2026-11-05 |
| src/career_track_record/ab_reader_command.py | claude-code | claude-sonnet-5-5 | 2026-10-30 |
| src/career_track_record/barred.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| src/career_track_record/claims.py | claude-code | claude-sonnet-5-5 | 2026-11-03 |
| src/career_track_record/cli.py | claude-code | claude-fable-5-1, claude-sonnet-5-5 | 2026-11-05 |
| src/career_track_record/data/tone-default.json | not recorded | not recorded | not recorded |
| src/career_track_record/keywords.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| src/career_track_record/panel.py | claude-code | claude-fable-5-1, claude-opus-5-5 | 2026-11-05 |
| src/career_track_record/pdf_text.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| src/career_track_record/posting_file.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| src/career_track_record/quote_check.py | claude-code | claude-sonnet-5-5 | 2026-11-03 |
| src/career_track_record/reader_harness.py | claude-code | claude-fable-5-1 | 2026-11-05 |
| src/career_track_record/tone.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| tests/__init__.py | not recorded | not recorded | not recorded |
| tests/fixtures/ab/base.txt | not recorded | not recorded | not recorded |
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
| tests/fixtures/barred/lrm.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/make_fixtures.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| tests/fixtures/barred/moonshot-notes.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/moonshot-plain.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/moonshot-short.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/nbhyph.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/nbsp.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/nlnote.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/nocontrol.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/nokeep.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/note.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/plain.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/prefix-notes.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/sample.pdf | not recorded | not recorded | not recorded |
| tests/fixtures/barred/short.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/single.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/soft.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/spcolon.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/src.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/strblock.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/strip.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/substr.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/trim.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/two.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/unterm.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/url.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/value.ts | not recorded | not recorded | not recorded |
| tests/fixtures/barred/word.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/word2.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/wrap.txt | not recorded | not recorded | not recorded |
| tests/fixtures/barred/zw.txt | not recorded | not recorded | not recorded |
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
| tests/fixtures/panel/hiring-manager.lens.txt | claude-code | claude-fable-5-1 | 2026-11-05 |
| tests/fixtures/panel/recruiter.lens.txt | claude-code | claude-fable-5-1 | 2026-11-05 |
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
| tests/test_ab.py | claude-code | claude-sonnet-5-5 | 2026-10-30 |
| tests/test_ab_escape.py | claude-code | claude-sonnet-5-5 | 2026-10-30 |
| tests/test_ab_live.py | claude-code | claude-sonnet-5-5 | 2026-10-30 |
| tests/test_ab_reader_command.py | not recorded | not recorded | not recorded |
| tests/test_ab_run_failures.py | claude-code | claude-sonnet-5-5 | 2026-10-30 |
| tests/test_ab_vr1.py | claude-code | claude-sonnet-5-5 | 2026-10-30 |
| tests/test_ab_vr2.py | claude-code | claude-sonnet-5-5 | 2026-10-30 |
| tests/test_barred.py | claude-code | claude-sonnet-5-5 | 2026-11-02 |
| tests/test_barred_strings.py | not recorded | not recorded | not recorded |
| tests/test_claims.py | claude-code | claude-sonnet-5-5 | 2026-11-02 |
| tests/test_claims_runs.py | claude-code | claude-sonnet-5-5 | 2026-11-04 |
| tests/test_cli.py | claude-code | claude-sonnet-5-5 | 2026-11-02 |
| tests/test_keywords.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| tests/test_no_network.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| tests/test_output_failures.py | not recorded | not recorded | not recorded |
| tests/test_packaging.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| tests/test_panel.py | claude-code | claude-fable-5-1, claude-opus-5-5 | 2026-11-05 |
| tests/test_pdf_text.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| tests/test_posting_file.py | claude-code | claude-sonnet-5-5 | 2026-10-20 |
| tests/test_provenance.py | claude-code | claude-sonnet-5-5 | 2026-11-01 |
| tests/test_quote_check.py | claude-code | claude-sonnet-5-5 | 2026-11-03 |
| tests/test_source_hygiene.py | not recorded | not recorded | not recorded |
| tests/test_spec_revisions.py | claude-code | claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5 | 2026-11-05 |
| tests/test_tone.py | claude-code | claude-sonnet-5-5 | 2026-11-02 |
| tests/test_tone_pdf.py | not recorded | not recorded | not recorded |
