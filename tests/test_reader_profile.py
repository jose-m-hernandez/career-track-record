"""Case R18 of the reader-contract spec: what the `codex` permission profile refuses, with no
model call. All data here is invented.

Runs where `codex` is installed, on macOS (the profile was measured there); otherwise each
case is skipped with a reason that says "not run", never passed. The profile is built by the
example reader's own function, so the string that ships is the string that is tested. Every
command runs through pipes: a sandboxed command whose standard output is redirected to a file
in the run's root reads as a refusal, so nothing here does that. The run's root is made twice,
once under the system temporary folder and once under /tmp, and every planted file is deleted
at the end and shown gone."""

import importlib.util
import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READER = os.path.join(ROOT, "examples", "readers", "model_reader.py")
CODEX = shutil.which("codex")
RUBY = "/usr/bin/ruby"
FILES = {"PROMPT.txt": "invented prompt text", "POSTING.txt": "invented posting text",
         "A.txt": "invented version alpha", "B.txt": "invented version beta"}
REFUSED = "Operation not permitted"
MISSING = "No such file or directory"
# The names a command under the profile may print without a shell (the six of M9, one of which
# begins NODE_REPL).
SIX = ("CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "PWD", "SHLVL", "_")
TIMEOUT = 120

# Prints the environment of one process of the user through the system's process-argument call
# (`sysctl`, KERN_PROCARGS2) by way of `fiddle` (M17). The target is the process that started
# this one (the `codex` process) when target.txt says `parent`, else a process id.
PROCARGS = """require 'fiddle'
target = File.read('target.txt').strip
pid = target == 'parent' ? Process.ppid : target.to_i
libc = Fiddle.dlopen(nil)
sysctl = Fiddle::Function.new(libc['sysctl'], [Fiddle::TYPE_VOIDP, Fiddle::TYPE_INT,
  Fiddle::TYPE_VOIDP, Fiddle::TYPE_VOIDP, Fiddle::TYPE_VOIDP, Fiddle::TYPE_LONG], Fiddle::TYPE_INT)
mib = Fiddle::Pointer[[1, 49, pid].pack('i*')]
size = Fiddle::Pointer.malloc(8)
size[0, 8] = [0].pack('Q')
abort('sysctl size failed') unless sysctl.call(mib, 3, nil, size, nil, 0) == 0
want = size[0, 8].unpack('Q')[0]
buf = Fiddle::Pointer.malloc(want)
size[0, 8] = [want].pack('Q')
abort('sysctl read failed') unless sysctl.call(mib, 3, buf, size, nil, 0) == 0
data = buf[0, size[0, 8].unpack('Q')[0]]
argc = data[0, 4].unpack('i')[0]
parts = data[4..-1].split("\\0", -1)
parts.shift
parts.shift while parts.first == ''
parts.shift(argc)
env = []
env << parts.shift until parts.empty? || parts.first == ''
puts env
"""


def load_reader():
    spec = importlib.util.spec_from_file_location("model_reader_profile_test", READER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def token():
    return os.urandom(16).hex()


def name():
    return "R18_" + os.urandom(6).hex().upper()


def sandbox(profile_entry, cwd, command, *extra, profile="reader", env=None):
    """`codex sandbox` on one command, through pipes. Returns (status, output of both streams)."""
    args = [CODEX, "sandbox", "-P", profile, "-C", cwd]
    if profile_entry:
        args += ["-c", "permissions.reader.filesystem=" + profile_entry]
    args += list(extra) + ["--"] + list(command)
    done = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=env, timeout=TIMEOUT)
    return done.returncode, (done.stdout + done.stderr).decode("utf-8", "replace")


def names_of(output):
    return [line.partition("=")[0] for line in output.splitlines() if "=" in line]


def setUpModule():
    """Print the codex version once per run, so the record of the run carries it."""
    if not CODEX:
        return
    done = subprocess.run([CODEX, "--version"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=TIMEOUT)
    sys.stderr.write("R18 codex version: %s\n" % done.stdout.decode("utf-8", "replace").strip())


@unittest.skipUnless(CODEX, "not run: codex is not installed")
@unittest.skipUnless(sys.platform == "darwin", "not run: the profile was measured on macOS only")
class ProfileRows(object):
    """The rows of R18, for one run root. `root_dir` is where the root is made."""

    root_dir = None

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="r18-", dir=self.root_dir)
        self.folder = os.path.join(self.base, "f")
        self.paths = {"K": os.path.join(self.base, "key.txt"),
                      "S": os.path.join(self.base, "sib", "token.txt"),
                      "H": os.path.join(pwd.getpwuid(os.getuid()).pw_dir, "r18-" + token()[:16]),
                      "T": os.path.join("/tmp", "r18-" + token()[:16])}
        # The clean-up is registered before anything is planted, so a failure part-way through
        # setUp still deletes what was made.
        self.addCleanup(self.clean_up)
        self.reader = load_reader()
        os.makedirs(self.folder)
        for file_name, text in FILES.items():
            with open(os.path.join(self.folder, file_name), "w", encoding="utf-8") as handle:
                handle.write(text + "\n")
        self.tokens = {}
        os.makedirs(os.path.join(self.base, "sib"))
        for key, path in self.paths.items():
            self.tokens[key] = token()
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.tokens[key] + "\n")
        install = os.path.realpath(os.path.dirname(os.path.abspath(CODEX)))
        self.install = install
        self.profile = self.reader.codex_profile(install)

    def clean_up(self):
        shutil.rmtree(self.base, ignore_errors=True)
        for key in ("H", "T"):
            try:
                os.remove(self.paths[key])
            except OSError:
                pass
        for path in list(self.paths.values()) + [self.base]:
            shown = subprocess.run(["/bin/ls", "-d", path], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT).stdout.decode("utf-8", "replace")
            self.assertTrue(MISSING in shown, "left behind: " + os.path.basename(path))

    def run_in_f(self, command, *extra, **kw):
        return sandbox(self.profile, self.folder, command, *extra, **kw)

    def assert_no_token(self, output):
        for key in "KSHT":
            self.assertTrue(self.tokens[key] not in output, "the token of %s was printed" % key)

    def test_control_a_file_in_the_folder_is_read(self):
        status, output = self.run_in_f(["/bin/cat", "PROMPT.txt"])
        self.assertTrue((status, output) == (0, "invented prompt text\n"),
                        "the read of PROMPT.txt did not print exactly its text")

    def test_control_a_missing_file_says_so(self):
        status, output = self.run_in_f(["/bin/cat", "nope.txt"])
        self.assertEqual(status, 1, "the read of a missing file did not exit 1")
        self.assertTrue(MISSING in output, "the missing-file message was not printed")

    def test_every_read_outside_the_folder_is_refused_and_no_token_is_printed(self):
        commands = (["/bin/cat", self.paths["S"]], ["/bin/cat", "../key.txt"],
                    ["/bin/cat", self.paths["K"]], ["/bin/cat", self.paths["H"]],
                    ["/bin/cat", self.paths["T"]], ["/bin/ls", ".."],
                    ["/bin/sh", "-c", "cd .. && cat key.txt"])
        for command in commands:
            with self.subTest(command=" ".join(command)):
                status, output = self.run_in_f(command)
                self.assertEqual(status, 1, "the read outside the folder did not exit 1")
                self.assertTrue(REFUSED in output, "the refusal message was not printed")
                self.assert_no_token(output)

    def test_a_write_in_the_folder_is_refused(self):
        status, output = self.run_in_f(["/bin/sh", "-c", "echo x > w.txt"])
        self.assertEqual(status, 1, "the write in the folder did not exit 1")
        self.assertFalse(os.path.exists(os.path.join(self.folder, "w.txt")))

    def test_positive_control_the_read_only_profile_reads_the_sibling_file(self):
        status, output = sandbox(None, self.folder, ["/bin/cat", self.paths["S"]],
                                 profile=":read-only")
        self.assertEqual(status, 0, "the read-only profile run did not exit 0")
        self.assertTrue(self.tokens["S"] in output, "the token of S was not printed by the control")

    def test_the_environment_of_the_command_is_cut_to_the_names_codex_sets(self):
        planted, value = name(), token()
        # Built from nothing, with invented values: the three names the reader ships, the
        # planted one, and ten more invented names, so the control below sees more than six.
        env = self.reader.codex_env(self.install, self.base, self.base)
        env.update({"R18_EXTRA_%d" % number: "invented-extra-%d" % number for number in range(10)})
        env[planted] = value
        status, output = self.run_in_f(["/usr/bin/env"], "-c",
                                       "shell_environment_policy.inherit=none", env=env)
        self.assertEqual(status, 0, "the cut run did not exit 0")
        self.assertTrue(value not in output, "the planted token was printed by the cut run")
        shown = names_of(output)
        self.assertGreater(len(shown), 0, "the profile run printed no names")
        self.assertTrue(all(found in SIX or found.startswith("NODE_REPL") for found in shown),
                        "the cut run printed a name outside the names codex sets")
        # Positive control, in the same run: without the entry the token is there.
        status, output = self.run_in_f(["/usr/bin/env"], env=env)
        self.assertEqual(status, 0, "the control run did not exit 0")
        self.assertTrue(value in output, "the planted token was not printed by the control run")
        self.assertGreater(len(set(names_of(output))), 6)
        self.assertGreater(len(names_of(output)), 0)

    def test_debug_prompt_input_lists_the_profile(self):
        args = self.reader.codex_args(self.install, "/unused/reply.txt")
        flags = []
        for at, text in enumerate(args):
            if text == "-c":
                flags += ["-c", args[at + 1]]
        # An environment built from nothing, and an empty Codex home this test makes, so the
        # runner's own instruction file is not read into the captured text.
        codex_home = os.path.join(self.base, "codex-home")
        os.makedirs(codex_home)
        env = self.reader.codex_env(self.install, self.base, self.base)
        env["CODEX_HOME"] = codex_home
        done = subprocess.run([CODEX, "debug", "prompt-input"] + flags, cwd=self.folder,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=env, timeout=TIMEOUT)
        text = done.stdout.decode("utf-8", "replace")
        self.assertEqual(done.returncode, 0, "debug prompt-input did not exit 0")
        for special in (":slash_tmp", ":tmpdir"):
            found = re.search(r'access=\\"deny\\"[^>]*><special>%s</special>' % special, text)
            self.assertTrue(found is not None, "the deny entry for %s is not listed" % special)
        wanted = 'access=\\"read\\"><path>%s</path>' % os.path.realpath(self.folder)
        self.assertTrue(wanted in text, "the read entry for the start folder is not listed")

    @unittest.skipUnless(os.path.exists(RUBY), "not run: /usr/bin/ruby is absent")
    def test_the_codex_process_environment_holds_only_its_three_names(self):
        planted, value = name(), token()
        home = self.reader.home_folders({})
        work = os.path.join(self.base, "g")
        os.makedirs(work)
        with open(os.path.join(work, "procargs.rb"), "w", encoding="utf-8") as handle:
            handle.write(PROCARGS)
        child_env = {"PATH": "/usr/bin:/bin", "HOME": self.base, "TMPDIR": self.base,
                     planted: value}
        bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"],
                                     env=child_env, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: (bystander.kill(), bystander.wait()))
        shipped = self.reader.codex_env(self.install, home[0] or home[1], self.base)
        command = [RUBY, "--disable-gems", "procargs.rb"]

        def call(target, env):
            with open(os.path.join(work, "target.txt"), "w", encoding="utf-8") as handle:
                handle.write(str(target))
            return sandbox(self.profile, work, command, env=env)

        status, output = call("parent", shipped)
        self.assertEqual(status, 0, "the shipped-environment call did not exit 0")
        self.assertTrue(value not in output, "the planted token was printed by the shipped call")
        for expected in ("PATH=", "HOME=", "TMPDIR="):
            self.assertTrue(expected in output, "%s is not printed by the shipped call" % expected)
        self.assertTrue(sorted(names_of(output)) == ["HOME", "PATH", "TMPDIR"],
                        "the shipped call printed names other than HOME, PATH and TMPDIR")
        # Positive control, in the same run: a process of the user that is not a protected
        # system program, started with the token, prints it through the same call.
        status, output = call(bystander.pid, shipped)
        self.assertEqual(status, 0, "the bystander control call did not exit 0")
        self.assertTrue(value in output, "the planted token was not printed for the bystander")
        # Recorded as M14 says, and not a pass criterion. This call shows the environment a
        # process was started with, and a token put in this process's environment after it
        # started is not in it, so what is recorded here is that fact and nothing more.
        os.environ[planted] = value
        try:
            _status, own = call(os.getpid(), shipped)
        finally:
            del os.environ[planted]
        sys.stderr.write("R18 recorded (M14, not a pass criterion): the call printed a token "
                         "set in the case's own process after it started: %s\n" % (value in own))


class UnderTheSystemTemporaryFolder(ProfileRows, unittest.TestCase):
    root_dir = tempfile.gettempdir()


class UnderSlashTmp(ProfileRows, unittest.TestCase):
    root_dir = "/tmp"


if __name__ == "__main__":
    unittest.main()
