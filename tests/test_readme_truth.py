"""Pin test: the example plans in the guides can be met under 0.8.0, and the ab guide names the plan keys 0.8.0 adds."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab, panel  # noqa: E402

README = os.path.join(ROOT, "README.md")
AB_GUIDE = os.path.join(ROOT, "docs", "guides", "ab.md")
PANEL_GUIDE = os.path.join(ROOT, "docs", "guides", "panel.md")
AB_SPEC = os.path.join(ROOT, "docs", "specs", "reader-ab.md")
AGENTS = os.path.join(ROOT, "AGENTS.md")
CLI_SPEC = os.path.join(ROOT, "docs", "specs", "cli.md")

BEGIN = "<!-- signed spec begins"
END = "<!-- signed spec ends -->"
FENCE = "`" * 3
LIMIT = "Known limit: it does not show they could see one as small as the change under test."


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def guides():
    return read(AB_GUIDE) + "\n" + read(PANEL_GUIDE)


def blocks(text):
    """The first fenced block after each of the two tool headings, as a dict keyed by
    ``ab`` and ``panel``."""
    lines = text.split("\n")
    found = {}
    for key, heading in (("ab", "# `track-record ab`"), ("panel", "# `track-record panel`")):
        start = lines.index(heading)
        first = start + 1
        while lines[first] != FENCE:
            first += 1
        last = first + 1
        while lines[last] != FENCE:
            last += 1
        found[key] = "\n".join(lines[first + 1:last]) + "\n"
    return found


def need_of(clause):
    return clause.n if clause.n is not None else clause.k


def problems(text):
    """Every rule in the guides' two example plans that its blind reads cannot meet. An ab
    rule counts paired picks: each blind reader's reads come in pairs."""
    found = blocks(text)
    out = []
    plan = ab.parse_text(found["ab"])
    pairs = len([r for r in plan.readers if not r.not_blind]) * plan.reads_per_reader // 2
    for hyp in plan.hypotheses:
        for kind, clause in hyp.clauses:
            need = need_of(clause)
            if need > pairs:
                out.append("ab %s %s needs %d, blind pairs %d" % (hyp.name, kind, need, pairs))
    plan = panel.parse_text(found["panel"])
    per_lens = len([r for r in plan.readers if not r.not_blind]) * plan.reads_per_reader
    for rule in plan.rules:
        available = per_lens * len(plan.lenses) if rule.lens is None else per_lens
        for kind, clause in rule.clauses:
            need = need_of(clause)
            if need > available:
                out.append("panel %s %s needs %d, counted reads %d" % (rule.name, kind, need, available))
    return out


class ReadmeTruthTest(unittest.TestCase):
    def test_the_example_plans_can_be_met(self):
        self.assertEqual(problems(guides()), [])

    def test_a_not_blind_reader_two_is_caught(self):
        old = "  reader-2 | /path/to/my-reader.sh | cost 3"
        new = "  reader-2 | /path/to/my-reader.sh | not-blind | cost 3"
        text = guides()
        # The ab example's reader-2 line goes on with its family, so this exact line, with
        # its line break, is the panel example's alone; the replacement reaches both.
        self.assertEqual(text.count(old + "\n"), 1)
        self.assertEqual(text.count(old), 2)
        self.assertEqual(problems(text.replace(old, new)), [
            "ab h1 SUPPORTED needs 6, blind pairs 3", "ab h1 REFUTED needs 4, blind pairs 3",
            "panel r1 PASS needs 6, counted reads 3", "panel r2 PASS needs 6, counted reads 3",
            "panel r3 PASS needs 10, counted reads 6"])

    def test_the_readme_lists_the_new_plan_keys(self):
        lines = read(AB_GUIDE).split("\n")
        heading = "## Plan keys added in 0.8.0"
        self.assertEqual(lines.count(heading), 1)
        section = []
        for line in lines[lines.index(heading) + 1:]:
            if line.startswith("## "):
                break
            section.append(line)
        for start in ("- `sensitivity: X vs W`", "- `sensitivity-scope`", "- `sensitivity-threshold`",
                      "- `min-valid-reads`", "- `replicate-of`", "- `reader-group <name>`"):
            self.assertEqual(len([s for s in section if s.startswith(start)]), 1, start)

    def test_the_panel_guide_lists_the_revision_4_plan_keys(self):
        lines = read(PANEL_GUIDE).split("\n")
        heading = "## Plan keys added in revision 4"
        self.assertEqual(lines.count(heading), 1)
        section = []
        for line in lines[lines.index(heading) + 1:]:
            if line.startswith("## "):
                break
            section.append(line)
        for start in ("- `written-by <who>`", "- `author-edited-version yes`", "- `criteria <A>",
                      "- `calibration-only: yes`", "- `calibration: <freeze file>`",
                      "- `extends: <freeze file>`", "- The headroom check",
                      "- `anchor-reads-per-reader` now defaults to 2"):
            self.assertEqual(len([s for s in section if s.startswith(start)]), 1, start)

    def test_the_sensitivity_line_quotes_the_signed_limit(self):
        bullets = [l for l in read(AB_GUIDE).split("\n") if l.startswith("- `sensitivity: X vs W`")]
        self.assertEqual(len(bullets), 1)
        self.assertIn(LIMIT, bullets[0])
        spec = read(AB_SPEC)
        signed = spec[spec.index(BEGIN):spec.index(END)]
        self.assertIn(LIMIT, signed)

    def test_the_public_counts_agree(self):
        self.assertTrue(read(README).startswith("# "))
        self.assertIn("\nEight checks for the career copy you send, and a setup command.", read(README))
        self.assertIn("The other seven tools are under", read(README))
        self.assertIn("\nTo set up your record folder, run track-record setup.\n\n## Exit codes",
                      read(README))
        self.assertIn("\nEight tools ship:", read(AGENTS))
        self.assertIn("lists the eight commands,", read(CLI_SPEC))


if __name__ == "__main__":
    unittest.main()
