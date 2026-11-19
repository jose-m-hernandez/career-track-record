"""Write the barred-check fixtures (invented data) into OUTDIR.

Usage: python3 make_fixtures.py OUTDIR

The output is deterministic: the same bytes every run. The contents follow
docs/specs/barred.md section 10.
"""

import os
import sys

sys.dont_write_bytecode = True

PAD_LINE = "Example Corp shipped a reporting tool for teams."

L1 = (
    "# an invented list\n"
    "\n"
    "turnkey synergy\tnote: entry one\n"
    "rockstar ninja\tnote: entry two\n"
    "—\tnote: the em dash\n"
    "moonshot\n"
    "fix it\n"
)
L2 = (
    "# a second invented list, in the CI format\n"
    "barred-strings-canary-example0001\n"
    "grossweg\n"
    "   padded phrase   \tnote: trimmed\n"
    "fix\tWORD\n"
    "café\n"
)
L3 = (
    "# a third invented list\n"
    "zebra-word\n"
)
L4 = (
    "# a fourth invented list\n"
    "zebra\tword\n"
    "word\tword\n"
)
SHORT_LINE = "Example Corp wrote it."


def padded(block, eol="\n"):
    """Twelve padding lines, the test block (a list of lines), twelve padding lines."""
    lines = [PAD_LINE] * 12 + list(block) + [PAD_LINE] * 12
    return "".join(line + eol for line in lines)


CLEAN = padded(["We wrote tests for the importer."])
SUBSTR = padded(["the moonshots were many"])
SHORT = "turnkey synergy here but no anchor word\n"
PLAIN = padded(["We delivered a turnkey synergy for the team."])
HYPH = padded(["a turnkey syn-", "ergy plan"])

TEXT_FILES = {
    "plain.txt": PLAIN,
    "case.txt": padded(["TURNKEY SYNERGY was the pitch."]),
    "wrap.txt": padded(["turnkey", "synergy across lines"]),
    "hyph.txt": HYPH,
    "hyphcrlf.txt": padded(["a turnkey syn-", "ergy plan"], eol="\r\n"),
    "hyphcr.txt": (
        "".join(PAD_LINE + "\n" for _ in range(12))
        + "a turnkey syn-\rergy plan\n"
        + "".join(PAD_LINE + "\n" for _ in range(12))
    ),
    "hyphsp.txt": padded(["a turnkey syn-  ", "ergy plan"]),
    "soft.txt": padded(["turnkey syn\u00adergy"]),
    "shyend.txt": padded(["a turnkey syn\u00ad", "ergy plan"]),
    "shyendsp.txt": padded(["a turnkey syn\u00ad  \t", "ergy plan"]),
    "shyendcrlf.txt": padded(["a turnkey syn\u00ad", "ergy plan"], eol="\r\n"),
    "shyendcr.txt": (
        "".join(PAD_LINE + "\n" for _ in range(12))
        + "a turnkey syn\u00ad\rergy plan\n"
        + "".join(PAD_LINE + "\n" for _ in range(12))
    ),
    "shymid.txt": padded(["a turnkey syn\u00ad x", "ergy plan"]),
    "shynonword.txt": padded(["a turnkey syn.\u00ad", "ergy plan"]),
    "shyalone.txt": padded(["\u00ad", "ergy plan"]),
    "shyspace.txt": padded(["a blorf\u00ad", "quaxel here"]),
    "shyline.txt": padded(["a blorf\u00ad", "quaxel plan", "blorfquaxel again"]),
    "shycomment.ts": padded(["a turnkey syn\u00ad // a note", "ergy plan"]),
    "zw.txt": padded(["turnkey\u200b synergy"]),
    "nbsp.txt": padded(["turnkey\u00a0synergy"]),
    "lig.txt": padded(["weﬁx it fast"]),
    "emdash.txt": padded(["fast — and more"]),
    "clean.txt": CLEAN,
    "endash.txt": padded(["from 2017–2026"]),
    "compound.txt": padded(["end-to-end tests and moon-shot ideas"]),
    "note.txt": padded(["note: entry one"]),
    "nbhyph.txt": padded(["a turnkey syn‑", "ergy plan"]),
    "two.txt": padded(["a turnkey synergy and a rockstar ninja and another turnkey synergy"]),
    "substr.txt": SUBSTR,
    "early.txt": padded(["turnkey syn-", "ergy and later turnkey", "synergy"]),
    "src.ts": padded([
        "// turnkey synergy in a comment",
        'export default { value: "clean text", note: "rockstar ninja" + "more" };',
        "/* moonshot in a block */",
    ]),
    "lines.ts": padded(["/* a block", "that spans */", "rockstar ninja here"]),
    "nlnote.ts": padded(["x = { note:", '  "moonshot" +', '  "more" };']),
    "url.ts": padded(['x = "https://moonshot.example";']),
    "footnote.ts": padded(['x = { footnote: "moonshot" };']),
    "spcolon.ts": padded(['x = { note : "moonshot" };']),
    "single.ts": padded(["x = { note: 'moonshot' };"]),
    "unterm.ts": padded(["/* moonshot never closed"]),
    "strblock.ts": padded(['x = "a/*b"; moonshot; y = "*/";']),
    "strip.txt": padded(["// turnkey synergy"]),
    "value.ts": padded(['export default { value: "turnkey synergy" };']),
    "short.txt": SHORT,
    "nocontrol.txt": "A turnkey synergy line. " * 40 + "\n",
    "fold.txt": padded(["the Großweg plan"]),
    "trim.txt": padded(["a padded phrase here"]),
    "word.txt": padded(["we fix bugs; prefix and fixes do not count; fix."]),
    "word2.txt": padded(["fix_it and fix2"]),
    "decomp.txt": padded(["café menu"]),
    "lrm.txt": padded(["gross\u200eweg"]),
    "canary.txt": padded(["barred-strings-canary-example0001"]),
    "moonshot-notes.txt": CLEAN,
    "moonshot-plain.txt": SUBSTR,
    "moonshot-short.txt": SHORT,
    "prefix-notes.txt": CLEAN,
    "hyphkeep.txt": padded(["a zebra-", "word here"]),
    "hyphff1.txt": padded(["a zebra-", "\fword here"]),
    "hyphff2.txt": padded(["a zebra-\f", "word here"]),
    "hyphkeepcrlf.txt": padded(["a zebra-", "word here"], eol="\r\n"),
    "nokeep.txt": padded(["a zebra -", "word here"]),
}


