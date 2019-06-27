from .activity import ActivityTracker
from .gameflags import GameFlagsManager
from .proposal import ProposalManager
from .quantity import QuantityManager
from .rule import RuleManager


class Game(
    ActivityTracker,
    GameFlagsManager,
    ProposalManager,
    QuantityManager,
    RuleManager,
):
    """A Nomic game, including proposals, rules, etc."""

    def load(self):
        self.assert_locked()
        ActivityTracker.load(self)
        GameFlagsManager.load(self)
        ProposalManager.load(self)
        QuantityManager.load(self)
        RuleManager.load(self)

    def save(self):
        self.assert_locked()
        ActivityTracker.save(self)
        GameFlagsManager.save(self)
        ProposalManager.save(self)
        QuantityManager.save(self)
        RuleManager.save(self)
