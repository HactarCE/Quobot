from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Set
import discord
import functools

from .gameflags import GameFlagManager
from .playerdict import PlayerDict
from .repoman import GameRepoManager
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
        self.game.save()
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
        self.game.save()

    async def set_content(self, new_content: str):
        self.game.assert_locked()
        self.content = new_content
        await self.refresh()
        self.game.save()

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

    @property
    def markdown(self):
        s = f"<a name='{self.n}'/> "
        s += '\n\n'
        s += f"## #{self.n}"
        if self.status != ProposalStatus.VOTING:
            s += f" \N{EM DASH} {self.status.value.capitalize()}"
        s += '\n\n'
        if self.status != ProposalStatus.DELETED:
            s += self.content
            s += '\n\n'
        return s

    def __str__(self):
        return f"proposal #{self.n}"

    def __lt__(self, other):
        return self.n < other.n

    def __eq__(self, other):
        return self.n == other.n

    def __hash__(self):
        # None of these values should ever change, and they should uniquely
        # identify this proposal.
        return hash((self.game.guild.id, self.n, self.timestamp))


class ProposalManager(GameRepoManager):

    def load(self):
        db = self.get_db('proposals')
        self.proposals_channel = db.get('channel')
        if self.proposals_channel:
            self.proposals_channel = self.guild.get_channel(self.proposals_channel)
        self.proposals = []
        if db.get('proposals'):
            for proposal in db['proposals']:
                self.proposals.append(Proposal(game=self, **proposal))

    def save(self):
        db = self.get_db('proposals')
        db.replace(OrderedDict(
            channel=self.proposals_channel and self.proposals_channel.id,
            proposals=[p.export() for p in self.proposals],
        ))
        db.save()
        with open(self.get_file('proposals.md'), 'w') as f:
            f.write(f"# {self.guild.name} \N{EM DASH} Proposals")
            f.write('\n\n')
            for p in self.proposals:
                f.write(p.markdown)

    async def commit_proposals_and_log(self,
                                       agent: discord.Member,
                                       action: str,
                                       proposal: Proposal,
                                       post: str = '',
                                       link_to_proposal: bool = True,
                                       **kwargs):
        """Commit the proposals Markdown file and log the event."""
        if await self.repo.is_clean('proposals.md'):
            return
        commit_msg = markdown_msg = f"{utils.discord.fake_mention(agent)} {action} "
        commit_msg += str(proposal)
        if link_to_proposal:
            markdown_msg += f"[{proposal}](../proposals.md#{proposal.n})"
        else:
            markdown_msg += str(proposal)
        await self.commit('proposals.md', msg=commit_msg + post)
        await self.log(markdown_msg + post, **kwargs)

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
        self.save()
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
        # ProposalManager.repost_proposal() calls BaseGame.save() so we
        # don't have to do that here.
        await self.repost_proposal(new_proposal)
        return new_proposal

    async def permadel_proposal(self, proposal: Proposal):
        self.assert_locked()
        if not proposal.n == len(self.proposals):
            raise RuntimeError("Cannot delete any proposal other than the last one")
        del self.proposals[proposal.n - 1]
        self.save()
        await (await proposal.fetch_message()).delete()

    async def log_proposal_submit(self,
                                  agent: discord.Member,
                                  proposal: Proposal):
        await self.commit_proposals_and_log(
            agent, "submitted", proposal, link_to_commit=True
        )

    async def log_proposal_permadel(self,
                                    agent: discord.Member,
                                    proposal: Proposal):
        await self.commit_proposals_and_log(
            agent, "permanently deleted", proposal, link_to_proposal=False, link_to_commit=True
        )

    async def log_proposal_change_status(self,
                                         agent: discord.Member,
                                         proposal: Proposal):
        if proposal.status == ProposalStatus.VOTING:
            action = "reopened"
        else:
            action = proposal.status.value
        await self.commit_proposals_and_log(
            agent, action, proposal, link_to_commit=True
        )

    async def log_proposal_change_content(self,
                                          agent: discord.Member,
                                          proposal: Proposal):
        await self.commit_proposals_and_log(
            agent, "edited", proposal, link_to_commit=True
        )

    async def log_proposal_vote(self,
                                agent: discord.Member,
                                proposal: Proposal,
                                player: discord.Member,
                                old_vote_amount: Optional[int],
                                new_vote_amount: Optional[int]):

        if old_vote_amount == new_vote_amount:
            return

        if new_vote_amount is None:
            action = "removed their vote from"
        elif old_vote_amount is not None:
            action = "changed their vote on"
        elif new_vote_amount == 0:
            action = "abstained on"
        elif new_vote_amount > 0:
            action = "voted for"
        elif new_vote_amount < 0:
            action = "voted against"
        else:
            action = "WTFed"

        if player != agent:
            post = f" on behalf of {utils.discord.fake_mention(player)}"
        else:
            post = ''
        if abs(old_vote_amount or 0) > 1 or abs(new_vote_amount or 0) > 1:
            post += " ("
            if old_vote_amount is not None:
                post += f"was {old_vote_amount}"
                if new_vote_amount:
                    post += "; "
            if new_vote_amount is not None:
                post += f"now {new_vote_amount}"
            post += ")"

        await self.commit_proposals_and_log(
            agent, action, proposal, post=post
        )