def one_page_pdf(lines):
    """A one-page PDF, built by hand, whose text is the given lines (ASCII only)."""
    stream = "BT\n/F1 11 Tf\n13 TL\n40 770 Td\n"
    stream += "".join("(%s) '\n" % line for line in lines)
    stream += "ET\n"
    stream = stream.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    start = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, start)
    return out


def sample_pdf():
    """The PDF whose text is the padded test line of plain.txt."""
    return one_page_pdf(
        [PAD_LINE] * 12 + ["We delivered a turnkey synergy for the team."] + [PAD_LINE] * 12)


def hyphmid_pdf():
    """The PDF whose one page wraps `a zebra-` / `word here` inside the page."""
    return one_page_pdf([PAD_LINE] * 12 + ["a zebra-", "word here"] + [PAD_LINE] * 12)


BLOCK_PLACES = ("40 770", "330 770")


def pages_pdf(pages, encoding=None):
    """A PDF, built by hand, with one page per item of ``pages`` (ASCII only).

    Each page is a list of text blocks, each block a list of lines. The first block
    starts at ``40 770``, the second at ``330 770``. Every block is written as
    one_page_pdf writes its one block. ``encoding``, if given, is the font's
    /Encoding value."""
    font = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica"
    if encoding is not None:
        font += b" /Encoding " + encoding.encode("latin-1")
    font += b" >>"
    count = len(pages)
    kids = " ".join("%d 0 R" % (4 + 2 * i) for i in range(count))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        ("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, count)).encode("latin-1"),
        font,
    ]
    for index, blocks in enumerate(pages):
        stream = ""
        for place, lines in zip(BLOCK_PLACES, blocks):
            stream += "BT\n/F1 11 Tf\n13 TL\n%s Td\n" % place
            stream += "".join("(%s) '\n" % line for line in lines)
            stream += "ET\n"
        stream = stream.encode("latin-1")
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (5 + 2 * index))
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream")
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    start = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, start)
    return out


