from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, List, Set
import discord
import functools
import re

from .repoman import GameRepoManager
from constants import colors, info
from utils import l
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
            content=self.content if self.tag != 'root' else None,
            parent_tag=self.parent_tag,
            child_tags=self.child_tags,
            message_ids=self.message_ids,
        )

    async def refresh(self):
        await self.game.refresh_rule(self)

    async def repost(self):
        await self.game.repost_rule(self)

    async def fetch_messages(self) -> discord.Message:
        try:
            return [await self.game.rules_channel.fetch_message(message_id)
                    for message_id in self.message_ids]
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return []

    @property
    def parent(self):
        return self.parent_tag and self.game.get_rule(self.parent_tag, tag_only=True)

    @property
    def children(self):
        return [self.game.get_rule(tag, tag_only=True) for tag in self.child_tags]

    @property
    def descendants(self):
        yield self
        for child in self.children:
            yield from child.descendants

    @property
    def depth(self):
        if self.tag == 'root':
            return 0
        return self.parent.depth + 1

    @property
    def section_number(self) -> str:
        parent_rule = self.parent
        i = parent_rule.child_tags.index(self.tag) + 1
        if self.parent.tag == 'root':
            return f"{i}."
        else:
            return f"{parent_rule.section_number}{i}."

    @property
    def section_title(self) -> str:
        if self.tag == 'root':
            return "Table of contents"
        else:
            return f"{self.section_number} {self.title}"

    @property
    def discord_link(self) -> str:
        if self.message_ids:
            return utils.discord.MESSAGE_LINK_FORMAT.format(
                guild=self.game.guild,
                channel=self.game.rules_channel,
                message_id=self.message_ids[0],
            )
        else:
            return ''

    @property
    def github_link(self):
        return f'{info.GITHUB_REPO_LINK}/blob/{self.game.repo.name}/rules.md#{self.tag}'

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
        return re.sub(r'\[#([a-z0-9\-_]+)\]', replace_func, content)

    def discord_link_sub(self, paragraph):
        s = self._link_sub('[**{rule.section_title}**]({rule.discord_link})', paragraph)
        if len(s) < 2000:
            return s
        s = self._link_sub(f'**{self.section_title}**', paragraph)
        if len(s) < 2000:
            return s
        s = paragraph
        if len(s) < 2000:
            return s
        end = " ... <truncated to 2000 chars>"
        return s[:(2000 - len(end))] + end

    def markdown_link_sub(self, paragraph):
        return self._link_sub('[**{rule.section_title}**](#{rule.tag})', paragraph)

    @property
    def discord_content(self) -> List[str]:
        if self.tag == 'root':
            s = '\n'.join(f"[#{rule.tag}]" for rule in self.descendants if rule != self)
        else:
            s = self.content
        s = re.sub(r'[ \t]*(\*) ', "\N{BULLET}", s)
        paragraphs = map(self.discord_link_sub, s.splitlines())
        # Substitute bullet points
        chunks = ['']
        for paragraph in paragraphs:
            if len(chunks[-1]) + len(paragraph) >= 2000:
                chunks.append('')
            chunks[-1] += paragraph + '\n'
        return chunks

    @property
    def embeds(self) -> List[discord.Embed]:
        chunks = self.discord_content
        embeds = []
        for i, chunk in enumerate(chunks):
            title = self.section_title
            if len(chunks) > 1:
                title += f" ({i + 1}/{len(chunks)})"
            embeds.append(discord.Embed(
                color=colors.INFO,
                title=title,
                description=chunk,
            ).set_footer(text=f'#{self.tag}'))
        return embeds

    @property
    def markdown(self):
        if self.tag == 'root':
            s = self.section_title
            s += "\n\n"
            for rule in self.descendants:
                if rule != self:
                    s += " " * 4 * (rule.depth - 1)
                    s += f"* [#{rule.tag}]\n"
            self.content = s + "\n"
        else:
            s = f"<a name='{self.tag}'/>"
            s += "\n\n"
            s += "#" * (self.depth + 1)
            s += f" {self.title}"
            s += "\n\n"
            s += self.markdown_link_sub(self.content)
            s += "\n\n"
        return s

    def __str__(self):
        return f"rule section `#{self.tag}`"

    def __lt__(self, other):
        if self == other:
            return False
        if not (self.parent_tag or other.parent_tag):
            return False
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


