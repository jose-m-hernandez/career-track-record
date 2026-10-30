import ast
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_version():
    path = os.path.join(REPO_ROOT, "src", "career_track_record", "__init__.py")
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    return ast.literal_eval(node.value)
    raise AssertionError("no __version__ in src/career_track_record/__init__.py")


def bdist_wheel_found(find_spec=importlib.util.find_spec):
    """True when setuptools is importable and so is a provider of the ``bdist_wheel`` command:
    the ``wheel`` package, or setuptools' own command (setuptools 70.1 and later)."""
    def has(name):
        try:
            return find_spec(name) is not None
        except (ImportError, ValueError):
            return False

    return has("setuptools") and (has("wheel") or has("setuptools.command.bdist_wheel"))


def setuptools_gate(found, environ):
    if found:
        return "run"
    if environ.get("GITHUB_ACTIONS") == "true":
        return "fail"
    return "skip"


class PackagingCase(unittest.TestCase):
    def test_offline_wheel_has_right_name_and_version(self):
        gate = setuptools_gate(bdist_wheel_found(), os.environ)
        if gate == "skip":
            self.skipTest(
                "no bdist_wheel provider: setuptools 70.1 or later, "
                "or setuptools plus wheel, is not installed"
            )
        if gate == "fail":
            self.fail(
                "no bdist_wheel provider is installed in CI; "
                "install ci/requirements-build.txt so the wheel test runs"
            )
        version = read_version()
        with tempfile.TemporaryDirectory() as tmp:
            copy_dir = os.path.join(tmp, "tree")
            out_dir = os.path.join(tmp, "out")
            os.mkdir(out_dir)
            shutil.copytree(REPO_ROOT, copy_dir, ignore=shutil.ignore_patterns(".git"))
            env = dict(os.environ, SOURCE_DATE_EPOCH="1760918400")
            with open(os.devnull, "rb") as devnull:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "wheel", "--no-deps",
                     "--no-build-isolation", "--no-index", "-w", out_dir, copy_dir],
                    stdin=devnull, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    env=env, universal_newlines=True,
                )
            self.assertEqual(result.returncode, 0, result.stdout)
            names = os.listdir(out_dir)
            wheels = [n for n in names if n.endswith(".whl")]
            self.assertEqual(
                wheels, ["career_track_record-%s-py3-none-any.whl" % version]
            )
            self.assertFalse([n for n in names if "UNKNOWN" in n], names)
            with zipfile.ZipFile(os.path.join(out_dir, wheels[0])) as wheel:
                held = wheel.namelist()
                entry_names = [n for n in held if n.endswith("entry_points.txt")]
                self.assertEqual(len(entry_names), 1, held)
                entry_points = wheel.read(entry_names[0]).decode("utf-8")
                data_name = "career_track_record/data/tone-default.json"
                self.assertIn(data_name, held, held)
                shipped = wheel.read(data_name)
            source_path = os.path.join(REPO_ROOT, "src", "career_track_record", "data",
                                       "tone-default.json")
            with open(source_path, "rb") as handle:
                self.assertEqual(shipped, handle.read())
            self.assertIn("career_track_record/__init__.py", held, held)
            for module in ("keywords", "posting_file", "cli", "barred", "pdf_text"):
                self.assertIn("career_track_record/%s.py" % module, held, held)
            self.assertIn("track-record = career_track_record.cli:main", entry_points)


class SetuptoolsGateCase(unittest.TestCase):
    def test_runs_when_setuptools_is_found(self):
        for environ in ({}, {"GITHUB_ACTIONS": "true"}, {"GITHUB_ACTIONS": "false"}):
            self.assertEqual(setuptools_gate(True, environ), "run", environ)

    def test_skips_outside_ci_without_setuptools(self):
        for environ in (
            {},
            {"GITHUB_ACTIONS": "false"},
            {"GITHUB_ACTIONS": "1"},
            {"GITHUB_ACTIONS": "TRUE"},
        ):
            self.assertEqual(setuptools_gate(False, environ), "skip", environ)

    def test_fails_in_ci_without_setuptools(self):
        self.assertEqual(setuptools_gate(False, {"GITHUB_ACTIONS": "true"}), "fail")


class BdistWheelProbeCase(unittest.TestCase):
    @staticmethod
    def finder(*present):
        def find_spec(name):
            if name in present:
                return object()
            if "." in name and name.split(".")[0] not in present:
                raise ModuleNotFoundError("No module named %r" % name.split(".")[0])
            return None
        return find_spec

    def test_found_with_both_providers_or_either_one(self):
        command = "setuptools.command.bdist_wheel"
        for present in (("setuptools", "wheel", command), ("setuptools", "wheel"),
                        ("setuptools", command)):
            self.assertTrue(bdist_wheel_found(self.finder(*present)), present)

    def test_not_found_with_neither_provider(self):
        self.assertFalse(bdist_wheel_found(self.finder("setuptools")))
        self.assertFalse(bdist_wheel_found(self.finder()))

    def test_not_found_without_setuptools_even_with_wheel(self):
        self.assertFalse(bdist_wheel_found(self.finder("wheel")))

    def test_the_real_probe_agrees_with_what_can_be_imported(self):
        try:
            import setuptools  # noqa: F401
            try:
                import setuptools.command.bdist_wheel  # noqa: F401
                has_command = True
            except ImportError:
                has_command = False
            has_wheel = importlib.util.find_spec("wheel") is not None
            expected = has_command or has_wheel
        except ImportError:
            expected = False
        self.assertEqual(bdist_wheel_found(), expected)


if __name__ == "__main__":
    unittest.main()
