from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, List, Set
import discord
import functools
import re

from .base import BaseGame
from constants import colors
import utils


@dataclass
class _Rule:
    game: object  # We can't access nomic.game.Game from here.
    tag: str
    title: str
    content: str
    parent_tag: Optional[str] = None
    child_tags: List[str] = None
    message_ids: List[int] = None


@functools.total_ordering
class Rule(_Rule):
    """A dataclass representing a section or subsection of the game rules.

    Attributes:
    - game
    - tag -- string; unique tag consisting of lowercase `a`-`z` and hyphen `-`
    - title -- string; human-friendly title
    - content -- string

    Optional attribiutes:
    - parent_tag (default None) -- string
    - child_tags (default []) -- list of strings
    - message_ids (default []) -- list of discord.Message or IDs (converted to
      list of integer IDs)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.child_tags is None:
            self.child_tags = []
        if self.message_ids is None:
            self.message_ids = []

    def export(self) -> dict:
        return OrderedDict(
            tag=self.tag,
            title=self.title,
            content=self.content,
            parent_tag=self.parent_tag,
            child_tags=self.child_tags,
            message_ids=self.message_ids,
        )

    async def refresh(self):
        await self.game.refresh_rule(self)

    async def repost(self):
        await self.game.repost_rule(self)

    async def fetch_messages(self) -> discord.Message:
        return [self.game.rules_channel.fetch_message(message_id)
                async for message_id in self.message_ids]

    @property
    def parent(self):
        return self.parent_tag and self.game.get_rule(self.parent_tag)

    @property
    def children(self):
        return [self.game.get_rule(tag) for tag in self.child_tags]

    @property
    def descendants(self):
        for child in self.children:
            yield from child.descendants

    @property
    def depth(self):
        if self.tag == 'root':
            return 0
        return self.parent.depth + 1

    @property
    def section_number(self) -> str:
        parent_rule = self.game.get_rule(self.parent)
        i = parent_rule.children.index(self.tag) + 1
        if self.parent.tag == 'root':
            return f"{i}"
        else:
            return f"{parent_rule.section_number}.{i}"

    @property
    def section_title(self) -> str:
        return f"{self.section_number} {self.title}"

    @property
    def discord_link(self) -> str:
        return utils.discord.MESSAGE_LINK_FORMAT.format(
            guild=self.game.guild,
            channel=self.game.rules_channel,
            message_id=self.message_ids[0],
        )

    def _link_sub(self, format_string: str, content: str = None) -> str:
        """Replace rule tag links with Markdown links of a given format.

        Arguments:
        - format_string -- str; format string taking a keyword argument `rule`
        - content -- str; content in which to replace links
        """
        def replace_func(match):
            rule = self.game.get_rule(match.group(1))
            if rule is None:
                return match.group()
            else:
                return format_string.format(rule=rule)
        if content is None:
            content = self.content
        return re.sub(r'\[(#[a-z\-]+)\]', replace_func, content)

    def discord_link_sub(self, paragraph):
        s = self._link_sub('[**{rule.section_title}**]({rule.discord_link})', paragraph)
        if len(s) < 2000:
            return s
        s = self._link_sub('**{rule.section_title}**', paragraph)
        if len(s) < 2000:
            return s
        s = paragraph
        if len(s) < 2000:
            return s
        end = " ... <truncated to 2000 chars>"
        return s[:(2000 - len(end))] + end

    @property
    def discord_content(self) -> List[str]:
        paragraphs = map(self.discord_link_sub, self.content.splitlines())
        chunks = ['']
        for paragraph in paragraphs:
            if len(chunks[-1]) + len(paragraph) >= 2000:
                chunks.append('')
            chunks[-1] += paragraph
        return chunks

    @property
    def embeds(self) -> List[discord.Embed]:
        if self.tag == 'root':
            return []
        chunks = self.discord_content
        embeds = []
        for i, chunk in enumerate(chunks):
            title = self.title
            if len(chunks) > 1:
                title += f" ({i + 1}/{len(chunks)})"
            embeds.append(discord.Embed(
                color=colors.INFO,
                title=title,
                description=chunk,
            ).set_footer(text=self.tag))

    def __lt__(self, other):
        if self.parent == other.parent:
            return self.parent.child_tags.index(self.tag) < self.parent.child_tags.index(other.tag)
        elif self.depth > other.depth:
            return self.parent < other
        elif self.depth < other.depth:
            return self < other.parent
        else:
            return self.parent < other.parent

    def __eq__(self, other):
        return self.tag == other.tag

    def __hash__(self):
        # This isn't ideal, but it should have all the necessary properties of a
        # __hash__().
        return id(self)


class RuleManager(BaseGame):

    def init_data(self, rule_data: Optional[dict]):
        if rule_data:
            self.rules = {}
            for tag, rule in rule_data.items():
                self.rules[tag] = Rule(game=self, **rule)
        else:
            self.rules = {
                'root': {'tag': 'root', 'title': None, 'content': None},
            }

    def export(self) -> dict:
        return utils.sort_dict({k: r.export() for k, r in self.rules.items()})

    async def refresh_rule(self, *rules: Rule):
        """Update the messages for one or more proposals.

        May throw `TypeError`, `ValueError`, or `discord.Forbidden` exceptions.
        """
        self.assert_locked()
        for rule in sorted(set(rules)):
            try:
                messages = rule.fetch_messages()
                embeds = rule.embeds
                # Handle too few messages
                if len(messages) < len(embeds):
                    await self.repost_rule(rule)
                    return
                # Handle too many messages
                for m in messages[len(embeds):]:
                    await m.delete()
                for m, embed in zip(messages, embeds):
                    await m.edit(embed=embed)
            except discord.NotFound:
                await self.repost_rule(rule)
                return

    async def repost_rule(self, *rules: Rule):
        """Remove and repost the messages for one or more proposals.

        May throw `TypeError`, `ValueError`, or `discord.Forbidden` exceptions.
        """
        self.assert_locked()
        start = min(rules)
        all_rules = self.root_rule.descendants
        while next(all_rules) < start:
            pass
        repost_rules = [start] + list(all_rules)
        rule_messages = []
        for rule in repost_rules:
            rule_messages += rule.fetch_messages()
        if rule_messages:
            try:
                await utils.discord.safe_bulk_delete(rule_messages)
            except (discord.ClientException, discord.HTTPException):
                for m in rule_messages:
                    await m.delete()
        for rule in repost_rules:
            rule.message_ids = []
            for embed in rule.embeds:
                m = await self.rules_channel.send(embed=embed)
                rule.message_ids.append(m.id)
        self.need_save()

    def get_rule(self, tag: str) -> Optional[Rule]:
        return tag != 'root' and self.rules.get(tag)

    @property
    def root_rule(self):
        return self.rules['root']

    async def get_rule_messages(self) -> Set[discord.Message]:
        messages = set()
        for rule in self.rules.values():
            for m in await rule.fetch_messages():
                messages.add(m)
        return messages

    def assert_rules_validity(self):
        root = self.root_rule
        visited = set()
        if not root:
            raise RuntimeError(f"Error loading rules: Root rule does not exist")
        self._assert_rules_validity(self.get_rule('root'), visited)
        for rule in self.rules.values():
            if rule not in visited:
                raise RuntimeError(f"Error loading rules: Rule {rule} does not exist in the rule hierarchy")

    def _assert_rules_validity(self, start: Rule, visited: Set[Rule]):
        for child in start.children:
            if not child.parent == start:
                raise RuntimeError(f"Error loading rules: Rule {child} has {child.parent} as a child instead of {start}")
            if child in visited:
                raise RuntimeError(f"Error loading rules: Rule {child} appears as a child multiple times")
            visited.add(child)
            self.assert_rules_validity(child, visited)

    def _check_rule_tag(self, *tags):
        for tag in tags:
            if not isinstance(tag, str):
                raise TypeError(f"Invalid rule tag: {tag!r}")
            if not re.match(r'^[a-z\-]+$', tag):
                raise ValueError(f"Invalid rule tag: {tag!r}")
