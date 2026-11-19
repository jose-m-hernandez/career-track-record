"""Tests for the config module: its location, its strict reading and its atomic write.
All data here is invented; every test points the config at a fresh temporary folder."""

import json
import os
import stat
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import config  # noqa: E402

FOLDER = "/Users/example/career-record"


def valid_text(**changes):
    record = {"config-version": 1, "record-folder": FOLDER}
    record.update(changes)
    return json.dumps(record)


class Temp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)
        self.env = {"CTR_CONFIG_DIR": os.path.join(self.tmp, "cfg")}

    def put(self, data):
        os.makedirs(self.env["CTR_CONFIG_DIR"], exist_ok=True)
        with open(os.path.join(self.env["CTR_CONFIG_DIR"], "config.json"), "wb") as handle:
            handle.write(data if isinstance(data, bytes) else data.encode("utf-8"))


class LocationCase(Temp):
    def test_s38_ctr_config_dir_holds_config_json_directly(self):
        self.assertEqual(config.config_path(self.env),
                         os.path.join(self.tmp, "cfg", "config.json"))

    def test_s38_xdg_config_home_adds_the_track_record_folder(self):
        env = {"XDG_CONFIG_HOME": os.path.join(self.tmp, "xdg")}
        self.assertEqual(config.config_path(env),
                         os.path.join(self.tmp, "xdg", "track-record", "config.json"))

    def test_s38_unset_empty_or_relative_ctr_config_dir_is_ignored(self):
        xdg = os.path.join(self.tmp, "xdg")
        want = os.path.join(xdg, "track-record", "config.json")
        for value in (None, "", "relative/dir"):
            with self.subTest(value=value):
                env = {"XDG_CONFIG_HOME": xdg}
                if value is not None:
                    env["CTR_CONFIG_DIR"] = value
                self.assertEqual(config.config_path(env), want)

    def test_s38_unset_empty_or_relative_xdg_falls_back_to_the_home_config(self):
        home = os.path.join(os.path.expanduser("~"), ".config", "track-record", "config.json")
        for value in (None, "", "relative/dir"):
            with self.subTest(value=value):
                env = {} if value is None else {"XDG_CONFIG_HOME": value}
                self.assertEqual(config.config_path(env), home)

    def test_s38_the_config_is_read_and_written_only_where_ctr_config_dir_says(self):
        other = os.path.join(self.tmp, "xdg")
        env = dict(self.env, XDG_CONFIG_HOME=other)
        config.write_config(FOLDER, env)
        self.assertEqual(config.read_config(env)[1], FOLDER)
        self.assertFalse(os.path.exists(other))
        self.assertEqual(os.listdir(self.env["CTR_CONFIG_DIR"]), ["config.json"])


BREAKAGES = [
    ("an unknown key", '{"config-version": 1, "recrod-folder": "/a"}', "unknown key recrod-folder"),
    ("an unknown key beside the real two",
     '{"config-version": 1, "record-folder": "/a", "extra": 1}', "unknown key extra"),
    ("a repeated key", '{"config-version": 1, "record-folder": "/a", "record-folder": "/b"}',
     "repeated key record-folder"),
    ("version 2", '{"config-version": 2, "record-folder": "/a"}',
     "config-version is from a newer version"),
    ("version 0", '{"config-version": 0, "record-folder": "/a"}',
     "config-version must be the whole number 1"),
    ("version 1.0", '{"config-version": 1.0, "record-folder": "/a"}',
     "config-version must be the whole number 1"),
    ("version true", '{"config-version": true, "record-folder": "/a"}',
     "config-version must be the whole number 1"),
    ("version as text", '{"config-version": "1", "record-folder": "/a"}',
     "config-version must be the whole number 1"),
    ("no version", '{"record-folder": "/a"}', "config-version is missing"),
    ("no folder", '{"config-version": 1}', "record-folder is missing"),
    ("a relative folder", '{"config-version": 1, "record-folder": "career-record"}',
     "record-folder must be an absolute path"),
    ("an empty folder", '{"config-version": 1, "record-folder": ""}',
     "record-folder must be an absolute path"),
    ("a non-string folder", '{"config-version": 1, "record-folder": 7}',
     "record-folder must be a string"),
    ("a null folder", '{"config-version": 1, "record-folder": null}',
     "record-folder must be a string"),
    ("a NUL in the folder", '{"config-version": 1, "record-folder": "/a\\u0000b"}',
     "record-folder is not a usable path"),
    ("not JSON", "config-version = 1", "cannot read config"),
    ("empty", "", "cannot read config"),
    ("a trailing comma", '{"config-version": 1, "record-folder": "/a",}', "cannot read config"),
    ("NaN", '{"config-version": NaN, "record-folder": "/a"}', "cannot read config"),
    ("a list", "[1]", "the config is not one JSON object"),
    ("a bare number", "1", "the config is not one JSON object"),
    ("deep nesting", "[" * 100000, "cannot read config"),
]


