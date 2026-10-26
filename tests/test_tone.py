"""Tests for ``track-record tone``: every case of docs/specs/tone-and-tells.md section 11.

All data here is invented. The fixtures come from tests/fixtures/tone/make_fixtures.py.
Scratch rule files and the files that cannot be committed (a byte-order mark, bytes that
are not UTF-8) are built in temporary directories. Characters that are hard to see are
written as escapes.
"""

import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FX = os.path.join(ROOT, "tests", "fixtures", "tone")
DEFAULT_RULES = os.path.join(SRC, "career_track_record", "data", "tone-default.json")
sys.path.insert(0, SRC)

from career_track_record import tone  # noqa: E402

R1 = "rules-r1.json"
R2 = "rules-r2.json"
WHY = "invented rationale"


def run_cli(args, cwd=FX):
    """Run the command line; return (exit status, stdout text, stderr text)."""
    env = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")
    with open(os.devnull, "rb") as devnull:
        done = subprocess.run(
            [sys.executable, "-m", "career_track_record", "tone"] + list(args),
            cwd=cwd, env=env, stdin=devnull,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return done.returncode, done.stdout.decode("utf-8"), done.stderr.decode("utf-8")


def finding(name, line, level, rule, sentence, category=None, why=WHY):
    label = "" if category is None else " [%s]" % category
    return "%s:%d: %s %s%s: %s\n    %s\n" % (name, line, level, rule, label, why, sentence)


def summary(files, errors, warnings):
    return "%d file(s), %d error(s), %d warning(s)\n" % (files, errors, warnings)


def one_file(name, errors=0, warnings=0, body=""):
    """Expected stdout for one file: its findings (body) or clean, then the summary."""
    return (body or "%s: clean\n" % name) + summary(1, errors, warnings)


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def write_bytes(path, data):
    with open(path, "wb") as handle:
        handle.write(data)


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def stderr_of(*lines):
    return "".join(line + "\n" for line in lines)


class ToneCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name
        self._count = 0

    def scratch(self, data):
        """Write a scratch rule file (JSON from data) and return its path."""
        self._count += 1
        path = os.path.join(self.tmp, "scratch-%d.json" % self._count)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return path

    def r1(self):
        return copy.deepcopy(load_json(os.path.join(FX, R1)))

    def r1_rule(self, data, rule_id):
        return [r for r in data["rules"] if r["id"] == rule_id][0]

    def assertRun(self, args, code, out, cwd=FX):
        self.assertEqual(run_cli(args, cwd=cwd), (code, out, ""))

    def assertCannot(self, args, *lines, cwd=FX):
        self.assertEqual(run_cli(args, cwd=cwd), (2, "", stderr_of(*lines)))


class SectionElevenCase(ToneCase):
    def test_11_01_error_in_a_sentence(self):
        self.assertRun(["--rules", R1, "case-11-01.txt"], 1, one_file(
            "case-11-01.txt", errors=1, body=finding(
                "case-11-01.txt", 1, "error", "turnkey",
                "We shipped a Turnkey importer last spring.")))

    def test_11_02_warn_only_hides_errors(self):
        self.assertRun(["--rules", R1, "--warn-only", "case-11-01.txt"], 0,
                       one_file("case-11-01.txt"))

    def test_11_03_exempt(self):
        self.assertRun(["--rules", R1, "case-11-03.txt"], 0, one_file("case-11-03.txt"))

    def test_11_04_anchor_case_differs(self):
        self.assertRun(["--rules", R1, "case-11-04.txt"], 1, one_file(
            "case-11-04.txt", errors=1, body=finding(
                "case-11-04.txt", 1, "error", "turnkey",
                "built the turnkey importer for example corp in a week.")))

    def test_11_05_same_phrase_after_the_anchor(self):
        self.assertRun(["--rules", R1, "case-11-05.txt"], 1, one_file(
            "case-11-05.txt", errors=1, body=finding(
                "case-11-05.txt", 1, "error", "turnkey", "Also a turnkey dashboard.")))

    def test_11_06_em_dash(self):
        self.assertRun(["--rules", R1, "case-11-06.txt"], 1, one_file(
            "case-11-06.txt", errors=1, body=finding(
                "case-11-06.txt", 1, "error", "no-em-dash", "fast \u2014 and more")))

    def test_11_07_sensitive_rule_and_first_sentence(self):
        self.assertRun(["--rules", R1, "case-11-07.txt"], 0, one_file(
            "case-11-07.txt", warnings=1, body=finding(
                "case-11-07.txt", 1, "warn", "lower-we", "Then we moved on.")))

    def test_11_08_rule_order_and_category(self):
        self.assertRun(["--rules", R1, "case-11-08.txt"], 0, one_file(
            "case-11-08.txt", warnings=2,
            body=finding("case-11-08.txt", 1, "warn", "assisted-with",
                         "I assisted with planning.", category="hedge")
            + finding("case-11-08.txt", 1, "warn", "as-you-can-see",
                      "As you can see, it worked.", category="tell")))

    def test_11_09_two_occurrences(self):
        self.assertRun(["--rules", R1, "case-11-09.txt"], 1, one_file(
            "case-11-09.txt", errors=2,
            body=finding("case-11-09.txt", 1, "error", "turnkey", "turnkey turnkey") * 2))

    def test_11_10_no_word_boundary(self):
        self.assertRun(["--rules", R1, "case-11-10.txt"], 0, one_file("case-11-10.txt"))

    def test_11_11_three_lines(self):
        self.assertRun(["--rules", R1, "case-11-11.txt"], 0, one_file(
            "case-11-11.txt", warnings=1, body=finding(
                "case-11-11.txt", 2, "warn", "assisted-with",
                "line one assisted with line three", category="hedge")))

    def test_11_12_stale_exemption(self):
        self.assertRun(["--rules", R1, "--stale-check", "case-11-12.txt"], 1,
                       "case-11-12.txt: clean\nstale exemption: turnkey\n"
                       + summary(1, 1, 0))

    def test_11_13_no_stale_check_without_the_flag(self):
        self.assertRun(["--rules", R1, "case-11-12.txt"], 0, one_file("case-11-12.txt"))

    def test_11_14_anchor_present(self):
        self.assertRun(["--rules", R1, "--stale-check", "case-11-03.txt"], 0,
                       one_file("case-11-03.txt"))


class SelfTestCase(ToneCase):
    def test_11_15_no_must_fire(self):
        data = self.r1()
        del self.r1_rule(data, "turnkey")["must_fire"]
        self.assertCannot(["--rules", self.scratch(data), "case-11-01.txt"],
                          "self-test: rule turnkey: must_fire is missing")

    def test_11_15_empty_must_fire(self):
        data = self.r1()
        self.r1_rule(data, "turnkey")["must_fire"] = []
        self.assertCannot(["--rules", self.scratch(data), "case-11-01.txt"],
                          "self-test: rule turnkey: must_fire must be a non-empty "
                          "array of strings")

    def test_11_15_no_must_not(self):
        data = self.r1()
        del self.r1_rule(data, "lower-we")["must_not"]
        self.assertCannot(["--rules", self.scratch(data), "case-11-01.txt"],
                          "self-test: rule lower-we: must_not is missing")

    def test_11_16_must_fire_does_not_fire(self):
        data = self.r1()
        self.r1_rule(data, "turnkey")["must_fire"] = ["A turn key plan."]
        self.assertCannot(["--rules", self.scratch(data), "case-11-01.txt"],
                          "self-test: rule turnkey: must_fire example 1 gives no finding")

    def test_11_17_must_not_fires(self):
        data = self.r1()
        self.r1_rule(data, "turnkey")["must_not"] = ["A turnkey plan."]
        self.assertCannot(["--rules", self.scratch(data), "case-11-01.txt"],
                          "self-test: rule turnkey: must_not example 1 gives a finding")

    def test_11_18_duplicate_id(self):
        data = self.r1()
        data["rules"].append(copy.deepcopy(self.r1_rule(data, "turnkey")))
        self.assertCannot(["--rules", self.scratch(data), "case-11-01.txt"],
                          "self-test: rule turnkey: id is used more than once")

    def test_11_19_exemption_names_a_warn_rule(self):
        data = self.r1()
        data["exemptions"][0]["rule"] = "assisted-with"
        self.assertCannot(["--rules", self.scratch(data), "case-11-01.txt"],
                          "self-test: exemption 1: names a rule that is not an error "
                          "rule")

    def test_exemption_names_no_rule(self):
        data = self.r1()
        data["exemptions"][0]["rule"] = "no-such-rule"
        self.assertCannot(["--rules", self.scratch(data), "case-11-01.txt"],
                          "self-test: exemption 1: names no rule")

    def test_regex_that_does_not_compile(self):
        data = self.r1()
        data["rules"].append({"id": "broken", "level": "warn", "kind": "regex",
                              "text": "(", "rationale": WHY,
                              "must_fire": ["x"], "must_not": ["y"]})
        self.assertCannot(["--rules", self.scratch(data), "case-11-01.txt"],
                          "self-test: rule broken: regex does not compile")

    def test_11_20_default_rules_pass_their_own_self_test(self):
        self.assertEqual(tone.self_test(tone.load_rules()), [])
        self.assertEqual(tone.self_test(tone.load_rules(DEFAULT_RULES)), [])

    def test_11_21_one_finding_per_default_must_fire_text(self):
        data = load_json(DEFAULT_RULES)
        self.assertEqual(len(data["rules"]), 8)
        for rule in data["rules"]:
            for key, expected in (("must_fire", 1), ("must_not", 0)):
                for example in rule[key]:
                    with self.subTest(rule=rule["id"], key=key):
                        path = os.path.join(self.tmp, "example.txt")
                        write_bytes(path, example.encode("utf-8"))
                        result = tone.run(files=[path])
                        self.assertTrue(result.ran, result.error)
                        counts = re.search(r"(\d+) error\(s\), (\d+) warning\(s\)\n\Z",
                                           result.text)
                        found = [line for line in result.text.splitlines()
                                 if line.startswith(path + ":")
                                 and (" %s:" % rule["id"]) in line]
                        self.assertEqual(int(counts.group(1)) + int(counts.group(2)),
                                         expected, result.text)
                        self.assertEqual(len(found), expected, result.text)

    def test_self_test_runs_before_any_input_file_is_opened(self):
        data = self.r1()
        del self.r1_rule(data, "turnkey")["must_fire"]
        self.assertCannot(["--rules", self.scratch(data), "no-such-file.txt"],
                          "self-test: rule turnkey: must_fire is missing")

    def test_self_test_ignores_exemptions(self):
        data = {"rules": [{"id": "kit", "level": "error", "kind": "phrase",
                           "text": "kit", "rationale": WHY,
                           "must_fire": ["A kit here."], "must_not": ["A kitten."]}],
                "exemptions": [{"rule": "kit", "anchor": "A kit here.",
                                "reason": "invented reason"}]}
        path = self.scratch(data)
        self.assertEqual(tone.self_test(tone.load_rules(path)), [])
        kit = os.path.join(self.tmp, "kit.txt")
        write_bytes(kit, b"A kit here.\n")
        self.assertRun(["--rules", path, kit], 0, one_file(kit))
        write_bytes(kit, b"A kit here. And a kit there.\n")
        self.assertRun(["--rules", path, kit], 1, one_file(
            kit, errors=1, body=finding(kit, 1, "error", "kit", "And a kit there.")))

    def test_every_failure_is_reported(self):
        data = self.r1()
        del self.r1_rule(data, "turnkey")["must_fire"]
        self.r1_rule(data, "lower-we")["must_not"] = ["then we left"]
        self.assertCannot(["--rules", self.scratch(data), "case-11-01.txt"],
                          "self-test: rule turnkey: must_fire is missing",
                          "self-test: rule lower-we: must_not example 1 gives a finding")


class CannotRunCase(ToneCase):
    def test_11_22_missing_rule_file(self):
        self.assertCannot(["--rules", "no-such-rules.json", "case-11-01.txt"],
                          "cannot run: cannot read the rule file")

    def test_11_22_rule_file_not_json(self):
        path = os.path.join(self.tmp, "not.json")
        write_bytes(path, b"this is not JSON\n")
        self.assertCannot(["--rules", path, "case-11-01.txt"],
                          "cannot run: the rule file is not valid JSON")

    def test_rule_file_not_utf8(self):
        path = os.path.join(self.tmp, "bad.json")
        write_bytes(path, b"{\"rules\": \"\xff\"}\n")
        self.assertCannot(["--rules", path, "case-11-01.txt"],
                          "cannot run: the rule file is not valid UTF-8")

    def test_11_22_missing_input_file(self):
        self.assertCannot(["--rules", R1, "no-such-file.txt"],
                          "cannot run: cannot read no-such-file.txt")

    def test_11_22_no_input_file(self):
        self.assertCannot(["--rules", R1], "cannot run: no input file")
        self.assertCannot([], "cannot run: no input file")

    def test_input_file_that_is_a_directory(self):
        self.assertCannot(["--rules", R1, self.tmp],
                          "cannot run: cannot read %s" % self.tmp)

    def test_11_34_input_not_utf8(self):
        write_bytes(os.path.join(self.tmp, "case-11-34.txt"), b"turnkey\xff plan\n")
        self.assertCannot(["--rules", os.path.join(FX, R1), "case-11-34.txt"],
                          "cannot run: case-11-34.txt is not valid UTF-8", cwd=self.tmp)

    def test_every_unreadable_input_is_reported(self):
        write_bytes(os.path.join(self.tmp, "bad.txt"), b"\xff\n")
        self.assertCannot(["--rules", os.path.join(FX, R1), "gone.txt", "bad.txt"],
                          "cannot run: cannot read gone.txt",
                          "cannot run: bad.txt is not valid UTF-8", cwd=self.tmp)

    def test_all_inputs_are_opened_before_any_output(self):
        self.assertCannot(["--rules", R1, "case-11-01.txt", "no-such-file.txt"],
                          "cannot run: cannot read no-such-file.txt")


class PhraseCase(ToneCase):
    def test_11_23_plus_signs(self):
        self.assertRun(["--rules", R2, "case-11-23.txt"], 0, one_file(
            "case-11-23.txt", warnings=1, body=finding(
                "case-11-23.txt", 1, "warn", "cpp", "I wrote C++ and C# daily.")))

    def test_11_24_phrase_ending_in_a_dot(self):
        self.assertRun(["--rules", R2, "case-11-24.txt"], 0, one_file(
            "case-11-24.txt", warnings=1, body=finding(
                "case-11-24.txt", 1, "warn", "etc-dot", "Go, Rust, etc.")))

    def test_11_25_no_overlap(self):
        self.assertRun(["--rules", R2, "case-11-25.txt"], 0, one_file(
            "case-11-25.txt", warnings=1, body=finding(
                "case-11-25.txt", 1, "warn", "aa", "a a a")))

    def test_11_26_regex_across_a_sentence_end(self):
        self.assertRun(["--rules", R2, "case-11-26.txt"], 0, one_file(
            "case-11-26.txt", warnings=1, body=finding(
                "case-11-26.txt", 1, "warn", "done-next", "It was done. Next came more.")))

    def test_11_27_closing_quote(self):
        self.assertRun(["--rules", R1, "case-11-27.txt"], 1, one_file(
            "case-11-27.txt", errors=1, body=finding(
                "case-11-27.txt", 1, "error", "turnkey", "He said \"turnkey.\"")))

    def test_11_28_whitespace_runs(self):
        self.assertRun(["--rules", R1, "case-11-28.txt"], 1, one_file(
            "case-11-28.txt", errors=1, body=finding(
                "case-11-28.txt", 1, "error", "turnkey", "A turnkey plan.")))

    def test_11_29_blank_line_of_spaces(self):
        self.assertRun(["--rules", R1, "case-11-29.txt"], 1, one_file(
            "case-11-29.txt", errors=1, body=finding(
                "case-11-29.txt", 3, "error", "turnkey", "turnkey here")))

    def test_11_30_anchor_does_not_match_across_a_line_break(self):
        self.assertRun(["--rules", R1, "case-11-30.txt"], 1, one_file(
            "case-11-30.txt", errors=1, body=finding(
                "case-11-30.txt", 1, "error", "turnkey",
                "Built the turnkey importer for Example Corp in a week.")))

    def test_11_31_crlf(self):
        self.assertRun(["--rules", R1, "case-11-31.txt"], 0, one_file(
            "case-11-31.txt", warnings=1, body=finding(
                "case-11-31.txt", 2, "warn", "assisted-with",
                "line one assisted with line three", category="hedge")))

    def test_11_32_lone_cr(self):
        self.assertRun(["--rules", R1, "case-11-32.txt"], 0, one_file(
            "case-11-32.txt", warnings=1, body=finding(
                "case-11-32.txt", 2, "warn", "assisted-with",
                "line one assisted with line three", category="hedge")))

    def test_11_33_word_character_neighbours(self):
        self.assertRun(["--rules", R1, "case-11-33.txt"], 0, one_file("case-11-33.txt"))

    def test_t_cf_full_case_folding(self):
        data = {"rules": [{"id": "strasse", "level": "warn", "kind": "phrase",
                           "text": "strasse", "case": "insensitive",
                           "rationale": WHY, "must_fire": ["Die Stra\u00dfe war lang."],
                           "must_not": ["Die Strasser."]}]}
        path = self.scratch(data)
        self.assertEqual(tone.self_test(tone.load_rules(path)), [])
        name = os.path.join(self.tmp, "strasse.txt")
        write_bytes(name, "Die Stra\u00dfe war lang.\n".encode("utf-8"))
        self.assertRun(["--rules", path, name], 0, one_file(
            name, warnings=1, body=finding(
                name, 1, "warn", "strasse", "Die Stra\u00dfe war lang.")))

    def test_part_of_a_folded_character_is_not_a_match(self):
        data = {"rules": [{"id": "stras", "level": "warn", "kind": "phrase",
                           "text": "stra", "rationale": WHY,
                           "must_fire": ["A stra."], "must_not": ["A strasse."]}]}
        path = self.scratch(data)
        self.assertEqual(tone.self_test(tone.load_rules(path)), [])

    def test_t_anc_the_whole_match_inside_the_anchor(self):
        data = self.r1()
        data["exemptions"][0]["anchor"] = "Built the turn"
        name = os.path.join(self.tmp, "anchor.txt")
        write_bytes(name, b"Built the turnkey plan.\n")
        self.assertRun(["--rules", self.scratch(data), name], 1, one_file(
            name, errors=1, body=finding(
                name, 1, "error", "turnkey", "Built the turnkey plan.")))

    def test_t_bom_stays_in_the_text(self):
        name = os.path.join(self.tmp, "bom.txt")
        write_bytes(name, b"\xef\xbb\xbfturnkey plan.\n")
        self.assertRun(["--rules", os.path.join(FX, R1), name], 1, one_file(
            name, errors=1, body=finding(
                name, 1, "error", "turnkey", "\ufeffturnkey plan.")))

    def test_a_blank_line_ends_a_sentence(self):
        name = os.path.join(self.tmp, "blank.txt")
        write_bytes(name, b"first part\n\nturnkey second part\n\nthird\n")
        self.assertRun(["--rules", os.path.join(FX, R1), name], 1, one_file(
            name, errors=1, body=finding(
                name, 3, "error", "turnkey", "turnkey second part")))

    def test_a_match_across_a_sentence_end_prints_both_sentences(self):
        name = os.path.join(self.tmp, "across.txt")
        write_bytes(name, b"Ok. It was done. Next came more. Done.\n")
        self.assertRun(["--rules", os.path.join(FX, R2), name], 0, one_file(
            name, warnings=1, body=finding(
                name, 1, "warn", "done-next", "It was done. Next came more.")))

    def test_findings_follow_rule_order_then_position(self):
        data = {"rules": [
            {"id": "b-rule", "level": "warn", "kind": "phrase", "text": "bb",
             "rationale": WHY, "must_fire": ["bb"], "must_not": ["b"]},
            {"id": "a-rule", "level": "warn", "kind": "phrase", "text": "aa",
             "rationale": WHY, "must_fire": ["aa"], "must_not": ["a"]}]}
        name = os.path.join(self.tmp, "order.txt")
        write_bytes(name, b"aa bb aa\n")
        self.assertRun(["--rules", self.scratch(data), name], 0, one_file(
            name, warnings=3,
            body=finding(name, 1, "warn", "b-rule", "aa bb aa")
            + finding(name, 1, "warn", "a-rule", "aa bb aa") * 2))


class OptionsCase(ToneCase):
    def test_11_35_warn_only_never_hides_a_stale_exemption(self):
        self.assertRun(["--rules", R1, "--warn-only", "--stale-check", "case-11-12.txt"], 1,
                       "case-11-12.txt: clean\nstale exemption: turnkey\n"
                       + summary(1, 1, 0))

    def test_11_36_same_file_twice(self):
        one = finding("case-11-01.txt", 1, "error", "turnkey",
                      "We shipped a Turnkey importer last spring.")
        self.assertRun(["--rules", R1, "case-11-01.txt", "case-11-01.txt"], 1,
                       one + one + summary(2, 2, 0))

    def test_11_37_default_rules(self):
        self.assertRun(["case-11-37.txt"], 1, one_file(
            "case-11-37.txt", errors=1, body=finding(
                "case-11-37.txt", 1, "error", "team-player", "I am a team player.",
                why="A claim every applicant makes; name what you did with the team.")))

    def test_11_38_print_defaults_is_the_shipped_file(self):
        with open(DEFAULT_RULES, "rb") as handle:
            shipped = handle.read()
        env = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")
        with open(os.devnull, "rb") as devnull:
            done = subprocess.run(
                [sys.executable, "-m", "career_track_record", "tone", "--print-defaults"],
                cwd=self.tmp, env=env, stdin=devnull,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, shipped, b""))

    def test_11_38_print_defaults_allows_no_other_argument(self):
        for args in (["--print-defaults", "case-11-01.txt"],
                     ["case-11-01.txt", "--print-defaults"],
                     ["--print-defaults", "--warn-only"],
                     ["--print-defaults", "--rules", R1],
                     ["--print-defaults", "--print-defaults"],
                     ["--print-defaults", "--"]):
            with self.subTest(args=args):
                self.assertCannot(
                    args, "cannot run: --print-defaults allows no other argument")

    def test_11_39_rules_given_twice(self):
        self.assertCannot(["--rules", R1, "--rules", R2, "case-11-01.txt"],
                          "cannot run: --rules given twice")

    def test_11_39_unknown_option(self):
        self.assertCannot(["--bogus", "case-11-01.txt"],
                          "cannot run: unknown option --bogus")

    def test_rules_without_a_value(self):
        self.assertCannot(["case-11-01.txt", "--rules"], "cannot run: --rules needs a value")
        self.assertCannot(["--rules", "--warn-only", "case-11-01.txt"],
                          "cannot run: --rules needs a value")

    def test_flag_given_a_value(self):
        self.assertCannot(["--warn-only=yes", "case-11-01.txt"],
                          "cannot run: --warn-only takes no value")

    def test_one_line_per_reason(self):
        self.assertCannot(["--bogus", "--rules", R1, "--rules", R2, "case-11-01.txt"],
                          "cannot run: unknown option --bogus",
                          "cannot run: --rules given twice")

    def test_rules_with_an_equals_sign(self):
        self.assertRun(["--rules=" + R1, "case-11-03.txt"], 0, one_file("case-11-03.txt"))

    def test_double_dash_ends_the_options(self):
        self.assertRun(["--rules", R1, "--", "case-11-03.txt"], 0, one_file("case-11-03.txt"))

    def test_a_warning_never_changes_the_exit_status(self):
        self.assertRun(["--rules", R1, "case-11-08.txt"], 0, one_file(
            "case-11-08.txt", warnings=2,
            body=finding("case-11-08.txt", 1, "warn", "assisted-with",
                         "I assisted with planning.", category="hedge")
            + finding("case-11-08.txt", 1, "warn", "as-you-can-see",
                      "As you can see, it worked.", category="tell")))

    def test_the_tool_never_writes(self):
        def snapshot():
            state = {}
            for name in sorted(os.listdir(FX)):
                path = os.path.join(FX, name)
                if os.path.isfile(path):
                    state[name] = (read_bytes(path), os.stat(path).st_mtime_ns)
            return state

        before = snapshot()
        for args in (["--rules", R1, "case-11-08.txt", "case-11-01.txt"],
                     ["--rules", R2, "--stale-check", "case-11-26.txt"],
                     ["case-11-37.txt"], ["--print-defaults"],
                     ["--rules", R1, "no-such-file.txt"]):
            run_cli(args)
        self.assertEqual(snapshot(), before)


