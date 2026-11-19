# `track-record keywords`

Keep a folder of job postings you've saved yourself, and a table of the terms you care about. The scan shows which terms the postings ask for that your copy never uses. It has three modes: `demand` shows which terms the postings ask for, `coverage` shows which terms your copy uses, and `report` puts the two together and lists the gaps.

Each posting is a `.txt` file whose short header, or `.meta.json` sidecar, records its SHA-256; a posting that no longer matches is refused. [keyword-scan.md § 4](../specs/keyword-scan.md) shows both formats. The term table is a tab-separated file with the columns `family`, `pattern` and `note`. In `demand` and `report`, mark at least one family `must-find` in its note, so a run that can't see the postings stops instead of reporting zeros. Mark a term `chosen` when it's your own choice of word.

    track-record keywords demand   --postings postings/ --terms terms.tsv
    track-record keywords coverage --terms terms.tsv resume.md
    track-record keywords report   --postings postings/ --terms terms.tsv --copy resume.md

It reports gaps and never rewrites your copy or sets a keyword-score target. A `chosen` term is labelled as yours in the report, and the scan never suggests dropping or replacing one your copy uses. Spec: [docs/specs/keyword-scan.md](../specs/keyword-scan.md). If your copy comes from a PDF, run [wrapped-compounds](wrapped-compounds.md) first: a word split at its hyphen can read as `crossfunctional` there and show as a gap.

## A worked example

The files below are in `examples/keywords/`, invented, and the commands run green on them from the top folder of your clone.

**A posting needs a record of its hash.** A posting you save by hand is the easiest with a sidecar: save the job text as `postings/care-manager.txt`, then write a file beside it named `postings/care-manager.txt.meta.json`:

    {
      "format": "raw-posting-with-sidecar",
      "source_url": "https://example.com/jobs/care-manager",
      "bytes": 247,
      "sha256": "09bda8265d4b4efe4c0d42083bbc9d48841a7325242cca51a2e8aac48a0d2a8a"
    }

`source_url` must start with `https://`; `bytes` and `sha256` describe the posting file exactly as saved, so change one character of the posting and you must redo both. Get the size and the hash with Python, which works the same on macOS, Linux and Windows:

    python3 -c "import os,sys;print(os.path.getsize(sys.argv[1]))" examples/keywords/postings/care-manager.txt
    python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" examples/keywords/postings/care-manager.txt

On Windows use `python` if that is the command you have. `shasum -a 256 FILE` on macOS and Linux, or `certutil -hashfile FILE SHA256` on Windows, print the same hash; the Windows one was not run for this guide. The tool has no command of its own that writes the hash for you.

**The other form is a header.** `examples/keywords/postings/support-lead.txt` starts with six header lines and then the job text. This is the form a fetch tool writes; it is harder by hand, because its `sha256` is the hash of the text after the header, with no line break added at the end, and many editors add one:

    source_url: https://example.com/jobs/support-lead
    api_endpoint: https://example.com/api/jobs/support-lead
    fetched_at: 2026-01-15T09:00:00Z
    http_status: 200
    sha256: 4db3f35cf7f352de2b622cba5944069bced330073beedcd496c35838e55fdb17
    bytes: 306
    Support Operations Lead
    Brightfield Goods, remote
    ...

A posting with neither a header nor a sidecar is refused, and the error says so.

**The term table** is `examples/keywords/terms.tsv`: one header row and then one row per term, with the three columns separated by a tab (not spaces). The pattern is a regular expression, matched without regard to case; the note may be empty.

    family	pattern	note
    help-desk	help desk	must-find
    reply-templates	reply templates?
    reporting	report(ing)?

`help-desk` is marked `must-find`: it has to appear in the postings, or the run stops, because zero hits could mean the scan could not see them.

**Run it.** `resume.txt` is an invented copy to check:

    track-record keywords demand   --postings examples/keywords/postings --terms examples/keywords/terms.tsv
    track-record keywords coverage --terms examples/keywords/terms.tsv examples/keywords/resume.txt
    track-record keywords report   --postings examples/keywords/postings --terms examples/keywords/terms.tsv --copy examples/keywords/resume.txt

Each exits 0. The report ends with `Keywords: reply-templates (100% of postings, 0 in copy)`: both postings ask for reply templates and the copy never says so.
