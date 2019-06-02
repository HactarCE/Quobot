from discord.ext import commands
from typing import List, Optional, Union
import discord
import re

from constants import colors, emoji, strings
from cogs.general import invoke_command_help
import nomic
import utils


class Quantities(commands.Cog):
    """Commands pertaining to quantities/currencies and transactions."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group('quantities', aliases=['$', 'c', 'currencies', 'currency', 'q', 'quan', 'quantity'])
    async def quantities(self, ctx):
        """Manage game quantities."""
        if ctx.invoked_subcommand is None:
            await invoke_command_help(ctx)

    ########################################
    # INFO COMMANDS
    ########################################

    @quantities.command('list', aliases=['l', 'ls'])
    async def list_quantities(self, ctx, user: utils.discord.MeOrMemberConverter() = None):
        """List all game quantities.

        If a user is supplied, list that user's value for each quantity.
        """
        game = nomic.get_game(ctx)
        title = "Quantities"
        if user:
            title += f" ({utils.discord.fake_mention(user)})"
        description = ''
        for quantity in utils.sort_dict(game.quantities).values():
            description += f"\N{BULLET} **{quantity.name.capitalize()}**"
            if user:
                description += f" \N{EM DASH} {quantity.get(user)}"
            elif quantity.aliases:
                description += f" ({', '.join(quantity.aliases)})"
            description += "\n"
        await ctx.send(embed=discord.Embed(
            color=colors.INFO,
            title=title,
            description=description or strings.EMPTY_LIST,
        ))

    @quantities.command('info', aliases=['i'])
    async def quantity_info(self, ctx, *quantity_names: str):
        """List each player's values for a given quantity"""
        game = nomic.get_game(ctx)
        embed = discord.Embed(color=colors.INFO)
        if not quantity_names:
            quantity_names = game.quantities.keys()
        quantity_names = sorted(set(quantity_names))
        if len(quantity_names) > 1:
            embed.title = "Quantities"
        for quantity_name in quantity_names:
            quantity = game.get_quantity(quantity_name)
            self._check_quantity(quantity, quantity_name)
            value = ''
            for member, amount in quantity.players.sorted_items():
                value += f"{member.mention} has **{amount}**\n"
            embed.add_field(
                name=quantity.name.capitalize(),
                value=value or "(all players have zero)",
                inline=False,
            )
        await utils.discord.send_split_embed(ctx, embed)

    @quantities.command('add', aliases=['create'])
    @commands.check(utils.discord.is_admin)
    async def add_quantity(self, ctx, quantity_name: str, *aliases: str):
        """Create a new quantity."""
        game = nomic.get_game(ctx)
        quantity_name = quantity_name.lower()
        aliases = [s.lower() for s in aliases]
        for s in [quantity_name] + aliases:
            if game.get_quantity(s):
                raise commands.UserInputError(f"Quantity name {s!r} is already in use.")
        for s in [quantity_name] + aliases:
            if len(s) > 32:
                raise commands.UserInputError(f"Quantity name {s!r} is too long.")
            if not re.match(r'[a-z][0-9a-z\-_]+', s):
                raise commands.UserInputError(f"Quantity name {s!r} is invalid. Quantity names and aliases may only contain lowercase letters, numbers, hyphens, or underscores, and must begin with a lowercase letter.")
        description = "Aliases: " + utils.human_list(f"**{s}**" for s in aliases)
        m, response = await utils.discord.get_confirm_embed(
            ctx,
            title=f"Create quantity {quantity_name!r}?",
            description=description,
        )
        if response == 'y':
            async with game:
                game.quantities[quantity_name] = nomic.Quantity(
                    game=game,
                    name=quantity_name,
                    aliases=aliases,
                )
                await game.save()
        await m.edit(embed=discord.Embed(
            color=colors.YESNO[response],
            title=f"New quantity {quantity_name!r} {strings.YESNO[response]}",
            description=description,
        ))

    @quantities.command('remove', aliases=['del', 'delete', 'rm'])
    @commands.check(utils.discord.is_admin)
    async def remove_quantity(self, ctx, quantity_name: str):
        """Delete an existing quantity."""
        game = nomic.get_game(ctx)
        quantity = game.get_quantity(quantity_name)
        self._check_quantity(quantity, quantity_name)
        m, response = await utils.discord.get_confirm_embed(
            ctx,
            title=f"Delete quantity {quantity.name!r}?",
            description="Are you sure? This cannot be undone.",
        )
        if response == 'y':
            async with game:
                del game.quantities[quantity.name]
                await game.save()
        await m.edit(embed=discord.Embed(
            color=colors.YESNO[response],
            title=f"Deletion of quantity {quantity.name!r} {strings.YESNO[response]}",
        ))

    @quantities.command('rename', aliases=['setname'])
    @commands.check(utils.discord.is_admin)
    async def rename_quantity(self, ctx, quantity_name: str, new_quantity_name: str):
        """Rename a quantity."""
        game = nomic.get_game(ctx)
        quantity = game.get_quantity(quantity_name)
        self._check_quantity(quantity, quantity_name)
        # TODO: check new name
        m, response = await utils.discord.get_confirm_embed(
            ctx,
            title=f"Rename quantity {quantity.name!r} to {new_quantity_name!r}?",
        )
        if response == 'y':
            async with game:
                game.quantities[new_quantity_name] = quantity
                del game.quantities[quantity.name]
        await m.edit(embed=discord.Embed(
            color=colors.YESNO[response],
            title=f"Renaming of quantity {quantity.name!r} {strings.YESNO[response]}",
        ))

    @quantities.command('setaliases')
    @commands.check(utils.discord.is_admin)
    async def set_quantity_aliases(self, ctx, quantity_name: str, *new_aliases: str):
        """Change a quantity's aliases."""
        game = nomic.get_game(ctx)
        quantity = game.get_quantity(quantity_name)
        self._check_quantity(quantity, quantity_name)
        # TODO: check new aliases
        async with game:
            quantity.aliases = new_aliases
            game.save()
        await ctx.message.add_reaction(emoji.SUCCESS)

    ########################################
    # CHANNEL COMMANDS
    ########################################

    @quantities.group('channel', aliases=['chan'])
    @commands.check(utils.discord.is_admin)
    async def channel(self, ctx):
        await utils.commands.desig_chan_show(
            ctx,
            "quantities channel",
            nomic.get_game(ctx).quantities_channel
        )

    @channel.command('set')
    async def set_channel(self, ctx, new_channel: discord.TextChannel = None):
        await utils.commands.desig_chan_set(
            ctx,
            "quantities channel",
            old_channel=nomic.get_game(ctx).quantities_channel,
            new_channel=new_channel or ctx.channel,
            callback=self._set_channel_callback,
        )

    @channel.command('unset', aliases=['reset'])
    async def unset_channel(self, ctx):
        await utils.commands.desig_chan_set(
            ctx,
            "quantities channel",
            old_channel=nomic.get_game(ctx).quantities_channel,
            new_channel=None,
            callback=self._set_channel_callback,
        )

    async def _set_channel_callback(self, ctx, new_channel=None):
        async with nomic.get_game(ctx) as game:
            game.quantities_channel = new_channel
            await game.save()

    def _check_quantity(self, quantity: Optional[nomic.Quantity], quantity_name: str):
        if not quantity:
            raise commands.UserInputError(f"No such quantity {quantity_name!r}.")

    ########################################
    # TRANSACTION COMMANDS
    ########################################

    @quantities.command('give', aliases=['+', 'inc', 'increase'], rest_is_raw=True)
    async def transact_give(self, ctx, amount: Union[int, float], quantity_name: str, user: utils.discord.MeOrMemberConverter(), *, reason: str = ''):
        """Increase the value a quantity for a player or role."""
        await self.transact(ctx, amount, quantity_name, user, reason=reason)

    @quantities.command('take', aliases=['-', 'dec', 'decrease'], rest_is_raw=True)
    async def transact_take(self, ctx, amount: Union[int, float], quantity_name: str, user: utils.discord.MeOrMemberConverter(), *, reason: str = ''):
        """Decrease the value a quantity for a player or role."""
        await self.transact(ctx, -abs(amount), quantity_name, user, reason=reason)

    @quantities.command('reset', aliases=['=0'])
    async def transact_reset(self, ctx, quantity_name: str, user: utils.discord.MeOrMemberConverter(), *, reason: str = ''):
        """Reset the value of a quantity for a player or role to ."""
        quantity = nomic.get_game(ctx).get_quantity(quantity_name)
        self._check_quantity(quantity, quantity_name)
        amount = -quantity.get(user)
        await self.transact(ctx, amount, quantity_name, user, reason=reason)

    @quantities.command('set', aliases=['='])
    async def transact_set(self, ctx, amount: Union[int, float], quantity_name: str, user: utils.discord.MeOrMemberConverter(), *, reason: str = ''):
        """Set the value of a quantity for a player or role."""
        quantity = nomic.get_game(ctx).get_quantity(quantity_name)
        self._check_quantity(quantity, quantity_name)
        amount = amount - quantity.get(user)
        await self.transact(ctx, amount, quantity_name, user, reason=reason)

    @commands.command('give', aliases=['+'])
    async def give(self, ctx, amount: Union[int, float], quantity_name: str, user: utils.discord.MeOrMemberConverter(), *, reason: str = ''):
        """See `quantity give`."""
        await self.transact(ctx, amount, quantity_name, user, reason=reason)

    @commands.command('take', aliases=['-'])
    async def take(self, ctx, amount: Union[int, float], quantity_name: str, user: utils.discord.MeOrMemberConverter(), *, reason: str = ''):
        """See `quantity take`."""
        await self.transact(ctx, -abs(amount), quantity_name, user, reason=reason)

    async def transact(self, ctx, amount: Union[int, float], quantity_name: str, user: utils.discord.MeOrMemberConverter(), *, reason: str = ''):
        game = nomic.get_game(ctx)
        quantity = game.get_quantity(quantity_name)
        self._check_quantity(quantity, quantity_name)
        positive = amount >= 0
        new_amount = quantity.get(user) + amount
        description = f"**{'+' if positive else '-'}{abs(amount)} {quantity.name}**"
        description += f" {'to' if positive else 'from'} {user.mention}"
        ask_description = description + f" (will be **{new_amount}**)"
        m, response = await utils.discord.get_confirm_embed(
            ctx,
            title=f"Authorize transaction?",
            description=ask_description,
        )
        if response == 'y':
            async with game:
                # Compute new amount again, in case the amount has changed since
                # the beginning of this function's execution.
                new_amount = quantity.get(user) + amount
                quantity.set(user, new_amount)
                await game.save()
                description += f" (now **{new_amount}**)"
        await m.edit(embed=discord.Embed(
            color=colors.YESNO[response],
            title=f"Transaction {strings.YESNO[response]}",
            description=description
        ))


def setup(bot):
    bot.add_cog(Quantities(bot))
