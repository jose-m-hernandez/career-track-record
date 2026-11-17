"""Tests that the commands in the keywords guide run against examples/keywords/. All data
here is invented."""

import hashlib
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class KeywordsExampleCase(unittest.TestCase):
    """The commands in the keywords guide run green against examples/keywords/."""

    def track(self, *args):
        env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"),
                   PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run([sys.executable, "-m", "career_track_record"] + list(args),
                              cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")

    def test_the_three_modes_run_green_on_the_example(self):
        base = os.path.join("examples", "keywords")
        postings = os.path.join(base, "postings")
        terms = os.path.join(base, "terms.tsv")
        copy = os.path.join(base, "resume.txt")
        code, out, err = self.track("keywords", "demand", "--postings", postings,
                                    "--terms", terms)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("(2 postings)", out)
        code, out, err = self.track("keywords", "coverage", "--terms", terms, copy)
        self.assertEqual((code, err), (0, ""))
        code, out, err = self.track("keywords", "report", "--postings", postings,
                                    "--terms", terms, "--copy", copy)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("Keywords: reply-templates (100% of postings, 0 in copy)", out)

    def test_the_sidecar_hash_command_in_the_guide_matches_the_example(self):
        path = os.path.join(ROOT, "examples", "keywords", "postings", "care-manager.txt")
        with open(path, "rb") as handle:
            stored = handle.read()
        with open(path + ".meta.json", encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["sha256"], hashlib.sha256(stored).hexdigest())
        self.assertEqual(meta["bytes"], len(stored))


if __name__ == "__main__":
    unittest.main()
