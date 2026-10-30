"""Tests for the reader command module (career_track_record.ab_reader_command).

They start only the Python program that runs the tests, a local program with no network."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab_reader_command  # noqa: E402


class ReaderCommandCase(unittest.TestCase):
    def test_it_runs_the_list_in_the_folder_and_returns_the_output(self):
        with tempfile.TemporaryDirectory() as folder:
            done = ab_reader_command.run_reader_command(
                [sys.executable, "-c", "print('ok')"], folder, 30)
            self.assertEqual((done.returncode, done.stdout, done.stderr), (0, b"ok\n", b""))
            where = ab_reader_command.run_reader_command(
                [sys.executable, "-c", "import os; print(os.getcwd())"], folder, 30)
            self.assertEqual(os.path.realpath(where.stdout.decode("utf-8").strip()),
                             os.path.realpath(folder))

    def test_it_gives_the_program_no_input(self):
        with tempfile.TemporaryDirectory() as folder:
            done = ab_reader_command.run_reader_command(
                [sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"], folder, 30)
            self.assertEqual(done.stdout, b"''\n")

    def test_a_failing_program_is_returned_not_raised(self):
        with tempfile.TemporaryDirectory() as folder:
            done = ab_reader_command.run_reader_command(
                [sys.executable, "-c", "import sys; sys.exit(3)"], folder, 30)
            self.assertEqual(done.returncode, 3)

    def test_anything_but_a_list_of_strings_raises_type_error(self):
        with tempfile.TemporaryDirectory() as folder:
            for bad in ("echo hi", ("echo", "hi"), [], ["echo", 1], None, b"echo"):
                with self.subTest(bad):
                    with self.assertRaises(TypeError):
                        ab_reader_command.run_reader_command(bad, folder, 30)

    def test_a_missing_program_raises_its_error(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = os.path.join(folder, "no-such-reader")
            with self.assertRaises(ab_reader_command.ReaderCommandError) as caught:
                ab_reader_command.run_reader_command([missing], folder, 30)
            self.assertEqual(caught.exception.reason, "not found")

    def test_a_timeout_raises_its_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ab_reader_command.ReaderCommandError) as caught:
                ab_reader_command.run_reader_command(
                    [sys.executable, "-c", "import time; time.sleep(10)"], folder, 0.5)
            self.assertEqual(caught.exception.reason, "timed out")

    def test_a_missing_working_folder_raises_its_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ab_reader_command.ReaderCommandError) as caught:
                ab_reader_command.run_reader_command(
                    [sys.executable, "-c", "pass"], os.path.join(folder, "gone"), 30)
            self.assertEqual(caught.exception.reason, "not found")


if __name__ == "__main__":
    unittest.main()
