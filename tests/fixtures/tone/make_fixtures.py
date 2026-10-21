"""Write the tone-check fixtures (invented data) into OUTDIR.

Usage: python3 make_fixtures.py OUTDIR

The output is deterministic: the same bytes every run. The contents follow
docs/specs/tone-and-tells.md section 11. Characters that are hard to see are written
as escapes here.
"""

import json
import os
import sys

sys.dont_write_bytecode = True

RATIONALE = "invented rationale"


def rule(rule_id, level, kind, text, example_fire, example_not,
         case=None, category=None):
    """One rule as an ordered dict; case and category only when given."""
    item = {"id": rule_id, "level": level, "kind": kind, "text": text}
    if case is not None:
        item["case"] = case
    if category is not None:
        item["category"] = category
    item["rationale"] = RATIONALE
    item["must_fire"] = [example_fire]
    item["must_not"] = [example_not]
    return item


R1 = {
    "rules": [
        rule("turnkey", "error", "phrase", "turnkey", "A turnkey plan.",
             "A turn key plan.", case="insensitive"),
        rule("no-em-dash", "error", "char", "\u2014", "a \u2014 b", "a \u2013 b"),
        rule("assisted-with", "warn", "phrase", "assisted with", "I assisted with it.",
             "It was assisted by me.", case="insensitive", category="hedge"),
        rule("lower-we", "warn", "phrase", "we", "then we left", "We left.",
             case="sensitive"),
        rule("as-you-can-see", "warn", "phrase", "as you can see",
             "As you can see, yes.", "You can see it.", case="insensitive",
             category="tell"),
    ],
    "exemptions": [
        {"rule": "turnkey",
         "anchor": "Built the turnkey importer for Example Corp",
         "reason": "invented reason"},
    ],
}

R2 = {
    "rules": [
        rule("cpp", "warn", "phrase", "C++", "I wrote C++ daily.", "I wrote C daily.",
             case="insensitive"),
        rule("etc-dot", "warn", "phrase", "etc.", "Go, etc. Then more.", "The etc file.",
             case="insensitive"),
        rule("aa", "warn", "phrase", "a a", "a a", "a b", case="insensitive"),
        rule("done-next", "warn", "regex", "done\\. next",
             "It was done. Next came more.", "done next", case="insensitive"),
    ],
    "exemptions": [],
}

THREE_LINES = ["line one", "assisted with", "line three"]

TEXT_FILES = {
    "case-11-01.txt": "We shipped a Turnkey importer last spring.\n",
    "case-11-03.txt": "Built the turnkey importer for Example Corp in a week.\n",
    "case-11-04.txt": "built the turnkey importer for example corp in a week.\n",
    "case-11-05.txt":
        "Built the turnkey importer for Example Corp. Also a turnkey dashboard.\n",
    "case-11-06.txt": "fast \u2014 and more\n",
    "case-11-07.txt": "Then we moved on. We stayed.\n",
    "case-11-08.txt": "As you can see, it worked. I assisted with planning.\n",
    "case-11-09.txt": "turnkey turnkey\n",
    "case-11-10.txt": "x" * 60 + "turnkey" + "y" * 60 + "\n",
    "case-11-11.txt": "".join(line + "\n" for line in THREE_LINES),
    "case-11-12.txt": "No anchor here.\n",
    "case-11-23.txt": "I wrote C++ and C# daily.\n",
    "case-11-24.txt": "Go, Rust, etc. Then more.\n",
    "case-11-25.txt": "a a a\n",
    "case-11-26.txt": "It was done. Next came more.\n",
    "case-11-27.txt": "He said \"turnkey.\" Then he left.\n",
    "case-11-28.txt": "A  turnkey\t\tplan.\n",
    "case-11-29.txt": "intro line\n   \nturnkey here\n",
    "case-11-30.txt":
        "Built the turnkey importer for\nExample Corp in a week.\n",
    "case-11-31.txt": "".join(line + "\r\n" for line in THREE_LINES),
    "case-11-32.txt": "".join(line + "\r" for line in THREE_LINES),
    "case-11-33.txt": "\u00e9turnkey\n\u0663turnkey\n_turnkey\n",
    "case-11-37.txt": "I am a team player.\n",
}


def rule_file_text(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def build():
    """File name -> bytes, for everything this generator writes."""
    files = {"rules-r1.json": rule_file_text(R1).encode("utf-8"),
             "rules-r2.json": rule_file_text(R2).encode("utf-8")}
    for name, text in TEXT_FILES.items():
        files[name] = text.encode("utf-8")
    return files


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: make_fixtures.py OUTDIR\n")
        return 2
    outdir = argv[1]
    os.makedirs(outdir, exist_ok=True)
    for name, data in sorted(build().items()):
        with open(os.path.join(outdir, name), "wb") as handle:
            handle.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
