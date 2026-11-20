"""Tests that the README's diagram of how `track-record barred` reaches OK, FAIL or DEAD agrees
with the tool. Every file used here is an invented fixture.

The README holds a Mermaid block and a plain-text twin of it. The test reads both, checks that
they name the same nodes, then walks the Mermaid graph for one case per verdict and compares
the verdict and the exit code it reaches with what the command line
(`python3 -m career_track_record barred`, run as a subprocess) gives for that case.
"""

import inspect
import os
import re
import subprocess
import sys
import unittest

from tests.test_record_check import fenced_after

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import barred, cli  # noqa: E402

README = os.path.join(ROOT, "README.md")
FX = os.path.join(ROOT, "tests", "fixtures", "barred")
LEAD = "How `track-record barred` reaches OK, FAIL or DEAD"
TWIN_LEAD = "The same picture in plain text"

# Every node: its id, a phrase its Mermaid label holds, and a phrase the plain-text twin holds.
# The code that gives each one (src/career_track_record/):
#   start    cli.py:203-204 (the usage line)
#   pre      barred.py:422-433 (no file, no control, no usable control, no list); cannot run:
#            cli.py:606-608 (one line on standard error, the run's exit code, which is 2)
#   read     barred.py:373-383 (a read that fails is DEAD "cannot read")
#   len      barred.py:384-386 (DEAD "too short"); default 500: cli.py:541, cli.py:211 and the
#            default of barred.run
#   ctl      barred.py:387-388 (DEAD "control not found")
#   hit      barred.py:367-369 (file name) and 392-400 (text)
#   fail     barred.py:404-408 (the entry number only)
#   ok       barred.py:400-402
#   x2/x1/x0 barred.py:442-447
NODES = {
    "start": ("a list, a control, your files", "a list, a control, your files"),
    "pre": ("A file named, a usable control, a usable list?", "no usable list"),
    "cannot": ("cannot run", "cannot run"),
    "read": ("Can the file be read?", "cannot be read"),
    "dead": ("DEAD: the check does not vouch", "DEAD: the check does not vouch"),
    "len": ("At least the minimum length?", "shorter than the minimum"),
    "ctl": ("Is any control string found in it?", "no control string found in it"),
    "hit": ("Does any list entry match the text or the file name?",
            "a list entry matches its text or its file name"),
    "fail": ("FAIL: findings name an entry by number only",
             "FAIL: findings name an entry by number only"),
    "ok": ("OK: control found", "OK: control found"),
    "x2": ("Any file DEAD: exit 2", "any file DEAD        --> exit 2"),
    "x1": ("A FAIL and no DEAD: exit 1", "a FAIL and no DEAD   --> exit 1"),
    "x0": ("Every file OK: exit 0", "every file OK        --> exit 0"),
}

NODE = r'(\w+)(?:\["([^"]*)"\]|\{"([^"]*)"\})?'
EDGE = re.compile(r"^\s*" + NODE + r"\s*(?:--\s*(yes|no)\s*-->|-->)\s*" + NODE + r"\s*$")

# One case per way out of the picture: the answer to each question, and the verdict word
# and exit code the diagram must reach.
CASES = {
    "cannot run": ({"pre": "no"}, "cannot", 2),
    "unreadable": ({"pre": "yes", "read": "no"}, "dead", 2),
    "too short": ({"pre": "yes", "read": "yes", "len": "no"}, "dead", 2),
    "no control": ({"pre": "yes", "read": "yes", "len": "yes", "ctl": "no"}, "dead", 2),
    "a finding": ({"pre": "yes", "read": "yes", "len": "yes", "ctl": "yes", "hit": "yes"},
                  "fail", 1),
    "clean": ({"pre": "yes", "read": "yes", "len": "yes", "ctl": "yes", "hit": "no"}, "ok", 0),
}


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def readme_drawings(text):
    start = text.index(LEAD)
    return fenced_after(text[start:], LEAD), fenced_after(text[start:], TWIN_LEAD)


def parse(mermaid):
    """The labels by node id and the edges as (from, answer, to), or a list of lines it cannot read."""
    labels, edges, unread = {}, [], []
    for line in mermaid.split("\n")[1:]:
        if not line.strip():
            continue
        match = EDGE.match(line)
        if not match:
            unread.append(line)
            continue
        a, a_box, a_diamond, answer, b, b_box, b_diamond = match.groups()
        for ident, label in ((a, a_box or a_diamond), (b, b_box or b_diamond)):
            if label is not None:
                labels[ident] = label
        edges.append((a, answer, b))
    return labels, edges, unread


