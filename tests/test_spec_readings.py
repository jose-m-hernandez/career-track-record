"""Pin test: the build interpretations after the signed text of docs/specs/reader-ab.md (revision 4) and docs/specs/reader-panel.md (revision 3.1)."""

import hashlib
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BEGIN = "<!-- signed spec begins"
END = "<!-- signed spec ends -->"
HEADINGS = {
    "reader-ab.md": "## Build interpretations of revision 4 (maintainer, 2026-11-15)",
    "reader-panel.md": "## Build interpretations of revision 3 (maintainer, 2026-11-10)",
}

BLOCK_SHA = {
    "reader-ab.md": "ef5492839202bdaf53a9dbd523c4f9c080f5da9088cc50334b4025b14a306589",
    "reader-panel.md": "81e6106c69e18c4fc96edf59bea0f758d654e085a7a7cabbb9099795683f21cf",
}

# Signed blocks pinned without a build-interpretations section after them, so the section tests skip them.
BLOCK_ONLY_SHA = {
    "record-check.md": "faba1585b0407cf770b282276101c5f381bea78a419bb5c8ddd1706e95174a0a",
    "barred.md": "fa6f8d817514531bedb877e3d9913a31ef43e540120be7eecd4d850b0cc2a685",
    "claims.md": "ac84d164527c93bd3f8d47b1284bb8bcdb3ae39c3ff7bb73a19580e351273f41",
    "drafts.md": "e75158e6844427dfc19ffcbb5f6616fafb4b79454f186ef3592c13f01c374426",
}

# The key phrases that the restored 2.1 methods pin, and those pinned by the revision 4 section's points.
AB_RESTORED = {
    "point_1": ["gets no flag line"],
    "point_2": ['including when the gate is "not evaluated"'],
    "point_3": ["Every split of an arm's missing pairs"],
    "point_4": ["The validity line is the last line before the result's tail"],
}
AB_REVISION_4 = [
    "the A/A slightly rate counts this run's valid blind A/A reads",
    "the order consistency lines are printed for blind readers only",
    "the readers did not detect the planted difference",
    "prints reduced",
    "the weakened copy, and no more",
    "never -0.00",
    "A settled INCONCLUSIVE lifts nothing",
    "the first clause of the lifted kind",
    "equal to the floor is not below it",
    "byte-identical to the first plan",
    "Known limits, not built",
    "capped at 1",
    "once per reader",
    "a family named twice in one list counts once",
    "has no family on a reader or no drafted-by on a version",
    "reads-per-reader must be an even number, read in pairs (revision 4)",
    "pair as first and second, third and fourth",
    "The printed verdict, after position",
    "taken up to the next whole number",
    "A lifted verdict meets the family rule",
    "the floor never uses reads pooled with `aa-pool`",
    "a pair with both reads missing counts once",
    "compared as exact fractions",
    "from the plan it amends",
    "a reader name both plans use must name the same model",
    "pooled planned pairs over the first plan's planned pairs",
    "the first run already has an extension",
    "pairs are formed within each run, never across them",
    "never reads it pooled itself",
    "fewer valid blind reads than its planned blind reads",
    "those problems are all that is printed",
    "revision 4 results of the same four tests",
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


ERRATA_HEADING = "## Errata (maintainer, 2026-11-17)"

# One key phrase per erratum entry (E-number as in the entry), by spec file.
ERRATA = {
    "drafts.md": {"E1": "after any warnings already written, one line `cannot run: cannot write output`"},
    "reader-ab.md": {
        "E2": "A reader's name is a label; an extension may name every reader anew.",
        "E4": "Correction: delete the sentence.",
        "E5": "`freeze` does not refuse it, as in revision 3.\"",
    },
    "keyword-scan.md": {"E3": "Every cited line can be checked word for word against the saved copy of the posting"},
}


def read_spec(name):
    with open(os.path.join(ROOT, "docs", "specs", name), encoding="utf-8") as handle:
        return handle.read()


def section_of(name):
    """The build interpretations: from the heading to the end of the file, taken after the
    signed text."""
    text = read_spec(name)
    after = text[text.index(END):]
    return after[after.index(HEADINGS[name]):]


def errata_of(name):
    """The errata section: from its heading to the end of the file."""
    text = read_spec(name)
    return text[text.index(ERRATA_HEADING):]


class SpecReadingsCase(unittest.TestCase):
    def assertOnce(self, name, phrase):
        self.assertEqual(section_of(name).count(phrase), 1, "%s: %r" % (name, phrase))

    def test_the_signed_blocks_are_unchanged(self):
        for name, expected in {**BLOCK_SHA, **BLOCK_ONLY_SHA}.items():
            with self.subTest(name=name):
                text = read_spec(name)
                begin = text.index("\n", text.index(BEGIN)) + 1
                end = text.index(END)
                self.assertEqual(hashlib.sha256(text[begin:end].encode()).hexdigest(), expected)

    def test_each_section_follows_the_signed_text(self):
        for name in BLOCK_SHA:
            with self.subTest(name=name):
                text = read_spec(name)
                self.assertEqual(text.count(HEADINGS[name]), 1)
                self.assertGreater(text.index(HEADINGS[name]), text.index(END))

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

    def test_ab_revision_4_readings(self):
        for phrase in AB_REVISION_4:
            with self.subTest(phrase=phrase):
                self.assertOnce("reader-ab.md", phrase)

    def test_panel_revision_3_readings(self):
        for phrase in PANEL_REVISION_3:
            with self.subTest(phrase=phrase):
                self.assertOnce("reader-panel.md", phrase)

    def test_errata_sections_follow_the_signed_text_once_each(self):
        for name in ERRATA:
            with self.subTest(name=name):
                text = read_spec(name)
                self.assertEqual(text.count(ERRATA_HEADING), 1)
                if END in text:
                    self.assertGreater(text.index(ERRATA_HEADING), text.index(END))
                if name in HEADINGS:
                    self.assertGreater(text.index(ERRATA_HEADING), text.index(HEADINGS[name]))

    def test_each_erratum_entry_is_present_once(self):
        for name, entries in ERRATA.items():
            for number, phrase in entries.items():
                with self.subTest(name=name, entry=number):
                    section = errata_of(name)
                    self.assertEqual(section.count("**%s. " % number), 1)
                    self.assertEqual(section.count(phrase), 1, phrase)

    def test_no_seat_names_in_the_sections(self):
        for name in BLOCK_SHA:
            text = section_of(name)
            with self.subTest(name=name):
                self.assertIsNone(re.search(r"\b(cto|career)\b", text, re.I))
                for word in ("slice", "copy review", "session", " xo ", "engineer", "I-1"):
                    self.assertNotIn(word.lower(), text.lower(), word)


if __name__ == "__main__":
    unittest.main()
