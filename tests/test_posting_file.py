"""Tests for the saved-posting file format. All data here is invented."""

import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from career_track_record import posting_file  # noqa: E402
from career_track_record.posting_file import PostingError  # noqa: E402

EXAMPLE_A_BODY = (
    "Senior Engineer, Example A\n"
    "You will build agents and evals in Python.\n"
    "Experience with a knowledge graph is a plus."
)
EXAMPLE_A_SHA = "7d2961bb63a0934815529950556722eac09f95910c6c0cf6e0391a6948adac7d"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def header_lines(body, **overrides):
    values = [
        ("source_url", "https://example.com/jobs/x"),
        ("api_endpoint", "https://example.com/api/jobs/x"),
        ("fetched_at", "2026-01-15T09:00:00Z"),
        ("http_status", "200"),
        ("sha256", sha(body)),
        ("bytes", str(len(body.encode("utf-8")))),
    ]
    return ["%s: %s" % (k, overrides.get(k, v)) for k, v in values]


class TempCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def put(self, name, data):
        path = os.path.join(self.dir, name)
        if isinstance(data, str):
            data = data.encode("utf-8")
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def assertCase(self, path, case):
        with self.assertRaises(PostingError) as ctx:
            posting_file.read_posting(path)
        self.assertEqual(ctx.exception.case, case, ctx.exception.message)
        self.assertTrue(ctx.exception.message)
        self.assertNotIn("\n", ctx.exception.message)
        return ctx.exception