def walk(edges, answers):
    """The nodes passed from ``start`` when each question gets its answer, in order."""
    node, path = "start", ["start"]
    while True:
        out = [(answer, to) for frm, answer, to in edges if frm == node]
        if not out:
            return path
        if len(out) == 1:
            node = out[0][1]
        elif answers.get(node) in ("yes", "no") and answers[node] in dict(out):
            node = dict(out)[answers[node]]
        else:
            return path + ["?"]
        path.append(node)


def problems(mermaid, twin):
    """What is wrong with the pair of drawings, as a list of short sentences; empty when none."""
    found = []
    labels, edges, unread = parse(mermaid)
    found.extend("cannot read: " + line for line in unread)
    if set(labels) != set(NODES):
        found.append("nodes differ: %s" % sorted(set(labels) ^ set(NODES)))
    for ident, (in_mermaid, in_twin) in NODES.items():
        if in_mermaid not in labels.get(ident, ""):
            found.append("%s: label lacks %r" % (ident, in_mermaid))
        if in_twin not in twin:
            found.append("%s: twin lacks %r" % (ident, in_twin))
    # cli.py:541 and 211, and the default of barred.run: the minimum in both drawings.
    default = cli._parse_barred(["x.txt"])["min_chars"]
    if default != inspect.signature(barred.run).parameters["min_chars"].default:
        found.append("cli and barred.run disagree on the default minimum")
    in_mermaid = re.search(r"minimum length\? (\d+) characters", mermaid)
    in_twin = re.search(r"minimum \((\d+) unless", twin)
    if not in_mermaid or int(in_mermaid.group(1)) != default:
        found.append("the diagram does not state the default minimum, %d" % default)
    if not in_twin or int(in_twin.group(1)) != default:
        found.append("the twin does not state the default minimum, %d" % default)
    for name, (answers, verdict, code) in CASES.items():
        path = walk(edges, answers)
        # "cannot run" is its own exit; every other verdict is followed by an exit node.
        reached = path[-1] if verdict == "cannot" else (path[-2] if len(path) > 1 else "")
        if reached != verdict:
            found.append("%s: reaches %s, not %s" % (name, path[-3:], verdict))
        elif "exit %d" % code not in labels.get(path[-1], ""):
            found.append("%s: exit is not %d" % (name, code))
    return found