class StrictnessCase(ToneCase):
    def run_scratch(self, data):
        return run_cli(["--rules", self.scratch(data), "case-11-01.txt"])

    def assertScratch(self, data, *lines):
        self.assertEqual(self.run_scratch(data), (2, "", stderr_of(*lines)))

    def test_11_40_unknown_key_in_a_rule(self):
        data = self.r1()
        self.r1_rule(data, "turnkey")["colour"] = "red"
        self.assertScratch(data, "self-test: rule turnkey: unknown key \"colour\"")

    def test_11_40_unknown_key_in_an_exemption(self):
        data = self.r1()
        data["exemptions"][0]["colour"] = "red"
        self.assertScratch(data, "self-test: exemption 1: unknown key \"colour\"")

    def test_11_40_unknown_key_at_the_top(self):
        data = self.r1()
        data["colour"] = "red"
        self.assertScratch(data, "self-test: unknown key \"colour\"")

    def test_11_41_must_fire_as_a_bare_string(self):
        data = self.r1()
        self.r1_rule(data, "turnkey")["must_fire"] = "A turnkey plan."
        self.assertScratch(data, "self-test: rule turnkey: must_fire must be a "
                                 "non-empty array of strings")

    def test_11_42_rationale_with_a_line_feed(self):
        data = self.r1()
        self.r1_rule(data, "turnkey")["rationale"] = "two\nlines"
        self.assertScratch(data, "self-test: rule turnkey: rationale must be one "
                                 "non-empty line")

    def test_11_42_reason_with_a_line_feed(self):
        data = self.r1()
        data["exemptions"][0]["reason"] = "two\nlines"
        self.assertScratch(data, "self-test: exemption 1: reason must be one "
                                 "non-empty line")

    def test_11_43_category_with_a_bracket(self):
        data = self.r1()
        self.r1_rule(data, "assisted-with")["category"] = "he]dge"
        self.assertScratch(data, "self-test: rule assisted-with: category must be a "
                                 "non-empty label without ], line feed or carriage "
                                 "return")

    def test_11_44_empty_text(self):
        data = self.r1()
        self.r1_rule(data, "turnkey")["text"] = ""
        self.assertScratch(data, "self-test: rule turnkey: text must be a non-empty "
                                 "string")

    def test_11_44_empty_anchor(self):
        data = self.r1()
        data["exemptions"][0]["anchor"] = ""
        self.assertScratch(data, "self-test: exemption 1: anchor must be a non-empty "
                                 "string")

    def test_11_45_char_rule_of_two_code_points(self):
        data = self.r1()
        self.r1_rule(data, "no-em-dash")["text"] = "\U0001f1e9\U0001f1ea"
        self.assertScratch(data, "self-test: rule no-em-dash: text of a char rule must "
                                 "be exactly one code point")

    def test_11_45_char_rule_with_case(self):
        data = self.r1()
        self.r1_rule(data, "no-em-dash")["case"] = "sensitive"
        self.assertScratch(data, "self-test: rule no-em-dash: a char rule cannot set case")

    def test_11_46_empty_rules_array(self):
        self.assertScratch({"rules": [], "exemptions": []},
                           "self-test: rules must be a non-empty array")

    def test_11_47_regex_matching_the_empty_string(self):
        data = self.r1()
        data["rules"].append({"id": "empty", "level": "warn", "kind": "regex",
                              "text": "x*", "rationale": WHY,
                              "must_fire": ["x"], "must_not": ["y"]})
        self.assertScratch(data, "self-test: rule empty: regex matches the empty string")

    def test_11_48_two_broken_rules_two_lines(self):
        data = self.r1()
        self.r1_rule(data, "turnkey")["must_fire"] = ["A turn key plan."]
        self.r1_rule(data, "lower-we")["case"] = "loud"
        self.assertScratch(data,
                           "self-test: rule turnkey: must_fire example 1 gives no finding",
                           "self-test: rule lower-we: case must be insensitive or "
                           "sensitive")

    def test_a_rule_file_that_is_not_an_object(self):
        path = os.path.join(self.tmp, "list.json")
        write_bytes(path, b"[]\n")
        self.assertCannot(["--rules", path, "case-11-01.txt"],
                          "self-test: the rule file must be a JSON object")

    def test_an_id_outside_the_pattern(self):
        data = self.r1()
        self.r1_rule(data, "turnkey")["id"] = "Turn_Key"
        code, out, err = self.run_scratch(data)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("self-test: rule #1: id must be lower-case letters, digits "
                      "and hyphens", err.splitlines())

    def test_an_id_with_a_trailing_line_feed(self):
        data = self.r1()
        self.r1_rule(data, "turnkey")["id"] = "turnkey\n"
        code, out, err = self.run_scratch(data)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("self-test: rule #1: id must be lower-case letters, digits "
                      "and hyphens", err.splitlines())

    def test_a_duplicate_key_in_the_file(self):
        path = os.path.join(self.tmp, "dup.json")
        write_bytes(path, b"{\"rules\": [], \"rules\": []}\n")
        code, out, err = run_cli(["--rules", path, "case-11-01.txt"])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("self-test: duplicate key \"rules\"", err.splitlines())


