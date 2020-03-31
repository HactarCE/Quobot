from discord.ext import commands
from io import StringIO
from typing import List, Optional
import asyncio
import discord


from cogs.general import invoke_command_help
from constants import colors, emoji
import nomic
import utils


class RuleConverter(commands.Converter):
    allow_root = False
    async def convert(self, ctx, argument):
        argument = argument.lower()
        if argument.startswith('%'):
            argument = argument[1:]
        if argument == 'root' and not self.allow_root:
            raise commands.UserInputError(f"Root section is now allowed for this action")
        rule = nomic.Game(ctx).get_rule(argument)
        if rule:
            return rule
        raise commands.UserInputError(f"Unable to fetch rule with tag `{argument!r}`")


class RuleConverterAllowRoot(RuleConverter):
    allow_root = True


class RuleLocationConverter(commands.Converter):
    async def convert(self, ctx, argument):
        """Return a tuple (new_parent: Rule, index: int)."""
        argument = argument.lower()
        try:
            preposition, other_rule = argument.lower().split()
            other_rule = await RuleConverterAllowRoot().convert(ctx, other_rule)
            if preposition in ('before', 'above', 'after', 'below') and other_rule.tag != 'root':
                i = other_rule.parent.child_tags.index(other_rule.tag)
                if preposition in ('after', 'below'):
                    return other_rule.parent, i + 1
                else:
                    return other_rule.parent, i
            elif preposition in ('in', 'into', 'within', 'under'):
                return other_rule, len(other_rule.child_tags)
            else:
                raise ValueError
        except ValueError:
            raise commands.UserInputError(f"Invalid rule location: `{argument!r}`")
        if argument.startswith('%'):
            argument = argument[1:]
        rule = nomic.Game(ctx).get_rule(argument)
        if rule:
            return rule
        raise commands.UserInputError(f"Unable to fetch rule with tag `{argument!r}`")


