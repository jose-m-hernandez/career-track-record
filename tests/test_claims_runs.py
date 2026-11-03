"""Tests for the run bound of the claim gate. All data here is invented.

``reference_check_text`` is the loop as it stood before the bound, copied byte for byte
from the base; the bounded loop must give the same answer on every text. Invisible
characters, hyphens, dashes and curly quotes are written as escapes, never raw.
"""

import bisect
import os
import random
import subprocess
import sys
import tempfile
import unicodedata
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

import career_track_record.claims as claims  # noqa: E402
from career_track_record import tone  # noqa: E402
from career_track_record.claims import (  # noqa: E402
    _Used, _blocks, _keep_hyphen, _line_starts, _sentences, _shown, _working, prepare,
)


def reference_check_text(text, by_sentence, longest):
    work, spans = _working(text)
    joined, joined_spans = _keep_hyphen(work, spans)
    starts = _line_starts(text)
    result = _Used()
    for block_start, block_end in _blocks(joined):
        sentences = _sentences(joined, block_start, block_end)
        result.checked += len(sentences)
        i = 0
        while i < len(sentences):
            first = sentences[i][0]
            source_start = joined_spans[first][0]
            line = bisect.bisect_right(starts, source_start)
            covered = None
            for j in range(i, len(sentences)):
                source_end = joined_spans[sentences[j][1] - 1][1]
                prepared = prepare(text[source_start:source_end])
                if len(prepared) > longest:
                    break
                if prepared in by_sentence:
                    covered = (j, by_sentence[prepared])
            if covered is None:
                result.failed += 1
                result.findings.append(
                    (line, "unlisted", _shown(text, source_start,
                                              joined_spans[sentences[i][1] - 1][1])))
                i += 1
                continue
            j, (number, status) = covered
            if status == "approved":
                result.used.add(number)
            else:
                result.failed += j - i + 1
                result.findings.append(
                    (line, "%s, entry #%d" % (status, number),
                     _shown(text, source_start, joined_spans[sentences[j][1] - 1][1])))
            i = j + 1
    return result


STATUSES = ("approved", "proposed", "refused")


def sentence_sources(text):
    """The source slice of each checked sentence of text, in order."""
    work, spans = _working(text)
    joined, joined_spans = _keep_hyphen(work, spans)
    out = []
    for block_start, block_end in _blocks(joined):
        for a, b in _sentences(joined, block_start, block_end):
            out.append(text[joined_spans[a][0]:joined_spans[b - 1][1]])
    return out


def limits(entries):
    """longest and most_stops, the way _run computes them."""
    longest = max([len(p) for p, _s in entries] or [0])
    most_stops = max([sum(p.count(c) for c in ".!?") for p, _s in entries] or [0])
    return longest, most_stops


def by_of(entries):
    return dict((p, (n, s)) for n, (p, s) in enumerate(entries, 1))


def summary(found):
    return (found.checked, found.failed, found.findings, sorted(found.used))


def own_runs_entries(text):
    """Entries from the first one, two and three sentences of text, in turn."""
    sources = sentence_sources(text)
    entries = []
    for k in (1, 2, 3):
        if len(sources) >= k:
            span = text[text.find(sources[0]):text.find(sources[k - 1]) + len(sources[k - 1])]
            entries.append((prepare(span), STATUSES[k - 1]))
    return entries


def special_code_points():
    found = []
    closers = set(tone._CLOSERS)
    for cp in range(0x110000):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        ch = chr(cp)
        category = unicodedata.category(ch)
        folded = claims._fold(ch)
        if (any(c in folded for c in ".!?") or any(c.isspace() for c in folded)
                or category[0] == "M" or category == "Cf" or ch in closers):
            found.append(ch)
    return found


class ParityTests(unittest.TestCase):
    def assert_parity(self, text, entries, label):
        longest, most_stops = limits(entries)
        by = by_of(entries)
        want = summary(reference_check_text(text, by, longest))
        got = summary(claims._check_text(text, by, longest, most_stops))
        self.assertEqual(got, want, "mismatch at %s: %r" % (label, text))

    def test_code_point_sweep(self):
        points = special_code_points()
        self.assertGreater(len(points), 100)
        covered = 0
        for ch in points:
            for text in ("Ab" + ch + "cd. Ef gh. Ij.",
                         "Ab cd." + ch + " Ef gh. Ij.",
                         "Ab cd. " + ch + "Ef gh. Ij."):
                entries = own_runs_entries(text)
                covered += len(entries)
                self.assert_parity(text, entries, "U+%04X" % ord(ch))
        self.assertGreater(covered, 100)

    def test_seeded_random_corpus(self):
        rng = random.Random(20261103)
        pieces = [
            "Led a team.", "Shipped it!", "Did it work?", "Wait...", "Really?!",
            "He said \"go.\"", "Done (mostly.)", "Built b.", "Cut costs.", "Ran c.",
            "Fixed d!", "A \u2026 B.", "One\u2024 two.", "Rate \u338f here.",
            "Met at 9 \u33c2 sharp.",
            "- a bullet.", "1. A numbered line.", "# A heading", "",
            "cross-\nfunctional work.", "Plain words", "Led a.", "Led b.",
        ]
        seps = [" ", " ", "\n", "\r\n", "  "]
        texts = []
        for _ in range(2000):
            parts = []
            for _k in range(rng.randint(2, 9)):
                parts.append(rng.choice(pieces))
                parts.append(rng.choice(seps))
            texts.append("".join(parts))
        sentence_lists = [sentence_sources(t) for t in texts]
        for index, text in enumerate(texts):
            sentences = sentence_lists[index]
            entries = []
            for _ in range(rng.randint(1, 4)):
                if not sentences:
                    break
                start = rng.randrange(len(sentences))
                count = rng.randint(1, 4)
                chunk = sentences[start:start + count]
                a = text.find(chunk[0])
                b = text.find(chunk[-1], a) + len(chunk[-1])
                entries.append((prepare(text[a:b]), rng.choice(STATUSES)))
            other = sentence_lists[rng.randrange(len(texts))]
            if other:
                entries.append((prepare(other[0]), rng.choice(STATUSES)))
            entries = [e for e in entries if e[0] != ""]
            self.assert_parity(text, entries, "seed index %d" % index)