class ReadingCase(Temp):
    def test_no_file_is_not_an_error(self):
        path, folder = config.read_config(self.env)
        self.assertEqual(path, os.path.join(self.tmp, "cfg", "config.json"))
        self.assertIsNone(folder)

    def test_a_config_folder_that_is_a_file_is_no_config(self):
        with open(os.path.join(self.tmp, "cfg"), "w") as handle:
            handle.write("x")
        self.assertIsNone(config.read_config(self.env)[1])

    def test_a_valid_config_gives_its_folder(self):
        self.put(valid_text())
        self.assertEqual(config.read_config(self.env)[1], FOLDER)

    def test_s12_a_percent_and_a_quote_are_read_as_written(self):
        odd = '/Users/example/100%s "quoted" and \'single\''
        self.put(valid_text(**{"record-folder": odd}))
        self.assertEqual(config.read_config(self.env)[1], odd)

    def test_s7_every_breakage_is_refused_with_its_reason(self):
        for name, text, reason in BREAKAGES:
            with self.subTest(name):
                self.put(text)
                with self.assertRaises(config.ConfigError) as caught:
                    config.read_config(self.env)
                self.assertEqual(caught.exception.reason, reason)

    def test_s7_a_file_that_is_not_utf8_is_refused(self):
        for name, data in (("a lone continuation byte", b'{"config-version": 1, '
                            b'"record-folder": "/a\xff"}'),
                           ("a byte order mark", b"\xef\xbb\xbf" + valid_text().encode()),
                           ("utf-16", valid_text().encode("utf-16"))):
            with self.subTest(name):
                self.put(data)
                with self.assertRaises(config.ConfigError) as caught:
                    config.read_config(self.env)
                self.assertEqual(caught.exception.reason, "cannot read config")

    def test_a_config_that_is_a_folder_cannot_be_read(self):
        os.makedirs(os.path.join(self.env["CTR_CONFIG_DIR"], "config.json"))
        with self.assertRaises(config.ConfigError) as caught:
            config.read_config(self.env)
        self.assertEqual(caught.exception.reason, "cannot read config")

    def test_a_huge_config_cannot_be_read(self):
        self.put(b" " * (config.MAX_BYTES + 1))
        with self.assertRaises(config.ConfigError) as caught:
            config.read_config(self.env)
        self.assertEqual(caught.exception.reason, "cannot read config")

    def test_a_key_with_control_characters_is_named_on_one_line(self):
        self.put('{"config-version": 1, "a\\nb\\u202e": 1}')
        with self.assertRaises(config.ConfigError) as caught:
            config.read_config(self.env)
        line = caught.exception.line()
        self.assertNotIn("\n", line)
        self.assertIn("unknown key a\\nb\\u202e", line)

    def test_the_line_ends_with_the_six_literal_characters(self):
        line = config.ConfigError("cannot read config").line()
        self.assertEqual(line, "cannot run: the track-record config is not usable "
                               "(cannot read config); run track-record setup --folder "
                               "<folder>")
        self.assertTrue(line.endswith("--folder <folder>"))

    def test_the_record_folder_must_be_a_folder_for_a_command(self):
        config.require_record_folder(self.tmp)
        for path in (os.path.join(self.tmp, "nowhere"), "/a\0b"):
            with self.subTest(path=path):
                with self.assertRaises(config.ConfigError) as caught:
                    config.require_record_folder(path)
                self.assertEqual(caught.exception.reason, "the record folder is missing")
        file_path = os.path.join(self.tmp, "file")
        with open(file_path, "w") as handle:
            handle.write("x")
        with self.assertRaises(config.ConfigError):
            config.require_record_folder(file_path)


