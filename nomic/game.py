from collections import OrderedDict

from database import get_db
from utils import mutget
from .activity import ActivityTracker
from .gameflags import GameFlagManager
from .proposal import ProposalManager
from .quantity import QuantityManager
from .rule import RuleManager


class Game(
    ActivityTracker,
    ProposalManager,
    QuantityManager,
    RuleManager,
):
    """A Nomic game, including proposals, rules, etc."""

    def load_guild_data(self):
        self.db = get_db('guild_' + str(self.guild.id))
        ActivityTracker.init_data(self, self.db.get('player_activity'))
        GameFlagManager.init_data(self, self.db.get('flags'))
        ProposalManager.init_data(self, self.db.get('proposals'))
        QuantityManager.init_data(self, self.db.get('quantities'))
        RuleManager.init_data(self, self.db.get('rules'))
        channels = mutget(self.db, 'channels', {})
        self.proposals_channel  = self.guild.get_channel(channels.get('proposals'))
        self.rules_channel      = self.guild.get_channel(channels.get('rules'))

    async def save(self) -> None:
        self.assert_locked()
        self.db.clear()
        self.db.update(self.export())
        self.db.save()

    def export(self) -> dict:
        return OrderedDict(
            channels=OrderedDict(
                proposals=self.proposals_channel and self.proposals_channel.id,
                rules=self.rules_channel and self.rules_channel.id,
            ),
            flags=GameFlagManager.export(self),
            player_activity=ActivityTracker.export(self),
            proposals=ProposalManager.export(self),
            quantities=QuantityManager.export(self),
            rules=RuleManager.export(self),
        )
