import json
from os import path

DATA_DIR = path.join(path.dirname(path.realpath(__file__)), 'data')


def load_data(filename):
    with open(path.join(DATA_DIR, filename), 'r', encoding='utf-8') as f:
        return json.load(f)


def save_data(filename, data):
    with open(path.join(DATA_DIR, filename), 'w', encoding='utf-8') as f:
        json.dump(f)


class DB(dict):
    """A simple subclass of dict implementing JSON save/load."""
    def __init__(self, db_name):
        self.filename = path.join(DATA_DIR, db_name + '.json')
        self.reload()

    def reload(self):
        self.clear()
        self.update(load_data(self.filename))

    def save(self):
        save_data(filename, self)
