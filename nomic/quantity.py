from collections import OrderedDict
from dataclasses import dataclass, field
from typing import List

from .playerdict import PlayerDict


@dataclass
class _Quantity:
    game: object  # We can't access nomic.game.Game from here.
    name: str
    aliases: List[str] = field(default_factory=list)
    players: PlayerDict = None


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

    def set(self, player, value):
        if int(value) == value:
            value = int(value)
        if value == 0:
            del self.players[player]
        else:
            self.players[player] = value

    def get(self, player):
        return self.players.get(player, 0)

    def export(self) -> dict:
        return OrderedDict(
            name=self.name,
            aliases=self.aliases,
            players=self.players.export(),
        )
