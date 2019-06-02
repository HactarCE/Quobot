from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import discord

from .playerdict import PlayerDict
from constants import colors, strings
import utils


class ProposalStatus(Enum):
    VOTING = 'voting'
    PASSED = 'passed'
    FAILED = 'failed'
    DELETED = 'deleted'


VOTE_TYPES = ('for', 'against', 'abstain')


@dataclass
class _Proposal:
    game: object  # We can't access nomic.game.Game from here.
    n: int
    author: discord.User
    content: str
    status: ProposalStatus = ProposalStatus.VOTING
    message_id: Optional[int] = None
    votes: PlayerDict = None
    timestamp: int = None


class Proposal(_Proposal):
    """A dataclass representing a Nomic proposal.

    Attributes:
    - game
    - n -- integer; proposal ID number
    - author -- discord.User
    - content -- string

    Optional attributes:
    - status (default Proposal.Status.Voting)
    - message_id (default None) -- discord.Message or the ID of one (converted
      to integer ID)
    - votes (default {}) -- PlayerDict of ints; positive numbers are votes
      for, negative numbers are votes against, and zero is an abstention
    - timestamp (default now)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not isinstance(self.author, discord.User):
            self.author = self.game.get_member(self.author)
        # if isinstance(self.message_id, discord.Message):
        #     self.message_id = self.message_id.id
        self.votes = PlayerDict(self.game, self.votes)
        if self.timestamp is None:
            self.timestamp = utils.now()

    def export(self) -> dict:
        return OrderedDict(
            n=self.n,
            author=self.author.id,
            content=self.content,
            status=self.status.value,
            message_id=self.message_id,
            votes=self.votes.export(),
            timestamp=self.timestamp,
        )

    async def fetch_message(self) -> discord.Message:
        return await self.game.proposals_channel.fetch_message(self.message_id)

    @property
    def embed(self) -> discord.Embed:
        """Return an embed displaying this proposal."""
        # Make the title; e.g. "Proposal #10   --    Passed"
        title = f"Proposal #{self.n}"
        if self.status != ProposalStatus.VOTING:
            self.title += "   \N{EM DASH}   "
            self.title += self.status.value.capitalize()
        if self.status == ProposalStatus.DELETED:
            return utils.make_embed(
                color=colors.DELETED,
                title=title,
            )
        # Make an embed field for each type of vote
        field_titles = {k: k.capitalize() for k in VOTE_TYPES}
        field_lines = {k: '' for k in VOTE_TYPES}
        totals = {k: 0 for k in VOTE_TYPES}
        # Count the votes
        for player, vote_amount in self.votes.sorted_items():
            line = player.mention
            if vote_amount > 0:
                vote_type = 'for'
            elif vote_amount < 0:
                vote_type = 'against'
            else:
                vote_type = 'abstain'
            if abs(vote_amount) > 1:
                line += f" ({abs(vote_amount)}x)"
            totals[vote_type] += abs(vote_amount) or 1
            field_lines[vote_type] += line + '\n'
        for vote_type in VOTE_TYPES:
            field_lines[vote_type] or strings.EMPTY_LIST
            if totals:
                field_titles[vote_type] += f" ({totals[vote_type]})"
        # Make the fields
        fields = [(field_titles[k], field_lines[k], True) for k in VOTE_TYPES]
        timestamp_str = datetime.fromtimestamp(self.timestamp).strftime(utils.TIME_FORMAT)
        footer = f"Submitted at {timestamp_str} by {self.author.name}#{self.author.discriminator}"
        return utils.make_embed(
            color={
                ProposalStatus.VOTING: colors.INFO,
                ProposalStatus.PASSED: colors.SUCCESS,
                ProposalStatus.FAILED: colors.ERROR,
            }[self.status],
            title=title,
            description=self.content,
            fields=fields,
            footer_text=footer,
        )
