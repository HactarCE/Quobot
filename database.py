import json
from os import path

DATA_DIR = path.join(path.dirname(path.realpath(__file__)), 'data')


def load_data(filename):
    try:
        with open(path.join(DATA_DIR, filename), 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Successfully loaded {filename}.")
        print('-' * 10)
        return data
    except:
        print(f"There was an error loading {filename}.")
        print('-' * 10)
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
        self.reload()

    def reload(self):
        self.clear()
        self.update(load_data(self.filename))

    def save(self):
        save_data(self.filename, self)