class PinnedRuleCase(ToneCase):
    """Rules of spec sections 4 and 5 that the tool follows, each pinned by one exact run."""

    def phrase_rule(self, rule_id, text, fire, no):
        return {"id": rule_id, "level": "error", "kind": "phrase", "text": text,
                "rationale": WHY, "must_fire": [fire], "must_not": [no]}

    def test_a_phrase_space_matches_a_line_break(self):
        rules = self.scratch({"rules": [self.phrase_rule(
            "tp", "team player", "A team player here.", "A teamplayer here.")]})
        write_bytes(os.path.join(self.tmp, "wrap.txt"), b"I am a team\nplayer, really.\n")
        self.assertRun(["--rules", rules, "wrap.txt"], 1, one_file(
            "wrap.txt", errors=1, body=finding(
                "wrap.txt", 1, "error", "tp", "I am a team player, really.")), cwd=self.tmp)

    def test_a_non_word_edge_needs_no_boundary(self):
        rules = self.scratch({"rules": [self.phrase_rule(
            "cpp", "C++", "We used C++ daily.", "We used C daily.")]})
        write_bytes(os.path.join(self.tmp, "cpp.txt"), b"We used C++11 daily.\n")
        self.assertRun(["--rules", rules, "cpp.txt"], 1, one_file(
            "cpp.txt", errors=1, body=finding(
                "cpp.txt", 1, "error", "cpp", "We used C++11 daily.")), cwd=self.tmp)

    def test_a_non_word_left_edge_needs_no_boundary(self):
        rules = self.scratch({"rules": [self.phrase_rule(
            "net", ".NET", "We used .NET daily.", "We used NET daily.")]})
        write_bytes(os.path.join(self.tmp, "net.txt"), b"We used ASP.NET daily.\n")
        self.assertRun(["--rules", rules, "net.txt"], 1, one_file(
            "net.txt", errors=1, body=finding(
                "net.txt", 1, "error", "net", "We used ASP.NET daily.")), cwd=self.tmp)

    def test_an_exemption_covers_only_its_own_rule(self):
        rules = self.scratch({
            "rules": [self.phrase_rule("a", "alpha", "An alpha here.", "A plan here."),
                      self.phrase_rule("b", "gamma", "A gamma here.", "A plan here.")],
            "exemptions": [{"rule": "a", "anchor": "alpha and gamma", "reason": "invented reason"}]})
        write_bytes(os.path.join(self.tmp, "ex.txt"), b"We use alpha and gamma.\n")
        self.assertRun(["--rules", rules, "ex.txt"], 1, one_file(
            "ex.txt", errors=1, body=finding(
                "ex.txt", 1, "error", "b", "We use alpha and gamma.")), cwd=self.tmp)

    def test_a_stale_anchor_is_matched_case_sensitively(self):
        rules = self.scratch({
            "rules": [self.phrase_rule("tk", "turnkey", "A turnkey plan.", "A plan.")],
            "exemptions": [{"rule": "tk", "anchor": "Turnkey Plan", "reason": "invented reason"}]})
        write_bytes(os.path.join(self.tmp, "stale.txt"), b"A turnkey plan we built.\n")
        self.assertRun(["--rules", rules, "--stale-check", "stale.txt"], 1,
                       finding("stale.txt", 1, "error", "tk", "A turnkey plan we built.")
                       + "stale exemption: tk\n" + summary(1, 2, 0), cwd=self.tmp)


