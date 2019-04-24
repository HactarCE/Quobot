from dataclasses import dataclass


@dataclass
class GameFlags:
    """A dataclass tracking several variations on bot mechanics."""

    allow_vote_abstain: bool = False
    allow_vote_change: bool = True
    allow_vote_multi: bool = False
    player_activity_cutoff: int = 24 * 60 * 60

    def export(self) -> dict:
        return self._asdict()
