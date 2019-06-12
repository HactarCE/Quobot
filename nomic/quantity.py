from collections import OrderedDict
from dataclasses import dataclass, field
from typing import List, Optional, Union
import discord
import functools
import re

from .base import BaseGame
from .playerdict import PlayerDict
import utils


@dataclass
class _Quantity:
    game: object  # We can't access nomic.game.Game from here.
    name: str
    aliases: List[str] = field(default_factory=list)
    players: PlayerDict = None


@functools.total_ordering
class Quantity(_Quantity):
    """A dataclass representing a game quantity, such as points.

    Attributes:
    - game
    - name -- string

    Optional attributes:
    - aliases (default []) -- list of strings
    - players (default {}) -- PlayerDict
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.players = PlayerDict(self.game, self.players)

    def export(self) -> dict:
        return OrderedDict(
            name=self.name,
            aliases=sorted(self.aliases),
            players=self.players.export(),
        )

    def rename(self, new_name: str):
        self.game.rename_quantity(self, new_name)

    def set_aliases(self, new_aliases: List[str]):
        self.game.set_quantity_aliases(self, new_aliases)

    def set(self, player: discord.Member, value: Union[int, float]):
        if int(value) == value:
            value = int(value)
        if value == 0:
            del self.players[player]
        else:
            self.players[player] = value

    def get(self, player: discord.Member):
        return self.players.get(player, 0)

    def __lt__(self, other):
        return self.name < other.name

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        # This isn't ideal, but it should have all the necessary properties of a
        # __hash__().
        return id(self)


class QuantityManager(BaseGame):

    def init_data(self, quantity_data: Optional[dict]):
        self.quantities = {}
        if quantity_data:
            for name, quantity in quantity_data.items():
                self.quantities[name] = Quantity(game=self, **quantity)

    def export(self) -> dict:
        return utils.sort_dict({k: q.export() for k, q in self.quantities.items()})

    def add_quantity(self, quantity_name: str, aliases: List[str]):
        """Create a new game quantity.

        May throw `ValueError` if name or aliases are invalid.
        """
        self.assert_locked()
        quantity_name = quantity_name.lower()
        aliases = [s.lower() for s in aliases]
        for name in [quantity_name] + aliases:
            self._check_quantity_name(name)
        self.quantities[quantity_name] = Quantity(
            game=self,
            name=quantity_name,
            aliases=aliases,
        )
        self.need_save()

    def rename_quantity(self, quantity: Quantity, new_name: str):
        self.assert_locked()
        new_name = new_name.lower()
        self._check_quantity_name(new_name, ignore=quantity)
        if new_name in quantity.aliases:
            quantity.aliases.remove(new_name)
        del self.quantities[quantity.name]
        quantity.name = new_name
        self.quantities[quantity.name] = quantity
        self.need_save()

    def remove_quantity(self, quantity: Quantity):
        self.assert_locked()
        del self.quantities[quantity.name]
        self.need_save()

    def set_quantity_aliases(self, quantity: Quantity, new_aliases: List[str]):
        self.assert_locked()
        for name in new_aliases:
            self._check_quantity_name(name, ignore=quantity)
        quantity.aliases = new_aliases
        self.need_save()

    def get_quantity(self, name: str) -> Optional[Quantity]:
        name = name.lower()
        if name in self.quantities:
            return self.quantities[name]
        for quantity in self.quantities.values():
            if name in quantity.aliases:
                return quantity

    def _check_quantity_name(self, name: str, *, ignore: Optional[Quantity] = None):
        # TODO: this is duplicated in cogs.quantities
        if len(name) > 32:
            raise ValueError(f"Quantity name {name!r} is too long")
        if not re.match(r'[a-z][0-9a-z\-_]+', name):
            raise ValueError(f"Quantity name {name!r} is invalid; quantity names and aliases may only contain lowercase letters, numbers, hyphens, or underscores, and must begin with a lowercase letter")
        if not (ignore and name in ignore.aliases):
            if self.get_quantity(name):
                raise ValueError(f"Quantity name {name!r} is already in use")

    async def log_quantity_add(self, quantity: Quantity, player: discord.Member):
        self.assert_locked()
        # TODO: log it!

    async def log_quantity_remove(self, quantity: Quantity, player: discord.Member):
        self.assert_locked()
        # TODO: log it!

    async def log_quantity_rename(self,
                                  quantity: Quantity,
                                  player: discord.Member,
                                  old_name: str,
                                  new_name: str):
        self.assert_locked()
        # TODO: log it!

    async def log_quantity_change_aliases(self,
                                          quantity: Quantity,
                                          player: discord.Member,
                                          old_aliases: List[str],
                                          new_aliases: List[str]):
        self.assert_locked()
        # TODO: log it!

    async def log_quantity_set_value(self,
                                     quantity: Quantity,
                                     agent: discord.Member,
                                     player: discord.Member,
                                     old_value: int,
                                     new_value: int):
        self.assert_locked()
        # TODO: log it!
