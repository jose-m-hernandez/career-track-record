"""Pin test: the README's example plans can be met under 0.8.0, and the README names the plan keys 0.8.0 adds."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab, panel  # noqa: E402

README = os.path.join(ROOT, "README.md")
AB_SPEC = os.path.join(ROOT, "docs", "specs", "reader-ab.md")

BEGIN = "<!-- signed spec begins"
END = "<!-- signed spec ends -->"
FENCE = "`" * 3
LIMIT = "Known limit: it does not show they could see one as small as the change under test."


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def blocks(text):
    """The first fenced block after each of the two tool headings, as a dict keyed by
    ``ab`` and ``panel``."""
    lines = text.split("\n")
    found = {}
    for key, heading in (("ab", "### `track-record ab`"), ("panel", "### `track-record panel`")):
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
    """Every rule in the README's two example plans that its blind reads cannot meet."""
    found = blocks(text)
    out = []
    plan = ab.parse_text(found["ab"])
    blind = len([r for r in plan.readers if not r.not_blind]) * plan.reads_per_reader
    for hyp in plan.hypotheses:
        for kind, clause in hyp.clauses:
            need = need_of(clause)
            if need > blind:
                out.append("ab %s %s needs %d, blind reads %d" % (hyp.name, kind, need, blind))
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
        self.assertEqual(problems(read(README)), [])

    def test_a_not_blind_reader_two_is_caught(self):
        old = "  reader-2 | /path/to/my-reader.sh | cost 3"
        new = "  reader-2 | /path/to/my-reader.sh | not-blind | cost 3"
        text = read(README)
        self.assertEqual(text.count(old + "\n"), 2)
        self.assertEqual(problems(text.replace(old, new)), [
            "ab h1 SUPPORTED needs 6, blind reads 3", "ab h1 REFUTED needs 4, blind reads 3",
            "panel r1 PASS needs 6, counted reads 3", "panel r2 PASS needs 6, counted reads 3",
            "panel r3 PASS needs 10, counted reads 6"])

    def test_the_readme_lists_the_new_plan_keys(self):
        lines = read(README).split("\n")
        heading = "### Plan keys added in 0.8.0"
        self.assertEqual(lines.count(heading), 1)
        section = []
        for line in lines[lines.index(heading) + 1:]:
            if line.startswith("## "):
                break
            section.append(line)
        for start in ("- `sensitivity: X vs W`", "- `sensitivity-scope`", "- `sensitivity-threshold`",
                      "- `min-valid-reads`", "- `replicate-of`", "- `reader-group <name>`"):
            self.assertEqual(len([s for s in section if s.startswith(start)]), 1, start)

    def test_the_sensitivity_line_quotes_the_signed_limit(self):
        bullets = [l for l in read(README).split("\n") if l.startswith("- `sensitivity: X vs W`")]
        self.assertEqual(len(bullets), 1)
        self.assertIn(LIMIT, bullets[0])
        spec = read(AB_SPEC)
        signed = spec[spec.index(BEGIN):spec.index(END)]
        self.assertIn(LIMIT, signed)


if __name__ == "__main__":
    unittest.main()