class RuleManager(GameRepoManager):

    def load(self):
        db = self.get_db('rules')
        self.rules_channel = db.get('channel')
        if self.rules_channel:
            self.rules_channel = self.guild.get_channel(self.rules_channel)
        self.rules = {}
        if db.get('rules'):
            for _, rule_data in db['rules'].items():
                rule = Rule(game=self, **rule_data)
                self.rules[rule.tag] = rule
        else:
            self.rules['root'] = Rule(game=self, tag='root', title=None, content=None)
        try:
            self.assert_rules_validity()
        except RuntimeError as e:
            l.error(str(e))

    def save(self):
        db = self.get_db('rules')
        db.replace(OrderedDict(
            channel=self.rules_channel and self.rules_channel.id,
            rules=utils.sort_dict({k: r.export() for k, r in self.rules.items()}),
        ))
        db.save()
        with open(self.get_file('rules.md'), 'w') as f:
            f.write(f"# {self.guild.name} \N{EM DASH} Rules")
            f.write('\n\n')
            for r in self.root_rule.descendants:
                f.write(r.markdown)

    async def commit_rules_and_log(self,
                                   agent: discord.Member,
                                   action: str,
                                   rule: Rule,
                                   link_to_rule: bool = True,
                                   **kwargs):
        """Commit the rules Markdown file and log the event."""
        if await self.repo.is_clean('rules.md'):
            return
        commit_msg = markdown_msg = f"{utils.discord.fake_mention(agent)} {action} "
        commit_msg += str(rule)
        if link_to_rule:
            markdown_msg += f"[{rule}](../rules.md#{rule.tag})"
        else:
            markdown_msg += str(rule)
        await self.commit('rules.md', msg=commit_msg)
        await self.log(markdown_msg, **kwargs)

    async def refresh_rule(self, *rules: Rule):
        """Update the messages for one or more proposals.

        May throw `TypeError`, `ValueError`, or `discord.Forbidden` exceptions.
        """
        self.assert_locked()
        for rule in sorted(set(rules)):
            try:
                messages = await rule.fetch_messages()
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
            rule_messages += await rule.fetch_messages()
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
        await self.refresh_rule(self.root_rule)
        self.save()

    def get_rule(self, tag_or_section_number: str, *, tag_only: bool = False) -> Optional[Rule]:
        tag = section_number = tag_or_section_number
        if tag.startswith('#'):
            tag = tag[1:]
        if tag in ('contents', 'toc'):
            return self.root_rule
        rule = self.rules.get(tag)
        if rule or tag_only:
            return rule
        try:
            rule = self.root_rule
            for i in section_number.split('.'):
                if i:
                    rule = rule.children[int(i) - 1]
            return rule
        except (IndexError, ValueError):
            return None

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
        """Raises RuntimeError if the rules aren't hierarchically valid."""
        root = self.root_rule
        visited = set()
        try:
            if not root:
                raise RuntimeError(f"Error loading rules: Root rule does not exist")
            self._assert_rules_validity(self.root_rule, visited)
            for rule in self.rules.values():
                if rule not in visited:
                    raise RuntimeError(f"Error loading rules: Rule {rule} does not exist in the rule hierarchy")
        except RuntimeError:
            l.error("Error loading rules; reloading from disk")
            RuleManager.load(self)
            raise

    def _assert_rules_validity(self, start: Rule, visited: Set[Rule]):
        visited.add(start)
        for child in start.children:
            if not child.parent == start:
                raise RuntimeError(f"Error loading rules: Rule {child} has {child.parent} as a child instead of {start}")
            if child in visited:
                raise RuntimeError(f"Error loading rules: Rule {child} appears as a child multiple times")
            self._assert_rules_validity(child, visited)

    def check_rule_tag(self, *tags):
        for tag in tags:
            if not isinstance(tag, str):
                raise TypeError(f"Invalid rule tag: {tag!r}")
            if not re.match(r'^[a-z0-9\-_]+$', tag):
                raise ValueError(f"Invalid rule tag: {tag!r}\n\nRules must be alphanumeric plus `_` and `-`.")

    def check_rule_tag_unused(self, *tags):
        self.check_rule_tag(*tags)
        for tag in tags:
            if tag in self.rules:
                raise ValueError(f"Rule with tag {tag!r} already exists")

    def check_move_rule(self, rule: Rule, new_parent: Rule):
        """Raises ValueError if the proposed move would result in an invalid
        rule hierarchy.
        """
        if new_parent in rule.descendants:
            raise ValueError("Cannot move rule into itself or its own child")

    async def add_rule(self, parent: Rule, index: Optional[int], *, tag, **kwargs):
        self.assert_locked()
        self.check_rule_tag_unused(tag)
        if int is None:
            parent.child_tags.append(tag)
        else:
            parent.child_tags.insert(index, tag)
        self.rules[tag] = rule = Rule(game=self, tag=tag, parent_tag=parent.tag, **kwargs)
        self.assert_rules_validity()
        await self.repost_rule(rule)
        self.save()
        return rule

    async def retag_rule(self, rule: Rule, new_tag: str):
        self.assert_locked()
        self.check_rule_tag_unused(new_tag)
        parents_children = rule.parent.child_tags
        parents_children[parents_children.index(rule.tag)] = new_tag
        for child in rule.children:
            child.parent_tag = new_tag
        del self.rules[rule.tag]
        self.rules[new_tag] = rule
        rule.tag = new_tag
        self.assert_rules_validity()
        await self.refresh_rule(rule)
        self.save()

    async def set_rule_title(self, rule: Rule, new_title: str):
        self.assert_locked()
        rule.title = new_title
        await rule.refresh()
        await self.root_rule.refresh()
        self.save()

    async def set_rule_content(self, rule: Rule, new_content: str):
        self.assert_locked()
        rule.content = new_content
        await self.refresh_rule(rule)
        self.save()

    async def move_rule(self, rule: Rule, new_parent: Rule, new_index: int = None):
        self.assert_locked()
        self.check_move_rule(rule, new_parent, new_index)
        if new_index is None:
            new_index = len(new_parent.child_tags)
        rule.parent.child_tags.remove(rule.tag)
        new_parent.child_tags.insert(new_index, rule.tag)
        rule.parent_tag = new_parent.tag
        self.assert_rules_validity()
        await self.repost_rule(rule)
        self.save()

    async def remove_rule(self, rule: Rule):
        """Remove a rule and all its descendants.

        Raises ValueError if the rule cannot be deleted.
        """
        self.assert_locked()
        if rule == self.root_rule:
            raise ValueError("Cannot delete root rule")
        for child in rule.children:
            child.remove()
        rule.parent.child_tags.remove(rule.tag)
        del self.rules[rule.tag]
        self.assert_rules_validity()
        for m in await rule.fetch_messages():
            await m.delete()
        self.save()

    async def log_rule_add(self,
                           agent: discord.Member,
                           rule: Rule):
        await self.commit_rules_and_log(
            agent, "added new", rule, link_to_commit=True,
        )

    async def log_rule_remove(self,
                              agent: discord.Member,
                              rule: Rule):
        await self.commit_rules_and_log(
            agent, "deleted", rule, link_to_rule=False, link_to_commit=True,
        )

    async def log_rule_change_tag(self,
                                  agent: discord.Member,
                                  rule: Rule,
                                  old_tag: str):
        await self.commit_rules_and_log(
            agent, "changed the tag of rule section `#{old_tag}` to", rule, link_to_commit=True,
        )

    async def log_rule_change_title(self,
                                    agent: discord.Member,
                                    rule: Rule):
        await self.commit_rules_and_log(
            agent, "changed the title of", rule, link_to_commit=True,
        )

    async def log_rule_change_content(self,
                                      agent: discord.Member,
                                      rule: Rule):
        await self.commit_rules_and_log(
            agent, "changed the content of", rule, link_to_commit=True,
        )

    async def log_rule_move(self,
                            agent: discord.Member,
                            rule: Rule):
        await self.commit_rules_and_log(
            agent, "moved", rule, link_to_commit=True,
        )
