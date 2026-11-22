"""Tests that the review method names only commands the command line has. Every example here is invented.

The method file is ``docs/review.md``. Its code spans are read for the commands and
subcommands they name, and each is checked against the command line itself. The
parser gives the commands and the keywords modes, ``_AB_SUBCOMMANDS`` gives the steps
of ``ab`` and ``panel``, and ``_DRAFTS_VALUE_OPTIONS`` gives those of ``drafts``. The review sheet in
the file is checked against the rules the file gives for it. No reader is started.
"""

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import cli  # noqa: E402

METHOD = os.path.join(ROOT, "docs", "review.md")
CLI_SPEC = os.path.join(ROOT, "docs", "specs", "cli.md")
PATH_NAME = "docs/review.md"
CLI_WORDS = ("<cli>", "track-record")
GATE4 = tuple("<cli> %s %s PLAN" % (command, step)
              for command in ("ab", "panel") for step in ("freeze", "run", "score"))
KEYS = ("draft", "parent", "posting", "structure", "claims", "barred", "tone", "keywords",
        "parse", "edit review", "cold read", "diff", "hashes", "tailoring",
        "form questions", "ready")
RESULT_WORDS = dict(
    [(key, ("pass", "fail", "pending")) for key in KEYS[3:12]]
    + [("hashes", ("recorded", "pending")), ("tailoring", ("decided", "pending")),
       ("form questions", ("answered", "pending"))])
EXIT_KEYS = ("claims", "barred", "tone", "keywords", "edit review", "cold read", "diff")
OK_WORDS = ("pass", "recorded", "decided", "answered")
WALK = ("structure", "claims", "barred", "tone", "keywords", "parse", "edit review",
        "cold read", "diff", "hashes", "tailoring", "form questions")
MD_PARSE = "pass (not a PDF: no parse step)"
PDF_LABELS = ("pdf sha256 ", "extracted text sha256 ", "parent sha256 ")
TEXT_LABELS = ("draft sha256 ", "parent sha256 ")
EXIT_N = re.compile(r"\bexit \d+")
FULL_HASH = re.compile(r"[0-9a-f]{64}")
SHORT_HASH = re.compile(r"[0-9a-f]{4}\.\.\.[0-9a-f]{4}")
DRAFT_FULL = "3f1a9c0e" * 8
PARENT_FULL = "a90c41e7" * 8
SPAN = re.compile(r"`([^`\n]+)`")
HELP_CODES = {}


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def code_spans(text):
    """Contents of inline backtick spans outside fenced blocks."""
    kept, fenced = [], False
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced:
            kept.append(line)
    return SPAN.findall("\n".join(kept))


def tables():
    """The command tables, read from the command line itself."""
    message = "the parser's tables cannot be read as the test expects"

    def choices_of(parser):
        found = [a for a in parser._actions if getattr(a, "choices", None)]
        if len(found) != 1 or not hasattr(found[0].choices, "keys"):
            raise AssertionError(message)
        return found[0].choices

    try:
        top = choices_of(cli._build_parser())
        keywords = choices_of(top["keywords"])
        return {"top": tuple(top), "keywords": tuple(keywords),
                "ab": tuple(cli._AB_SUBCOMMANDS), "panel": tuple(cli._AB_SUBCOMMANDS),
                "drafts": tuple(cli._DRAFTS_VALUE_OPTIONS)}
    except (AttributeError, KeyError, TypeError):
        raise AssertionError(message)


def run_cli(argv):
    """The exit code of one in-process call, with both streams held."""
    saved = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
    try:
        try:
            code = cli.main(list(argv))
        except SystemExit as exc:
            code = exc.code
    finally:
        sys.stdout, sys.stderr = saved
    return 0 if code is None else code


def help_code(command):
    if command not in HELP_CODES:
        HELP_CODES[command] = run_cli([command, "--help"])
    return HELP_CODES[command]


def named(span):
    """(command, subcommand word or None) a span names, or None."""
    words = span.split()
    if len(words) < 2 or words[0] not in CLI_WORDS or words[1].startswith("-"):
        return None
    sub = words[2] if len(words) > 2 and not words[2].startswith("-") else None
    return words[1], sub


