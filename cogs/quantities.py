from discord.ext import commands
from typing import Iterable, Union
import discord
import re

from constants import colors, emoji, strings
from cogs.general import invoke_command_help
import nomic
import utils


class QuantityConverter(commands.Converter):
    async def convert(self, ctx, argument):
        quantity = nomic.Game(ctx).get_quantity(argument)
        if quantity:
            return quantity
        raise commands.UserInputError(f"No quantity named {argument!r}")


class Quantities(commands.Cog):
    """Commands pertaining to quantities/currencies and transactions."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return nomic.Game(ctx).ready

    @commands.group('quantities', aliases=['$', 'c', 'currencies', 'currency', 'q', 'quan', 'quantity'], invoke_without_command=True)
    async def quantities(self, ctx):
        """Manage game quantities."""
        await invoke_command_help(ctx)

    ########################################
    # INFO COMMANDS
    ########################################

    @quantities.command('list', aliases=['l', 'ls'])
    async def list_quantities(self, ctx, user: utils.discord.MeOrMemberConverter() = None):
        """List all game quantities.

        If a user is supplied, list that user's value for each quantity.
        """
        game = nomic.Game(ctx)
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
    async def quantity_info(self, ctx, *quantities: QuantityConverter()):
        """List each player's values for a given quantity"""
        game = nomic.Game(ctx)
        embed = discord.Embed(color=colors.INFO)
        if not quantities:
            quantities = game.quantities.values()
        quantity_names = sorted(set(q.name for q in quantities))
        quantities = [game.get_quantity(name) for name in quantity_names]
        if len(quantities) > 1:
            embed.title = "Quantities"
        for quantity in quantities:
            value = ''
            for member, amount in quantity.players.sorted_items():
                value += f"{member.mention} has **{amount}**\n"
            embed.add_field(
                name=quantity.name.capitalize(),
                value=value or "(all players have zero)",
                inline=False,
            )
        await utils.discord.send_split_embed(ctx, embed)

    @quantities.command('new', aliases=['add', 'create'])
    @commands.check(utils.discord.is_admin)
    async def add_quantity(self, ctx, quantity_name: str, *aliases: str):
        """Create a new quantity."""
        game = nomic.Game(ctx)
        quantity_name = quantity_name.lower()
        aliases = [s.lower() for s in aliases]
        self._check_quantity_names(game, [quantity_name] + aliases)
        description = "Aliases: " + utils.human_list(f"**{s}**" for s in aliases)
        m, response = await utils.discord.get_confirm_embed(
            ctx,
            title=f"Create quantity {quantity_name!r}?",
            description=description,
        )
        if response == 'y':
            async with game:
                try:
                    quantity = game.add_quantity(quantity_name, aliases)
                    await game.log_quantity_add(ctx.author, quantity)
                except ValueError as exc:
                    raise discord.UserInputError(str(exc))
        await m.edit(embed=discord.Embed(
            color=colors.YESNO[response],
            title=f"New quantity {quantity_name!r} {strings.YESNO[response]}",
            description=description,
        ))

    @quantities.command('remove', aliases=['del', 'delete', 'rm'])
    @commands.check(utils.discord.is_admin)
    async def remove_quantity(self, ctx, quantity: QuantityConverter()):
        """Delete a quantity."""
        game = nomic.Game(ctx)
        m, response = await utils.discord.get_confirm_embed(
            ctx,
            title=f"Delete quantity {quantity.name!r}?",
            description="Are you sure? This cannot be undone.",
        )
        if response == 'y':
            async with game:
                game.remove_quantity(quantity)
                await game.log_quantity_remove(ctx.author, quantity)
        await m.edit(embed=discord.Embed(
            color=colors.YESNO[response],
            title=f"Deletion of quantity {quantity.name!r} {strings.YESNO[response]}",
        ))

    @quantities.command('rename', aliases=['setname'])
    @commands.check(utils.discord.is_admin)
    async def rename_quantity(self, ctx, quantity: QuantityConverter(), new_name: str):
        """Rename a quantity."""
        game = nomic.Game(ctx)
        new_name = new_name.lower()
        self._check_quantity_names(game, new_name, quantity)
        m, response = await utils.discord.get_confirm_embed(
            ctx,
            title=f"Rename quantity {quantity.name!r} to {new_name!r}?",
        )
        if response == 'y':
            async with game:
                old_name = quantity.name
                quantity.rename(new_name)
                await game.log_quantity_rename(ctx.author, old_name, new_name)
        await m.edit(embed=discord.Embed(
            color=colors.YESNO[response],
            title=f"Renaming of quantity {quantity.name!r} {strings.YESNO[response]}",
        ))

    @quantities.command('setaliases', aliases=['setalias'])
    @commands.check(utils.discord.is_admin)
    async def set_quantity_aliases(self, ctx, quantity: QuantityConverter(), *new_aliases: str):
        """Change a quantity's aliases."""
        game = nomic.Game(ctx)
        new_aliases = [s.lower() for s in new_aliases]
        self._check_quantity_names(game, new_aliases, quantity)
        async with game:
            old_aliases = quantity.aliases
            quantity.set_aliases(new_aliases)
            await game.log_quantity_change_aliases(ctx.author, quantity, old_aliases, quantity.aliases)
        await ctx.message.add_reaction(emoji.SUCCESS)

    ########################################
    # TRANSACTION COMMANDS
    ########################################

    @quantities.command('give', aliases=['+', 'inc', 'increase'], rest_is_raw=True)
    async def transact_give(self, ctx,
                            amount: Union[int, float],
                            quantity: QuantityConverter(),
                            user: utils.discord.MeOrMemberConverter(),
                            *, reason: str = ''):
        """Increase the value a quantity for a player or role."""
        await self.transact(ctx, amount, quantity, user, reason=reason)

    @quantities.command('take', aliases=['-', 'dec', 'decrease'], rest_is_raw=True)
    async def transact_take(self, ctx,
                            amount: Union[int, float],
                            quantity: QuantityConverter(),
                            user: utils.discord.MeOrMemberConverter(),
                            *, reason: str = ''):
        """Decrease the value a quantity for a player or role."""
        await self.transact(ctx, -abs(amount), quantity, user, reason=reason)

    @quantities.command('reset', aliases=['=0'])
    async def transact_reset(self, ctx,
                             quantity: QuantityConverter(),
                             user: utils.discord.MeOrMemberConverter(),
                             *, reason: str = ''):
        """Reset the value of a quantity for a player or role to ."""
        await self.transact(ctx, -quantity.get(user), quantity, user, reason=reason)

    @quantities.command('set', aliases=['='])
    async def transact_set(self, ctx,
                           amount: Union[int, float],
                           quantity: QuantityConverter(),
                           user: utils.discord.MeOrMemberConverter(),
                           *, reason: str = ''):
        """Set the value of a quantity for a player or role."""
        await self.transact(ctx, amount - quantity.get(user), quantity, user, reason=reason)

    @commands.command('give', aliases=['+'])
    async def give(self, ctx,
                   amount: Union[int, float],
                   quantity: QuantityConverter(),
                   user: utils.discord.MeOrMemberConverter(),
                   *, reason: str = ''):
        """See `quantity give`."""
        await self.transact(ctx, amount, quantity, user, reason=reason)

    @commands.command('take', aliases=['-'])
    async def take(self, ctx,
                   amount: Union[int, float],
                   quantity: QuantityConverter(),
                   user: utils.discord.MeOrMemberConverter(),
                   *, reason: str = ''):
        """See `quantity take`."""
        await self.transact(ctx, -abs(amount), quantity, user, reason=reason)

    async def transact(self, ctx,
                       amount: Union[int, float],
                       quantity: QuantityConverter(),
                       user: utils.discord.MeOrMemberConverter(),
                       *, reason: str = ''):
        game = nomic.Game(ctx)
        positive = amount >= 0
        old_amount = quantity.get(user)
        new_amount = old_amount + amount
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
                await game.log_quantity_set_value(ctx.author, quantity, user, old_amount, new_amount)
                description += f" (now **{new_amount}**)"
        await m.edit(embed=discord.Embed(
            color=colors.YESNO[response],
            title=f"Transaction {strings.YESNO[response]}",
            description=description
        ))

    def _check_quantity_names(self,
                              game: nomic.Game,
                              names: Union[str, Iterable[str]],
                              ignore_quantity: nomic.Quantity = None):
        if isinstance(names, str):
            names = [names]
        for name in names:
            if len(name) > 32:
                raise commands.UserInputError(f"Quantity name {name!r} is too long")
            if not re.match(r'[a-z][0-9a-z\-_]*', name):
                raise commands.UserInputError(f"Quantity name {name!r} is invalid; quantity names and aliases may only contain lowercase letters, numbers, hyphens, or underscores, and must begin with a lowercase letter")
            if not (ignore_quantity and name in ignore_quantity.aliases):
                if game.get_quantity(name):
                    raise commands.UserInputError(f"Quantity name {name!r} is already in use")


def setup(bot):
    bot.add_cog(Quantities(bot))
