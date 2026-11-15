"""Tests for the optional ``document`` plan key of ``track-record ab``. All data here is invented.

The key is decision 26 of revision 4 of the signed Reader A/B spec (docs/specs/reader-ab.md),
and these are its tests 10.91 to 10.93."""

import hashlib
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab  # noqa: E402
from tests.test_ab import Setup  # noqa: E402

# The sha256 of the built-in reader prompt before the key existed (the same value 0.7.0 pinned).
RESUME_PROMPT_SHA256 = "567b9bc16d86abfe4af935a844e28a1b6d2d257aa4f93b6ab3de8e97ce1fdd14"
NOUNS = {"cover letter": ("a cover letter", "cover letter"),
         "essay": ("an essay", "essay"),
         "profile": ("a profile", "profile")}


def normalised(text, article_noun, noun):
    """The prompt with the document's words put back to the default's."""
    text = text.replace("reading " + article_noun + " for", "reading a résumé for")
    text = text.replace("version of the same " + noun, "version of the same résumé")
    return text.replace("version of the " + noun, "version of the résumé")


class RenderCase(unittest.TestCase):
    def test_10_92_the_default_is_byte_identical_and_pinned(self):
        self.assertEqual(ab.render_prompt(), ab.PROMPT)
        self.assertEqual(ab.render_prompt("résumé"), ab.PROMPT)
        digest = hashlib.sha256(ab.PROMPT.encode("utf-8")).hexdigest()
        self.assertEqual(digest, RESUME_PROMPT_SHA256)
        self.assertEqual(ab.prompt_sha256(), RESUME_PROMPT_SHA256)
        self.assertEqual(ab.prompt_sha256("résumé"), RESUME_PROMPT_SHA256)

    def test_10_91_each_other_kind_changes_only_the_noun_and_its_article(self):
        for document, (article_noun, noun) in NOUNS.items():
            with self.subTest(document=document):
                text = ab.render_prompt(document)
                self.assertNotEqual(text, ab.PROMPT)
                self.assertNotIn("résumé", text)
                self.assertIn("You are reading %s for a job." % article_noun, text)
                self.assertIn("  A.txt        one version of the %s\n" % noun, text)
                self.assertIn("  B.txt        another version of the same %s\n" % noun, text)
                mine, default = text.splitlines(), ab.PROMPT.splitlines()
                self.assertEqual(len(mine), len(default))
                changed = [n for n, (a, b) in enumerate(zip(mine, default)) if a != b]
                self.assertEqual(len(changed), 3)
                self.assertEqual(normalised(text, article_noun, noun), ab.PROMPT)

    def test_10_91_the_sha_is_that_of_the_rendered_prompt(self):
        seen = set([RESUME_PROMPT_SHA256])
        for document in NOUNS:
            digest = hashlib.sha256(ab.render_prompt(document).encode("utf-8")).hexdigest()
            self.assertEqual(ab.prompt_sha256(document), digest)
            seen.add(digest)
        self.assertEqual(len(seen), 4)


class PlanCase(unittest.TestCase):
    def test_the_key_is_optional_and_defaults_to_resume(self):
        self.assertEqual(Setup(self).plan.document, "résumé")
        self.assertEqual(Setup(self, document="résumé").plan.document, "résumé")

    def test_the_allowed_values_parse(self):
        for document in NOUNS:
            self.assertEqual(Setup(self, document=document).plan.document, document)

    def test_10_93_an_unknown_value_is_refused_at_freeze(self):
        for value in ("resume", "letter", "Essay", "poem"):
            with self.subTest(value=value):
                s = Setup(self, document=value)
                result = s.freeze()
                self.assertEqual(result.exit_code, 2)
                self.assertEqual(result.error.splitlines(), [
                    "plan line %d: document is résumé, cover letter, essay or profile"
                    % s.line_of("document:")])
                self.assertFalse(s.exists("plan.txt.freeze"))


class RunCase(unittest.TestCase):
    def test_10_92_the_default_run_records_todays_hash_and_no_document_line(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        self.assertIn("%s  %s" % (RESUME_PROMPT_SHA256, ab.PROMPT_LABEL),
                      s.read("plan.txt.freeze").splitlines())
        self.assertIn("prompt sha256: " + RESUME_PROMPT_SHA256, s.result_lines())
        self.assertFalse([x for x in s.result_lines() if x.startswith("document:")])
        self.assertEqual(s.read(ab.READS_DIR, "c1", "1", ab.READ_PROMPT), ab.PROMPT)

    def test_10_91_a_rendered_prompt_is_what_the_readers_see_and_what_is_recorded(self):
        for document in NOUNS:
            with self.subTest(document=document):
                s = Setup(self, document=document)
                self.assertEqual(s.frozen_run().exit_code, 0)
                rendered = ab.render_prompt(document)
                digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
                for arm in ("aa", "c1"):
                    self.assertEqual(s.read(ab.READS_DIR, arm, "1", ab.READ_PROMPT), rendered)
                self.assertIn("%s  %s" % (digest, ab.PROMPT_LABEL),
                              s.read("plan.txt.freeze").splitlines())
                lines = s.result_lines()
                self.assertIn("prompt sha256: " + digest, lines)
                self.assertIn("document: " + document, lines)

    def test_10_93_changing_document_after_freeze_is_caught_like_another_scalar(self):
        # The control: the same edit to another scalar key.
        control = Setup(self)
        self.assertEqual(control.freeze().exit_code, 0)
        control.change(noise_threshold="1/3")
        expected = control.run()
        self.assertEqual(expected.exit_code, 2)
        self.assertEqual(expected.error.splitlines(), ["changed since the freeze: plan.txt"])

        s = Setup(self, document="essay")
        self.assertEqual(s.freeze().exit_code, 0)
        s.change(document="cover letter")
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("changed since the freeze: plan.txt", result.error.splitlines())
        self.assertFalse(s.exists(ab.READS_DIR))

        dropped = Setup(self, document="essay")
        self.assertEqual(dropped.freeze().exit_code, 0)
        dropped.change(document=None)
        again = dropped.run()
        self.assertEqual(again.exit_code, 2)
        self.assertIn("changed since the freeze: plan.txt", again.error.splitlines())
        self.assertFalse(dropped.exists(ab.READS_DIR))


if __name__ == "__main__":
    unittest.main()