def command_problems(text):
    table = tables()
    every_sub = set(word for key in ("keywords", "ab", "panel", "drafts") for word in table[key])
    problems = []
    for span in code_spans(text):
        words = span.split()
        if len(words) == 1 and words[0] in every_sub:
            problems.append("bare subcommand: " + words[0])
        hit = named(span)
        if hit is None:
            continue
        command, sub = hit
        if command not in table["top"]:
            problems.append("no such command: " + command)
        elif help_code(command) != 0:
            problems.append("help does not exit 0: " + command)
        elif command in ("keywords", "ab", "panel", "drafts") and sub is not None:
            if sub not in table[command]:
                problems.append("no such subcommand: %s %s" % (command, sub))
    return problems


def gate4_problems(text):
    spans = code_spans(text)
    return ["gate 4 span missing: " + span for span in GATE4 if span not in spans]


def copy_problems(text):
    problems = []
    for span in code_spans(text):
        words = span.split()
        if "keywords" not in words or "--copy" not in words:
            continue
        for word in words[words.index("--copy") + 1:]:
            if word.startswith("-"):
                break
            if word.lower().endswith(".pdf"):
                problems.append("--copy " + word)
    return problems


def short_copy_problems(text):
    problems = []
    for needed in ("`--min-chars 0`", "Do not join a short draft to another file"):
        if text.count(needed) != 1:
            problems.append("required once: " + needed)
    return problems


def all_problems(text):
    return (command_problems(text) + gate4_problems(text) + copy_problems(text)
            + short_copy_problems(text))


def fenced_blocks(text):
    """The content of each fenced block, as a string, in order."""
    blocks, current = [], None
    for line in text.split("\n"):
        if line.startswith("```"):
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
        elif current is not None:
            current.append(line)
    return blocks


def sheet_blocks(text):
    assert "## The review sheet" in text,"the review sheet heading is missing"
    return fenced_blocks(text[text.index("## The review sheet"):])


def example_sheet(text):
    for block in sheet_blocks(text):
        if block.startswith("draft:"):
            return block
    raise AssertionError("no example sheet under the review sheet heading")


def failing_lines(text):
    blocks = sheet_blocks(text)
    after = blocks[blocks.index(example_sheet(text)) + 1:]
    for block in after:
        if "ready: no" in block:
            return [line for line in block.split("\n") if line.strip()]
    raise AssertionError("no block of failing lines under the review sheet heading")


def parse_sheet(block):
    pairs = []
    for line in block.split("\n"):
        if line.strip():
            key, _sep, value = line.partition(": ")
            pairs.append((key, value))
    return pairs


def leading_word(value, words):
    for word in words:
        if value == word or value.startswith(word + " ") or value.startswith(word + "("):
            return word
    return None


# Known limit: a draft name that contains a space is read by its first word only, and a hash is lowercase hex.
def is_pdf(sheet):
    first = sheet["draft"].split()
    return bool(first) and first[0].lower().endswith(".pdf")


def expected_ready(pairs):
    sheet = dict(pairs)
    for key in WALK:
        match = re.match(r"[a-z]+", sheet[key])
        word = match.group(0) if match else ""
        if word not in OK_WORDS:
            return "no (%s %s)" % (key, "failed" if word == "fail" else "pending")
    return "yes"


def label_match(hashes, label):
    """The match of ``label`` as a whole label: it opens the bracket or follows a comma."""
    rest = hashes[len("recorded"):]
    return re.search(r"(?:\(|, )" + re.escape(label), rest)


def hash_value(hashes, label):
    """The token after ``label``, up to the next comma or closing bracket."""
    rest = hashes[len("recorded"):]
    rest = rest[label_match(hashes, label).end():]
    return re.split(r"[,)]", rest, maxsplit=1)[0]


