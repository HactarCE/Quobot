from dataclasses import asdict, dataclass
from typing import Dict, Optional

from .base import BaseGame
import utils


@dataclass
class GameFlags:
    """A dataclass tracking several variations on bot behavior."""

    allow_vote_abstain: bool = False
    allow_vote_change: bool = True
    allow_vote_multi: bool = False
    player_activity_cutoff: int = 24

    def export(self) -> dict:
        return utils.sort_dict(asdict(self))


class GameFlagManager(BaseGame):

    def init_data(self, data: Optional[Dict]):
        self.flags = GameFlags(**data or {})

    def export(self) -> dict:
        return self.flags.export()
