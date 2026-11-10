"""Tests for revision 3 of the reader panel spec (docs/specs/reader-panel.md). All data here is invented."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from career_track_record import panel  # noqa: E402
from tests.test_panel import Setup, RANK, SIX_PASS  # noqa: E402


class PanelReaderGroupCase(unittest.TestCase):
    def done(self, **overrides):
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def grouped(self):
        return self.done(
            readers=["reader-1 | fake | reader-group f1", "reader-2 | fake | reader-group f2"],
            fake_reader=RANK, rules=["recruiter | " + SIX_PASS])

    def test_10_44_groups_count_version_and_anchor_reads(self):
        s, result, lines = self.grouped()
        self.assertEqual([x for x in lines if x.startswith("reader-group ")],
                         ["reader-group f1: 10 valid reads", "reader-group f2: 10 valid reads"])
        self.assertTrue([x for x in lines if x.startswith("rule r1 (l1) verdict: PASS [")])
        self.assertEqual(result.exit_code, 0)

    def test_the_panel_group_lines_come_just_before_the_validity_line(self):
        s, result, lines = self.grouped()
        last = max(i for i, x in enumerate(lines) if x.startswith("reader-group "))
        self.assertTrue(lines[last + 1].startswith("validity: "))


if __name__ == "__main__":
    unittest.main()
