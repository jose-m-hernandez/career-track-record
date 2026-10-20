"""Write the keyword-scan fixtures (invented data) into OUTDIR.

Usage: python3 make_fixtures.py OUTDIR
"""

import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "src"))

from career_track_record import posting_file  # noqa: E402

TERMS_T1 = (
    "family\tpattern\tnote\n"
    "agents\tagents\tmust-find\n"
    "evals\tevals\n"
    "python\tpython\n"
    "knowledge-graph\tknowledge graph\n"
    "field-notes\tfield notes\tchosen\n"
)

P1 = {
    "example-a": [
        "Senior Engineer, Example A",
        "You will build agents and evals in Python.",
        "Experience with a knowledge graph is a plus.",
    ],
    "example-b": [
        "Staff Engineer, Example B",
        "We ship agents to customers.",
        "Python is required.",
    ],
    "example-c": [
        "Lead Engineer, Example C",
        "Build evals for our agents.",
        "Field notes from customers guide the roadmap.",
    ],
}

P_D = {"example-d": ["Data Engineer, Example D", "Python and evals."]}

COPY_FILES = {
    "copy.txt": ["I build agents and write evals."],
    "copy2.ts": [
        "// python appears only in this comment line",
        'export default { text: "Python services in production", note: "knowledge graph" };',
        "/* field notes appear only in this block */",
    ],
    "copy3.txt": ["Field notes shape everything I write. I build agents."],
    "copy4.txt": ["I build agents."],
}


def write_folder(folder, postings):
    os.makedirs(folder, exist_ok=True)
    for slug, lines in postings.items():
        posting_file.write_posting(
            os.path.join(folder, "2026-01-15-%s.txt" % slug),
            source_url="https://example.com/jobs/" + slug,
            api_endpoint="https://example.com/api/jobs/" + slug,
            fetched_at="2026-01-15T09:00:00Z",
            http_status=200,
            body="\n".join(lines),
        )


def edge_set(count, python_count):
    postings = {}
    for i in range(1, count + 1):
        tail = "Python" if i <= python_count else "Go"
        postings["edge-%02d" % i] = [
            "Engineer %d, Example Edge" % i,
            "We build agents. %s helps." % tail,
        ]
    return postings


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


CRLF_NAME = "2026-01-15-example-r.txt"
CRLF_BYTES = (
    b"Data Engineer, Example R\r\n"
    b"We build agents with Python.\r\n"
    b"Remote is fine.\r\n"
)


def write_crlf_raw(folder):
    """A raw posting stored with CRLF line endings, written in binary."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, CRLF_NAME)
    with open(path, "wb") as handle:
        handle.write(CRLF_BYTES)
    meta = {
        "format": "raw-posting-with-sidecar",
        "source_url": "https://example.com/jobs/example-r",
        "bytes": len(CRLF_BYTES),
        "sha256": hashlib.sha256(CRLF_BYTES).hexdigest(),
    }
    with open(path + ".meta.json", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(meta, indent=2, sort_keys=True) + "\n")


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: make_fixtures.py OUTDIR\n")
        return 2
    out = argv[1]
    os.makedirs(out, exist_ok=True)
    write_text(os.path.join(out, "terms-t1.tsv"), TERMS_T1)
    write_folder(os.path.join(out, "postings-p1"), P1)
    write_folder(os.path.join(out, "postings-p1-ab"),
                 {k: P1[k] for k in ("example-a", "example-b")})
    write_folder(os.path.join(out, "postings-d"), P_D)
    write_folder(os.path.join(out, "postings-e10"), edge_set(10, 3))
    write_folder(os.path.join(out, "postings-e7"), edge_set(7, 2))
    write_folder(os.path.join(out, "postings-e8"), edge_set(8, 1))
    write_crlf_raw(os.path.join(out, "postings-raw-crlf"))
    for name, lines in COPY_FILES.items():
        write_text(os.path.join(out, name), "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
