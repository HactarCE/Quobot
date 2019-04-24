import discord

import utils


class PlayerDict(dict):
    """A dict subclass for managing a dictionary of Discord members."""

    def __init__(self, member_getter, member_values=None):
        """Instantiate a PlayerDict.

        Arguments:
        - member_getter -- any object with a get_member() method (e.g. an
          instance of discord.Guild)

        Optional arguments:
        - member_values -- dict mapping discord.Users or user IDs to any other
          value
        """
        self.get_member = member_getter.get_member
        if not member_values:
            member_values = {}
        super().__init__(**{self._to_member(m): v for m, v in member_values})
        if None in self:
            del self[None]

    def _to_member(self, m):
        if isinstance(m, discord.User):
            return m
        else:
            return self.get_member(int(m))

    def __setitem__(self, key, value):
        return super()

    def export(self):
        return {str(m.id): v for m, v in self}

    def sorted_keys(self):
        return utils.sort_users(self.keys(), self.member_getter)

    def sorted_items(self):
        return ((k, self[k]) for k in self.sorted_keys())
