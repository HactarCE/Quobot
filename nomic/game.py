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
        ActivityTracker.load(self)
        GameFlagManager.load(self)
        ProposalManager.load(self)
        QuantityManager.load(self)
        RuleManager.load(self)

    def save(self):
        self.assert_locked()
        ActivityTracker.save(self)
        GameFlagManager.save(self)
        ProposalManager.save(self)
        QuantityManager.save(self)
        RuleManager.save(self)