def twocol_pdf():
    """One page in two columns; the left one wraps `a zebra-` / `word here`."""
    left = ([SHORT_LINE] * 12 + ["a turnkey", "synergy plan", "a zebra-", "word here"]
            + [SHORT_LINE] * 12)
    right = ["Right column text line %d." % n for n in range(1, 29)]
    return pages_pdf([[left, right]])


SOFT_HYPHEN_ENCODING = (
    "<< /Type /Encoding /BaseEncoding /WinAnsiEncoding /Differences [173 /sfthyphen] >>")


def softhyph_pdf():
    """One page that wraps `a turnkey syn` / `ergy plan` at a soft hyphen (byte 0xAD)."""
    lines = [PAD_LINE] * 12 + ["a turnkey syn\\255", "ergy plan"] + [PAD_LINE] * 12
    return pages_pdf([[lines]], encoding=SOFT_HYPHEN_ENCODING)


def pagewrap_pdf():
    """Two pages: `a zebra-` ends page 1 and `word here` starts page 2."""
    return pages_pdf([[[PAD_LINE] * 12 + ["a zebra-"]],
                      [["word here"] + [PAD_LINE] * 12]])


def page3wrap_pdf():
    """Three pages; the wrap `a zebra-` / `word here` is inside page 3."""
    return pages_pdf([[[PAD_LINE] * 12], [[PAD_LINE] * 12],
                      [["a zebra-", "word here"] + [PAD_LINE] * 12]])


PARSE_GOOD_PAGE1 = [
    "Ada Example",
    "ada@example.com",
    "Experience",
    "Built reporting tools for small teams.",
    "Wrote guides for new staff.",
    "Jan 2020 - Present",
    "Mar 2017 - Dec 2019",
    "Jun 2014 - Feb 2017",
    "Education",
    "Studied data analysis at Example College.",
    "Finished a short course in writing.",
    "Skills",
    "Reporting and charts.",
    "Clear writing and teaching.",
]


def parse_good_pdf():
    """The base fixture of docs/specs/parse.md (spec 1, section 7), also examples/good.pdf:
    page 1 holds the name, an email, three headings and three date ranges; page 2 holds
    the padding line six times. ASCII only."""
    return pages_pdf([[PARSE_GOOD_PAGE1], [[PAD_LINE] * 6]])


def parse_name_page2_pdf():
    """The name and the email are on page 2 only; page 1 holds two headings and one range."""
    page1 = ["Experience", "Built reporting tools for small teams.", "Jan 2020 - Present",
             "Skills", "Reporting and charts."]
    return pages_pdf([[page1], [["Ada Example", "ada@example.com"] + [PAD_LINE] * 3]])


def parse_empty_page2_pdf():
    """The base fixture's page 1, then a page 2 with no text (an image-only page)."""
    return pages_pdf([[PARSE_GOOD_PAGE1], [[""]]])


def parse_empty_pdf():
    """One page with no text."""
    return pages_pdf([[[""]]])


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: make_fixtures.py OUTDIR\n")
        return 2
    outdir = argv[1]
    os.makedirs(outdir, exist_ok=True)
    files = {"list-l1.txt": L1.encode("utf-8"), "list-l2.txt": L2.encode("utf-8"),
             "list-l3.txt": L3.encode("utf-8"), "list-l4.txt": L4.encode("utf-8")}
    for name, text in TEXT_FILES.items():
        files[name] = text.encode("utf-8")
    files["bom.txt"] = b"\xef\xbb\xbf" + PLAIN.encode("utf-8")
    files["sample.pdf"] = sample_pdf()
    files["hyphmid.pdf"] = hyphmid_pdf()
    files["twocol.pdf"] = twocol_pdf()
    files["softhyph.pdf"] = softhyph_pdf()
    files["pagewrap.pdf"] = pagewrap_pdf()
    files["page3wrap.pdf"] = page3wrap_pdf()
    for name in sorted(files):
        with open(os.path.join(outdir, name), "wb") as handle:
            handle.write(files[name])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
