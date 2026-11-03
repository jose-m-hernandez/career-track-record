"""Check that a quoted phrase appears word for word in the source it cites.

This is the engine for rule 5 of METHOD.md: a quoted phrase only counts as verified once a
check has found it, word for word, in the source it cites. No command calls this module yet;
``track-record claims`` still stores each source and never reads it.

``check_quote(quote, path)`` returns ``(status, reason)``. The rules, in plain words:

* The quote is prepared the way the claim gate prepares a sentence (``claims.prepare``): folded,
  line-end hyphens joined, whitespace runs turned into one space, trimmed, and one final full
  stop, exclamation mark or question mark (with its closing characters) dropped. A quote with no
  letter or digit is DEAD ("no quote").
* The source is a UTF-8 text file (one leading byte order mark is dropped) or, when the name ends
  in ``.pdf`` in any case, a PDF read with ``pdftotext`` through ``barred._read_text``. It is
  prepared the same way, without the final-stop drop.
* FOUND needs the quote inside the source with a word boundary at each end that is a word
  character; an edge that is not a word character needs no boundary there (``.NET`` is found in
  ``ASP.NET``). Otherwise NOT_FOUND.
* Anything that cannot be checked is DEAD with a reason: "no quote", "cannot read", "not UTF-8",
  "pdftotext not found", "pdftotext failed", or "cannot check" for an unexpected error.
* It never raises and never prints.
"""

from career_track_record import barred, claims

FOUND = "found"
NOT_FOUND = "not found"
DEAD = "dead"


def _search(q, s):
    """True when ``q`` occurs in ``s`` with the boundaries of rule 4 holding.

    After a failed occurrence the search resumes at the next position where a start boundary
    can hold, so a long run of word characters is scanned once, not once per position."""
    is_word = barred._is_word_char
    need_start = is_word(q[0])
    need_end = is_word(q[-1])
    size = len(q)
    total = len(s)
    p = s.find(q)
    while p >= 0:
        start_ok = (not need_start) or p == 0 or not is_word(s[p - 1])
        if start_ok:
            end = p + size
            if (not need_end) or end == total or not is_word(s[end]):
                return True
        nxt = p + 1
        if need_start:
            # A start boundary needs a non-word character just before the position.
            j = p
            while j < total and is_word(s[j]):
                j += 1
            nxt = j + 1
        p = s.find(q, nxt)
    return False


def check_quote(quote, path):
    """Return (status, reason). reason is "" unless status is DEAD."""
    try:
        if not isinstance(quote, str):
            return (DEAD, "no quote")
        q = claims.prepare(quote)
        if not claims._has_letter_or_digit(q):
            return (DEAD, "no quote")
        if not isinstance(path, str):
            return (DEAD, "cannot read")
        if path.lower().endswith(".pdf"):
            try:
                text = barred._read_text(path, False)
            except barred._Dead as dead:
                return (DEAD, dead.args[0])
        else:
            try:
                with open(path, "rb") as handle:
                    data = handle.read()
            except (OSError, ValueError, TypeError):
                return (DEAD, "cannot read")
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                return (DEAD, "not UTF-8")
            if text.startswith("\ufeff"):
                text = text[1:]
        s = claims._squash(text)
        if _search(q, s):
            return (FOUND, "")
        return (NOT_FOUND, "")
    except Exception:
        return (DEAD, "cannot check")
