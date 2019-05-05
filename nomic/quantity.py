from dataclasses import dataclass
from typing import List

from .playerdict import PlayerDict


@dataclass
class _Quantity:
    game: object  # We can't access nomic.game.Game from here.
    name: str
    aliases: List[str]
    players: PlayerDict = None


class Quantity(_Quantity):
    """A dataclass representing a game quantity, such as points.

    Attributes:
    - game
    - name -- string

    Optional attributes:
    - aliases -- list of strings
    - players (default {}) -- PlayerDict
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.players = PlayerDict(self.game, self.players)

    # TODO __repr__ and __str__
