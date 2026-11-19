"""The track-record config: where it lives, how it is read strictly, how it is written.

The config is one small JSON file that names the record folder. This module owns its
location, its reading (every breakage is a ConfigError with one-line reason words) and its
atomic write. It reads and writes nothing else."""

import json
import os
import tempfile

from career_track_record.barred import printed_path

CONFIG_VERSION = 1
KEYS = ("config-version", "record-folder")
MAX_BYTES = 1 << 20
_FIX = "run track-record setup --folder <folder>"


class ConfigError(Exception):
    """The config exists and is not usable. ``reason`` is one line of plain words."""

    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason

    def line(self):
        """The whole 'cannot run' line for a command other than setup (the closing
        ``<folder>`` is eight literal characters, never a path)."""
        return "cannot run: the track-record config is not usable (%s); %s" % (
            self.reason, _FIX)


class ConfigWriteError(Exception):
    """The config could not be written."""


def _usable(value):
    return isinstance(value, str) and value != ""


def _from(environ, name):
    value = (environ if environ is not None else os.environ).get(name)
    if _usable(value) and os.path.isabs(value) and "\0" not in value:
        return value
    return None


def config_path(environ=None):
    """The config file's path: CTR_CONFIG_DIR/config.json, else
    XDG_CONFIG_HOME/track-record/config.json, else ~/.config/track-record/config.json."""
    direct = _from(environ, "CTR_CONFIG_DIR")
    if direct is not None:
        return os.path.join(direct, "config.json")
    xdg = _from(environ, "XDG_CONFIG_HOME")
    if xdg is not None:
        return os.path.join(xdg, "track-record", "config.json")
    return os.path.join(os.path.expanduser("~"), ".config", "track-record", "config.json")


class _Repeated(Exception):
    def __init__(self, key):
        Exception.__init__(self, key)
        self.key = key


def _pairs(pairs):
    seen = set()
    for key, _value in pairs:
        if key in seen:
            raise _Repeated(key)
        seen.add(key)
    return dict(pairs)


def _refuse_constant(_name):
    raise ValueError("not a JSON value")


def parse(data):
    """The record folder from the bytes of a config. Raises ConfigError."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ConfigError("cannot read config")
    try:
        found = json.loads(text, object_pairs_hook=_pairs, parse_constant=_refuse_constant)
    except _Repeated as exc:
        raise ConfigError("repeated key %s" % printed_path(exc.key))
    except (ValueError, RecursionError):
        raise ConfigError("cannot read config")
    if not isinstance(found, dict):
        raise ConfigError("the config is not one JSON object")
    for key in found:
        if key not in KEYS:
            raise ConfigError("unknown key %s" % printed_path(key))
    if "config-version" not in found:
        raise ConfigError("config-version is missing")
    version = found["config-version"]
    if type(version) is not int:
        raise ConfigError("config-version must be the whole number 1")
    if version > CONFIG_VERSION:
        raise ConfigError("config-version is from a newer version")
    if version != CONFIG_VERSION:
        raise ConfigError("config-version must be the whole number 1")
    if "record-folder" not in found:
        raise ConfigError("record-folder is missing")
    folder = found["record-folder"]
    if not isinstance(folder, str):
        raise ConfigError("record-folder must be a string")
    if not os.path.isabs(folder):
        raise ConfigError("record-folder must be an absolute path")
    if "\0" in folder:
        raise ConfigError("record-folder is not a usable path")
    return folder


def read_config(environ=None):
    """(path, folder). ``folder`` is None when there is no config file; a config that
    exists and is not usable raises ConfigError."""
    path = config_path(environ)
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_BYTES + 1)
    except (FileNotFoundError, NotADirectoryError):
        return path, None
    except (OSError, ValueError):
        raise ConfigError("cannot read config")
    if len(data) > MAX_BYTES:
        raise ConfigError("cannot read config")
    return path, parse(data)


def require_record_folder(folder):
    """Raise ConfigError unless the record folder the config names is a folder."""
    try:
        present = os.path.isdir(folder)
    except (OSError, ValueError):
        present = False
    if not present:
        raise ConfigError("the record folder is missing")


class Defaults:
    """The config's defaults: every input's path is the record folder joined to a fixed
    name. ``config_file`` is the config's path, for the ``using`` line."""

    def __init__(self, config_file, folder):
        self.config_file = config_file
        self.folder = folder

    def path(self, name):
        return os.path.join(self.folder, name)

    def using(self, name):
        """The one standard-error line a command writes for a path it took from the config."""
        return "using %s (from config %s)" % (printed_path(self.path(name)),
                                              printed_path(self.config_file))


def load_defaults(environ=None):
    """The Defaults of a valid config whose record folder is there, or None when there is no
    config file. Raises ConfigError for a config that is not usable and for a record folder
    that is missing. Called only when a command needs a default, so a command given every
    path never reads the config."""
    config_file, folder = read_config(environ)
    if folder is None:
        return None
    require_record_folder(folder)
    return Defaults(config_file, folder)


def _encoded(folder):
    record = {"config-version": CONFIG_VERSION, "record-folder": folder}
    try:
        text = json.dumps(record, indent=2, ensure_ascii=False)
        return (text + "\n").encode("utf-8")
    except UnicodeEncodeError:
        return (json.dumps(record, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def write_config(folder, environ=None):
    """Write the whole config to a temporary file in the config folder, then rename it over
    the config. The file is mode 0600 whatever the umask. Raises ConfigWriteError."""
    path = config_path(environ)
    directory = os.path.dirname(path)
    temp = None
    try:
        os.makedirs(directory, exist_ok=True)
        descriptor, temp = tempfile.mkstemp(dir=directory, prefix=".config-", suffix=".tmp")
        try:
            os.fchmod(descriptor, 0o600)
            view = memoryview(_encoded(folder))
            while len(view):
                view = view[os.write(descriptor, view):]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temp, path)
        temp = None
    except (OSError, ValueError):
        raise ConfigWriteError("cannot write the config")
    finally:
        if temp is not None:
            try:
                os.unlink(temp)
            except OSError:
                pass
    return path
