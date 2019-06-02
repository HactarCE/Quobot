from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, List
import discord
import re

from constants import colors
import utils


@dataclass
class _Rule:
    game: object  # We can't access nomic.game.Game from here.
    tag: str
    title: str
    content: str
    parent: Optional['Rule'] = 'root'
    children: List['Rule'] = None
    message_ids: List[int] = None


class Rule(_Rule):
    """A dataclass representing a section or subsection of the game rules.

    Attributes:
    - game
    - tag -- string; unique tag consisting of lowercase `a`-`z` and hyphen `-`
    - title -- string; human-friendly title
    - content -- string

    Optional attribiutes:
    - parent (default game.get_rule('root')) -- string or Rule (converted to
      Rule)
    - children (default []) -- list of strings or list of Rules (converted to
      list of Rules)
    - message_ids (default []) -- list of discord.Message or IDs (converted to
      list of integer IDs)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.children is None:
            self.children = []
        if self.message_ids is None:
            self.message_ids = []
        if isinstance(self.parent, str):
            self.parent = self.game.get_rule(self.parent)
        for i, v in enumerate(self.children):
            if isinstance(i, str):
                self.children[i] = self.game.get_rule(v)

    def export(self) -> dict:
        return OrderedDict(
            tag=self.tag,
            title=self.title,
            content=self.content,
            parent=self.parent and self.parent.tag,
            children=[r.tag for r in self.children],
            message_ids=self.message_ids,
        )

    async def fetch_messages(self) -> discord.Message:
        return [self.game.rules_channel.fetch_message(message_id)
                async for message_id in self.message_ids]

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

    @classmethod
    def get_root(cls, game: object) -> 'Rule':
        return cls(game=game, tag='root', title=None, content=None)
