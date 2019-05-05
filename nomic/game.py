from discord.ext import commands
from typing import Dict, Union
import asyncio
import discord
import re

from constants import colors, emoji
from database import get_db
from utils import l, mutget
from .gameflags import GameFlags
from .proposal import Proposal
from .quantity import Quantity
from .rule import Rule
import utils


class Game:
    """A Nomic game, including proposals, rules, etc.

    Do not instantiate this class directly; use game.get_game() instead.
    """

    def __init__(self, guild: discord.Guild, do_not_instantiate_directly: None):
        """Do not instantiate this class directly; use game.get_game() instead.
        """
        if do_not_instantiate_directly != 'ok':
            # I'm not sure whether TypeError is really the best choice here.
            raise TypeError("Do not instantiate DB object directly; use get_db() instead")
        self.lock = asyncio.Lock()
        self.guild = guild
        self.db = get_db('guild_' + str(guild.id))
        self.flags = GameFlags(**self.db.get('flags', {}))
        self.proposals = [Proposal(game=self, **p) for p in mutget(self.db, 'proposals', [])]
        self.quantities = {k: Quantity(**q) for k, q in mutget(self.db, 'quantities', {})}
        self.rules = {}
        self._load_rule(mutget(self.db, 'rules', {
            'root': {'tag': 'root', 'title': None, 'content': None},
        }), 'root')
        self.player_activity = mutget(self.db, 'last_activity', {})
        channels = mutget(self.db, 'channels', {})
        self.proposals_channel  = guild.get_channel(channels.get('proposals'))
        self.quantities_channel = guild.get_channel(channels.get('quantities'))
        self.rules_channel      = guild.get_channel(channels.get('rules'))

    def _load_rule(self, rules_dict: Dict[str, Dict], tag: str) -> None:
        if tag not in rules_dict:
            l.warning(f"No such rule found: {tag!r}")
            return
        if tag in self.rules:
            l.warning(f"Rule recursion or repetition found: {tag!r} is a child of multiple rules")
            return
        rule = Rule(game=self, **rules_dict[tag])
        if rule.tag != 'root':
            if rule.parent is None:
                l.warning(f"Rule section inconsistency found; {tag!r} is not root but has no parent")
            if rule not in rule.parent.children:
                l.warning(f"Rule section inconsistency found; {tag!r} is not a child of its parent, {rule.parent.tag!r}")
                return
        self.rules[tag] = rule
        for child in rule.children:
            self._load_rule(rules_dict, child)

    async def save(self) -> None:
        async with self.lock:
            self._save()

    def _save(self) -> None:
        self.db.clear()
        self.db.update(self.export())
        self.db.save()

    def export(self) -> dict:
        return {
            'channels': {
                'proposals': self.proposals_channel and self.proposals_channel.id,
                'quantities': self.quantities_channel and self.quantities_channel.id,
                'rules': self.rules_channel and self.rules_channel.id,
            },
            'flags': self.flags.export(),
            'proposals': [p.export() for p in self.proposals],
            'quantities': {k: q.export() for k, q in self.quantities.items()},
            'rules': {k: r.export() for k, r in self.rules.items()},
        }

    def get_member(self, user_id: int) -> discord.User:
        if isinstance(user_id, discord.User):
            return user_id
        else:
            return self.guild.get_member(user_id)

    def record_activity(self, user: discord.User) -> None:
        """Mark a player as being active right now."""
        self.player_activity[str(user.id)] = utils.now()

    @property
    def activity_diffs(self) -> Dict[discord.User, float]:
        now = utils.now()
        return {self.get_member(k): now - v for k, v in self.player_activity.items()}

    def _check_proposal(self, *ns) -> None:
        for n in ns:
            if not isinstance(n, int):
                raise TypeError(f"Invalid proposal ID: {n!r}")
            if not 1 <= n <= len(self.proposals):
                raise ValueError(f"No such proposal with ID: {n!r}")

    def has_proposal(self, n: int) -> bool:
        return isinstance(n, int) and 1 <= n <= len(self.proposals)

    def get_proposal(self, n: int) -> Proposal:
        if self.has_proposal(n):
            return self.proposals[n]

    async def get_proposal_messages(self) -> set:
        messages = set()
        for proposal in self.proposals:
            messages.add(await proposal.fetch_message())
        return messages

    def _check_rule(self, *tags) -> None:
        for tag in tags:
            if not isinstance(tag, str):
                raise TypeError(f"Invalid rule tag: {tag!r}")
            if not re.match(r'^[a-z\-]+$', tag):
                raise ValueError(f"Invalid rule tag: {tag!r}")
            if tag not in self.rules:
                raise KeyError(f"No such rule with tag: {tag!r}")

    def has_rule(self, tag: str) -> bool:
        try:
            self._check_rule(tag)
        except (KeyError, TypeError, ValueError):
            return False
        return True

    def get_rule(self, tag: str) -> Rule:
        if self.has_rule(tag):
            return self.rules[tag]

    async def get_rule_messages(self) -> set:
        messages = set()
        for rule in self.rules.values():
            messages.add(await rule.fetch_message())
        return messages

    @property
    def root_rule(self) -> Rule:
        return self.get_rule('root')

    async def refresh_proposal(self, *ns: int) -> None:
        """Update the messages for one or more proposals.

        May throw `TypeError`, `ValueError`, or `discord.Forbidden` exceptions.
        """
        async with self.lock:
            await self._refresh_proposal(self, *ns)

    async def _refresh_proposal(self, *ns: int) -> None:
        for n in ns:
            self._check_proposal(n)
        for n in sorted(set(ns)):
            proposal = self.get_proposal(n)
            try:
                m = await proposal.fetch_message()
                await m.clear_reactions()
                await m.edit(embed=proposal.embed)
                await m.add_reaction(emoji.VOTE_FOR)
                await m.add_reaction(emoji.VOTE_AGAINST)
                await m.add_reaction(emoji.VOTE_ABSTAIN)
            except discord.NotFound:
                self._repost_proposal(n)
                return

    async def repost_proposal(self, *ns: int) -> None:
        """Remove and repost the messages for one or more proposals.

        May throw `TypeError`, `ValueError`, or `discord.Forbidden` exceptions.
        """
        async with self.lock:
            await self._repost_proposal(self, *ns)

    async def _repost_proposal(self, *ns: int) -> None:
        for n in ns:
            self._check_proposal(n)
        proposal_range = range(min(ns), len(self.proposals) + 1)
        proposals = list(map(self.get_proposal, proposal_range))
        proposal_messages = []
        for proposal in proposals:
            try:
                proposal_messages.append(await proposal.fetch_message())
            except discord.NotFound:
                pass
        await self.proposals_channel.delete_messages(*proposal_messages)
        for n, proposal in zip(proposal_range, proposals):
            m = await self.proposals_channel.send(embed=discord.Embed(
                color=colors.TEMPORARY,
                title=f"Preparing proposal #{n}\N{HORIZONTAL ELLIPSIS}",
            ))
            proposal.message_id = m.id
        self._save()
        await self._refresh_proposal(*proposal_range)

    async def refresh_rule(self, *tags: str) -> None:
        """Update the messages for one or more rules.

        May throw `KeyError`, `TypeError`, `ValueError`, `discord.NotFound`,
        or `discord.Forbidden` exceptions.
        """
        async with self.lock:
            await self._refresh_rule(*tags)

    async def _refresh_rule(self, *tags: str) -> None:
        for tag in tags:
            self._check_rule(tag)
        for tag in sorted(set(tags)):
            rule = self.get_rule(tag)
            m = await rule.fetch_message()
            await m.edit(embed=rule.embed)

    async def repost_rules(self) -> None:
        """Delete and repost the messages for all rules."""
        with self.lock:
            await self.rules_channel.delete_messages(*(await self.get_rule_messages()))
            await self._repost_child_rules(self.root_rule)

    async def _repost_child_rules(self, parent: Rule) -> None:
        for rule in parent.children:
            self.rules_channel.send(embed=rule.embed)
            self._repost_child_rules(rule)


_GAMES = {}


def get_game(guild: Union[discord.Guild, commands.Context]):
    if not isinstance(guild, discord.Guild):
        ctx = guild
        guild = ctx.guild
    if guild.id not in _GAMES:
        _GAMES[guild.id] = Game(guild, 'ok')
    return _GAMES[guild.id]
