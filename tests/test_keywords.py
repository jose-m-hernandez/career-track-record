"""Tests for the keyword scan API. All data here is invented."""

import datetime
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import keywords, posting_file  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "keywords")
TODAY = datetime.date(2026, 10, 20)

T1 = [
    ("agents", "agents", "must-find"),
    ("evals", "evals", ""),
    ("python", "python", ""),
    ("knowledge-graph", "knowledge graph", ""),
    ("field-notes", "field notes", "chosen"),
]


def fx(*parts):
    return os.path.join(FX, *parts)


def put_posting(folder, name, body):
    os.makedirs(folder, exist_ok=True)
    posting_file.write_posting(
        os.path.join(folder, name),
        source_url="https://example.com/jobs/" + name,
        api_endpoint="https://example.com/api/jobs/" + name,
        fetched_at="2026-01-15T09:00:00Z", http_status=200, body=body)


def put(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)

    def path(self, *parts):
        return os.path.join(self.tmp, *parts)

    def assertCannotRun(self, result, *needles):
        self.assertEqual(result.exit_code, 2)
        self.assertFalse(result.ran)
        self.assertEqual(result.text, "")
        self.assertTrue(result.error)
        self.assertNotIn("\n", result.error)
        for needle in needles:
            self.assertIn(needle, result.error)

    def report(self, postings, *copy, **kw):
        return keywords.run("report", terms=kw.pop("terms", T1), postings=postings,
                            copy=list(copy), **kw)

    def rows(self, result):
        return {r["family"]: r for r in result.families}