class BoundTests(unittest.TestCase):
    def check(self, entry, sentences):
        with tempfile.TemporaryDirectory() as folder:
            lst = os.path.join(folder, "list.tsv")
            copy = os.path.join(folder, "copy.txt")
            with open(lst, "w", encoding="utf-8") as handle:
                handle.write("approved\t%s\n" % entry)
            with open(copy, "w", encoding="utf-8") as handle:
                handle.write("Example. " + sentences)
            # The control sentence is approved too, so the file is wholly approved.
            with open(lst, "a", encoding="utf-8") as handle:
                handle.write("approved\tExample.\n")
            return claims.run(list_path=lst, files=[copy], controls=["Example"])

    def test_entry_with_s_inner_stops_covers_s_plus_one_sentences(self):
        for s in (1, 2, 5):
            entry = "Led a. " * s + "Led b."
            result = self.check(entry, entry)
            self.assertEqual(result.exit_code, 0, "s=%d: %r" % (s, result))

    def test_inner_stops_that_are_marks(self):
        result = self.check("Led a! Led b? Led c.", "Led a! Led b? Led c.")
        self.assertEqual(result.exit_code, 0)

    def test_bound_counts_stops_in_every_status(self):
        with tempfile.TemporaryDirectory() as folder:
            lst = os.path.join(folder, "list.tsv")
            copy = os.path.join(folder, "copy.txt")
            with open(lst, "w", encoding="utf-8") as handle:
                handle.write("approved\tExample.\napproved\tLed a.\n"
                             "proposed\tLed b. Led c.\nrefused\tLed d. Led e. Led f.\n")
            with open(copy, "w", encoding="utf-8") as handle:
                handle.write("Example. Led a. Led b. Led c. Led d. Led e. Led f.")
            result = claims.run(list_path=lst, files=[copy], controls=["Example"])
            label = claims.printed_path(copy)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.text.splitlines(), [
            "FAIL  %s: 5 of 7 sentences not approved" % label,
            "%s:1: proposed, entry #3: Led b. Led c." % label,
            "%s:1: refused, entry #4: Led d. Led e. Led f." % label,
        ])


CODE = """
import os, sys
from career_track_record import claims
d = sys.argv[1]
lst = os.path.join(d, "list.txt"); cp = os.path.join(d, "copy.txt")
open(lst, "w").write("approved\\t%s\\n" % (("word " * 480).strip() + "."))
open(cp, "w").write("Example. " + "Led a. " * 2000)
r = claims.run(list_path=lst, files=[cp], controls=["Example"])
print(r.exit_code)
"""


class TimingTests(unittest.TestCase):
    def test_long_file_with_one_long_entry_finishes(self):
        env = dict(os.environ, PYTHONPATH=SRC)
        with tempfile.TemporaryDirectory() as folder:
            try:
                done = subprocess.run([sys.executable, "-c", CODE, folder], timeout=10,
                                      env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.TimeoutExpired:
                self.fail("the claim gate took more than 10 s on 2000 short sentences")
        self.assertEqual(done.stdout.decode().strip(), "1", done.stderr.decode())


class KnownLimitTests(unittest.TestCase):
    # Known limit: an entry made of N short sentences lets each start sentence try N + 1 runs,
    # so a long file can still be slow. Measured on Python 3.9 with an entry of 800 short
    # sentences, ("b. " * 800).strip(), against "Example. " + "a. " * n: 1.01 s at n=200 here;
    # the reviewer measured 1.04 s at n=200 and 116 s at n=1000, a file of about 3 KB.
    def test_many_stop_entry_gives_correct_output(self):
        with tempfile.TemporaryDirectory() as folder:
            lst = os.path.join(folder, "list.tsv")
            copy = os.path.join(folder, "copy.txt")
            with open(lst, "w", encoding="utf-8") as handle:
                handle.write("approved\t%s\n" % ("Led b. " * 340).strip())
            with open(copy, "w", encoding="utf-8") as handle:
                handle.write("Example. " + "Led a. " * 50)
            result = claims.run(list_path=lst, files=[copy], controls=["Example"])
        self.assertEqual(result.exit_code, 1)
        first = result.text.splitlines()[0]
        self.assertEqual(
            first, "FAIL  %s: 51 of 51 sentences not approved" % claims.printed_path(copy))


if __name__ == "__main__":
    unittest.main()
