from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Set
import discord
import functools

from .gameflags import GameFlagManager
from .playerdict import PlayerDict
from constants import colors, emoji, strings
import utils


class ProposalStatus(Enum):
    VOTING = 'voting'
    PASSED = 'passed'
    FAILED = 'failed'
    DELETED = 'deleted'


VOTE_ALIASES = {
    '+': 'for',
    '-': 'against',
    'abstain': 'abstain',
    'against': 'against',
    'del': 'remove',
    'delete': 'remove',
    'for': 'for',
    'remove': 'remove',
    'rm': 'remove',
}

VOTE_TYPES = ('for', 'against', 'abstain')


@dataclass
class _Proposal:
    game: 'ProposalManager' and GameFlagManager
    n: int
    author: discord.Member
    content: str
    status: ProposalStatus = ProposalStatus.VOTING
    message_id: Optional[int] = None
    votes: PlayerDict = None
    timestamp: int = None


@functools.total_ordering
class Proposal(_Proposal):
    """A dataclass representing a Nomic proposal.

    Attributes:
    - game
    - n -- integer; proposal ID number
    - author -- discord.Member
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
        if not isinstance(self.author, discord.Member):
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

    async def set_vote(self, player: discord.Member, new_vote_amount: int):
        self.game.assert_locked()
        if self.status != ProposalStatus.VOTING:
            return False
        if new_vote_amount == 0 and not self.game.flags.allow_vote_abstain:
            new_vote_amount = None
        if player in self.votes and not self.game.flags.allow_vote_change:
            return False
        if new_vote_amount and abs(new_vote_amount) > 1 and not self.game.flags.allow_vote_multi:
            new_vote_amount //= abs(new_vote_amount)
        self.votes[player] = new_vote_amount
        if new_vote_amount is None:
            del self.votes[player]
        await self.refresh()
        self.game.need_save()
        return True

    async def vote_for(self, player: discord.Member, amount: int = 1):
        old_vote_amount = self.votes.get(player)
        if old_vote_amount is None:
            new_vote_amount = amount
        elif old_vote_amount < 0:
            new_vote_amount = None
        else:
            new_vote_amount = old_vote_amount + amount
        return await self.set_vote(player, new_vote_amount)

    async def vote_against(self, player: discord.Member, amount: int = 1):
        old_vote_amount = self.votes.get(player)
        if old_vote_amount is None:
            new_vote_amount = -amount
        elif old_vote_amount > 0:
            new_vote_amount = None
        else:
            new_vote_amount = old_vote_amount - amount
        return await self.set_vote(player, new_vote_amount)

    async def vote_abstain(self, player: discord.Member):
        old_vote_amount = self.votes.get(player)
        if old_vote_amount == 0:
            new_vote_amount = None
        else:
            new_vote_amount = 0
        return await self.set_vote(player, new_vote_amount)

    async def vote_abstain_or_remove(self, player: discord.Member):
        old_vote_amount = self.votes.get(player)
        if old_vote_amount is None:
            new_vote_amount = 0
        else:
            new_vote_amount = None
        return await self.set_vote(player, new_vote_amount)

    async def vote_remove(self, player: discord.Member):
        return await self.set_vote(player, None)

    @property
    def votes_for(self) -> int:
        return sum(v for v in self.votes.values() if v > 0)

    @property
    def votes_against(self) -> int:
        return -sum(v for v in self.votes.values() if v < 0)

    @property
    def votes_abstain(self) -> int:
        return sum(v == 0 for v in self.votes.values())

    async def set_status(self, new_status: ProposalStatus):
        self.game.assert_locked()
        self.status = new_status
        await self.refresh()
        self.game.need_save()

    async def set_content(self, new_content: str):
        self.game.assert_locked()
        self.content = new_content
        await self.refresh()
        self.game.need_save()

    async def refresh(self):
        await self.game.refresh_proposal(self)

    async def repost(self):
        await self.game.repost_proposal(self)

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
            title += "   \N{EM DASH}   "
            title += self.status.value.capitalize()
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
                if vote_type == 'for':
                    if vote_amount <= 0:
                        continue
                elif vote_type == 'against':
                    if vote_amount >= 0:
                        continue
                    vote_amount *= -1
                elif vote_type == 'abstain':
                    if vote_amount != 0:
                        continue
                    vote_amount = 1
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

    def __lt__(self, other):
        return self.n < other.n

    def __eq__(self, other):
        return self.n == other.n

    def __hash__(self):
        # None of these values should ever change, and they should uniquely
        # identify this proposal.
        return hash((self.game.guild.id, self.n, self.timestamp))


class ProposalManager(GameFlagManager):

    def init_data(self, proposal_data: Optional[List]):
        self.proposals = []
        if proposal_data:
            for proposal in proposal_data:
                self.proposals.append(Proposal(game=self, **proposal))

    def export(self):
        return [p.export() for p in self.proposals]

    async def refresh_proposal(self, *proposals: Proposal):
        """Update the messages for one or more proposals.

        May throw `TypeError`, `ValueError`, or `discord.Forbidden` exceptions.
        """
        self.assert_locked()
        for proposal in sorted(set(proposals)):
            try:
                m = await proposal.fetch_message()
                await m.clear_reactions()
                await m.edit(embed=proposal.embed)
                if proposal.status == ProposalStatus.VOTING:
                    await m.add_reaction(emoji.VOTE_FOR)
                    await m.add_reaction(emoji.VOTE_AGAINST)
                    await m.add_reaction(emoji.VOTE_ABSTAIN)
            except discord.NotFound:
                await self.repost_proposal(proposal)
                return

    async def repost_proposal(self, *proposals: Proposal):
        """Remove and repost the messages for one or more proposals.

        May throw `TypeError`, `ValueError`, or `discord.Forbidden` exceptions.
        """
        self.assert_locked()
        proposal_range = range(min(proposals).n, len(self.proposals) + 1)
        proposals = list(map(self.get_proposal, proposal_range))
        proposal_messages = []
        for proposal in proposals:
            m = await proposal.fetch_message()
            if m:
                proposal_messages.append(m)
        if proposal_messages:
            await utils.discord.safe_bulk_delete(proposal_messages)
        for proposal in proposals:
            m = await self.proposals_channel.send(embed=discord.Embed(
                color=colors.TEMPORARY,
                title=f"Preparing proposal #{proposal.n}\N{HORIZONTAL ELLIPSIS}",
            ))
            proposal.message_id = m.id
        self.need_save()
        await self.refresh_proposal(*proposals)

    def has_proposal(self, n: int) -> bool:
        return isinstance(n, int) and 1 <= n <= len(self.proposals)

    def get_proposal(self, n: int) -> Optional[Proposal]:
        if self.has_proposal(n):
            return self.proposals[n - 1]

    async def get_proposal_messages(self) -> Set[discord.Message]:
        messages = set()
        for proposal in self.proposals:
            messages.add(await proposal.fetch_message())
        return messages

    async def add_proposal(self, **kwargs):
        self.assert_locked()
        n = len(self.proposals) + 1
        new_proposal = Proposal(game=self, n=n, **kwargs)
        self.proposals.append(new_proposal)
        # ProposalManager.repost_proposal() calls BaseGame.need_save() so we
        # don't have to do that here.
        await self.repost_proposal(new_proposal)
        return new_proposal

    async def permadel_proposal(self, proposal: Proposal):
        self.assert_locked()
        if not proposal.n == len(self.proposals):
            raise RuntimeError("Cannot delete any proposal other than the last one")
        del self.proposals[proposal.n - 1]
        self.need_save()
        await (await proposal.fetch_message()).delete()

    async def log_proposal_add(self, proposal: Proposal):
        self.assert_locked()
        # TODO: log it!

    async def log_proposal_permadel(self, proposal: Proposal):
        self.assert_locked()
        # TODO: log it!

    async def log_proposal_change_status(self,
                                         proposal: Proposal,
                                         player: discord.Member,
                                         old_status: ProposalStatus,
                                         new_status: ProposalStatus):
        self.assert_locked()
        # TODO: log it!

    async def log_proposal_change_content(self,
                                          proposal: Proposal,
                                          player: discord.Member,
                                          old_content: str,
                                          new_content: str):
        self.assert_locked()
        # TODO: log it!

    async def log_proposal_vote(self,
                                proposal: Proposal,
                                agent: discord.Member,
                                player: discord.Member,
                                old_vote_amount: Optional[int],
                                new_vote_amount: Optional[int]):
        self.assert_locked()
        # TODO: log it!
