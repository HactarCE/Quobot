import json
from os import mkdirs, path, remove, rename
from tempfile import mkstemp
from datetime import datetime

from utils import l, LOG_SEP


DATA_DIR = path.join(path.dirname(path.realpath(__file__)), 'data')

TOKEN_FILE_PATH = path.join(DATA_DIR, 'token.txt')


def get_token() -> str:
    with open(TOKEN_FILE_PATH, 'r') as f:
        return f.read().strip()


def load_data(filename: str) -> dict:
    fullpath = path.join(DATA_DIR, filename)
    try:
        with open(fullpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        l.info(f"Loaded data file {filename}")
        return data
    except Exception:
        msg = f"Error loading {filename};"
        try:
            rename(fullpath, f'{path.basename(fullpath)}.{int(datetime.now().timestamp())}.bak')
            msg += f" backing up existing file and"
        except Exception:
            pass
        msg += " assuming empty dictionary"
        l.warning(msg)
        return {}


def save_data(filename: str, data: dict) -> None:
    # Use a temporary file so that the original one doesn't get corrupted in the
    # case of an error.
    fullpath = path.join(DATA_DIR, filename)
    try:
        mkdirs(path.dirname(fullpath))
        tempfile, tempfile_path = mkstemp(dir=DATA_DIR)
        with open(tempfile, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent='\t')
        rename(tempfile_path, path.join(DATA_DIR, filename))
    except Exception:
        l.warning(f"Error saving {filename}")
    finally:
        try:
            remove(tempfile_path)
        except Exception:
            pass


_DATABASES = {}


class DB(dict):
    """A simple subclass of dict implementing JSON save/load.

    Do not instantiate this class directly; use database.get_db() instead.
    """

    def __init__(self, db_name: str, do_not_instantiate_directly: None):
        """Do not instantiate this class directly; use database.get_db()
        instead.
        """
        self.filename = path.join(DATA_DIR, db_name + '.json')
        self.reload()

    def reload(self) -> None:
        self.clear()
        self.update(load_data(self.filename))

    def save(self) -> None:
        save_data(self.filename, self)


def get_db(db_name: str) -> DB:
    if db_name not in _DATABASES:
        _DATABASES[db_name] = DB(db_name, None)
    return _DATABASES[db_name]