class Revision5Case(ToneCase):
    def test_11_52_repeated_warn_only(self):
        once = run_cli(["--rules", R1, "--warn-only", "case-11-01.txt"])
        twice = run_cli(["--rules", R1, "--warn-only", "--warn-only", "case-11-01.txt"])
        self.assertEqual(twice, once)
        self.assertEqual(twice[0], 0)

    def test_11_53_a_line_feed_in_a_name_is_escaped(self):
        write_bytes(os.path.join(self.tmp, "bad\nname.txt"),
                    read_bytes(os.path.join(FX, "case-11-01.txt")))
        code, out, err = run_cli(["--rules", os.path.join(FX, R1), "bad\nname.txt"],
                                 cwd=self.tmp)
        self.assertEqual(code, 1)
        lines = out.split("\n")
        self.assertTrue(lines[0].startswith("bad\\nname.txt:1: error turnkey"), lines[0])
        self.assertFalse(any(line.startswith("name.txt") for line in lines))

    def test_11_54_stops_at_the_command_line_stage(self):
        self.assertEqual(run_cli(["--rules", "missing.json"]),
                         (2, "", "cannot run: no input file\n"))

    def test_11_54_stops_at_the_rule_file_stage(self):
        code, out, err = run_cli(["--rules", "missing.json", "case-11-01.txt"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(len(err.splitlines()), 1)
        self.assertIn("rule file", err)

    def test_an_unreadable_name_is_escaped_on_stderr(self):
        self.assertEqual(run_cli(["--rules", R1, "no\nsuch.txt"]),
                         (2, "", "cannot run: cannot read no\\nsuch.txt\n"))

    def test_stale_check_over_several_files_uses_any_file(self):
        self.assertRun(["--rules", R1, "--stale-check", "case-11-03.txt", "case-11-12.txt"],
                       0, "case-11-03.txt: clean\ncase-11-12.txt: clean\n" + summary(2, 0, 0))
        self.assertRun(["--rules", R1, "--stale-check", "case-11-12.txt", "case-11-03.txt"],
                       0, "case-11-12.txt: clean\ncase-11-03.txt: clean\n" + summary(2, 0, 0))

    def test_regex_dollar_also_matches_before_a_final_line_feed(self):
        data = {"rules": [{"id": "ends-plan", "level": "error", "kind": "regex",
                           "text": "plan$", "case": "sensitive", "rationale": WHY,
                           "must_fire": ["the plan"], "must_not": ["plans"]}],
                "exemptions": []}
        path = self.scratch(data)
        write_bytes(os.path.join(self.tmp, "lf.txt"), b"We wrote the plan\n")
        write_bytes(os.path.join(self.tmp, "mid.txt"), b"the plan\nand more text here\n")
        self.assertEqual(run_cli(["--rules", path, "lf.txt"], cwd=self.tmp),
                         (1, finding("lf.txt", 1, "error", "ends-plan", "We wrote the plan")
                          + summary(1, 1, 0), ""))
        self.assertEqual(run_cli(["--rules", path, "mid.txt"], cwd=self.tmp),
                         (0, one_file("mid.txt"), ""))


class ApiCase(ToneCase):
    def test_run_returns_a_result(self):
        result = tone.run(rules_path=os.path.join(FX, R1),
                          files=[os.path.join(FX, "case-11-01.txt")])
        self.assertEqual((result.exit_code, result.ran, result.error), (1, True, ""))
        self.assertTrue(result.text.endswith(summary(1, 1, 0)))

    def test_run_never_raises(self):
        for kwargs in ({"files": None}, {"files": [None]}, {"files": [], "rules_path": 5}):
            result = tone.run(**kwargs)
            self.assertEqual((result.exit_code, result.ran), (2, False))
            self.assertNotEqual(result.error, "")
            self.assertFalse(result.error.endswith("\n"))

    def test_load_rules_defaults_to_the_shipped_file(self):
        self.assertEqual(tone.load_rules().data, load_json(DEFAULT_RULES))

    def test_the_default_file_is_written_the_way_the_brief_says(self):
        data = load_json(DEFAULT_RULES)
        self.assertEqual(list(data), ["rules", "exemptions"])
        self.assertEqual(data["exemptions"], [])
        keys = ["id", "level", "kind", "text", "case", "rationale", "must_fire", "must_not"]
        for rule in data["rules"]:
            self.assertEqual(list(rule), keys)
            self.assertEqual((rule["kind"], rule["case"]), ("phrase", "insensitive"))
            self.assertEqual(len(rule["must_fire"]), 1)
            self.assertEqual(len(rule["must_not"]), 1)
        self.assertEqual([r["id"] for r in data["rules"]],
                         ["results-driven", "team-player", "go-getter", "outside-the-box",
                          "detail-oriented", "assisted-with", "various", "etc"])
        self.assertEqual([r["level"] for r in data["rules"]],
                         ["error"] * 4 + ["warn"] * 4)
        with open(DEFAULT_RULES, encoding="utf-8", newline="") as handle:
            text = handle.read()
        self.assertEqual(text, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


class FixtureCase(unittest.TestCase):
    def generated(self, outdir):
        with open(os.devnull, "rb") as devnull:
            done = subprocess.run(
                [sys.executable, "-B", os.path.join(FX, "make_fixtures.py"), outdir],
                stdin=devnull, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, b"", b""))

    def committed(self):
        return sorted(n for n in os.listdir(FX)
                      if n != "make_fixtures.py" and not n.startswith("__"))

    def test_the_committed_fixtures_are_what_the_generator_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.generated(tmp)
            self.assertEqual(sorted(os.listdir(tmp)), self.committed())
            for name in self.committed():
                self.assertEqual(read_bytes(os.path.join(tmp, name)),
                                 read_bytes(os.path.join(FX, name)), name)

    def test_the_generator_is_deterministic(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            self.generated(one)
            self.generated(two)
            for name in os.listdir(one):
                self.assertEqual(read_bytes(os.path.join(one, name)),
                                 read_bytes(os.path.join(two, name)), name)

    def test_every_case_file_ends_with_its_line_ending(self):
        for name in self.committed():
            if not name.endswith(".txt"):
                continue
            data = read_bytes(os.path.join(FX, name))
            if name == "case-11-32.txt":
                self.assertTrue(data.endswith(b"\r") and b"\n" not in data, name)
            elif name == "case-11-31.txt":
                self.assertTrue(data.endswith(b"\r\n") and data.count(b"\r") == data.count(b"\n"),
                                name)
            else:
                self.assertTrue(data.endswith(b"\n") and not data.endswith(b"\n\n"), name)
                self.assertNotIn(b"\r", data, name)

    def test_no_file_holds_an_invisible_or_direction_character(self):
        paths = [os.path.join(FX, n) for n in os.listdir(FX) if not n.startswith("__")]
        paths += [DEFAULT_RULES, os.path.abspath(__file__),
                  os.path.join(SRC, "career_track_record", "tone.py")]
        for path in paths:
            with open(path, "rb") as handle:
                text = handle.read().decode("utf-8")
            bad = sorted(set(ch for ch in text if unicodedata.category(ch) == "Cf"
                             or ch in "\u2028\u2029"))
            self.assertEqual(bad, [], path)

    def test_every_tone_fixture_is_valid_utf8(self):
        for name in os.listdir(FX):
            if name.startswith("__"):
                continue
            read_bytes(os.path.join(FX, name)).decode("utf-8")


class K12PinsCase(ToneCase):
    """One pin per rule of docs/specs/tone-and-tells.md that a one-line mutant of
    tone.py or the default rule file used to get past the whole suite."""

    def checked(self, data, body, **options):
        """Run a scratch rule file over one file holding body; return the Result."""
        name = os.path.join(self.tmp, "pin.txt")
        write_bytes(name, body.encode("utf-8"))
        result = tone.run(rules_path=self.scratch(data), files=[name], **options)
        return name, result

    def test_the_default_rationales_are_the_ones_section_9_prints(self):
        # Section 9, the default rule set: "This ships as the tool's default rule file."
        # The rationale column is printed with every finding (section 3.1).
        expected = [
            ("results-driven", "A label the reader cannot check; show a result instead."),
            ("team-player", "A claim every applicant makes; name what you did with the team."),
            ("go-getter", "Hype that reads as filler."),
            ("outside-the-box", "A cliché in place of the idea itself."),
            ("detail-oriented", "Shows care better than it claims it."),
            ("assisted-with", "Names a supporting role without saying what you did."),
            ("various", "A vague quantity; name the things or the number."),
            ("etc", "A trailing list hides the item that mattered."),
        ]
        data = load_json(DEFAULT_RULES)
        self.assertEqual([(r["id"], r["rationale"]) for r in data["rules"]], expected)

    def test_a_phrase_ending_inside_a_folded_character_is_not_whole(self):
        # Section 4, phrase: "matched as whole words", with `case: insensitive` using
        # "full Unicode case folding". U+00DF folds to "ss", so in the folded text "mas"
        # (in Ma, U+00DF) is followed by the word character "s", and "sa" (in U+00DF, a)
        # is preceded by one: neither has a boundary, so neither is a match.
        sharp = "ß"
        for text, body in (("mas", "Ma" + sharp + "\n"), ("sa", sharp + "a\n")):
            with self.subTest(text=text):
                data = {"rules": [{"id": "part", "level": "warn", "kind": "phrase",
                                   "text": text, "rationale": WHY,
                                   "must_fire": ["A %s." % text],
                                   "must_not": ["A %sks." % text]}]}
                name, result = self.checked(data, body)
                self.assertEqual((result.exit_code, result.text),
                                 (0, one_file(name)), result)

    def test_a_zero_width_match_inside_the_text_is_no_finding(self):
        # Section 4, regex: "An empty match is never a finding." The pattern does not
        # match the empty string as a whole, but its lookahead matches with no width
        # before the b of the file.
        data = {"rules": [{"id": "zero", "level": "warn", "kind": "regex",
                           "text": "x|(?=b)", "rationale": WHY,
                           "must_fire": ["x"], "must_not": ["a"]}]}
        self.assertEqual(tone.self_test(tone.load_rules(self.scratch(data))), [])
        name, result = self.checked(data, "ab\n")
        self.assertEqual((result.exit_code, result.text), (0, one_file(name)), result)

    def test_a_char_rule_is_case_sensitive(self):
        # Section 4, char: "the single code point in `text`, anywhere it occurs,
        # case-sensitive." Only the upper-case Q is found, not the two q.
        data = {"rules": [{"id": "big-q", "level": "warn", "kind": "char",
                           "text": "Q", "rationale": WHY,
                           "must_fire": ["Q"], "must_not": ["z"]}]}
        name, result = self.checked(data, "q Q q\n")
        self.assertEqual((result.exit_code, result.text), (0, one_file(
            name, warnings=1, body=finding(name, 1, "warn", "big-q", "q Q q"))), result)

    def test_a_sentence_end_needs_whitespace_or_the_end_of_the_file(self):
        # Section 7: "A sentence end is a `.`, `!` or `?`, followed by any number of
        # closing quotes or brackets ..., followed by whitespace or the end of the
        # file." The dot in 3.5 is followed by a digit, so it ends nothing.
        name = os.path.join(self.tmp, "version.txt")
        write_bytes(name, b"A 3.5 turnkey plan.\n")
        self.assertRun(["--rules", os.path.join(FX, R1), name], 1, one_file(
            name, errors=1, body=finding(
                name, 1, "error", "turnkey", "A 3.5 turnkey plan.")))

    def test_stale_exemptions_print_in_exemption_order(self):
        # Section 5, stale anchors: "one line per stale exemption, in exemption order".
        # The exemptions name the rules in the reverse of the rule file's order.
        data = self.r1()
        data["exemptions"] = [
            {"rule": "no-em-dash", "anchor": "an anchor found nowhere",
             "reason": "invented reason"},
            {"rule": "turnkey", "anchor": "another anchor found nowhere",
             "reason": "invented reason"}]
        name, result = self.checked(data, "No anchor here.\n", stale_check=True)
        self.assertEqual((result.exit_code, result.text), (1, (
            "%s: clean\nstale exemption: no-em-dash\nstale exemption: turnkey\n" % name
            + summary(1, 2, 0))), result)


if __name__ == "__main__":
    unittest.main()