class ReadmeDiagramTest(unittest.TestCase):
    def setUp(self):
        self.mermaid, self.twin = readme_drawings(read(README))

    def run_barred(self, files, **kwargs):
        defaults = dict(list_path=os.path.join(FX, "list-l1.txt"), controls=["Example Corp"])
        defaults.update(kwargs)
        return barred.run(files=[os.path.join(FX, f) for f in files], **defaults)

    def test_the_drawings_agree(self):
        self.assertEqual(problems(self.mermaid, self.twin), [])

    def cli(self, *args, controls=("Example Corp",), list_path="list-l1.txt"):
        """Run the real command line, as the README's reader would, and return the process."""
        command = [sys.executable, "-m", "career_track_record", "barred"]
        if list_path is not None:
            command += ["--list", os.path.join(FX, list_path)]
        for control in controls:
            command += ["--control", control]
        command += [os.path.join(FX, f) if f.endswith(".txt") else f for f in args]
        env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"), PYTHONDONTWRITEBYTECODE="1")
        env.pop("BARRED_STRINGS_PATH", None)
        return subprocess.run(command, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=60, cwd=ROOT)

    def stated_exits(self):
        """The exit code each of the four exit statements gives, in the Mermaid and in the twin."""
        labels, _edges, _unread = parse(self.mermaid)
        found = {}
        for ident in ("cannot", "x2", "x1", "x0"):
            found["mermaid " + ident] = int(re.search(r"exit (\d)", labels[ident]).group(1))
        for ident, lead in (("cannot", "cannot run"), ("x2", "any file DEAD"),
                            ("x1", "a FAIL and no DEAD"), ("x0", "every file OK")):
            line = next(l for l in self.twin.split("\n") if lead in l and "exit" in l)
            found["twin " + ident] = int(re.search(r"exit (\d)", line).group(1))
        return found

    def test_the_diagram_reaches_what_the_command_line_gives_for_each_case(self):
        # The command, not barred.run: cli.py:586-608 turns the result into text and an exit code.
        _labels, edges, _unread = parse(self.mermaid)
        stated = self.stated_exits()
        exit_node = {"cannot": "cannot", "dead": "x2", "fail": "x1", "ok": "x0"}
        number = {"one": 1, "two": 2, "three": 3}
        # Cannot run: nothing to check is one line on standard error, no verdict word.
        for name, proc in (
                ("no file", self.cli()),
                ("empty control", self.cli("clean.txt", controls=("",))),
                ("no control", self.cli("clean.txt", controls=())),
                ("no list", self.cli("clean.txt", list_path=None))):
            self.assertEqual(walk(edges, CASES["cannot run"][0])[-1], "cannot")
            self.assertEqual(proc.returncode, CASES["cannot run"][2], name)
            self.assertEqual(proc.returncode, stated["mermaid cannot"], name)
            self.assertEqual(proc.returncode, stated["twin cannot"], name)
            self.assertEqual(proc.stdout, "", name)
            self.assertTrue(proc.stderr.startswith("cannot run"), (name, proc.stderr))
            lines = len(proc.stderr.rstrip("\n").split("\n"))
            for where in (parse(self.mermaid)[0]["cannot"],
                          next(l for l in self.twin.split("\n") if "cannot run" in l)):
                words = re.search(r"(\w+) lines? on standard error", where).group(1)
                self.assertEqual(number[words], lines, (name, where))
        real = {
            "unreadable": "absent.txt",    # barred.py:373-383
            "too short": "short.txt",      # barred.py:384-386
            "no control": "nocontrol.txt",  # barred.py:387-388
            "a finding": "two.txt",        # barred.py:404-408
            "clean": "clean.txt",          # barred.py:400-402
        }
        for name, fixture in real.items():
            answers, verdict, code = CASES[name]
            word = {"dead": "DEAD", "fail": "FAIL", "ok": "OK"}[verdict]
            path = walk(edges, answers)
            self.assertEqual(path[-2], verdict, name)
            proc = self.cli(fixture)
            self.assertTrue(proc.stdout.startswith(word + " "), (name, proc.stdout))
            self.assertEqual(proc.returncode, code, name)
            self.assertEqual(proc.returncode, stated["mermaid " + exit_node[path[-2]]], name)
            self.assertEqual(proc.returncode, stated["twin " + exit_node[path[-2]]], name)
            # The diagram says findings name an entry by number only.
            if verdict == "fail":
                self.assertRegex(proc.stdout, r"entry #\d+")
                self.assertNotIn("moonshot", proc.stdout.lower())
        # An exit code a script sees is the worst file's, as the three exit nodes say.
        for files, code in ((["clean.txt", "two.txt"], 1),
                            (["clean.txt", "two.txt", "nocontrol.txt"], 2), (["clean.txt"], 0)):
            self.assertEqual(self.cli(*files).returncode, code, files)

    def test_a_file_name_alone_makes_a_finding(self):
        # barred.py:367-369: "hit" is the text or the file name.
        result = self.run_barred(["moonshot-plain.txt"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("(file name)", result.text)

    def test_the_worst_file_sets_the_exit(self):
        # barred.py:442-447, and the three exit nodes of the diagram.
        self.assertEqual(self.run_barred(["clean.txt", "two.txt"]).exit_code, 1)
        self.assertEqual(self.run_barred(["clean.txt", "two.txt", "nocontrol.txt"]).exit_code, 2)
        self.assertEqual(self.run_barred(["clean.txt"]).exit_code, 0)

    def test_length_is_tested_before_the_control_and_the_list(self):
        # barred.py:384-388: short.txt holds no control and a listed phrase, and is still DEAD
        # for its length, as the diagram's order says.
        result = self.run_barred(["short.txt"])
        self.assertIn("too short", result.text)
        self.assertLess(len(read(os.path.join(FX, "short.txt"))), 500)

    def test_the_check_catches_a_changed_node_or_exit_code(self):
        # Control: the same checks, run on altered copies of the drawings, must report something.
        self.assertEqual(problems(self.mermaid, self.twin), [])
        changes = [
            (self.mermaid, "exit 1", "exit 0"),
            (self.mermaid, "exit 2", "exit 1"),
            (self.mermaid, "ctl -- no --> dead", "ctl -- no --> ok"),
            (self.mermaid, 'ctl{"Is any control string found in it?"}', 'ctl{"Is a control found?"}'),
            (self.mermaid, 'len -- no --> dead\n', ""),
            (self.mermaid, "  ok --> x0", "  ok --> x1"),
            (self.mermaid, "500 characters", "300 characters"),
            (self.mermaid, "start[", "begin["),
        ]
        for text, old, new in changes:
            self.assertIn(old, text)
            altered = text.replace(old, new, 1)
            self.assertNotEqual(problems(altered, self.twin), [], (old, new))
        for old, new in (("exit 0", "exit 3"), ("minimum (500 unless", "minimum (300 unless"), ("no control string found in it", "something else"),
                         ("--> OK: control found", "--> fine")):
            self.assertIn(old, self.twin)
            self.assertNotEqual(problems(self.mermaid, self.twin.replace(old, new, 1)), [],
                                (old, new))
        extra = self.mermaid + '  ok --> extra["A new node"]\n'
        self.assertNotEqual(problems(extra, self.twin), [])


if __name__ == "__main__":
    unittest.main()
