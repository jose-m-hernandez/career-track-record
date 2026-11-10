"""Pin test: the revision 3.1 readings in docs/specs/reader-ab.md and docs/specs/reader-panel.md, outside their signed text."""

import hashlib
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BEGIN = "<!-- signed spec begins"
END = "<!-- signed spec ends -->"
HEADING = "## Build interpretations of revision 3 (maintainer, 2026-11-10)"

BLOCK_SHA = {
    "reader-ab.md": "3b581c40da031b943ae5280a6881235c5b5b6c27d8568db1d3d3e85851ee1f6f",
    "reader-panel.md": "81e6106c69e18c4fc96edf59bea0f758d654e085a7a7cabbb9099795683f21cf",
}

# The key phrases that the ten restored 2.1 methods pin, and those pinned by the revision 3 methods.
AB_RESTORED = {
    "point_1": ["gets no flag line"],
    "point_2": ['including when the gate is "not evaluated"'],
    "point_3": ["Every split of an arm's missing reads"],
    "point_4": ["The validity line is the last line before the result's tail"],
}
AB_REVISION_3 = [
    "blind readers' missing reads",
    "counts blind readers only",
    "counts every reader's reads",
    "reads blind readers",
    "the readers did not detect the planted difference",
    "prints reduced",
    "only the weakened copy",
    "valid blind sensitivity reads",
    "never -0.00",
    "A settled INCONCLUSIVE lifts nothing",
    "the first clause of the lifted kind",
    "equal to the floor is not below it",
    "byte-identical to the first plan",
    "the first run has not been run yet",
    "capped at 1",
    "once per reader",
]
PANEL_RESTORED = {
    "point_1": ["keeps the label the tool printed before revision 2"],
    "point_2": ["room above the strong anchor: not assessable (scale maximum <max>)"],
    "point_3": ["counts no read prints no p-value"],
    "point_4": ["the completions try whole reads"],
    "point_5": ["printed for every lens, whether it is counted or not"],
    "point_6": ["Each lens's score lines follow its flag counts"],
}
PANEL_REVISION_3 = [
    "counts blind readers only",
    "counts every reader's reads",
    "reads blind readers <arm> version",
    "no per-reader score line",
    "whether or not that lens is counted",
    "a lens that is not counted gives its rule 0 counted reads",
    "A settled INCONCLUSIVE lifts nothing",
    "the freeze rules of reader-ab.md",
    "the first run's own anchor gates",
    "capped at 1",
    "anchors included",
]


def read_spec(name):
    with open(os.path.join(ROOT, "docs", "specs", name), encoding="utf-8") as handle:
        return handle.read()


def section_of(name):
    """The 3.1 section: from its heading to the end of the file, taken after the signed text."""
    text = read_spec(name)
    after = text[text.index(END):]
    return after[after.index(HEADING):]


class SpecReadingsCase(unittest.TestCase):
    def assertOnce(self, name, phrase):
        self.assertEqual(section_of(name).count(phrase), 1, "%s: %r" % (name, phrase))

    def test_the_signed_blocks_are_unchanged(self):
        for name, expected in BLOCK_SHA.items():
            with self.subTest(name=name):
                text = read_spec(name)
                begin = text.index("\n", text.index(BEGIN)) + 1
                end = text.index(END)
                self.assertEqual(hashlib.sha256(text[begin:end].encode()).hexdigest(), expected)

    def test_each_section_follows_the_signed_text(self):
        for name in BLOCK_SHA:
            with self.subTest(name=name):
                text = read_spec(name)
                self.assertEqual(text.count(HEADING), 1)
                self.assertGreater(text.index(HEADING), text.index(END))

    def test_ab_2_1_point_1_no_flag_beside_a_reason(self):
        self.assertOnce("reader-ab.md", AB_RESTORED["point_1"][0])

    def test_ab_2_1_point_2_the_aa_gate_interval(self):
        self.assertOnce("reader-ab.md", AB_RESTORED["point_2"][0])

    def test_ab_2_1_point_3_the_completions(self):
        self.assertOnce("reader-ab.md", AB_RESTORED["point_3"][0])

    def test_ab_2_1_point_4_where_the_lines_go(self):
        self.assertOnce("reader-ab.md", AB_RESTORED["point_4"][0])

    def test_panel_2_1_point_1_a_rules_name(self):
        self.assertOnce("reader-panel.md", PANEL_RESTORED["point_1"][0])

    def test_panel_2_1_point_2_room_with_no_strong_anchor_read(self):
        self.assertOnce("reader-panel.md", PANEL_RESTORED["point_2"][0])

    def test_panel_2_1_point_3_no_p_when_nothing_is_counted(self):
        self.assertOnce("reader-panel.md", PANEL_RESTORED["point_3"][0])

    def test_panel_2_1_point_4_the_completions(self):
        self.assertOnce("reader-panel.md", PANEL_RESTORED["point_4"][0])

    def test_panel_2_1_point_5_the_score_lines(self):
        self.assertOnce("reader-panel.md", PANEL_RESTORED["point_5"][0])

    def test_panel_2_1_point_6_where_the_lines_go(self):
        self.assertOnce("reader-panel.md", PANEL_RESTORED["point_6"][0])

    def test_ab_revision_3_readings(self):
        for phrase in AB_REVISION_3:
            with self.subTest(phrase=phrase):
                self.assertOnce("reader-ab.md", phrase)

    def test_panel_revision_3_readings(self):
        for phrase in PANEL_REVISION_3:
            with self.subTest(phrase=phrase):
                self.assertOnce("reader-panel.md", phrase)

    def test_no_seat_names_in_the_sections(self):
        for name in BLOCK_SHA:
            text = section_of(name)
            with self.subTest(name=name):
                self.assertIsNone(re.search(r"\b(cto|career)\b", text, re.I))
                for word in ("slice", "copy review", "session", " xo ", "engineer", "I-1"):
                    self.assertNotIn(word.lower(), text.lower(), word)


if __name__ == "__main__":
    unittest.main()