class DemandCase(Base):
    def test_11_1(self):
        result = keywords.run("demand", terms=T1, postings=fx("postings-p1"), today=TODAY)
        expected = (
            "# Demand, 2026-10-20 (3 postings)\n"
            "\n"
            "| family | postings | % | hits | top variants |\n"
            "|---|---|---|---|---|\n"
            "| agents | 3/3 | 100% | 3 | `agents` (3) |\n"
            "| evals | 2/3 | 67% | 2 | `evals` (2) |\n"
            "| python | 2/3 | 67% | 2 | `python` (2) |\n"
            "| field-notes | 1/3 | 33% | 1 | `field notes` (1) |\n"
            "| knowledge-graph | 1/3 | 33% | 1 | `knowledge graph` (1) |\n"
            "\n"
        )
        self.assertEqual(result.text, expected)
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.ran)
        self.assertEqual(result.error, "")
        self.assertEqual([r["family"] for r in result.families],
                         ["agents", "evals", "python", "field-notes", "knowledge-graph"])
        agents = result.families[0]
        self.assertEqual((agents["demand"], agents["percent"], agents["hits"]), (3, 100, 3))

    def test_default_date_is_today(self):
        result = keywords.run("demand", terms=T1, postings=fx("postings-p1"))
        first = result.text.split("\n")[0]
        self.assertEqual(first, "# Demand, %s (3 postings)" % datetime.date.today().isoformat())

    def test_row_order_demand_then_hits_then_name(self):
        folder = self.path("p")
        put_posting(folder, "a.txt", "agents agents agents beta beta zed Zeta")
        put_posting(folder, "b.txt", "agents beta zed")
        terms = [("agents", "agents", "must-find"), ("beta", "beta", ""),
                 ("zed", "zed", ""), ("Zeta", "zeta", ""), ("alpha", "zzz|zed", "")]
        result = keywords.run("demand", terms=terms, postings=folder, today=TODAY)
        # agents 2/2 (4 hits); beta 2/2 (3 hits); alpha 2/2 (2 hits); zed 2/2 (2 hits);
        # Zeta 1/2
        names = [r["family"] for r in result.families]
        self.assertEqual(names, ["agents", "beta", "alpha", "zed", "Zeta"])

    def test_name_order_is_code_point_case_sensitive(self):
        folder = self.path("p")
        put_posting(folder, "a.txt", "agents zeta alpha")
        terms = [("agents", "agents", "must-find"), ("alpha", "alpha", ""),
                 ("Zeta", "zeta", "")]
        result = keywords.run("demand", terms=terms, postings=folder, today=TODAY)
        names = [r["family"] for r in result.families]
        self.assertLess(names.index("Zeta"), names.index("agents"))
        self.assertLess(names.index("Zeta"), names.index("alpha"))

    def test_top_variants_order_tie_limit_and_pipe(self):
        folder = self.path("p")
        # b.txt reads before c.txt; row order breaks ties inside one posting
        put_posting(folder, "b.txt", "agents yy zz")
        put_posting(folder, "c.txt", "xx xx xx yy yy")
        terms = [
            ("agents", "agents", "must-find"),
            ("fam", "xx", ""),       # 3 hits, first in c
            ("fam", "yy", ""),       # 3 hits, first in b: ties xx, wins
            ("fam", "zz", ""),       # 1 hit
            ("fam", "q|r", ""),      # 0 hits: never listed
            ("fam", "agents|qq", ""),  # 1 hit in b, row after zz? row order: zz first
        ]
        result = keywords.run("demand", terms=terms, postings=folder, today=TODAY)
        cell = result.text.split("\n")[4].split(" | ")[-1].rstrip(" |")
        self.assertEqual(cell, "`yy` (3), `xx` (3), `zz` (1)")

    def test_pipe_in_pattern_is_escaped_and_no_hit_is_dash(self):
        folder = self.path("p")
        put_posting(folder, "a.txt", "agents or c++")
        terms = [("agents", "agents|zzz", "must-find"), ("none", "qqq", "")]
        result = keywords.run("demand", terms=terms, postings=folder, today=TODAY)
        self.assertIn("| agents | 1/1 | 100% | 1 | `agents\\|zzz` (1) |", result.text)
        self.assertIn("| none | 0/1 | 0% | 0 | - |", result.text)

    def test_tie_between_variants_uses_file_name_order(self):
        folder = self.path("p")
        put_posting(folder, "a.txt", "agents xx")
        put_posting(folder, "B.txt", "agents yy")
        terms = [("agents", "agents", "must-find"), ("fam", "xx", ""), ("fam", "yy", "")]
        result = keywords.run("demand", terms=terms, postings=folder, today=TODAY)
        self.assertIn("`yy` (1), `xx` (1)", result.text)  # B.txt sorts before a.txt

    def test_header_text_is_never_searched(self):
        folder = self.path("p")
        put_posting(folder, "python-role.txt", "agents only here")
        put_posting(folder, "z.txt", "agents")
        terms = [("agents", "agents", "must-find"), ("python", "python", "")]
        result = keywords.run("demand", terms=terms, postings=folder, today=TODAY)
        self.assertEqual(self.rows(result)["python"]["demand"], 0)

    def test_control_line_never_counts(self):
        folder = self.path("p")
        os.makedirs(folder)
        posting_file.write_posting(
            os.path.join(folder, "a.txt"),
            source_url="https://example.com/a", api_endpoint="https://example.com/b",
            fetched_at="t", http_status=200, body="agents here", control="python")
        terms = [("agents", "agents", "must-find"), ("python", "python", "")]
        result = keywords.run("demand", terms=terms, postings=folder, today=TODAY)
        self.assertEqual(self.rows(result)["python"]["demand"], 0)

    def test_hits_are_non_overlapping_and_case_insensitive(self):
        folder = self.path("p")
        put_posting(folder, "a.txt", "AGENTS agents Agents aaaa")
        terms = [("agents", "agents", "must-find"), ("aa", "aa", "")]
        result = keywords.run("demand", terms=terms, postings=folder, today=TODAY)
        rows = self.rows(result)
        self.assertEqual(rows["agents"]["hits"], 3)
        self.assertEqual(rows["aa"]["hits"], 2)

    def test_substring_inside_longer_word_counts(self):
        folder = self.path("p")
        put_posting(folder, "a.txt", "many agents")
        terms = [("agent", "agent", "must-find")]
        result = keywords.run("demand", terms=terms, postings=folder, today=TODAY)
        self.assertEqual(result.families[0]["hits"], 1)


