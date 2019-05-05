import json
from os import makedirs, path, remove, rename
from tempfile import mkstemp
from datetime import datetime

from utils import l


DATA_DIR = path.join(path.dirname(path.realpath(__file__)), 'data')


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
        makedirs(path.dirname(fullpath))
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

    Read-only attributes:
    - name -- str
    - filepath -- str
    """

    def __init__(self, db_name: str, do_not_instantiate_directly: None):
        """Do not instantiate this class directly; use database.get_db()
        instead.
        """
        if do_not_instantiate_directly != 'ok':
            # I'm not sure whether TypeError is really the best choice here.
            raise TypeError("Do not instantiate DB object directly; use get_db() instead")
        self.name = db_name
        self.filepath = path.join(DATA_DIR, db_name + '.json')
        self.reload()

    def reload(self) -> None:
        self.clear()
        self.update(load_data(self.filepath))

    def save(self) -> None:
        save_data(self.filepath, self)


def get_db(db_name: str) -> DB:
    if db_name not in _DATABASES:
        _DATABASES[db_name] = DB(db_name, 'ok')
    return _DATABASES[db_name]