class HeadedCase(TempCase):
    def test_spec_example_hash_and_bytes(self):
        path = os.path.join(self.dir, "a.txt")
        posting_file.write_posting(
            path, source_url="https://example.com/jobs/example-a",
            api_endpoint="https://example.com/api/jobs/example-a",
            fetched_at="2026-01-15T09:00:00Z", http_status=200, body=EXAMPLE_A_BODY)
        with open(path, "rb") as handle:
            raw = handle.read().decode("utf-8")
        self.assertIn("sha256: " + EXAMPLE_A_SHA + "\n", raw)
        self.assertIn("bytes: 114\n", raw)
        self.assertTrue(raw.endswith("a plus."))
        self.assertNotIn("\r", raw)

    def test_round_trip_11_8(self):
        path = os.path.join(self.dir, "a.txt")
        posting_file.write_posting(
            path, source_url="https://example.com/jobs/x",
            api_endpoint="https://example.com/api/jobs/x",
            fetched_at="2026-01-15T09:00:00Z", http_status=200, body=EXAMPLE_A_BODY)
        posting = posting_file.read_posting(path)
        self.assertEqual(posting.body, EXAMPLE_A_BODY)
        self.assertEqual(posting.fields["sha256"], EXAMPLE_A_SHA)
        self.assertEqual(posting.fields["http_status"], "200")
        self.assertFalse(posting.sidecar)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text.replace("Python", "Pythom"))
        self.assertCase(path, 3)

    def test_writer_bytes_is_utf8_length(self):
        path = os.path.join(self.dir, "u.txt")
        body = "Ingenieuré — café"
        posting_file.write_posting(
            path, source_url="https://example.com/x", api_endpoint="https://example.com/y",
            fetched_at="t", http_status=200, body=body)
        posting = posting_file.read_posting(path)
        self.assertEqual(posting.body, body)
        self.assertEqual(posting.fields["bytes"], str(len(body.encode("utf-8"))))
        self.assertNotEqual(posting.fields["bytes"], str(len(body)))

    def test_writer_control_line_and_blank_line(self):
        path = os.path.join(self.dir, "c.txt")
        posting_file.write_posting(
            path, source_url="https://example.com/x", api_endpoint="https://example.com/y",
            fetched_at="t", http_status=200, body="Body line\nSecond", control="note")
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        self.assertEqual(lines[6], "control: note")
        self.assertEqual(lines[7], "")
        posting = posting_file.read_posting(path)
        self.assertEqual(posting.body, "Body line\nSecond")
        self.assertEqual(posting.control, "control: note")

    def test_writer_rejects_bad_input(self):
        path = os.path.join(self.dir, "w.txt")
        with self.assertRaises(ValueError):
            posting_file.write_posting(
                path, source_url="", api_endpoint="e", fetched_at="t",
                http_status=200, body="x")
        with self.assertRaises(ValueError):
            posting_file.write_posting(
                path, source_url="u", api_endpoint="e", fetched_at="t",
                http_status=200, body="control: x\nmore")

    def test_control_line_and_one_blank_line_belong_to_header(self):
        body = "Real body\nline two"
        text = "\n".join(header_lines(body) + ["control: x", "", body])
        posting = posting_file.read_posting(self.put("c.txt", text))
        self.assertEqual(posting.body, body)

    def test_second_blank_line_is_body(self):
        body = "\nReal body"
        text = "\n".join(header_lines(body) + ["control: x", "", body])
        posting = posting_file.read_posting(self.put("c.txt", text))
        self.assertEqual(posting.body, body)

    def test_control_variants_qualify(self):
        for line in ("controller: x", "control: "):
            body = "Real body"
            text = "\n".join(header_lines(body) + [line, body])
            posting = posting_file.read_posting(self.put("c.txt", text))
            self.assertEqual(posting.body, body, line)

    def test_control_without_colon_space_is_body_text(self):
        body = "control:x\nrest of it"
        text = "\n".join(header_lines(body) + [body])
        posting = posting_file.read_posting(self.put("c.txt", text))
        self.assertEqual(posting.body, body)
        self.assertIsNone(posting.control)
        # the hash has to cover the line
        wrong = "\n".join(header_lines("rest of it") + [body])
        self.assertCase(self.put("d.txt", wrong), 3)

    def test_seven_lines_ending_in_control_line_is_blank_body(self):
        text = "\n".join(header_lines("x") + ["control: x"])
        self.assertCase(self.put("c.txt", text), 3)
        self.assertCase(self.put("d.txt", text + "\n"), 3)

    def test_fewer_than_seven_lines(self):
        lines = header_lines("x")
        self.assertCase(self.put("a.txt", "\n".join(lines)), 2)
        self.assertCase(self.put("b.txt", "\n".join(lines[:3])), 2)
        self.assertCase(self.put("c.txt", ""), 2)

    def test_wrong_key(self):
        lines = header_lines("body")
        lines[3] = lines[3].replace("http_status", "status")
        self.assertCase(self.put("a.txt", "\n".join(lines + ["body"])), 2)

    def test_wrong_order(self):
        lines = header_lines("body")
        lines[0], lines[1] = lines[1], lines[0]
        self.assertCase(self.put("a.txt", "\n".join(lines + ["body"])), 2)

    def test_missing_separator(self):
        for index, broken in ((0, "source_url https://example.com"), (4, "sha256:abc")):
            lines = header_lines("body")
            lines[index] = broken
            self.assertCase(self.put("a.txt", "\n".join(lines + ["body"])), 2)

    def test_empty_value(self):
        lines = header_lines("body")
        lines[2] = "fetched_at: "
        self.assertCase(self.put("a.txt", "\n".join(lines + ["body"])), 2)
        lines[2] = "fetched_at:"
        self.assertCase(self.put("b.txt", "\n".join(lines + ["body"])), 2)

    def test_byte_order_mark_fails_as_malformed_header(self):
        body = "body"
        data = b"\xef\xbb\xbf" + "\n".join(header_lines(body) + [body]).encode("utf-8")
        self.assertCase(self.put("a.txt", data), 2)

    def test_hash_mismatch(self):
        lines = header_lines("body", sha256="0" * 64)
        self.assertCase(self.put("a.txt", "\n".join(lines + ["body"])), 3)

    def test_blank_body(self):
        for body in (" ", "\t \n  "):
            text = "\n".join(header_lines(body) + [body])
            self.assertCase(self.put("a.txt", text), 3)

    def test_bytes_is_required_but_not_compared(self):
        body = "body text"
        lines = header_lines(body, bytes="9999")
        posting = posting_file.read_posting(self.put("a.txt", "\n".join(lines + [body])))
        self.assertEqual(posting.body, body)

    def test_line_endings_are_translated(self):
        body = "one\ntwo\nthree"
        text = "\r\n".join(header_lines(body) + body.split("\n"))
        posting = posting_file.read_posting(self.put("a.txt", text))
        self.assertEqual(posting.body, body)
        text = "\r".join(header_lines(body) + body.split("\n"))
        posting = posting_file.read_posting(self.put("b.txt", text))
        self.assertEqual(posting.body, body)

    def test_trailing_line_feed_is_part_of_the_body(self):
        body = "one\ntwo\n"
        text = "\n".join(header_lines(body) + [body])
        self.assertEqual(posting_file.read_posting(self.put("a.txt", text)).body, body)

    def test_body_with_added_trailing_line_feed_fails(self):
        body = "one\ntwo"
        text = "\n".join(header_lines(body) + [body])
        self.assertEqual(posting_file.read_posting(self.put("a.txt", text)).body, body)
        self.assertCase(self.put("b.txt", text + "\n"), 3)

    def test_invalid_utf8(self):
        data = "\n".join(header_lines("b") + ["b"]).encode("utf-8") + b"\xff\xfe"
        self.assertCase(self.put("a.txt", data), 8)


