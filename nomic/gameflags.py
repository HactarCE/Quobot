from dataclasses import asdict, dataclass

from .repoman import GameRepoManager
import utils


@dataclass
class GameFlags:
    """A dataclass tracking several variations on bot behavior."""

    allow_vote_abstain: bool = False
    allow_vote_change: bool = True
    allow_vote_multi: bool = False
    auto_upload: bool = True
    player_activity_cutoff: int = 24

    def export(self) -> dict:
        return utils.sort_dict(asdict(self))


class GameFlagManager(GameRepoManager):

    def load(self):
        db = self.get_db('flags')
        self.flags = GameFlags(**db or {})

    def save(self):
        db = self.get_db('flags')
        db.replace(self.flags.export())
        db.save()
