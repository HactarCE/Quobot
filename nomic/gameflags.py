from dataclasses import asdict, dataclass
from typing import Optional

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
    logs_channel_id: Optional[int] = None

    def export(self) -> dict:
        return utils.sort_dict(asdict(self))


class GameFlagsManager(GameRepoManager):

    def load(self):
        db = self.get_db('flags')
        self.flags = GameFlags(**db or {})

    def save(self):
        db = self.get_db('flags')
        db.replace(self.flags.export())
        db.save()

    @property
    def logs_channel(self):
        return self.flags.logs_channel_id and self.guild.get_channel(self.flags.logs_channel_id)

    @logs_channel.setter
    def logs_channel(self, new_logs_channel):
        if new_logs_channel:
            self.flags.logs_channel_id = new_logs_channel.id
        else:
            self.flags.logs_channel_id = None
