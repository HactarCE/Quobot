import json
from os import path, remove, rename
from tempfile import mkstemp
from datetime import datetime

from utils import l, LOG_SEP

DATA_DIR = path.join(path.dirname(path.realpath(__file__)), 'data')

TOKEN_FILE_PATH = path.join(DATA_DIR, 'token.txt')


def get_token():
    with open(TOKEN_FILE_PATH, 'r') as f:
        return f.read().strip()


def load_data(filename):
    try:
        with open(path.join(DATA_DIR, filename), 'r', encoding='utf-8') as f:
            data = json.load(f)
        l.info(f"Loaded data file {filename}")
        return data
    except:
        l.warning(f"There was an error loading {filename}; backing up file and assuming empty dictionary")
        rename(filename, f'{filename}.{int(datetime.now().timestamp())}.bak')
        return {}


def save_data(filename, data):
    # Use a temporary file so that the original one doesn't get corrupted in the
    # case of an error.
    try:
        tempfile, tempfile_path = mkstemp(dir=DATA_DIR)
        with open(tempfile, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        rename(tempfile_path, path.join(DATA_DIR, filename))
    finally:
        try:
            remove(tempfile_path)
        except:
            pass
    # with open(path.join(DATA_DIR, filename), 'w', encoding='utf-8') as f:
    #     json.dump(data, f)


databases = {}

def get_db(db_name):
    if db_name not in databases:
        databases[db_name] = DB(db_name)
    return databases[db_name]


class DB(dict):
    """A simple subclass of dict implementing JSON save/load."""
    def __init__(self, db_name):
        self.filename = path.join(DATA_DIR, db_name + '.json')
        try:
            self.reload()
        except:
            l.warning(f"There was an error loading {self.filename}; silently ignoring")

    def reload(self):
        self.clear()
        self.update(load_data(self.filename))

    def save(self):
        save_data(self.filename, self)
