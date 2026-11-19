"""The re-check before a write into the record folder.

A command that writes into the configured record folder first asks this module whether the
write may go ahead: the config must be usable, a path that is inside the record folder as
written must not resolve outside it, and a record folder that has since become tracked (or is
no longer ignored) is refused. Whether a path is inside the record folder is decided by asking
the file system (``os.path.samefile``), never by comparing strings, so a path spelled in
another case or another Unicode normalisation, and a configured symbolic link, are seen for
what they are. Nothing here creates, moves or deletes anything."""

import os

from career_track_record import config, reader_harness, record_folder
from career_track_record.barred import printed_path


class Refusal(Exception):
    """The write must not happen. ``code`` is the exit code and ``line`` the one line for
    standard error (without its line feed)."""

    def __init__(self, code, line):
        Exception.__init__(self, line)
        self.code = code
        self.line = line


def inside(path, root):
    """True when ``path`` is ``root`` or lies below it. Asked of the file system: take the
    path and its parents one at a time, by removing the last component without resolving
    anything, skip each that does not exist, and ask ``os.path.samefile`` of each existing one
    against ``root``."""
    here = path
    while True:
        try:
            if os.path.samefile(here, root):
                return True
        except (OSError, ValueError):
            pass
        parent = os.path.dirname(here)
        if parent == here:
            return False
        here = parent


def _absolute(path):
    """The path with the current directory put in front when it is relative, and nothing
    else done to it (no link followed, no ``..`` collapsed)."""
    return path if os.path.isabs(path) else os.path.join(os.getcwd(), path)


def recheck(targets, environ=None):
    """Raise Refusal when a write to any of ``targets`` (complete output paths, as the person
    or the command spells them) must not happen; return None when it may.

    The config is read first: a config that exists and is not usable stops the write (exit 2,
    the config message); no config file means no record folder is known, and nothing is
    re-checked. A target the config's record folder does not contain, as written or resolved,
    is not re-checked either."""
    try:
        _path, root = config.read_config(environ)
    except config.ConfigError as exc:
        raise Refusal(2, exc.line())
    if root is None or not os.path.exists(root):
        return
    reaches_in = False
    for target in targets:
        written = _absolute(target)
        resolved = record_folder.resolve(written)[0]
        inside_written = inside(written, root)
        inside_resolved = inside(resolved, root)
        if inside_written and not inside_resolved:
            raise Refusal(1, "refused: %s is inside the record folder as written but resolves "
                             "outside it" % printed_path(target))
        reaches_in = reaches_in or inside_resolved
    if not reaches_in:
        return
    refused = record_folder.refusal(record_folder.decide(root))
    if refused is not None:
        raise Refusal(*refused)


def next_result(folder):
    """The path of the result file a run or a score in ``folder`` writes next: the first
    ``result-N.txt`` that does not exist (a link counts as existing, as it does for the
    exclusive create that skips it)."""
    number = 1
    while os.path.lexists(os.path.join(folder, "%s%d.txt" % (reader_harness.RESULT_STEM,
                                                             number))):
        number += 1
    return os.path.join(folder, "%s%d.txt" % (reader_harness.RESULT_STEM, number))


def plan_targets(sub, plan_path):
    """Every path ``ab`` or ``panel`` ``sub`` (freeze, run or score) creates in the plan's
    folder, as complete paths, the files and the folder the command makes there first and the
    plan's folder itself last (so a refusal names the file when it can). Everything beneath
    ``reads`` is made new by the run, so ``reads`` itself stands for it: a run refuses to
    start when it already exists."""
    folder = reader_harness.folder_of(plan_path)
    if sub == "freeze":
        return [os.path.join(folder, os.path.basename(plan_path)
                             + reader_harness.FREEZE_SUFFIX), folder]
    if sub == "run":
        return [os.path.join(folder, reader_harness.KEY_FILE),
                os.path.join(folder, reader_harness.RUN_LOG),
                os.path.join(folder, reader_harness.READS_DIR), next_result(folder), folder]
    return [next_result(folder), folder]
