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


def setuptools_gate(found, environ):
    if found:
        return "run"
    if environ.get("GITHUB_ACTIONS") == "true":
        return "fail"
    return "skip"


class PackagingCase(unittest.TestCase):
    def test_offline_wheel_has_right_name_and_version(self):
        gate = setuptools_gate(
            importlib.util.find_spec("setuptools") is not None, os.environ
        )
        if gate == "skip":
            self.skipTest("setuptools is not installed")
        if gate == "fail":
            self.fail(
                "setuptools is not installed in CI; "
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


if __name__ == "__main__":
    unittest.main()