class Rules(commands.Cog):
    """Commands for managing the game rules."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await nomic.Game.is_ready(ctx)

    @commands.group('rules', aliases=['ru', 'rule'], invoke_without_command=True)
    async def rules(self, ctx):
        """Manage rules.

        When commands require a `<rule_location>`, this must be two words. The
        first word is either `before`/`above`, `after`/`below`, or
        `within`/`under`, and the second word is an existing rule tag. E.g.
        `before proposals` or `above proposals` would put the given rule section
        before the `proposals` section but on the same level. (`after` or
        `below` is on the same level but below, and `within` or `under` is
        nested beneath.) If no rules exist, use `within root` to place a
        top-level rule.
        """
        await invoke_command_help(ctx)

    ########################################
    # CHANNEL COMMANDS
    ########################################

    @rules.group('channel', aliases=['chan'], invoke_without_command=True)
    @commands.check(utils.discord.is_admin)
    async def channel(self, ctx):
        """Manage the rules channel."""
        await utils.commands.desig_chan_show(
            ctx,
            "rules channel",
            nomic.Game(ctx).rules_channel
        )

    @channel.command('set')
    async def set_channel(self, ctx, new_channel: discord.TextChannel = None):
        """Set the rules channel."""
        await utils.commands.desig_chan_set(
            ctx,
            "rules channel",
            old_channel=nomic.Game(ctx).rules_channel,
            new_channel=new_channel or ctx.channel,
            callback=self._set_channel_callback,
        )

    @channel.command('unset', aliases=['reset'])
    async def unset_channel(self, ctx):
        """Unset the rules channel."""
        await utils.commands.desig_chan_set(
            ctx,
            "rules channel",
            old_channel=nomic.Game(ctx).rules_channel,
            new_channel=None,
            callback=self._set_channel_callback,
        )

    async def _set_channel_callback(self, ctx, new_channel: Optional[discord.TextChannel] = None):
        async with nomic.Game(ctx) as game:
            game.rules_channel = new_channel
            game.save()

    @channel.command('clean')
    async def clean_channel__channel(self, ctx, limit: int = 100):
        """Clean non-rule messages from the rules channel.

        limit -- Number of messages to search (0 = all)
        """
        await self._clean_channel(ctx, limit)

    @rules.command('clean')
    async def clean_channel__rules(self, ctx, limit: int = 100):
        """See `rules channel clean`."""
        await self._clean_channel(ctx, limit)

    async def _clean_channel(self, ctx, limit: int = 100):
        await asyncio.sleep(1)  # Avoid ghost messages.
        game = nomic.Game(ctx)
        if not game.rules_channel:
            await ctx.send(embed=discord.Embed(
                color=colors.ERROR,
                title="No rules channel",
            ))
            return
        message_iter = game.rules_channel.history(limit=limit or None)
        rule_message_ids = set.union(*(set(r.message_ids) for r in game.rules.values()))
        unwanted_messages = message_iter.filter(lambda m: m.id not in rule_message_ids)
        await utils.discord.safe_bulk_delete(await unwanted_messages.flatten())
        if ctx.channel == game.rules_channel:
            try:
                await ctx.message.delete()
            except discord.NotFound:
                pass

    ########################################
    # MODIFYING RULES
    ########################################

    @rules.command('new', aliases=['add', 'create'], rest_is_raw=True)
    async def add_rule(self, ctx, rule_tag: str, *, rule_location: RuleLocationConverter):
        """Add a new rule section.

        You can type the entire contents of the rule section, or attach a raw
        file containing its Markdown content.

        See `rules` help for rule location syntax.
        """
        game = nomic.Game(ctx)
        try:
            game.check_rule_tag_unused(rule_tag)
        except (TypeError, ValueError) as e:
            raise commands.UserInputError(str(e))
        m, response, title = await utils.discord.query_content(
            ctx, clean_content=True, title="Write the title of the new rule:",
        )
        if response != 'y':
            await utils.discord.edit_embed_for_response(
                m, response, title_format="Rule creation {}"
            )
            return
        response, content = await self._rule_edit_wizard(ctx, nomic.Rule(
            game=game,
            tag=rule_tag,
            title=title,
            content='(none)'
        ), edit=False)
        if response != 'y':
            return
        async with game:
            rule = await game.add_rule(
                *rule_location, tag=rule_tag, title=title, content=content
            )
            await game.log_rule_add(ctx.author, rule)

    @rules.command('edit')
    async def edit_rule(self, ctx, rule: RuleConverter):
        """Edit a rule section.

        You can type the entire contents of the rule section, or attach a raw
        file containing its Markdown content.
        """
        if ctx.message.attachments:
            new_content = (await ctx.message.attachments[0].read()).decode().strip()
            await ctx.message.add_reaction(emoji.SUCCESS)
        else:
            if rule.tag != 'root':
                s = f"```\n{rule.content}\n```"
                if len(s) < utils.discord.MAX_EMBED_FIELD_VALUE:
                    await ctx.send(embed=discord.Embed(
                        color=colors.INFO,
                        title="Existing rule content",
                        description=s,
                    ))
                else:
                    await utils.discord.invoke_comamnd(ctx, 'rule', 'download', rule)
            response, new_content = await self._rule_edit_wizard(ctx, rule, edit=True)
            if response != 'y':
                return
        async with nomic.Game(ctx) as game:
            await game.set_rule_content(rule, new_content)
            await game.log_rule_change_content(ctx.author, rule)

    @rules.command('move', aliases=['mv'], rest_is_raw=True)
    async def move_rule(self, ctx, rule: RuleConverter, *, new_rule_location: RuleLocationConverter):
        """Move a rule section (and its subsections).

        See `rules` for rule location syntax.
        """
        game = nomic.Game(ctx)
        new_parent, new_index = new_rule_location
        try:
            game.check_move_rule(rule, new_parent)
        except ValueError as e:
            raise commands.UserInputError(str(e))
        m, response = await utils.discord.get_confirm_embed(
            ctx, title=f"Move {rule}?",
        )
        await utils.discord.edit_embed_for_response(
            m, response, title_format="Rule section move {}"
        )
        if response != 'y':
            return
        async with game:
            await game.move_rule(rule, new_parent, new_index)
            await game.log_rule_move(ctx.author, rule)

    @rules.command('remove', aliases=['del', 'delete', 'rm'])
    async def remove_rule(self, ctx, rule: RuleConverter):
        """Delete a rule (and its subsections)."""
        game = nomic.Game(ctx)
        m, response = await utils.discord.get_confirm_embed(
            ctx, title=f"Permanently delete {rule}?",
            description="This cannot be undone.",
        )
        if response != 'y':
            await utils.discord.edit_embed_for_response(
                m, response, title_format="Rule section removal {}"
            )
            return
        await m.edit(embed=discord.Embed(
            color=colors.SUCCESS,
            title=f"{str(rule).capitalize()} deleted",
        ))
        async with game:
            await game.remove_rule(rule)
            await game.log_rule_remove(ctx.author, rule)

    @rules.command('retag', aliases=['changetag'])
    async def retag_rule(self, ctx, rule: RuleConverter, new_tag: str):
        """Change a rule's tag."""
        game = nomic.Game(ctx)
        try:
            game.check_rule_tag_unused(new_tag)
        except ValueError as e:
            raise commands.UserInputError(str(e))
        async with nomic.Game(ctx) as game:
            old_tag = rule.tag
            await game.retag_rule(rule, new_tag)
            await game.log_rule_change_tag(ctx.author, rule, old_tag)

    @rules.command('retitle', aliases=['changetitle', 'rename'], rest_is_raw=True)
    async def retitle_rule(self, ctx, rule: RuleConverter, *, new_title):
        """Change a rule's title."""
        new_title = new_title.strip()
        if not new_title:
            m, response, new_title = await utils.discord.query_content(
                ctx, clean_content=True, title="Write the new title:"
            )
            if response != 'y':
                await utils.discord.edit_embed_for_response(
                    m, response, title_format="Rule title change {}"
                )
                return
        m, response = await utils.discord.get_confirm_embed(
            ctx, title=f"Change the title of {rule} to **{new_title}**?"
        )
        if response != 'y':
            await utils.discord.edit_embed_for_response(
                m, response, title_format="Rule title change {}"
            )
            return
        await m.edit(embed=discord.Embed(
            color=colors.SUCCESS,
            title=f"Title of {rule} changed to **{new_title}**",
        ))
        async with nomic.Game(ctx) as game:
            await game.set_rule_title(rule, new_title)
            await game.log_rule_change_title(ctx.author, rule)

    async def _rule_edit_wizard(self, ctx, rule: RuleConverter, *, edit: bool):
        m, response, content = await utils.discord.query_content(
            ctx, timeout=120, allow_file=True,
            title="Edit rule" if edit else "New rule",
            description=f"Write the new contents for {rule} here (must fit within one message) or attach a file:",
        )
        await utils.discord.edit_embed_for_response(
            m, response, title_format="Rule edit {}" if edit else "New rule {}"
        )
        return response, content

    ########################################
    # MISCELLANEOUS COMMANDS
    ########################################

    @rules.command('download', aliases=['dl'])
    async def download_rule(self, ctx, *rules: RuleConverterAllowRoot):
        """Download the raw content of one or more rule sections."""
        rules = sorted(set(rules))
        if not rules:
            await invoke_command_help(ctx)
            return
        title = "Rule section download"
        description = "Rule section"
        if len(rules) != 1:
            title += "s"
            description += "s"
        description += ' ' + ', '.join(r.tag for r in rules)
        await ctx.send(files=[
            discord.File(StringIO(r.content),
                         f"rule_{r.tag}.md")
            for r in rules
        ])

    @rules.command('link', aliases=['ln'])
    async def link_rule(self, ctx, *rules: RuleConverterAllowRoot):
        """Link to one or more rule sections."""
        rules = sorted(set(rules))
        if not rules:
            await invoke_command_help(ctx)
            return
        description = ''
        for r in rules:
            description += f"**%{r.tag}**"
            description += " \N{EN DASH} **[on Discord]({r.discord_link})**"
            description += " \N{EN DASH} **[on GitHub]({r.github_link})**"
            description += "\n"
        await ctx.send(embed=discord.Embed(
            color=colors.INFO,
            title="Rule links",
            description=description,
        ))

    @rules.command('refresh', aliases=['rf'])
    async def refresh_rule(self, ctx, *rules: RuleConverterAllowRoot):
        """Refresh one or more rule messages.

        This is mostly useful for fixing minor glitches.
        """
        await self.refresh_repost_rule(ctx, rules, False)

    @rules.command('repost', aliases=['rp'])
    @commands.check(utils.discord.is_admin)
    async def repost_rule(self, ctx, *rules: RuleConverterAllowRoot):
        """Repost one or more rule messages (and all subsequent ones).

        This command may repost potentially hundreds of messages, depending on
        how many rule sections there are and their size. USE IT WISELY.
        """
        await self.refresh_repost_rule(ctx, rules, True)

    async def refresh_repost_rule(self, ctx,
                                  rules: List[nomic.Rule],
                                  repost: bool):
        game = nomic.Game(ctx)
        if not rules:
            rules = game.root_rule.descendants
        try:
            async with game:
                if repost:
                    await game.repost_rule(*rules)
                else:
                    await game.refresh_rule(*rules)
            await ctx.message.add_reaction(emoji.SUCCESS)
        except (TypeError, ValueError, discord.Forbidden):
            await ctx.message.add_reaction(emoji.FAILURE)
        await self._clean_channel(ctx)


def setup(bot):
    bot.add_cog(Rules(bot))
