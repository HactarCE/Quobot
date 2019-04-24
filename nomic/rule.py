from typing import Optional, List
from dataclasses import dataclass
import discord
import re

from .rule import Rule
from utils import colors
import utils


@dataclass
class Rule:
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
    - message_id (default None) -- discord.Message or the ID of one (converted
      to integer ID)
    """

    game: object
    tag: str
    title: str
    content: str
    parent: Optional[Rule] = 'root'
    children: List[Rule] = []
    message_id: Optional[int] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(self.parent, str):
            self.parent = self.game.get_rule(self.parent)
        for i, v in enumerate(self.children):
            if isinstance(i, str):
                self.children[i] = self.game.get_rule(v)

    def export(self):
        d = self._asdict()
        d.update({
            'parent': self.parent and self.parent.tag,
            'children': [r.tag for r in self.children],
        })
        return d

    async def fetch_message(self) -> discord.Message:
        return await self.game.rules_channel.fetch_message(self.message_id)

    @property
    def section_number(self):
        parent_rule = self.game.get_rule(self.parent)
        i = parent_rule.children.index(self.tag) + 1
        if self.parent.tag == 'root':
            return f"{i}"
        else:
            return f"{parent_rule.section_number}.{i}"

    @property
    def section_title(self):
        return f"{self.section_number} {self.title}"

    @property
    def discord_link(self):
        return 'https://discordapp.com/channels/{self.game.guild.id}/{self.game.rules_channel.id}/{self.message_id}'

    def _link_sub(self, format_string):
        def replace_func(match):
            rule = self.game.get_rule(match.group(1))
            if rule is None:
                return match.group()
            else:
                return format_string.format(rule=rule)
        return re.sub(r'\[(#[a-z\-]+)\]', replace_func, self.content)

    @property
    def discord_content(self):
        s = self._link_sub('[**{rule.section_title}**]({rule.discord_link})')
        if len(s) < 2048:
            return s
        s = self._link_sub('**{rule.section_title}**')
        if len(s) < 2048:
            return s
        return self.content

    @property
    def embed(self):
        if self.tag != 'root':
            return utils.make_embed(
                color=colors.INFO,
                title=self.title,
                description=self.discord_content,
                footer_text=self.tag
            )

    @classmethod
    def get_root(cls, game: object) -> Rule:
        return cls(game=game, tag='root', title=None, content=None)
