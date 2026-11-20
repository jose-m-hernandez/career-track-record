"""Tests that the setup guide and the barred guide quote what the tool prints. All data here is
invented.

Every case runs with CTR_CONFIG_DIR, HOME and the working directory set to fresh temporary
folders, and with git's global and system configuration pointed at the null device, so no case
reads or writes a real config. The guides show invented paths; each test swaps them for the
temporary ones before it compares."""

import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
SETUP_GUIDE = os.path.join(ROOT, "docs", "guides", "setup.md")
BARRED_GUIDE = os.path.join(ROOT, "docs", "guides", "barred.md")
README = os.path.join(ROOT, "README.md")
INVENTED_CONFIG = "/home/you/.config/track-record/config.json"
INVENTED_FOLDER = "/home/you/my-record"


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def indented_blocks(text):
    """The runs of lines indented four spaces, each as a list of lines without the indent."""
    blocks, current = [], []
    for line in text.split("\n"):
        if line.startswith("    "):
            current.append(line[4:])
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


class DocsCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)
        self.home = os.path.join(self.tmp, "home")
        self.cwd = os.path.join(self.tmp, "cwd")
        self.cfg_dir = os.path.join(self.tmp, "cfg")
        self.cfg = os.path.join(self.cfg_dir, "config.json")
        self.folder = os.path.join(self.tmp, "myrecord")
        for name in (self.home, self.cwd):
            os.mkdir(name)

    def track(self, *args):
        env = {"PATH": "/usr/bin:/bin", "HOME": self.home, "PYTHONPATH": SRC,
               "PYTHONDONTWRITEBYTECODE": "1", "CTR_CONFIG_DIR": self.cfg_dir,
               "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
               "GIT_CONFIG_NOSYSTEM": "1"}
        proc = subprocess.run([sys.executable, "-m", "career_track_record"] + list(args),
                              cwd=self.cwd, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")

    def invented(self, text):
        return text.replace(self.cfg, INVENTED_CONFIG).replace(self.folder, INVENTED_FOLDER)

    def block_starting(self, guide, first_line):
        for block in indented_blocks(read(guide)):
            if block[0] == first_line:
                return block
        self.fail("the guide has no indented block starting with the expected line")


class SetupGuideCase(DocsCase):
    def test_no_terminal_and_no_folder_cannot_run(self):
        line = "cannot run: setup needs --folder when it is not run in a terminal"
        code, out, err = self.track("setup")
        self.assertEqual(code, 2, "setup with no terminal and no folder did not exit 2")
        self.assertTrue(out + err == line + "\n", "the cannot-run line changed")
        self.assertTrue(line in self.block_starting(SETUP_GUIDE, line),
                        "the setup guide does not show the cannot-run line")
        self.assertTrue("`Keep it? [Y/n]`" in read(SETUP_GUIDE),
                        "the setup guide does not quote the keep-it prompt")

    def test_the_summary_in_the_guide_is_what_setup_prints(self):
        code, out, err = self.track("setup", "--folder", self.folder)
        self.assertEqual(code, 0, "setup --folder did not exit 0")
        self.assertTrue(err == "", "setup --folder printed on standard error")
        shown = self.block_starting(SETUP_GUIDE, "Setup done.")
        self.assertTrue(self.invented(out) == "\n".join(shown) + "\n",
                        "the summary in the setup guide differs from the printed one")
        for name in ("sources", "postings", "drafts", "plans"):
            self.assertTrue(os.path.isdir(os.path.join(self.folder, name)),
                            "setup did not make one of the four folders")
        self.assertTrue(os.path.isfile(self.cfg), "setup wrote no config in the config folder")
        written = sorted(os.listdir(self.folder))
        self.assertTrue(written == ["drafts", "plans", "postings", "sources"],
                        "setup made something besides the four folders")

    def test_the_show_lines_in_the_guide_are_what_show_prints(self):
        self.track("setup", "--folder", self.folder)
        code, out, err = self.track("setup", "--show")
        self.assertEqual(code, 0, "setup --show did not exit 0")
        self.assertTrue(err == "", "setup --show printed on standard error")
        shown = self.block_starting(SETUP_GUIDE, "config: " + INVENTED_CONFIG + " (found)")
        self.assertTrue(self.invented(out) == "\n".join(shown) + "\n",
                        "the show lines in the setup guide differ from the printed ones")

    def test_the_config_and_exit_lines_come_from_the_help(self):
        code, out, err = self.track("setup", "--help")
        self.assertEqual(code, 0, "setup --help did not exit 0")
        guide = read(SETUP_GUIDE)
        for text in ("$CTR_CONFIG_DIR/config.json", "$XDG_CONFIG_HOME/track-record/config.json",
                     "~/.config/track-record/config.json"):
            self.assertTrue(text in out, "the help no longer names one of the config places")
            self.assertTrue(text in guide, "the setup guide does not name one of the config places")
        self.assertTrue("1 the folder is refused (git tracks it, or a work tree does\n"
                        "    not ignore it), 2 it cannot run" in out,
                        "the help's exit codes changed")
        for text in ("- 0: done, kept or shown.",
                     "- 1: the folder is refused, because git tracks it, or because it is in a "
                     "work tree that does not ignore it.",
                     "- 2: `setup` cannot run."):
            self.assertTrue(text in guide, "the setup guide lost an exit-code line")

    def test_the_readme_row_links_the_guide_and_the_guide_exists(self):
        readme = read(README)
        self.assertTrue("| [setup](docs/guides/setup.md) |" in readme,
                        "the README has no row linking the setup guide")
        self.assertTrue(os.path.isfile(SETUP_GUIDE), "the setup guide does not exist")


class BarredGuideCase(DocsCase):
    def test_a_run_with_no_list_says_which_list_it_used(self):
        code, out, err = self.track("setup", "--folder", self.folder)
        self.assertEqual(code, 0, "setup --folder did not exit 0")
        text = "Pat Example led a small team and wrote plain reports for the records office. " * 8
        for name, body in (("barred-list.txt", "zebra-word\n"), ("resume.md", text),
                           ("clean.md", text)):
            with open(os.path.join(self.folder, name), "w", encoding="utf-8") as handle:
                handle.write(body)
        self.cwd = self.folder
        code, out, err = self.track("barred", "--control", "Pat Example", "resume.md",
                                    "clean.md")
        self.assertEqual(code, 0, "barred with no --list did not exit 0")
        expected = ("using " + INVENTED_FOLDER + "/barred-list.txt (from config "
                    + INVENTED_CONFIG + ")")
        self.assertTrue(self.invented(err) == expected + "\n",
                        "the line on standard error that the barred guide quotes changed")
        self.assertTrue("`" + expected + "`" in read(BARRED_GUIDE),
                        "the barred guide does not quote the standard error line")
        self.assertTrue("[the setup guide](setup.md)" in read(BARRED_GUIDE),
                        "the barred guide does not link the setup guide")


if __name__ == "__main__":
    unittest.main()
