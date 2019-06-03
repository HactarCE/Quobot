import discord

from utils import l
import utils


class PlayerDict(dict):
    """A dict subclass for managing a dictionary of Discord members."""

    def __init__(self, member_getter, member_values=None):
        """Instantiate a PlayerDict.

        Arguments:
        - member_getter -- any object with a get_member() method (e.g. an
          instance of discord.Guild)

        Optional arguments:
        - member_values -- dict mapping discord.abc.Users or user IDs to any
          other value
        """
        self.get_member = member_getter.get_member
        if not member_values:
            member_values = {}
        for k, v in member_values.items():
            self[k] = v

    def _to_member(self, m):
        if isinstance(m, discord.Member):
            return m
        if isinstance(m, discord.abc.User):
            return self.get_member(m.id)
        try:
            return self.get_member(int(m))
        except TypeError:
            pass
        raise TypeError(f"{self.__class__.__name__} can only contain Member objects as keys, not {type(m)}: {m!r}")

    def __setitem__(self, key, value):
        key = self._to_member(key)
        if key:
            return super().__setitem__(key, value)
        else:
            l.warn(f"PlayerDict is unable to convert {key!r} to member; ignoring key-value pair {(key, value)!r}")

    def __getitem__(self, key):
        return super().__getitem__(self._to_member(key))

    def __delitem__(self, key):
        return super().__delitem__(self._to_member(key))

    def __contains__(self, key):
        try:
            return super().__contains__(self._to_member(key))
        except TypeError:
            return False

    def export(self):
        return utils.sort_dict({str(m.id): v for m, v in self.sorted_items()})

    def sorted_keys(self):
        return utils.discord.sort_users(self.keys())

    def sorted_items(self):
        return ((k, self[k]) for k in self.sorted_keys())