class FolderCase(Base):
    def test_folder_reading_rules(self):
        folder = self.path("p")
        put_posting(folder, "ok.txt", "agents")
        put_posting(folder, ".hidden.txt", "agents")
        put_posting(folder, "upper.TXT", "agents")
        put_posting(folder, "notes.md", "agents")
        put_posting(os.path.join(folder, "sub"), "inner.txt", "agents")
        put(os.path.join(folder, "ok.txt.meta.json.bak"), "x")
        result = keywords.run("demand", terms=[("agents", "agents", "must-find")],
                              postings=folder, today=TODAY)
        self.assertTrue(result.ran, result.error)
        self.assertIn("(2 postings)", result.text)

    def test_raw_posting_with_sidecar_is_read(self):
        folder = self.path("p")
        put_posting(folder, "a.txt", "agents")
        text = "raw agents text, no header"
        put(os.path.join(folder, "b.txt"), text)
        import hashlib
        put(os.path.join(folder, "b.txt.meta.json"), json.dumps({
            "format": "raw-posting-with-sidecar", "source_url": "https://example.com/b",
            "bytes": len(text), "sha256": hashlib.sha256(text.encode()).hexdigest()}))
        result = keywords.run("demand", terms=[("agents", "agents", "must-find")],
                              postings=folder, today=TODAY)
        self.assertTrue(result.ran, result.error)
        self.assertIn("(2 postings)", result.text)
        self.assertEqual(result.families[0]["hits"], 2)

    def test_case_1_empty_folder(self):
        folder = self.path("empty")
        os.makedirs(folder)
        for mode in ("demand", "report"):
            result = keywords.run(mode, terms=T1, postings=folder, copy=[fx("copy.txt")])
            self.assertCannotRun(result, ".txt")

    def test_case_1_only_upper_suffix_and_sidecars(self):
        folder = self.path("p")
        put_posting(folder, "x.TXT", "agents")
        put(os.path.join(folder, "y.txt.meta.json"), "{}")
        self.assertCannotRun(keywords.run("demand", terms=T1, postings=folder), ".txt")

    def test_case_1_missing_folder(self):
        self.assertCannotRun(keywords.run("demand", terms=T1, postings=self.path("none")))

    def test_case_2_malformed_header(self):
        folder = self.path("p")
        put_posting(folder, "a.txt", "agents")
        with open(fx("postings-p1", "2026-01-15-example-b.txt"), encoding="utf-8") as handle:
            text = handle.read()
        put(os.path.join(folder, "b.txt"), text.replace("http_status", "status"))
        result = keywords.run("demand", terms=T1, postings=folder)
        self.assertCannotRun(result, "b.txt", "header")

    def test_case_3_hash_mismatch(self):
        folder = self.path("p")
        with open(fx("postings-p1", "2026-01-15-example-a.txt"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("a plus.", text)
        put(os.path.join(folder, "a.txt"), text.replace("a plus.", "a must."))
        self.assertCannotRun(keywords.run("demand", terms=T1, postings=folder), "sha256")

    def test_case_8_invalid_utf8_posting(self):
        folder = self.path("p")
        put_posting(folder, "a.txt", "agents")
        put(os.path.join(folder, "b.txt"), b"\xff\xfe\xfd")
        self.assertCannotRun(keywords.run("demand", terms=T1, postings=folder), "UTF-8")


class MustFindCase(Base):
    def test_case_4_zero_demand_11_7(self):
        folder = self.path("p")
        put_posting(folder, "2026-01-15-example-d.txt",
                    "Data Engineer, Example D\nPython and evals.")
        for mode in ("demand", "report"):
            result = keywords.run(mode, terms=T1, postings=folder, copy=[fx("copy.txt")])
            self.assertCannotRun(result, "must-find")

    def test_case_4_fixture(self):
        result = self.report(fx("postings-d"), fx("copy.txt"))
        self.assertCannotRun(result, "must-find")

    def test_case_4_no_must_find_family(self):
        terms = [("agents", "agents", ""), ("evals", "evals", "chosen")]
        for mode in ("demand", "report"):
            result = keywords.run(mode, terms=terms, postings=fx("postings-p1"),
                                  copy=[fx("copy.txt")])
            self.assertCannotRun(result, "must-find")

    def test_coverage_never_checks_must_find(self):
        terms = [("agents", "agents", ""), ("evals", "evals", "")]
        result = keywords.run("coverage", terms=terms, copy=[fx("copy.txt")])
        self.assertTrue(result.ran, result.error)
        self.assertEqual(result.exit_code, 0)

    def test_one_live_must_find_family_is_enough(self):
        terms = [("agents", "agents", "must-find"), ("nope", "qqqq", "must-find")]
        result = keywords.run("demand", terms=terms, postings=fx("postings-p1"), today=TODAY)
        self.assertTrue(result.ran, result.error)

    def test_note_applies_to_whole_family_and_can_be_both(self):
        terms = [("agents", "zzzz", ""), ("agents", "agents", "must-find"),
                 ("agents", "qqqq", "chosen"), ("evals", "evals", "whatever")]
        result = self.report(fx("postings-p1"), fx("copy4.txt"), terms=terms)
        rows = self.rows(result)
        self.assertTrue(rows["agents"]["chosen"])
        self.assertFalse(rows["evals"]["chosen"])
        self.assertIn("| agents (chosen) |", result.text)
        self.assertIn("| evals | 2/3 (67%) |", result.text)  # other notes: no label


class CoverageCase(Base):
    def test_11_2(self):
        result = keywords.run("coverage", terms=T1, copy=[fx("copy.txt"), fx("copy2.ts")])
        self.assertEqual(result.text, (
            "| family | copy.txt | copy2.ts |\n"
            "|---|---|---|\n"
            "| agents | 1 | 0 |\n"
            "| evals | 1 | 0 |\n"
            "| python | 0 | 1 |\n"
            "| knowledge-graph | 0 | 0 |\n"
            "| field-notes | 0 | 0 |\n"))
        self.assertEqual(result.exit_code, 0)

    def test_11_3_keep_notes(self):
        result = keywords.run("coverage", terms=T1, copy=[fx("copy2.ts")], keep_notes=True)
        got = {r["family"]: r["copy"]["copy2.ts"] for r in result.families}
        self.assertEqual(got, {"agents": 0, "evals": 0, "python": 2,
                               "knowledge-graph": 1, "field-notes": 1})
        self.assertEqual(result.exit_code, 0)

    def test_only_ts_files_are_cleaned(self):
        text = "// python here\nagents\n"
        ts = put(self.path("a.ts"), text)
        txt = put(self.path("a.txt"), text)
        result = keywords.run("coverage", terms=T1, copy=[ts, txt])
        rows = self.rows(result)
        self.assertEqual(rows["python"]["copy"], {"a.ts": 0, "a.txt": 1})

    def test_non_ts_name_ending_in_s_is_not_cleaned(self):
        text = '// agents\n/* agents */\nnote: "agents"\n'
        js = put(self.path("copy.js"), text)
        result = keywords.run("coverage", terms=T1, copy=[js])
        rows = self.rows(result)
        self.assertEqual(rows["agents"]["copy"], {"copy.js": 3})

    def test_case_6_copy_missing_in_coverage(self):
        result = keywords.run("coverage", terms=T1,
                              copy=[fx("copy.txt"), self.path("missing.txt")])
        self.assertCannotRun(result, "missing.txt")

    def test_case_6_copy_missing_in_report(self):
        self.assertCannotRun(self.report(fx("postings-p1"), self.path("missing.txt")),
                             "missing.txt")

    def test_case_8_invalid_utf8_copy(self):
        bad = put(self.path("bad.txt"), b"agents \xff")
        self.assertCannotRun(keywords.run("coverage", terms=T1, copy=[bad]), "UTF-8")
        self.assertCannotRun(self.report(fx("postings-p1"), bad), "UTF-8")

    def test_byte_order_mark_in_copy_is_ordinary(self):
        bom = put(self.path("bom.txt"), b"\xef\xbb\xbfI build agents.")
        result = keywords.run("coverage", terms=T1, copy=[bom])
        self.assertEqual(self.rows(result)["agents"]["copy"], {"bom.txt": 1})


class CleanCase(unittest.TestCase):
    def test_note_key_rules(self):
        clean = keywords.clean_typescript
        self.assertEqual(clean('note: "x"'), "note: ''")
        self.assertEqual(clean("note: 'x'"), "note: ''")
        self.assertEqual(clean("note: `x`"), "note: ''")
        self.assertEqual(clean('a, my-note: "x"'), "a, my-note: ''")
        self.assertEqual(clean('footnote: "x"'), 'footnote: "x"')
        self.assertEqual(clean('notes: "x"'), 'notes: "x"')
        self.assertEqual(clean('Note: "x"'), 'Note: "x"')
        self.assertEqual(clean('note : "x"'), "note: ''")
        self.assertEqual(clean('note\n:\n  "x"'), "note: ''")
        self.assertEqual(clean('note: 5'), "note: 5")

    def test_note_strings_with_escapes(self):
        clean = keywords.clean_typescript
        self.assertEqual(clean(r'note: "a \" b", z: 1'), "note: '', z: 1")
        self.assertEqual(clean(r"note: 'a \' b', z: 1"), "note: '', z: 1")
        self.assertEqual(clean("note: `a\nb`, z: 1"), "note: '', z: 1")

    def test_blocks_and_comment_lines(self):
        clean = keywords.clean_typescript
        self.assertEqual(clean("aa/* x */bb"), "aabb")
        self.assertEqual(clean("a/* x\ny */b"), "ab")
        self.assertEqual(clean("one\n  // gone\ntwo\n"), "one\ntwo\n")
        self.assertEqual(clean("one\n// last"), "one\n")
        self.assertEqual(clean("x // stays\n"), "x // stays\n")

    def test_order_of_cleanings(self):
        clean = keywords.clean_typescript
        # a /* inside a note string goes with the string and opens nothing
        self.assertEqual(clean('note: "a /* b", c: 1 }\nkeep */'), "note: '', c: 1 }\nkeep */")
        # a // line inside a block goes with the block
        self.assertEqual(clean("a /* x\n// y\nz */ b"), "a  b")
        # a /* in a // line opens a block that runs to the next */ on a later line
        self.assertEqual(clean("x // c /* d\nkeep\nend */ tail\n"), "x // c  tail\n")
        # the joined remainder is then a comment line, and goes
        self.assertEqual(clean("// c /* d\nkeep\nend */ tail\nafter\n"), "after\n")


class ReportCase(Base):
    def test_11_4(self):
        result = self.report(fx("postings-p1"), fx("copy.txt"))
        self.assertEqual(result.text, (
            "| family | demand | copy.txt | gap |\n"
            "|---|---|---|---|\n"
            "| agents | 3/3 (100%) | 1 |  |\n"
            "| evals | 2/3 (67%) | 1 |  |\n"
            "| python | 2/3 (67%) | 0 | GAP |\n"
            "| field-notes (chosen) | 1/3 (33%) | 0 | GAP |\n"
            "| knowledge-graph | 1/3 (33%) | 0 | GAP |\n"
            "\n"
            "Keywords: python (67% of postings, 0 in copy); field-notes (33% of postings, "
            "0 in copy); knowledge-graph (33% of postings, 0 in copy)\n"))
        self.assertEqual(result.exit_code, 0)
        rows = self.rows(result)
        self.assertTrue(rows["python"]["gap"])
        self.assertFalse(rows["agents"]["gap"])
        self.assertTrue(rows["field-notes"]["chosen"])
        self.assertEqual(rows["python"]["copy"], {"copy.txt": 0})

    def test_11_5(self):
        result = self.report(fx("postings-p1"), fx("copy.txt"), fx("copy2.ts"))
        self.assertIn("| python | 2/3 (67%) | 0 | 1 |  |\n", result.text)
        self.assertTrue(result.text.endswith(
            "\nKeywords: field-notes (33% of postings, 0 in copy); "
            "knowledge-graph (33% of postings, 0 in copy)\n"))
        self.assertEqual(result.exit_code, 0)

    def test_11_6_edges(self):
        cases = (("postings-e10", "| python | 3/10 (30%) | 0 | GAP |",
                  "Keywords: python (30% of postings, 0 in copy)"),
                 ("postings-e7", "| python | 2/7 (29%) | 0 |  |", "Keywords: none"),
                 ("postings-e8", "| python | 1/8 (12%) | 0 |  |", "Keywords: none"))
        for folder, row, summary in cases:
            result = self.report(fx(folder), fx("copy4.txt"))
            self.assertTrue(result.ran, result.error)
            self.assertIn(row + "\n", result.text, folder)
            self.assertTrue(result.text.endswith("\n\n" + summary + "\n"), folder)

    def test_exactly_30_percent_is_a_gap_just_under_is_not(self):
        # 3 of 10 -> gap, 2 of 7 -> no gap (29%), checked through the API rows
        e10 = self.rows(self.report(fx("postings-e10"), fx("copy4.txt")))
        e7 = self.rows(self.report(fx("postings-e7"), fx("copy4.txt")))
        self.assertTrue(e10["python"]["gap"])
        self.assertFalse(e7["python"]["gap"])

    def test_any_copy_hit_in_any_file_closes_the_gap(self):
        none = self.rows(self.report(fx("postings-p1"), fx("copy.txt")))
        some = self.rows(self.report(fx("postings-p1"), fx("copy.txt"), fx("copy2.ts")))
        self.assertTrue(none["python"]["gap"])
        self.assertFalse(some["python"]["gap"])

    def test_11_9_chosen_term_is_never_something_to_replace(self):
        result = self.report(fx("postings-p1-ab"), fx("copy3.txt"))
        self.assertIn("| field-notes (chosen) | 0/2 (0%) | 1 |  |\n", result.text)
        summary = result.text.split("\n")[-2]
        self.assertTrue(summary.startswith("Keywords: "))
        self.assertNotIn("field-notes", summary)
        for name in ("python", "evals", "knowledge-graph"):
            self.assertIn(name, summary)
        lowered = result.text.lower()
        for word in ("remove", "replace", "reconsider", "unused", "unneeded", "suggest"):
            self.assertNotIn(word, lowered)
        self.assertFalse(self.rows(result)["field-notes"]["gap"])

    def test_chosen_term_over_threshold_with_no_copy_is_still_flagged(self):
        # 11.4: a chosen family is reported like any other
        rows = self.rows(self.report(fx("postings-p1"), fx("copy.txt")))
        self.assertTrue(rows["field-notes"]["gap"])

    def test_report_row_order_demand_then_name(self):
        folder = self.path("p")
        put_posting(folder, "a.txt", "agents zeta alpha alpha alpha")
        terms = [("agents", "agents", "must-find"), ("Zeta", "zeta", ""),
                 ("alpha", "alpha", "")]
        result = keywords.run("report", terms=terms, postings=folder,
                              copy=[fx("copy.txt")])
        self.assertEqual([r["family"] for r in result.families], ["Zeta", "agents", "alpha"])


class PercentCase(Base):
    def test_percent_function_halves_go_to_even(self):
        pct = keywords.percent
        self.assertEqual(pct(1, 40), 2)     # 2.5
        self.assertEqual(pct(3, 40), 8)     # 7.5
        self.assertEqual(pct(1, 8), 12)     # 12.5
        self.assertEqual(pct(3, 8), 38)     # 37.5
        self.assertEqual(pct(5, 8), 62)     # 62.5
        self.assertEqual(pct(7, 8), 88)     # 87.5
        self.assertEqual(pct(0, 5), 0)
        self.assertEqual(pct(5, 5), 100)
        self.assertEqual(pct(2, 3), 67)
        self.assertEqual(pct(1, 3), 33)
        self.assertEqual(pct(1, 200), 0)    # 0.5 goes to 0, not 1
        self.assertEqual(pct(3, 200), 2)    # 1.5 goes to 2

    def test_one_of_forty_prints_2_and_three_of_forty_prints_8(self):
        folder = self.path("p")
        for i in range(40):
            put_posting(folder, "p%02d.txt" % i, "agents python" if i == 0 else "agents")
        terms = [("agents", "agents", "must-find"), ("python", "python", "")]
        result = keywords.run("demand", terms=terms, postings=folder, today=TODAY)
        self.assertIn("| python | 1/40 | 2% | 1 |", result.text)
        for i in (1, 2):
            put_posting(folder, "p%02d.txt" % i, "agents python")
        result = keywords.run("demand", terms=terms, postings=folder, today=TODAY)
        self.assertIn("| python | 3/40 | 8% | 3 |", result.text)
        report = keywords.run("report", terms=terms, postings=folder, copy=[fx("copy4.txt")])
        self.assertIn("| python | 3/40 (8%) | 0 |  |", report.text)


class TermsCase(Base):
    def terms_file(self, text):
        return put(self.path("terms.tsv"), text)

    def test_load_terms_reads_t1(self):
        self.assertEqual(keywords.load_terms(fx("terms-t1.tsv")), T1)

    def test_load_terms_rejects_header_only_and_missing(self):
        with self.assertRaises(keywords.KeywordError):
            keywords.load_terms(self.terms_file("family\tpattern\tnote\n"))
        with self.assertRaises(keywords.KeywordError):
            keywords.load_terms(self.path("nope.tsv"))

    def test_case_5_empty_table_through_run(self):
        for mode in ("demand", "report", "coverage"):
            result = keywords.run(mode, terms=[], postings=fx("postings-p1"),
                                  copy=[fx("copy.txt")])
            self.assertCannotRun(result, "term table")

    def test_case_8_invalid_utf8_term_table(self):
        path = self.terms_file(b"family\tpattern\tnote\nagents\tagen\xffts\tmust-find\n")
        with self.assertRaises(keywords.KeywordError) as ctx:
            keywords.load_terms(path)
        self.assertIn("UTF-8", str(ctx.exception))

    def test_case_9_invalid_pattern(self):
        terms = [("agents", "agents", "must-find"), ("bad", "(unclosed", "")]
        for mode, kw in (("demand", {"postings": fx("postings-p1")}),
                         ("coverage", {"copy": [fx("copy.txt")]}),
                         ("report", {"postings": fx("postings-p1"), "copy": [fx("copy.txt")]})):
            self.assertCannotRun(keywords.run(mode, terms=terms, **kw), "(unclosed")
        path = self.terms_file("family\tpattern\tnote\nbad\t(unclosed\t\n")
        with self.assertRaises(keywords.KeywordError):
            keywords.load_terms(path)

    def test_pattern_is_case_insensitive_regex(self):
        path = self.terms_file("family\tpattern\tnote\nagents\tAGENT[s]?\tmust-find\n")
        terms = keywords.load_terms(path)
        result = keywords.run("coverage", terms=terms, copy=[fx("copy.txt")])
        self.assertEqual(result.families[0]["copy"], {"copy.txt": 1})

    def test_families_keep_first_appearance_order_and_sum_variants(self):
        terms = [("b", "bb", ""), ("a", "aa", ""), ("b", "cc", "")]
        text = put(self.path("c.txt"), "bb cc cc aa")
        result = keywords.run("coverage", terms=terms, copy=[text])
        self.assertEqual([r["family"] for r in result.families], ["b", "a"])
        self.assertEqual(result.families[0]["copy"], {"c.txt": 3})

    def test_unknown_mode_does_not_raise(self):
        self.assertCannotRun(keywords.run("nope", terms=T1))


class CollisionCase(Base):
    def labels(self, paths, **kw):
        result = keywords.run("coverage", terms=[("agents", "agents", "")],
                              copy=paths, **kw)
        self.assertTrue(result.ran, result.error)
        return list(result.families[0]["copy"].keys())

    def test_no_collision_keeps_base_names(self):
        a = put(self.path("one", "a.txt"), "agents")
        b = put(self.path("two", "b.txt"), "agents")
        self.assertEqual(self.labels([a, b]), ["a.txt", "b.txt"])

    def test_collision_uses_shortest_distinguishing_suffix(self):
        a = put(self.path("one", "x.txt"), "agents")
        b = put(self.path("two", "x.txt"), "agents")
        self.assertEqual(self.labels([a, b]), ["one/x.txt", "two/x.txt"])

    def test_k_is_chosen_per_group(self):
        p = put(self.path("p", "a", "x.txt"), "agents")
        q = put(self.path("q", "a", "x.txt"), "agents")
        r = put(self.path("r", "b", "x.txt"), "agents")
        m = put(self.path("m", "y.txt"), "agents")
        n = put(self.path("n", "y.txt"), "agents")
        z = put(self.path("z.txt"), "agents")
        labels = self.labels([p, m, q, z, r, n])
        self.assertEqual(labels, ["p/a/x.txt", "m/y.txt", "q/a/x.txt", "z.txt",
                                  "r/b/x.txt", "n/y.txt"])

    def test_a_shallower_path_in_a_group(self):
        deep = put(self.path("d", "x.txt"), "agents")
        old = os.getcwd()
        os.chdir(self.path("d"))
        self.addCleanup(os.chdir, old)
        other = put(self.path("e", "x.txt"), "agents")
        labels = self.labels(["x.txt", other])
        self.assertEqual(labels[0], "x.txt")
        self.assertTrue(labels[1].endswith("/x.txt") and labels[1] != "x.txt")
        self.assertEqual(deep, self.path("d", "x.txt"))

    def test_same_path_given_twice_is_one_column(self):
        a = put(self.path("one", "x.txt"), "agents")
        b = put(self.path("two", "x.txt"), "agents")
        again = self.path("one") + "//." + "/" + "x.txt"
        labels = self.labels([a, b, again, a])
        self.assertEqual(labels, ["one/x.txt", "two/x.txt"])
        self.assertEqual(self.labels([a, again]), ["x.txt"])

    def test_dot_slash_and_repeated_slashes_are_removed(self):
        old = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, old)
        put(self.path("sub", "x.txt"), "agents")
        put(self.path("x.txt"), "agents")
        labels = self.labels(["./sub//x.txt", "./x.txt"])
        self.assertEqual(labels, ["sub/x.txt", "x.txt"])


class CopyCleaningThroughRunCase(Base):
    def test_ts_notes_blocks_and_comments(self):
        ts = put(self.path("a.ts"),
                 '// agents in a comment\n'
                 'const a = { note: "agents in a note", t: "agents" };\n'
                 '/* agents in a block */\n')
        cleaned = keywords.run("coverage", terms=[("agents", "agents", "")], copy=[ts])
        kept = keywords.run("coverage", terms=[("agents", "agents", "")], copy=[ts],
                            keep_notes=True)
        self.assertEqual(cleaned.families[0]["copy"], {"a.ts": 1})
        self.assertEqual(kept.families[0]["copy"], {"a.ts": 4})


class FixturesCase(Base):
    def test_generator_output_equals_committed_tree(self):
        import subprocess
        out = self.path("fx")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        with open(os.devnull, "rb") as devnull:
            proc = subprocess.run(
                [sys.executable, os.path.join(FX, "make_fixtures.py"), out],
                stdin=devnull, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)

        def tree(base):
            found = {}
            for folder, dirs, names in os.walk(base):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for name in names:
                    full = os.path.join(folder, name)
                    rel = os.path.relpath(full, base)
                    if rel == "make_fixtures.py":
                        continue
                    with open(full, "rb") as handle:
                        found[rel] = handle.read()
            return found

        fresh, committed = tree(out), tree(FX)
        self.assertEqual(sorted(fresh), sorted(committed))
        for rel in fresh:
            self.assertEqual(fresh[rel], committed[rel], rel)
        self.assertEqual(len([r for r in fresh if r.startswith("postings-e10")]), 10)
        self.assertEqual(len([r for r in fresh if r.startswith("postings-e7")]), 7)
        self.assertEqual(len([r for r in fresh if r.startswith("postings-e8")]), 8)
        self.assertIn(os.path.join("postings-e10", "2026-01-15-edge-01.txt"), fresh)
        for rel in ("copy.txt", "copy2.ts", "copy3.txt", "copy4.txt", "terms-t1.tsv"):
            self.assertTrue(fresh[rel].endswith(b"\n") and not fresh[rel].endswith(b"\n\n"), rel)


class FixRoundCase(Base):
    def make_postings(self, name, total, hit, hit_text="agents", other_text="nothing"):
        folder = self.path(name)
        for i in range(total):
            put_posting(folder, "p%03d.txt" % i, hit_text if i < hit else other_text)
        return folder

    def test_exact_halves_that_float_rounding_gets_wrong(self):
        self.assertEqual(keywords.percent(69, 120), 58)   # exactly 57.5
        self.assertEqual(keywords.percent(218, 400), 54)  # exactly 54.5
        terms = [("agents", "agents", "must-find")]
        for total, hit, line in ((120, 69, "69/120 (58%)"), (400, 218, "218/400 (54%)")):
            folder = self.make_postings("p%d" % total, total, hit)
            copy = put(self.path("c%d.txt" % total), "agents")
            result = self.report(folder, copy, terms=terms)
            self.assertTrue(result.ran, result.error)
            self.assertIn(line, result.text)

    def test_non_ts_copy_file_is_never_cleaned(self):
        copy = put(self.path("copy.txt"), '// agents\n/* agents */\nnote: "agents"\n')
        terms = [("agents", "agents", "")]
        for keep in (False, True):
            result = keywords.run("coverage", terms=terms, copy=[copy], keep_notes=keep)
            self.assertTrue(result.ran, result.error)
            self.assertEqual(result.families[0]["copy"], {"copy.txt": 3})

    def test_two_blocks_keep_the_text_between(self):
        copy = put(self.path("a.ts"), "/* x */ agents /* y */\n")
        result = keywords.run("coverage", terms=[("agents", "agents", "")], copy=[copy])
        self.assertTrue(result.ran, result.error)
        self.assertEqual(result.families[0]["copy"], {"a.ts": 1})

    def test_directory_named_txt_is_not_a_posting(self):
        folder = self.path("p")
        put_posting(folder, "ok.txt", "agents")
        os.makedirs(os.path.join(folder, "extra.txt"))
        result = keywords.run("demand", terms=[("agents", "agents", "must-find")],
                              postings=folder, today=TODAY)
        self.assertTrue(result.ran, result.error)
        self.assertIn("(1 postings)", result.text)

    def test_share_just_under_30_is_not_a_gap_even_when_it_prints_30(self):
        folder = self.make_postings("p", 200, 59)
        copy = put(self.path("c.txt"), "nothing here")
        result = self.report(folder, copy, terms=[("agents", "agents", "must-find")])
        self.assertTrue(result.ran, result.error)
        self.assertIn("59/200 (30%)", result.text)
        self.assertFalse(self.rows(result)["agents"]["gap"])
        self.assertNotIn("GAP", result.text)


if __name__ == "__main__":
    unittest.main()