class SidecarCase(TempCase):
    def make(self, text="Raw posting text\nsecond line", **overrides):
        meta = {
            "format": "raw-posting-with-sidecar",
            "source_url": "https://example.com/jobs/raw",
            "bytes": len(text.encode("utf-8")),
            "sha256": sha(text),
        }
        meta.update(overrides)
        for key in [k for k, v in meta.items() if v is KeyError]:
            del meta[key]
        path = self.put("raw.txt", text)
        self.put("raw.txt.meta.json", json.dumps(meta))
        return path

    def test_happy_path(self):
        posting = posting_file.read_posting(self.make())
        self.assertEqual(posting.body, "Raw posting text\nsecond line")
        self.assertTrue(posting.sidecar)
        self.assertEqual(posting.fields["source_url"], "https://example.com/jobs/raw")

    def test_sidecar_is_used_instead_of_header(self):
        body = "Looks headed"
        text = "\n".join(header_lines(body) + [body])
        posting = posting_file.read_posting(self.make(text))
        self.assertEqual(posting.body, text)

    def test_bytes_wrong(self):
        self.assertCase(self.make(bytes=3), 3)

    def test_sha256_wrong(self):
        self.assertCase(self.make(sha256="0" * 64), 3)

    def test_source_url_not_https(self):
        self.assertCase(self.make(source_url="http://example.com/x"), 3)
        self.assertCase(self.make(source_url=5), 3)

    def test_format_wrong(self):
        self.assertCase(self.make(format="something-else"), 3)
        self.assertCase(self.make(format=KeyError), 3)

    def test_bytes_must_be_integer(self):
        self.assertCase(self.make(bytes="27"), 3)
        self.assertCase(self.make(bytes=True), 3)

    def test_sha256_must_be_string(self):
        self.assertCase(self.make(sha256=7), 3)

    def test_blank_body(self):
        self.assertCase(self.make(text="  \n "), 3)

    def test_sidecar_not_json_or_not_object(self):
        path = self.make()
        self.put("raw.txt.meta.json", "{not json")
        self.assertCase(path, 3)
        self.put("raw.txt.meta.json", "[1, 2]")
        self.assertCase(path, 3)

    def test_invalid_utf8(self):
        bad = b"\xff\xfe broken"
        path = self.make()
        self.put("raw.txt", bad)
        self.put("raw.txt.meta.json", json.dumps({
            "format": "raw-posting-with-sidecar",
            "source_url": "https://example.com/jobs/raw",
            "bytes": len(bad),
            "sha256": hashlib.sha256(bad).hexdigest(),
        }))
        self.assertCase(path, 8)


CRLF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "keywords",
                        "postings-raw-crlf")
CRLF_FILE = os.path.join(CRLF_DIR, "2026-01-15-example-r.txt")
CRLF_RAW_SHA = "c7399b181ce9a5c95413b787d70a42f4b44741bb8b96cb7374e12103c99c0702"
CRLF_LF_SHA = "335e2f6ccf72cd6561db93b1325d4f32a192eae0524fe6fd80b89e12f9c8061f"


class CrlfRawCase(TempCase):
    def copy_with(self, **overrides):
        with open(CRLF_FILE, "rb") as handle:
            data = handle.read()
        with open(CRLF_FILE + ".meta.json", encoding="utf-8") as handle:
            meta = json.load(handle)
        meta.update(overrides)
        path = self.put("r.txt", data)
        self.put("r.txt.meta.json", json.dumps(meta))
        return path

    def test_crlf_raw_posting_reads_against_stored_bytes(self):
        posting = posting_file.read_posting(CRLF_FILE)
        self.assertNotIn("\r", posting.body)
        self.assertTrue(posting.sidecar)
        with open(CRLF_FILE + ".meta.json", encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["bytes"], 73)
        self.assertEqual(meta["sha256"], CRLF_RAW_SHA)
        with open(CRLF_FILE, "rb") as handle:
            raw = handle.read()
        self.assertEqual(len(raw), meta["bytes"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["sha256"])

    def test_crlf_raw_posting_with_translated_hash_fails(self):
        self.assertCase(self.copy_with(sha256=CRLF_LF_SHA, bytes=70), 3)

    def test_crlf_raw_posting_with_translated_bytes_only_fails(self):
        self.assertCase(self.copy_with(bytes=70), 3)


if __name__ == "__main__":
    unittest.main()