class WritingCase(Temp):
    def mode(self, path):
        return stat.S_IMODE(os.stat(path).st_mode)

    def test_the_written_file_reads_back_and_leaves_no_temporary_file(self):
        path = config.write_config(FOLDER, self.env)
        self.assertEqual(os.listdir(os.path.dirname(path)), ["config.json"])
        self.assertEqual(config.read_config(self.env), (path, FOLDER))
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle),
                             {"config-version": 1, "record-folder": FOLDER})

    def test_s40_the_file_is_0600_as_new_and_as_a_replacement_whatever_the_umask(self):
        old = os.umask(0)
        self.addCleanup(os.umask, old)
        for mask in (0o022, 0o077, 0o000):
            with self.subTest(umask=oct(mask)):
                os.umask(mask)
                shutil_rm = os.path.join(self.env["CTR_CONFIG_DIR"], "config.json")
                if os.path.exists(shutil_rm):
                    os.unlink(shutil_rm)
                path = config.write_config(FOLDER, self.env)
                self.assertEqual(self.mode(path), 0o600)
                os.chmod(path, 0o644)
                config.write_config(FOLDER + "-two", self.env)
                self.assertEqual(self.mode(path), 0o600)

    def test_a_non_ascii_folder_is_written_and_read_back(self):
        folder = "/Users/example/récord"
        path = config.write_config(folder, self.env)
        self.assertEqual(config.read_config(self.env), (path, folder))

    def test_a_folder_with_a_lone_surrogate_still_round_trips(self):
        folder = "/Users/example/bad-" + chr(0xDCFF)
        path = config.write_config(folder, self.env)
        self.assertEqual(config.read_config(self.env), (path, folder))

    def test_the_config_folder_is_made_when_missing_and_may_be_deep(self):
        env = {"XDG_CONFIG_HOME": os.path.join(self.tmp, "a", "b")}
        path = config.write_config(FOLDER, env)
        self.assertEqual(path, os.path.join(self.tmp, "a", "b", "track-record", "config.json"))
        self.assertTrue(os.path.isfile(path))

    def test_a_failed_write_leaves_the_earlier_config_whole(self):
        path = config.write_config(FOLDER, self.env)
        with open(path, "rb") as handle:
            before = handle.read()
        folder = os.path.dirname(path)
        os.chmod(folder, 0o500)
        self.addCleanup(os.chmod, folder, 0o700)
        if os.access(folder, os.W_OK):
            self.skipTest("this account can write to a read-only folder")
        with self.assertRaises(config.ConfigWriteError):
            config.write_config(FOLDER + "-two", self.env)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), before)
        self.assertEqual(os.listdir(folder), ["config.json"])

    def test_a_config_folder_that_cannot_be_made_is_a_write_error(self):
        blocker = os.path.join(self.tmp, "file")
        with open(blocker, "w") as handle:
            handle.write("x")
        with self.assertRaises(config.ConfigWriteError):
            config.write_config(FOLDER, {"CTR_CONFIG_DIR": os.path.join(blocker, "sub")})


if __name__ == "__main__":
    unittest.main()
