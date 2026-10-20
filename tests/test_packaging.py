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


class PackagingCase(unittest.TestCase):
    def test_offline_wheel_has_right_name_and_version(self):
        if importlib.util.find_spec("setuptools") is None:
            self.skipTest("setuptools is not installed")
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
            self.assertIn("career_track_record/__init__.py", held, held)


if __name__ == "__main__":
    unittest.main()
