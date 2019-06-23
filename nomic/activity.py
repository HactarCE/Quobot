from typing import Optional
import discord

from .playerdict import PlayerDict
from .repoman import GameRepoManager
import utils


class ActivityTracker(GameRepoManager):

    def load(self):
        db = self.get_db('player_activity')
        self.player_activity = PlayerDict(self, db)

    def save(self):
        db = self.get_db('player_activity')
        db.replace(self.player_activity.export())
        db.save()

    def record_activity(self, user: discord.Member) -> None:
        """Mark a player as being active right now."""
        self.assert_locked()
        self.player_activity[user] = utils.now()
        self.save()

    def get_activity_diff(self, user: discord.Member) -> Optional[int]:
        """Get the number of seconds since a player was last active, or None if
        they have never been active.
        """
        if user in self.player_activity:
            return utils.now() - self.player_activity[user]

    @property
    def activity_diffs(self) -> PlayerDict:
        """Get a PlayerDict of values returned by Game.get_activity_diff()."""
        return PlayerDict(self, {
            user: self.get_activity_diff(user) for user in self.player_activity
        })

    def is_active(self, user: discord.Member) -> bool:
        diff = self.get_activity_diff(user)
        seconds_cutoff = self.flags.player_activity_cutoff * 3600
        return diff is not None and diff <= seconds_cutoff

    def is_inactive(self, user: discord.Member) -> bool:
        return not self.is_active(user)
