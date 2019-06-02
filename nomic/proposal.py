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
        self.status = ProposalStatus(self.status)
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

    @property
    def votes_for(self) -> int:
        return sum(v for v in self.votes if v > 0)

    @property
    def votes_against(self) -> int:
        return -sum(v for v in self.votes if v < 0)

    @property
    def votes_abstain(self) -> int:
        return sum(v == 0 for v in self.votes)

    async def fetch_message(self) -> discord.Message:
        try:
            return await self.game.proposals_channel.fetch_message(self.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    @property
    def discord_link(self) -> str:
        return utils.discord.MESSAGE_LINK_FORMAT.format(
            guild=self.game.guild,
            channel=self.game.proposals_channel,
            message_id=self.message_id,
        )

    @property
    def embed(self) -> discord.Embed:
        """Return an embed displaying this proposal."""
        # Make the title; e.g. "Proposal #10   --    Passed"
        title = f"Proposal #{self.n}"
        if self.status != ProposalStatus.VOTING:
            self.title += "   \N{EM DASH}   "
            self.title += self.status.value.capitalize()
        if self.status == ProposalStatus.DELETED:
            return discord.Embed(
                color=colors.DELETED,
                title=title,
            )
        embed = discord.Embed(
            color={
                ProposalStatus.VOTING: colors.INFO,
                ProposalStatus.PASSED: colors.SUCCESS,
                ProposalStatus.FAILED: colors.ERROR,
            }[self.status],
            title=title,
            description=self.content,
            timestamp=datetime.fromtimestamp(self.timestamp),
        )
        # Make an embed field for each type of vote
        for vote_type in VOTE_TYPES:
            total = 0
            value = ''
            # Count the votes and list the users
            for player, vote_amount in self.votes.items():
                vote_amount = 0
                if vote_type == 'for' and vote_amount > 0:
                    pass
                elif vote_type == 'against' and vote_amount < 0:
                    vote_amount *= -1
                elif vote_type == 'abstain' and vote_amount == 0:
                    vote_amount = 1
                if vote_amount:
                    value += player.mention
                    if vote_amount > 1:
                        value += f" ({vote_amount}x)"
                    value += "\n"
                    total += vote_amount
            name = vote_type.capitalize()
            if total:
                name += f" ({total})"
            if vote_type == 'abstain' and total == 0:
                continue
            embed.add_field(
                name=name,
                value=value or strings.EMPTY_LIST,
                inline=True,
            )
        # Set the footer
        embed.set_footer(**utils.discord.embed_happened_footer("Submitted", self.author))
        return embed
