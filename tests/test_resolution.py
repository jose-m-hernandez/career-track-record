"""Tests for the resolution layer: flag, then environment, then the setup config, then the
command's own default. All data here is invented.

Every case runs the command line in a child process with CTR_CONFIG_DIR, HOME and the working
directory set to fresh temporary folders, and with git's global and system configuration
pointed at the null device, so no case reads or writes a real config.

The case "no config means no change" compares each command with outputs captured by running
the code of the release before the config existed (tests/fixtures/resolution/base-outputs.json,
made by ``observe_all`` run against that code once)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FX = os.path.join(ROOT, "tests", "fixtures")
BASE_OUTPUTS = os.path.join(FX, "resolution", "base-outputs.json")
sys.path.insert(0, SRC)

from career_track_record import cli, config  # noqa: E402
from tests.test_ab import Setup as AbSetup  # noqa: E402
from tests.test_panel import Setup as PanelSetup  # noqa: E402
from tests.test_record_folder import git_env  # noqa: E402

# The source folder the child processes run from. Only the capture of the base outputs
# changes it.
RUN_SRC = SRC

CLAIMS_LIST = "approved\tLed a team of six engineers at Example Corp.\n"
CLAIMS_FILE = "Led a team of six engineers at Example Corp.\n"
CONTROL = "Example"

# A name holding a line feed, a tab, ESC, U+202E and a backslash.
ODD = "a\nb\tc" + chr(0x1B) + "d" + chr(0x202E) + "e\\f"
ODD_SHOWN = "a\\nb\\tc\\x1bd\\u202ee\\\\f"

BREAKAGES = (
    ("unknown key", '{"config-version": 1, "recrod-folder": "/a"}', "unknown key recrod-folder"),
    ("repeated key", '{"config-version": 1, "record-folder": "/a", "record-folder": "/b"}',
     "repeated key record-folder"),
    ("version 2", '{"config-version": 2, "record-folder": "/a"}',
     "config-version is from a newer version"),
    ("relative folder", '{"config-version": 1, "record-folder": "a"}',
     "record-folder must be an absolute path"),
    ("non-string", '{"config-version": 1, "record-folder": 3}', "record-folder must be a string"),
    ("not UTF-8", b'{"config-version": 1, "record-folder": "/a\xff"}', "cannot read config"),
)


def message_6(reason):
    return ("cannot run: the track-record config is not usable (%s); run track-record setup "
            "--folder <folder>\n" % reason)


class Sandbox(unittest.TestCase):
    """Fresh config folder, home and working folders, and a way to run the command line."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)
        self.home = os.path.join(self.tmp, "home")
        self.cwd = os.path.join(self.tmp, "cwd")
        self.record = os.path.join(self.tmp, "record")
        self.cfg_dir = os.path.join(self.tmp, "cfg")
        self.cfg = os.path.join(self.cfg_dir, "config.json")
        for folder in (self.home, self.cwd):
            os.mkdir(folder)

    def env(self, extra=None, path=None):
        env = git_env()
        for name in ("CTR_CONFIG_DIR", "XDG_CONFIG_HOME", "BARRED_STRINGS_PATH"):
            env.pop(name, None)
        env.update({"CTR_CONFIG_DIR": self.cfg_dir, "HOME": self.home, "PYTHONPATH": RUN_SRC,
                    "PYTHONDONTWRITEBYTECODE": "1"})
        if path is not None:
            env["PATH"] = path
        env.update(extra or {})
        return env

    def cli(self, *args, cwd=None, extra=None, path=None):
        """(exit code, standard output, standard error) of the command line."""
        proc = subprocess.run([sys.executable, "-m", "career_track_record"] + list(args),
                              cwd=cwd or self.cwd, env=self.env(extra, path),
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
        return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")

    def put_cfg(self, folder=None, raw=None):
        os.makedirs(self.cfg_dir, exist_ok=True)
        data = raw if raw is not None else json.dumps(
            {"config-version": 1, "record-folder": folder})
        with open(self.cfg, "wb") as handle:
            handle.write(data if isinstance(data, bytes) else data.encode("utf-8"))

    def put(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        mode = "wb" if isinstance(data, bytes) else "w"
        with open(path, mode, **({} if mode == "wb" else {"encoding": "utf-8", "newline": ""})) \
                as handle:
            handle.write(data)
        return path

    def fixture(self, name, to):
        """Copy a fixture file or folder from tests/fixtures into ``to`` and return the copy."""
        source = os.path.join(FX, name)
        os.makedirs(os.path.dirname(to), exist_ok=True)
        if os.path.isdir(source):
            shutil.copytree(source, to, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copyfile(source, to)
        return to

    def record_with(self, **files):
        """Make the record folder holding the named files (name -> text) and a config naming
        it; returns the folder."""
        os.makedirs(self.record, exist_ok=True)
        for name, text in files.items():
            self.put(os.path.join(self.record, name), text)
        self.put_cfg(self.record)
        return self.record

    def using(self, path):
        return "using %s (from config %s)\n" % (path, self.cfg)


# ---------------------------------------------------------------------------------------
# What every command does with no config, captured from the code before the config existed.

def _normal(text, tmp):
    import re
    text = text.replace(tmp, "<T>")
    return re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "<DATE>", text)


class Observer(object):
    """Runs each command of the path table, given all its paths as flags, in fresh folders."""

    def __init__(self, case):
        self.case = case
        self.seen = {}

    def run(self, name, args, cwd):
        code, out, err = self.case.cli(*args, cwd=cwd)
        tmp = self.case.tmp
        self.seen[name] = [code, _normal(out, tmp), _normal(err, tmp)]
        return code

    def all(self):
        case = self.case
        work = os.path.join(case.tmp, "work")
        os.mkdir(work)
        K = os.path.join(work, "keywords")
        case.fixture("keywords/postings-p1", os.path.join(K, "postings"))
        case.fixture("keywords/terms-t1.tsv", os.path.join(K, "terms.tsv"))
        case.fixture("keywords/copy.txt", os.path.join(K, "copy.txt"))
        pairs = ("--postings", "keywords/postings", "--terms", "keywords/terms.tsv")
        self.run("keywords-demand", ["keywords", "demand"] + list(pairs), work)
        self.run("keywords-demand-out", ["keywords", "demand"] + list(pairs)
                 + ["--out", "keywords/out.txt"], work)
        self.run("keywords-coverage", ["keywords", "coverage", "--terms", "keywords/terms.tsv",
                                       "keywords/copy.txt"], work)
        self.run("keywords-report", ["keywords", "report"] + list(pairs)
                 + ["--copy", "keywords/copy.txt"], work)
        # Missing flags, no config: argparse's own words.
        self.run("keywords-demand-bare", ["keywords", "demand"], work)
        self.run("keywords-demand-no-terms", ["keywords", "demand", "--postings",
                                              "keywords/postings"], work)
        self.run("keywords-coverage-bare", ["keywords", "coverage"], work)
        self.run("keywords-report-bare", ["keywords", "report"], work)
        B = os.path.join(work, "barred")
        for name in ("list-l1.txt", "clean.txt", "two.txt", "nocontrol.txt"):
            case.fixture("barred/" + name, os.path.join(B, name))
        self.run("barred", ["barred", "--list", "barred/list-l1.txt", "--control",
                            "Example Corp", "barred/clean.txt", "barred/two.txt",
                            "barred/nocontrol.txt"], work)
        self.run("barred-no-list", ["barred", "--control", "Example Corp",
                                    "barred/clean.txt"], work)
        T = os.path.join(work, "tone")
        case.fixture("tone/rules-r1.json", os.path.join(T, "rules.json"))
        case.fixture("tone/case-11-01.txt", os.path.join(T, "case.txt"))
        self.run("tone", ["tone", "--rules", "tone/rules.json", "tone/case.txt"], work)
        self.run("tone-default-rules", ["tone", "tone/case.txt"], work)
        case.put(os.path.join(work, "claims", "list.tsv"), CLAIMS_LIST)
        case.put(os.path.join(work, "claims", "f.txt"), CLAIMS_FILE)
        self.run("claims", ["claims", "--list", "claims/list.tsv", "--control", CONTROL,
                            "claims/f.txt"], work)
        self.run("claims-no-list", ["claims", "--control", CONTROL, "claims/f.txt"], work)
        case.fixture("record/known", os.path.join(work, "record"))
        self.run("record", ["record", "record/record.txt"], work)
        D = os.path.join(work, "drafts")
        case.fixture("drafts/letter.txt", os.path.join(D, "letter.txt"))
        self.run("drafts-check", ["drafts", "check", "drafts/letter.txt"], work)
        self.run("drafts-extract", ["drafts", "extract", "drafts/letter.txt", "v2", "--out",
                                    "drafts/v2.txt"], work)
        for number, setup in enumerate((AbSetup(case), PanelSetup(case))):
            command = ("ab", "panel")[number]
            plan = setup.plan_path
            for step in ("freeze", "run", "score"):
                self.run("%s-%s" % (command, step), [command, step, plan], setup.folder)
        return self.seen


def observe_all():
    """The outputs of every command with all its paths given and no config, as a dict (the
    content of base-outputs.json)."""
    case = Sandbox("setUp")
    case.setUp()
    try:
        return Observer(case).all()
    finally:
        case.doCleanups()


class NoConfigMeansNoChange(Sandbox):
    def test_s1_claims_without_list_and_no_config(self):
        code, out, err = self.cli("claims", "--control", CONTROL, "f.txt")
        with open(BASE_OUTPUTS, encoding="utf-8") as handle:
            expected = json.load(handle)["claims-no-list"]
        self.assertEqual([code, out, err.replace(self.tmp, "<T>")], [expected[0], "", expected[2]])
        self.assertEqual(code, 2)

    def test_s2_every_command_with_all_paths_as_flags_and_no_config(self):
        os.makedirs(self.cfg_dir)
        with open(BASE_OUTPUTS, encoding="utf-8") as handle:
            expected = json.load(handle)
        got = Observer(self).all()
        self.assertEqual(sorted(got), sorted(expected))
        for name in sorted(expected):
            with self.subTest(command=name):
                self.assertEqual(got[name], expected[name])

    def test_s2_the_captured_outputs_cover_every_command_of_the_table(self):
        with open(BASE_OUTPUTS, encoding="utf-8") as handle:
            names = set(json.load(handle))
        for need in ("keywords-demand", "keywords-demand-out", "keywords-coverage",
                     "keywords-report", "barred", "tone", "claims", "record", "drafts-check",
                     "drafts-extract", "ab-freeze", "ab-run", "ab-score", "panel-freeze",
                     "panel-run", "panel-score"):
            self.assertIn(need, names)

    def test_s2_the_commands_ran_where_the_capture_says(self):
        with open(BASE_OUTPUTS, encoding="utf-8") as handle:
            expected = json.load(handle)
        # A capture where nothing ran would make the comparison empty: the successes are real.
        self.assertEqual(expected["keywords-demand"][0], 0)
        self.assertEqual(expected["claims"][0], 0)
        self.assertEqual(expected["ab-run"][0], 0, expected["ab-run"])
        self.assertEqual(expected["panel-run"][0], 0, expected["panel-run"])


# ---------------------------------------------------------------------------------------
# The config supplies a default

class ClaimsFromTheConfig(Sandbox):
    def test_s3_claims_runs_as_with_the_flag_plus_one_using_line(self):
        self.record_with(**{"claims-list.txt": CLAIMS_LIST})
        self.put(os.path.join(self.cwd, "f.txt"), CLAIMS_FILE)
        listed = os.path.join(self.record, "claims-list.txt")
        flagged = self.cli("claims", "--list", listed, "--control", CONTROL, "f.txt")
        self.assertEqual(flagged[0], 0, flagged)
        code, out, err = self.cli("claims", "--control", CONTROL, "f.txt")
        self.assertEqual((code, out), (flagged[0], flagged[1]))
        self.assertEqual(err, self.using(listed))
        self.assertEqual(flagged[2], "")

    def test_s4_a_flag_wins_and_a_broken_config_makes_no_difference(self):
        self.record_with(**{"claims-list.txt": "approved\tSomething else entirely.\n"})
        self.put(os.path.join(self.cwd, "mine.tsv"), CLAIMS_LIST)
        self.put(os.path.join(self.cwd, "f.txt"), CLAIMS_FILE)
        args = ("claims", "--list", "mine.tsv", "--control", CONTROL, "f.txt")
        good = self.cli(*args)
        self.assertEqual(good, (0, good[1], ""))
        for _name, raw, _reason in BREAKAGES:
            with self.subTest(_name):
                self.put_cfg(raw=raw)
                self.assertEqual(self.cli(*args), good)

    def test_s6_a_missing_record_folder_is_message_6_with_nothing_on_standard_output(self):
        self.put_cfg(self.record)
        self.put(os.path.join(self.cwd, "f.txt"), CLAIMS_FILE)
        code, out, err = self.cli("claims", "--control", CONTROL, "f.txt")
        self.assertEqual((code, out, err), (2, "", message_6("the record folder is missing")))
        # Given every path, nothing changes.
        self.put(os.path.join(self.cwd, "mine.tsv"), CLAIMS_LIST)
        self.assertEqual(self.cli("claims", "--list", "mine.tsv", "--control", CONTROL,
                                  "f.txt")[0], 0)

    def test_s6_a_record_folder_that_is_a_file_is_the_same_message(self):
        self.put(self.record, "not a folder\n")
        self.put_cfg(self.record)
        self.put(os.path.join(self.cwd, "f.txt"), CLAIMS_FILE)
        code, out, err = self.cli("claims", "--control", CONTROL, "f.txt")
        self.assertEqual((code, out, err), (2, "", message_6("the record folder is missing")))

    def test_s7_every_breakage_is_message_6_naming_the_key_or_rule(self):
        self.put(os.path.join(self.cwd, "f.txt"), CLAIMS_FILE)
        for name, raw, reason in BREAKAGES:
            with self.subTest(name):
                self.put_cfg(raw=raw)
                code, out, err = self.cli("claims", "--control", CONTROL, "f.txt")
                self.assertEqual((code, out, err), (2, "", message_6(reason)))
        self.put_cfg(raw='{"config-version": 1, "recrod-folder": "/a"}')
        self.assertIn("unknown key recrod-folder", self.cli("claims", "--control", CONTROL,
                                                          "f.txt")[2])

    def test_s7_the_message_prints_no_folder(self):
        self.put_cfg(raw='{"config-version": 1, "record-folder": "relative/%s"}' % "x")
        err = self.cli("claims", "--control", CONTROL, "f.txt")[2]
        self.assertTrue(err.endswith("run track-record setup --folder <folder>\n"), err)
        self.assertNotIn("relative", err)

    def test_a_missing_list_under_the_record_folder_is_the_command_s_own_error(self):
        self.record_with(**{"other.txt": "x\n"})
        self.put(os.path.join(self.cwd, "f.txt"), CLAIMS_FILE)
        code, out, err = self.cli("claims", "--control", CONTROL, "f.txt")
        flagged = self.cli("claims", "--list", os.path.join(self.record, "claims-list.txt"),
                           "--control", CONTROL, "f.txt")
        self.assertEqual((code, out), (flagged[0], flagged[1]))
        self.assertEqual(code, 2)
        self.assertEqual(err, self.using(os.path.join(self.record, "claims-list.txt"))
                         + flagged[2])

    def test_s12_a_percent_and_a_quote_in_the_folder_are_read_as_written(self):
        self.record = os.path.join(self.tmp, '50%d "q" \'s\'')
        self.record_with(**{"claims-list.txt": CLAIMS_LIST})
        self.put(os.path.join(self.cwd, "f.txt"), CLAIMS_FILE)
        code, out, err = self.cli("claims", "--control", CONTROL, "f.txt")
        self.assertEqual(code, 0, err)
        self.assertEqual(err, self.using(os.path.join(self.record, "claims-list.txt")))

    def test_the_using_line_escapes_a_hostile_folder_on_one_line(self):
        self.record = os.path.join(self.tmp, ODD)
        self.record_with(**{"claims-list.txt": CLAIMS_LIST})
        self.put(os.path.join(self.cwd, "f.txt"), CLAIMS_FILE)
        code, out, err = self.cli("claims", "--control", CONTROL, "f.txt")
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "using %s/%s/claims-list.txt (from config %s)\n"
                         % (self.tmp, ODD_SHOWN, self.cfg))
        self.assertEqual(err.count("\n"), 1)


class BarredFromTheConfig(Sandbox):
    def setUp(self):
        Sandbox.setUp(self)
        for name in ("list-l1.txt", "clean.txt"):
            self.fixture("barred/" + name, os.path.join(self.cwd, name))
        self.args = ("barred", "--control", "Example Corp", "clean.txt")

    def test_the_config_list_is_used_with_one_using_line(self):
        shutil_list = os.path.join(self.cwd, "list-l1.txt")
        with open(shutil_list, encoding="utf-8") as handle:
            text = handle.read()
        self.record_with(**{"barred-list.txt": text})
        listed = os.path.join(self.record, "barred-list.txt")
        flagged = self.cli("barred", "--list", listed, "--control", "Example Corp", "clean.txt")
        self.assertEqual(flagged[0], 0, flagged)
        code, out, err = self.cli(*self.args)
        self.assertEqual((code, out), (flagged[0], flagged[1]))
        self.assertEqual(err, self.using(listed))

    def test_s5_the_variable_is_above_the_config_and_gets_no_using_line(self):
        with open(os.path.join(self.cwd, "list-l1.txt"), encoding="utf-8") as handle:
            self.record_with(**{"barred-list.txt": "other entry that matches nothing\n"})
            text = handle.read()
        mine = self.put(os.path.join(self.cwd, "mine.txt"), text)
        flagged = self.cli("barred", "--list", mine, "--control", "Example Corp", "clean.txt")
        code, out, err = self.cli(*self.args, extra={"BARRED_STRINGS_PATH": mine})
        self.assertEqual((code, out, err), flagged)
        self.assertEqual(err, "")

    def test_an_empty_variable_counts_as_absent(self):
        self.record_with(**{"barred-list.txt": "an entry\n"})
        code, out, err = self.cli(*self.args, extra={"BARRED_STRINGS_PATH": ""})
        self.assertEqual(err.splitlines()[0],
                         self.using(os.path.join(self.record, "barred-list.txt")).rstrip("\n"))

    def test_the_flag_wins_over_the_variable_and_the_config(self):
        self.record_with(**{"barred-list.txt": "an entry\n"})
        code, out, err = self.cli("barred", "--list", os.path.join(self.cwd, "list-l1.txt"),
                                  "--control", "Example Corp", "clean.txt",
                                  extra={"BARRED_STRINGS_PATH": "/nowhere"})
        self.assertEqual((code, err), (0, ""))

    def test_s6_message_6(self):
        self.put_cfg(self.record)
        self.assertEqual(self.cli(*self.args), (2, "", message_6("the record folder is missing")))

    def test_s7_breakages(self):
        for name, raw, reason in BREAKAGES:
            with self.subTest(name):
                self.put_cfg(raw=raw)
                self.assertEqual(self.cli(*self.args), (2, "", message_6(reason)))


class ToneFromTheConfig(Sandbox):
    def setUp(self):
        Sandbox.setUp(self)
        self.fixture("tone/case-11-01.txt", os.path.join(self.cwd, "case.txt"))
        self.fixture("tone/rules-r1.json", os.path.join(self.tmp, "rules-r1.json"))

    def test_s9_no_rules_file_in_the_record_folder_falls_back_and_says_so(self):
        self.record_with(**{"other.txt": "x\n"})
        shutil.rmtree(self.cfg_dir)
        plain = self.cli("tone", "case.txt")
        self.put_cfg(self.record)
        code, out, err = self.cli("tone", "case.txt")
        self.assertEqual((code, out), (plain[0], plain[1]))
        self.assertEqual(plain[2], "")
        self.assertEqual(err, "no tone-rules.json in %s; using the shipped rules\n" % self.record)
        self.assertNotIn("using " + self.record, err)

    def test_s9_with_the_file_its_rules_apply_with_one_using_line(self):
        with open(os.path.join(self.tmp, "rules-r1.json"), encoding="utf-8") as handle:
            rules = handle.read()
        self.record_with(**{"tone-rules.json": rules})
        listed = os.path.join(self.record, "tone-rules.json")
        flagged = self.cli("tone", "--rules", listed, "case.txt")
        code, out, err = self.cli("tone", "case.txt")
        self.assertEqual((code, out), (flagged[0], flagged[1]))
        self.assertEqual(err, self.using(listed))
        self.assertNotIn("no tone-rules.json", err)

    def test_s9_the_fallback_line_escapes_the_folder(self):
        self.record = os.path.join(self.tmp, ODD)
        self.record_with(**{"other.txt": "x\n"})
        err = self.cli("tone", "case.txt")[2]
        self.assertEqual(err, "no tone-rules.json in %s/%s; using the shipped rules\n"
                         % (self.tmp, ODD_SHOWN))

    def test_s9a_a_flag_reads_no_config_and_no_config_writes_nothing_to_standard_error(self):
        self.put_cfg(os.path.join(self.tmp, "nowhere"))
        code, out, err = self.cli("tone", "--rules", os.path.join(self.tmp, "rules-r1.json"),
                                  "case.txt")
        self.assertEqual(err, "")
        shutil.rmtree(self.cfg_dir)
        self.assertEqual(self.cli("tone", "case.txt")[2], "")

    def test_a_broken_config_does_not_stop_a_run_given_its_rules(self):
        self.put_cfg(raw="nope")
        code, out, err = self.cli("tone", "--rules", os.path.join(self.tmp, "rules-r1.json"),
                                  "case.txt")
        self.assertEqual(err, "")
        self.assertIn(code, (0, 1))

    def test_s6_and_s7(self):
        self.put_cfg(self.record)
        self.assertEqual(self.cli("tone", "case.txt"),
                         (2, "", message_6("the record folder is missing")))
        for name, raw, reason in BREAKAGES:
            with self.subTest(name):
                self.put_cfg(raw=raw)
                self.assertEqual(self.cli("tone", "case.txt"), (2, "", message_6(reason)))

    def test_print_defaults_never_reads_the_config(self):
        self.put_cfg(raw="nope")
        code, out, err = self.cli("tone", "--print-defaults")
        self.assertEqual((code, err), (0, ""))


class KeywordsFromTheConfig(Sandbox):
    def setUp(self):
        Sandbox.setUp(self)
        self.fixture("keywords/copy.txt", os.path.join(self.cwd, "copy.txt"))

    def make_record(self, with_terms=True):
        self.fixture("keywords/postings-p1", os.path.join(self.record, "postings"))
        if with_terms:
            self.fixture("keywords/terms-t1.tsv", os.path.join(self.record, "terms.tsv"))
        self.put_cfg(self.record)

    def test_s8_demand_runs_on_the_record_folder_with_two_using_lines(self):
        self.make_record()
        postings = os.path.join(self.record, "postings")
        terms = os.path.join(self.record, "terms.tsv")
        flagged = self.cli("keywords", "demand", "--postings", postings, "--terms", terms)
        self.assertEqual(flagged[0], 0, flagged)
        code, out, err = self.cli("keywords", "demand")
        self.assertEqual((code, out), (0, flagged[1]))
        self.assertEqual(err, self.using(postings) + self.using(terms))

    def test_s8_one_flag_given_one_taken_from_the_config(self):
        self.make_record()
        terms = os.path.join(self.record, "terms.tsv")
        own = os.path.join(self.tmp, "own-postings")
        self.fixture("keywords/postings-p1", own)
        code, out, err = self.cli("keywords", "demand", "--postings", own)
        self.assertEqual((code, err), (0, self.using(terms)))
        code, out, err = self.cli("keywords", "demand", "--terms", terms)
        self.assertEqual((code, err), (0, self.using(os.path.join(self.record, "postings"))))

    def test_s8_a_missing_terms_file_is_the_command_s_own_error(self):
        self.make_record(with_terms=False)
        postings = os.path.join(self.record, "postings")
        terms = os.path.join(self.record, "terms.tsv")
        flagged = self.cli("keywords", "demand", "--postings", postings, "--terms", terms)
        code, out, err = self.cli("keywords", "demand")
        self.assertEqual((code, out), (flagged[0], flagged[1]))
        self.assertEqual(code, 2)
        self.assertEqual(err, self.using(postings) + self.using(terms) + flagged[2])

    def test_coverage_and_report(self):
        self.make_record()
        terms = os.path.join(self.record, "terms.tsv")
        postings = os.path.join(self.record, "postings")
        flagged = self.cli("keywords", "coverage", "--terms", terms, "copy.txt")
        code, out, err = self.cli("keywords", "coverage", "copy.txt")
        self.assertEqual((code, out, err), (flagged[0], flagged[1], self.using(terms)))
        flagged = self.cli("keywords", "report", "--postings", postings, "--terms", terms,
                           "--copy", "copy.txt")
        code, out, err = self.cli("keywords", "report", "--copy", "copy.txt")
        self.assertEqual((code, out), (flagged[0], flagged[1]))
        self.assertEqual(err, self.using(postings) + self.using(terms))

    def test_a_missing_positional_is_the_usage_error_it_always_was(self):
        self.make_record()
        code, out, err = self.cli("keywords", "coverage")
        shutil.rmtree(self.cfg_dir)
        again = self.cli("keywords", "coverage")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual((code, out, err), again)

    def test_with_no_config_a_missing_flag_is_argparse_s_own_error(self):
        code, out, err = self.cli("keywords", "demand")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("the following arguments are required: --postings, --terms", err)

    def test_every_flag_given_never_reads_the_config(self):
        self.put_cfg(raw="nope")
        postings = os.path.join(self.tmp, "p")
        terms = os.path.join(self.tmp, "t.tsv")
        self.fixture("keywords/postings-p1", postings)
        self.fixture("keywords/terms-t1.tsv", terms)
        for args in (("demand", "--postings", postings, "--terms", terms),
                     ("coverage", "--terms", terms, "copy.txt"),
                     ("report", "--postings", postings, "--terms", terms, "--copy",
                      "copy.txt")):
            with self.subTest(args[0]):
                code, out, err = self.cli("keywords", *args)
                self.assertEqual((code, err), (0, ""))

    def test_s6_and_s7(self):
        self.put_cfg(self.record)
        self.assertEqual(self.cli("keywords", "demand"),
                         (2, "", message_6("the record folder is missing")))
        for name, raw, reason in BREAKAGES:
            with self.subTest(name):
                self.put_cfg(raw=raw)
                for args in (("demand",), ("coverage", "copy.txt"), ("report", "--copy",
                                                                       "copy.txt")):
                    self.assertEqual(self.cli("keywords", *args), (2, "", message_6(reason)))

    def test_keywords_help_is_the_same_with_a_config_and_without(self):
        plain = self.cli("keywords", "demand", "-h")
        self.put_cfg(raw="nope")
        self.assertEqual(self.cli("keywords", "demand", "-h"), plain)
        self.assertEqual(plain[0], 0)
        self.assertIn("usage: track-record keywords demand [-h] --postings DIR --terms FILE", plain[1])


class HelpAndOutputsKeepTheirDefaults(Sandbox):
    def test_s10_help_for_each_command_with_a_broken_config_is_as_without_one(self):
        commands = (["keywords"], ["keywords", "demand"], ["keywords", "coverage"],
                    ["keywords", "report"], ["barred"], ["tone"], ["claims"], ["record"],
                    ["drafts"], ["ab"], ["ab", "freeze"], ["ab", "run"], ["ab", "score"],
                    ["panel"], ["panel", "freeze"], ["panel", "run"], ["panel", "score"],
                    ["setup"], [])
        plain = {}
        for args in commands:
            plain[tuple(args)] = self.cli(*(args + ["-h"]))
            self.assertEqual(plain[tuple(args)][0], 0, args)
            self.assertEqual(plain[tuple(args)][2], "", args)
        self.put_cfg(raw="not json at all")
        for args in commands:
            with self.subTest(args=args):
                self.assertEqual(self.cli(*(args + ["-h"])), plain[tuple(args)])

    def test_s11_no_default_is_taken_for_a_positional_a_plan_path_or_an_output(self):
        self.record_with(**{"claims-list.txt": CLAIMS_LIST, "terms.tsv": "x\n"})
        os.mkdir(os.path.join(self.record, "postings"))
        before = sorted(os.listdir(self.record))
        # A plan, a version id and an output are never defaulted.
        for args in (("ab", "freeze"), ("panel", "run"), ("drafts", "extract", "f.txt", "v1"),
                     ("drafts", "check"), ("record",), ("barred", "--list", "x"),
                     ("claims", "--list", "x", "--control", "c")):
            with self.subTest(args=args):
                code, out, err = self.cli(*args)
                self.assertEqual((code, out), (2, ""), err)
                self.assertNotIn("using ", err)
        # keywords demand with no --out writes nowhere.
        self.fixture("keywords/postings-p1", os.path.join(self.tmp, "p"))
        self.fixture("keywords/terms-t1.tsv", os.path.join(self.tmp, "t.tsv"))
        code, out, err = self.cli("keywords", "demand", "--postings", os.path.join(self.tmp, "p"),
                                  "--terms", os.path.join(self.tmp, "t.tsv"))
        self.assertEqual(code, 0)
        self.assertEqual(sorted(os.listdir(self.record)), before)
        self.assertEqual(os.listdir(self.cwd), [])

    def test_the_config_is_never_written_by_a_command(self):
        self.record_with(**{"claims-list.txt": CLAIMS_LIST})
        self.put(os.path.join(self.cwd, "f.txt"), CLAIMS_FILE)
        with open(self.cfg, "rb") as handle:
            before = handle.read()
        self.cli("claims", "--control", CONTROL, "f.txt")
        with open(self.cfg, "rb") as handle:
            self.assertEqual(handle.read(), before)
        self.assertEqual(sorted(os.listdir(self.cfg_dir)), ["config.json"])


class TheLayerWritesNothing(Sandbox):
    def test_a_run_that_takes_its_paths_from_the_config_changes_nothing_anywhere(self):
        from tests.test_setup import snapshot
        self.fixture("keywords/postings-p1", os.path.join(self.record, "postings"))
        self.fixture("keywords/terms-t1.tsv", os.path.join(self.record, "terms.tsv"))
        self.fixture("barred/list-l1.txt", os.path.join(self.record, "barred-list.txt"))
        self.fixture("tone/rules-r1.json", os.path.join(self.record, "tone-rules.json"))
        self.put(os.path.join(self.record, "claims-list.txt"), CLAIMS_LIST)
        self.put_cfg(self.record)
        self.put(os.path.join(self.cwd, "f.txt"), CLAIMS_FILE)
        self.fixture("barred/clean.txt", os.path.join(self.cwd, "clean.txt"))
        self.fixture("tone/case-11-01.txt", os.path.join(self.cwd, "case.txt"))
        self.fixture("keywords/copy.txt", os.path.join(self.cwd, "copy.txt"))
        before = snapshot(self.tmp)
        for args in (("claims", "--control", CONTROL, "f.txt"),
                     ("barred", "--control", "Example Corp", "clean.txt"),
                     ("tone", "case.txt"), ("keywords", "demand"),
                     ("keywords", "coverage", "copy.txt"),
                     ("keywords", "report", "--copy", "copy.txt")):
            with self.subTest(args=args):
                code, out, err = self.cli(*args)
                self.assertIn(code, (0, 1, 2))
                self.assertIn("using ", err)
        self.assertEqual(snapshot(self.tmp), before)

    def test_a_missing_or_broken_config_changes_nothing_either(self):
        from tests.test_setup import snapshot
        self.put(os.path.join(self.cwd, "f.txt"), CLAIMS_FILE)
        before = snapshot(self.tmp)
        self.cli("claims", "--control", CONTROL, "f.txt")
        self.put_cfg(raw="nope")
        before = snapshot(self.tmp)
        self.cli("claims", "--control", CONTROL, "f.txt")
        self.assertEqual(snapshot(self.tmp), before)


class DefaultsUnit(Sandbox):
    def test_the_five_names_under_the_record_folder(self):
        self.put_cfg(self.record)
        os.mkdir(self.record)
        found = config.load_defaults({"CTR_CONFIG_DIR": self.cfg_dir})
        for name in ("postings", "terms.tsv", "barred-list.txt", "tone-rules.json",
                     "claims-list.txt"):
            self.assertEqual(found.path(name), os.path.join(self.record, name))
        self.assertEqual(found.using("terms.tsv"),
                         "using %s/terms.tsv (from config %s)" % (self.record, self.cfg))

    def test_no_config_is_none(self):
        self.assertIsNone(config.load_defaults({"CTR_CONFIG_DIR": self.cfg_dir}))

    def test_the_hook_that_fills_a_missing_flag_is_off_after_a_run(self):
        out = os.path.join(self.tmp, "out")
        with open(out, "w") as sink:
            stderr, sys.stderr = sys.stderr, sink
            try:
                code = cli.main(["keywords", "demand"], {"CTR_CONFIG_DIR": self.cfg_dir})
            except SystemExit as stop:
                code = stop.code
            finally:
                sys.stderr = stderr
        self.assertEqual(code, 2)
        self.assertFalse(cli._CATCH_REQUIRED[0])


if __name__ == "__main__":
    unittest.main()