def sheet_problems(block, abbreviated=False):
    pairs = parse_sheet(block)
    if tuple(key for key, _value in pairs) != KEYS:
        return ["sheet keys are not the sixteen keys in order"]
    sheet = dict(pairs)
    pdf = is_pdf(sheet)
    problems = []
    for key, words in RESULT_WORDS.items():
        word = leading_word(sheet[key], words)
        if word is None:
            problems.append("result word: " + key)
        elif word in ("pass", "fail") and (key in EXIT_KEYS or (key == "parse" and pdf)):
            first = EXIT_N.search(sheet[key])
            if not first:
                problems.append("exit N missing: " + key)
            elif word == "pass" and int(first.group(0).split()[1]) != 0:
                problems.append("exit 0 needed: " + key)
        if key == "cold read" and word == "pass" and "panel PASS" not in sheet[key]:
            problems.append("panel PASS missing: cold read")
    parse_word = leading_word(sheet["parse"], RESULT_WORDS["parse"])
    if not pdf and parse_word != "pending" and sheet["parse"] != MD_PARSE:
        problems.append("parse line of a text or Markdown sheet")
    if leading_word(sheet["hashes"], ("recorded",)):
        labels = PDF_LABELS if pdf else TEXT_LABELS
        for label in labels:
            if not label_match(sheet["hashes"], label):
                problems.append("hashes: missing " + label.strip())
                continue
            value = hash_value(sheet["hashes"], label)
            if not (FULL_HASH.fullmatch(value)
                    or (abbreviated and SHORT_HASH.fullmatch(value))):
                problems.append("hashes: bad value: " + label.strip())
        if not pdf and "extracted text" in sheet["hashes"]:
            problems.append("hashes: extracted text on a text or Markdown sheet")
    if sheet["ready"] != expected_ready(pairs):
        problems.append("ready line differs from the rules: expected " + expected_ready(pairs))
    return problems


def set_line(block, key, line):
    """The block with the one line of ``key`` replaced by ``line``."""
    lines = block.split("\n")
    where = [i for i, text in enumerate(lines) if text.startswith(key + ": ")]
    assert len(where) == 1, key
    lines[where[0]] = line
    return "\n".join(lines)


def swap_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def markdown_sheet(pdf_sheet):
    sheet = swap_once(pdf_sheet, "draft: example-corp-v2.pdf", "draft: example-corp-v2.md")
    sheet = swap_once(sheet, "parent: example-corp-v1.pdf", "parent: example-corp-v1.md")
    sheet = set_line(sheet, "parse", "parse: " + MD_PARSE)
    return set_line(sheet, "hashes", "hashes: recorded (draft sha256 %s, parent sha256 %s)"
                    % (DRAFT_FULL, PARENT_FULL))


