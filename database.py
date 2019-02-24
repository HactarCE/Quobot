import json
from os import path

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
        l.info(f"Successfully loaded {filename}.")
        # l.info(LOG_SEP)
        return data
    except:
        l.warning(f"There was an error loading {filename}.")
        # l.info(LOG_SEP)
        return {}


def save_data(filename, data):
    with open(path.join(DATA_DIR, filename), 'w', encoding='utf-8') as f:
        json.dump(data, f)


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
            print(f"Unable to load {self.filename}; silently ignoring.")

    def reload(self):
        self.clear()
        self.update(load_data(self.filename))

    def save(self):
        save_data(self.filename, self)