class ReviewMethodTest(unittest.TestCase):
    def setUp(self):
        self.text = read(METHOD)

    def assertFlagged(self, problems, name):
        self.assertTrue(problems, "nothing was flagged, wanted: " + name)
        self.assertTrue(any(name in problem for problem in problems),
                        "no problem names %r in %r" % (name, problems))

    def test_r1_the_file_exists_and_each_pointer_names_it_once(self):
        self.assertTrue(os.path.isfile(METHOD))
        for name in ("README.md", "AGENTS.md"):
            with self.subTest(name):
                self.assertEqual(read(os.path.join(ROOT, name)).count(PATH_NAME), 1)

    def test_r2_the_file_as_shipped_has_no_problem(self):
        self.assertEqual(all_problems(self.text), [])

    def test_the_tables_are_read_from_the_command_line(self):
        table = tables()
        self.assertIn("parse", table["top"])
        self.assertEqual(table["ab"], ("freeze", "run", "score"))
        self.assertEqual(table["panel"], table["ab"])
        self.assertIn("report", table["keywords"])
        self.assertEqual(sorted(table["drafts"]), ["check", "extract"])

    def test_r3_a_command_the_cli_lacks_is_named(self):
        problems = command_problems(self.text + "\n`<cli> nosuch`\n")
        self.assertFlagged(problems, "nosuch")

    def test_r4_a_subcommand_the_cli_lacks_is_named(self):
        problems = command_problems(self.text + "\n`<cli> ab nosuch`\n")
        self.assertFlagged(problems, "ab nosuch")

    def test_rule_4_a_text_naming_every_command_passes_and_a_bad_one_fails(self):
        table = tables()
        lines, forms = [], 0
        for key in ("keywords", "ab", "panel", "drafts"):
            for sub in table[key]:
                lines.append("`%s %s %s`" % (CLI_WORDS[forms % 2], key, sub))
                forms += 1
        for command in table["top"]:
            lines.append("`%s %s`" % (CLI_WORDS[forms % 2], command))
            forms += 1
        good = "\n".join(lines) + "\n"
        self.assertEqual(command_problems(good), [])
        self.assertFlagged(command_problems("`<cli> nosuch`\n"), "nosuch")

    def test_r5_every_command_named_is_in_the_cli_spec_list(self):
        spec = read(CLI_SPEC)
        anchor = re.search(r"lists the [a-z]+ commands", spec)
        self.assertTrue(anchor, "the cli spec no longer says it lists the commands")
        after = spec[anchor.start():].split("\n")[1:]
        listed = []
        for line in after:
            if not line.strip() and not listed:
                continue
            match = re.match(r"- ([a-z-]+): ", line)
            if not match:
                break
            listed.append(match.group(1))
        self.assertEqual(sorted(listed), sorted(tables()["top"]))
        used = set(hit[0] for hit in map(named, code_spans(self.text)) if hit)
        self.assertTrue(used)
        self.assertEqual(sorted(used - set(listed)), [])

    def test_r6_the_example_sheet_is_consistent(self):
        sheet = example_sheet(self.text)
        self.assertEqual(sheet_problems(sheet, abbreviated=True), [])
        self.assertEqual(tuple(key for key, _value in parse_sheet(sheet)), KEYS)
        self.assertEqual(dict(parse_sheet(sheet))["hashes"].count("sha256"), 3)

    def test_r6a_the_six_failing_lines_each_end_the_sheet_no(self):
        lines = failing_lines(self.text)
        self.assertEqual(len(lines), 6)
        sheet = example_sheet(self.text)
        for line in lines:
            parts = re.split(r"\s{2,}(?=ready:)", line)
            self.assertEqual(len(parts), 2)
            key = parts[0].split(":")[0]
            with self.subTest(key):
                self.assertEqual(parts[1], "ready: no (%s failed)" % key)
                mutated = set_line(set_line(sheet, key, parts[0]), "ready", parts[1])
                self.assertEqual(sheet_problems(mutated, abbreviated=True), [])

    def test_r6a_controls_a_failure_or_a_pending_with_ready_yes_is_flagged(self):
        sheet = example_sheet(self.text)
        claims = set_line(sheet, "claims", "claims: fail (exit 1, 1 sentence not approved)")
        self.assertFlagged(sheet_problems(set_line(claims, "ready", "ready: yes"), True), "ready")
        pending = set_line(sheet, "ready", "ready: yes")
        self.assertIn("form questions: pending", sheet)
        self.assertFlagged(sheet_problems(pending, True), "ready")
        failed = {"tone": "tone: fail (exit 1, 1 error)",
                  "barred": "barred: fail (exit 1, 1 entry found)",
                  "edit review": "edit review: fail (exit 0, ab INCONCLUSIVE)",
                  "cold read": "cold read: fail (exit 0, panel FAIL)",
                  "diff": "diff: fail (3 lines changed, 1 not intended)",
                  "parse": "parse: fail (exit 1, 1 finding)"}
        for key, line in failed.items():
            with self.subTest(key):
                bad = set_line(set_line(sheet, key, line), "ready", "ready: yes")
                self.assertFlagged(sheet_problems(bad, True), "ready")
                wrong = set_line(set_line(sheet, key, line), "ready", "ready: no (diff failed)"
                                 if key != "diff" else "ready: no (tone failed)")
                self.assertFlagged(sheet_problems(wrong, True), "ready")

    def test_r6a_controls_a_pass_line_with_a_nonzero_exit_is_flagged(self):
        sheet = example_sheet(self.text)
        ready = swap_once(sheet, "form questions: pending", "form questions: answered (all pulled)")
        ready = set_line(ready, "ready", "ready: yes")
        self.assertEqual(sheet_problems(ready, True), [])
        bad = swap_once(ready, "claims: pass (exit 0,", "claims: pass (exit 1,")
        self.assertFlagged(sheet_problems(bad, True), "exit 0 needed: claims")
        for key in EXIT_KEYS:
            with self.subTest(key):
                line = [x for x in sheet.split("\n") if x.startswith(key + ": ")][0]
                self.assertRegex(line, r"pass \((ab run )?exit 0")
                worse =set_line(ready, key, line.replace("exit 0", "exit 3"))
                self.assertFlagged(sheet_problems(worse, True), "exit 0 needed: " + key)

    def test_r6a_controls_a_cold_read_pass_needs_the_panel_verdict(self):
        sheet = example_sheet(self.text)
        self.assertEqual([x for x in sheet_problems(sheet, True) if "cold read" in x], [])
        bare = set_line(sheet, "cold read", "cold read: pass (exit 0)")
        self.assertFlagged(sheet_problems(bare, True), "panel PASS missing: cold read")

    def test_r6e_every_exit_the_passes_when_table_names_is_zero(self):
        start = self.text.index("| Sheet key | Passes when |")
        table = self.text[start:self.text.index("\n\n", start)]
        exits = re.findall(r"exited `(\d+)`", table)
        self.assertGreaterEqual(len(exits), 7)
        self.assertEqual(set(exits), {"0"})
        wrong = table.replace("`tone` exited `0`", "`tone` exited `1`")
        self.assertNotEqual(set(re.findall(r"exited `(\d+)`", wrong)), {"0"})

    def test_r6b_a_markdown_sheet_needs_its_own_hashes(self):
        pdf = example_sheet(self.text)
        markdown = markdown_sheet(pdf)
        self.assertEqual(sheet_problems(markdown), [])
        parent = ", parent sha256 " + PARENT_FULL
        short_parent = ", parent sha256 a90c...41e7"
        extracted = ", extracted text sha256 7b42...d518"
        self.assertFlagged(sheet_problems(swap_once(markdown, parent, "")), "parent sha256")
        self.assertFlagged(sheet_problems(swap_once(pdf, extracted, ""), True),
                           "extracted text sha256")
        self.assertFlagged(sheet_problems(swap_once(pdf, short_parent, ""), True),
                           "parent sha256")
        self.assertFlagged(sheet_problems(swap_once(markdown, parent, extracted + parent)),
                           "extracted text")

    def test_r6d_a_hash_label_needs_a_64_hex_value(self):
        pdf = example_sheet(self.text)
        markdown = markdown_sheet(pdf)
        label = "parent sha256 "
        for name, value in (("empty", ""), ("63", PARENT_FULL[:63]),
                            ("65", PARENT_FULL + "a"), ("upper", PARENT_FULL.upper()),
                            ("abbreviated", "a90c...41e7"), ("text", "recorded")):
            with self.subTest(name):
                bad = swap_once(markdown, label + PARENT_FULL, label + value)
                self.assertFlagged(sheet_problems(bad), "bad value: parent sha256")
        self.assertEqual(sheet_problems(markdown), [])
        emptied = swap_once(pdf, label + "a90c...41e7", label)
        self.assertFlagged(sheet_problems(emptied, True), "bad value: parent sha256")
        deleted = swap_once(pdf, "hashes: recorded (pdf sha256 3f1a...9c0e, extracted text "
                            "sha256 7b42...d518, parent sha256 a90c...41e7)",
                            "hashes: recorded (pdf sha256 , extracted text sha256 , parent sha256 )")
        for name in ("pdf sha256", "extracted text sha256", "parent sha256"):
            self.assertFlagged(sheet_problems(deleted, True), "bad value: " + name)

    def test_r6c_the_parse_line_carries_its_exit(self):
        pdf = example_sheet(self.text)
        line = dict(parse_sheet(pdf))["parse"]
        self.assertTrue(line.startswith("pass"))
        self.assertIn("exit 0", line)
        no_exit = set_line(pdf, "parse", "parse: " + swap_once(line, "exit 0: ", ""))
        self.assertFlagged(sheet_problems(no_exit, True), "exit N missing: parse")
        failed = set_line(set_line(pdf, "parse", "parse: fail"), "ready", "ready: yes")
        self.assertFlagged(sheet_problems(failed, True), "ready")
        ready = set_line(swap_once(pdf, "form questions: pending", "form questions: answered"),
                         "ready", "ready: yes")
        self.assertEqual(sheet_problems(ready, True), [])
        nonzero = set_line(ready, "parse", "parse: " + swap_once(line, "exit 0:", "exit 2:"))
        self.assertFlagged(sheet_problems(nonzero, True), "exit 0 needed: parse")
        other = set_line(markdown_sheet(pdf), "parse", "parse: pass (exit 0)")
        self.assertFlagged(sheet_problems(other), "parse")

    def ready_sheet(self):
        pdf = example_sheet(self.text)
        ready = swap_once(pdf, "form questions: pending", "form questions: answered (all pulled)")
        ready = set_line(ready, "ready", "ready: yes")
        self.assertEqual(sheet_problems(ready, True), [])
        return ready

    def assertExitOnly(self, problems, key):
        self.assertIn("exit 0 needed: " + key, problems)
        others = [p for p in problems if p.startswith("exit 0 needed:") and not p.endswith(key)]
        self.assertEqual(others, [], problems)

    def test_h1_the_first_exit_on_a_pass_line_decides(self):
        ready = self.ready_sheet()
        decoys = {
            "claims": "claims: pass (exit 3, control found; previous exit 0)",
            "barred": "barred: pass (exit 3, control found; previous exit 0)",
            "tone": "tone: pass (exit 3: 0 errors, 1 warning; previous exit 0)",
            "keywords": "keywords: pass (exit 3: 2 gaps, both left open: no true line in the "
                        "record; previous exit 0)",
            "parse": "parse: pass (exit 2: name and contact on page 1; previous exit 0)"}
        for key, line in decoys.items():
            with self.subTest(key):
                self.assertExitOnly(sheet_problems(set_line(ready, key, line), True), key)
        later = {
            "claims": "claims: pass (exit 0, control found; earlier exit 3)",
            "keywords": "keywords: pass (exit 0: 2 gaps, both left open; earlier exit 3)",
            "parse": "parse: pass (exit 0: name and contact on page 1; earlier exit 2)"}
        for key, line in later.items():
            with self.subTest("later " + key):
                self.assertEqual(sheet_problems(set_line(ready, key, line), True), [])

    def test_h2_each_pass_line_with_a_nonzero_exit_names_only_itself(self):
        ready = self.ready_sheet()
        for key in EXIT_KEYS + ("parse",):
            with self.subTest(key):
                line = dict(parse_sheet(ready))[key]
                self.assertRegex(line, r"pass \((ab run )?exit 0")
                bad =set_line(ready, key, key + ": " + line.replace("exit 0", "exit 2", 1))
                self.assertExitOnly(sheet_problems(bad, True), key)

    def test_h3_a_hash_label_is_a_whole_label(self):
        pdf = example_sheet(self.text)
        markdown = markdown_sheet(pdf)
        cases = ((pdf, True, "parent sha256 a90c...41e7", "grandparent sha256 a90c...41e7",
                  "parent sha256"),
                 (markdown, False, "draft sha256 ", "redraft sha256 ", "draft sha256"),
                 (pdf, True, "pdf sha256 ", "xpdf sha256 ", "pdf sha256"),
                 (pdf, True, "extracted text sha256 ", "reextracted text sha256 ",
                  "extracted text sha256"))
        for sheet, abbreviated, old, new, label in cases:
            with self.subTest(new):
                problems = sheet_problems(swap_once(sheet, old, new), abbreviated)
                self.assertIn("hashes: missing " + label, problems)
                self.assertEqual(sheet_problems(sheet, abbreviated), [])

    def test_h4_every_required_label_needs_its_own_good_value(self):
        pdf = example_sheet(self.text)
        for label, value in (("pdf sha256 ", "3f1a...9c0e"),
                             ("extracted text sha256 ", "7b42...d518"),
                             ("parent sha256 ", "a90c...41e7")):
            with self.subTest(label):
                problems = sheet_problems(swap_once(pdf, label + value, label), True)
                self.assertEqual([p for p in problems if "bad value" in p],
                                 ["hashes: bad value: " + label.strip()])
        markdown = markdown_sheet(pdf)
        for label, full, short in (("draft sha256 ", DRAFT_FULL, "3f1a...9c0e"),
                                   ("parent sha256 ", PARENT_FULL, "a90c...41e7")):
            for name, value in (("empty", ""), ("63", full[:63]), ("65", full + "a"),
                                ("abbreviated", short), ("upper", full.upper())):
                with self.subTest(label + name):
                    problems = sheet_problems(swap_once(markdown, label + full, label + value))
                    self.assertEqual([p for p in problems if "bad value" in p],
                                     ["hashes: bad value: " + label.strip()])

    def test_r9_no_pdf_follows_keywords_copy(self):
        self.assertEqual(copy_problems(self.text), [])
        bad = swap_once(self.text, "--copy FILE...", "--copy draft.pdf")
        self.assertFlagged(copy_problems(bad), "--copy draft.pdf")

    def test_r10_a_bare_span_or_a_missing_gate_4_span_fails(self):
        self.assertFlagged(all_problems(self.text + "\n`run`\n"), "run")
        span = "<cli> panel score PLAN"
        self.assertGreaterEqual(self.text.count("`" + span + "`"), 1)
        without = self.text.replace("`" + span + "`", "")
        self.assertNotIn(span, without)
        self.assertFlagged(all_problems(without), span)

    def test_r11_short_copy_names_min_chars_zero(self):
        self.assertEqual(short_copy_problems(self.text), [])
        bad = swap_once(self.text, "`--min-chars 0`", "`--min-chars 1`")
        self.assertFlagged(short_copy_problems(bad), "--min-chars 0")


if __name__ == "__main__":
    unittest.main()
