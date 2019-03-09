from typing import Optional, Union
import asyncio

from discord.ext import commands
import discord

from cogs.general import invoke_command_help
from constants import colors, emoji
from nomic import command_templates
from nomic.game import get_game
from utils import make_embed, YES_NO_EMBED_COLORS, YES_NO_HUMAN_RESULT, react_yes_no, is_bot_admin, invoke_command, format_discord_color


class Transactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group('currency', aliases=['$', 'c', 'cr', 'currencies', 'tr'])
    async def currency(self, ctx):
        """Manage game currencies."""
        if ctx.invoked_subcommand is None:
            await invoke_command_help(ctx)

    @currency.group('channel', aliases=['chan'])
    @commands.check(is_bot_admin)
    async def transaction_channel(self, ctx):
        """Manage the transaction channel."""
        if ctx.invoked_subcommand is ctx.command:
            await command_templates.display_designated_channel(
                ctx,
                "transaction channel",
                get_game(ctx).transaction_channel
            )

    @transaction_channel.command('reset')
    async def reset_transaction_channel(self, ctx):
        """Reset the transaction channel."""
        game = get_game(ctx)
        def deleter():
            del game.transaction_channel
            game.save()
        await command_templates.undesignate_channel(
            ctx,
            "transaction channel",
            get_game(ctx).transaction_channel,
            deleter=deleter,
            remove_warning="This could seriously mess up any existing transactions."
        )

    @transaction_channel.command('set')
    async def set_transaction_channel(self, ctx, channel: commands.TextChannelConverter=None):
        """Set the transaction channel.

        If no argument is supplied, then the current channel will be used.
        """
        game = get_game(ctx)
        def setter(new_channel):
            game.transaction_channel = new_channel
            game.save()
        await command_templates.designate_channel(
            ctx,
            "transaction channel",
            get_game(ctx).transaction_channel,
            new_channel=channel or ctx.channel,
            setter=setter,
            change_warning="This could seriously mess up any existing transactions."
        )

    @currency.command('clean')
    async def clean_transaction_channel(self, ctx, limit: int=100):
        """Clean unwanted messages from the transaction channel.

        limit -- Number of messages to search (0 = all)
        """
        game = get_game(ctx)
        if not game.transaction_channel:
            return
        message_iter = game.transaction_channel.history(limit=limit or None)
        # transaction_message_ids = set(t.get('message') for t in game.transactions)
        transaction_message_ids = set(game.transaction_messages)
        unwanted_messages = message_iter.filter(lambda m: m.id not in transaction_message_ids)
        await game.transaction_channel.delete_messages(await unwanted_messages.flatten())

    @currency.command('list')
    async def list_currencies(self, ctx, user: discord.Member = None):
        game = get_game(ctx)
        currencies = game.currencies
        if user is None:
            title = "Currency list"
        else:
            title = "Currency list for " + user.mention
        if currencies:
            description = ''
            for c in currencies.values():
                description += f"\N{BULLET} **{c['name'].capitalize()}** "
                if user is None:
                    description += f"(`{c['color']}`"
                    if c['aliases']:
                        description += "; " + ", ".join(c['aliases'])
                    description += ")\n"
                else:
                    description += f"\N{EM DASH} {c['players'].get(str(user.id), 0)}"
        else:
            description = "There are no defined currencies."
        await ctx.send(embed=make_embed(
            color=colors.EMBED_INFO,
            title=title,
            description=description
        ))

    @currency.command('add')
    @commands.check(is_bot_admin)
    async def add_currency(self, ctx, currency_name: str, color: discord.Color, *aliases: str):
        """Create a new currency."""
        game = get_game(ctx)
        currency_name = currency_name.lower()
        aliases = list(map(str.lower, aliases))
        for s in [currency_name] + aliases:
            if game.get_currency(s):
                raise discord.UserInputError(f"Currency name '{s}' is already used.")
        description = f"Color: #{format_discord_color(color)}"
        description += "\nAliases: " + ", ".join(f"`{a}`" for a in aliases)
        await ctx.send(embed=make_embed(
            color=colors.EMBED_ASK,
            title=f"Create currency '{currency_name}'?",
            description=description
        ))
        response = await react_yes_no(ctx, m)
        await m.edit(embed=make_embed(
            color=YES_NO_EMBED_COLORS[response],
            title=f"Currency '{currency_name}' established" if response else "Currency creation " + YES_NO_HUMAN_RESULT[response],
            description=description
        ))
        if response != 'y':
            return
        game.add_currency(currency_name, color=color, aliases=aliases)

    @currency.command('remove', aliases=['del', 'delete', 'rm'])
    @commands.check(is_bot_admin)
    async def remove_currency(self, ctx, currency_name: str):
        game = get_game(ctx)
        currency = game.get_currency(currency_name)
        if currency is None:
            raise commands.UserInputError(f"No such currency '{currency_name}'.")
        currency_name = currency.name
        m = await ctx.send(embed=make_embed(
            color=colors.EMBED_ASK,
            title=f"Delete currency '{currency_name}'?",
            description="Are you sure? This cannot be undone."
        ))
        response = await react_yes_no(ctx, m)
        await m.edit(embed=make_embed(
            color=YES_NO_EMBED_COLORS[response],
            title=f"Currency deletion '{currency_name}' {YES_NO_HUMAN_RESULT[response]}"
        ))
        if response == 'y':
            del game.currencies[currency_name]
            game.save()

    @currency.command('setcolor')
    @commands.check(is_bot_admin)
    async def set_currency_color(self, ctx, currency_name: str, color: discord.Color):
        game = get_game(ctx)
        currency = game.get_currency(currency_name)
        if currency is None:
            raise commands.UserInputError(f"No such currency '{currency_name}'.")
        currency['color'] = format_discord_color(color)
        game.save()
        await ctx.message.add_reaction(emoji.SUCCESS)

    @currency.command('setaliases')
    @commands.check(is_bot_admin)
    async def set_currency_aliases(self, ctx, currency_name: str, *new_aliases: str):
        game = get_game(ctx)
        currency = game.get_currency(currency_name)
        if currency is None:
            raise commands.UserInputError(f"No such currency '{currency_name}'.")
        currency['aliases'] = [s.lower() for s in new_aliases]
        game.save()
        await ctx.message.add_reaction(emoji.SUCCESS)

    @commands.command('transact', aliases=['give', 't', 'take'])
    async def transact(self, ctx, *transaction: Union[discord.Member, float, str]):
        """Make a transaction.

        Transactions are of the following form:
        ```
        give/take/transfer {<number> <currency> [from {user}] [to {user}]} [for/because <reason ...>]
        ```... where `<...>` is required, `[...]` is optionial, and `{...}` may be repeated.

        Multiple transactions can be specified in one message. Only one reason
        can be specified, and the reason must be the last thing in the message.
        Basically, just type normal English and it'll probably work.

        You can also use the special word `me` to refer to yourself. `to` or
        `from` is still required though.

        The number `all` may be used for all of a user's currency. Otherwise all
        numbers must be integers/decimals (no fractions).

        Instead of using this command, it's usually easier to just type directly
        into the transaction channel.

        Examples:
        ```
        give 10 point to @SomeUser
        take 3 points from @SomeUser
        transfer 13.6 mooncheese from @SomeUser to @SomeOtherUser
        take 1 mooncheese from @SomeUser and give it to @SomeOtherUser because @SomeOtherUser deserves it more
        ```
        """
        game = get_game(ctx)
        multiplier = 0
        amount = 0
        currency_name = None
        transactions = []
        reason = []
        for word in transaction:
            if reason:
                reason.append(word)
                continue
            if isinstance(word, int):
                amount = word
                currency_name = None
            elif isinstance(word, float):
                amount = int(word) if word.is_integer() else word
                currency_name = None
            elif isinstance(word, str):
                word = word.lower()
                if word == 'to':
                    multiplier = +1
                elif word == 'from':
                    multiplier = -1
                elif word == 'me':
                    word = ctx.author
                elif word in ('for', 'because'):
                    reason.append(word)
                elif currency_name is None and game.get_currency(word):
                    currency_name = game.get_currency(word)['name']
            elif isinstance(word, discord.Member):
                if not multiplier and amount and currency_name:
                    raise discord.UserInputError(f"Not sure what to do with {word.mention}. (Specify amount and currency.)")
                # "+10 points to"    ->  +
                # "-10 points to"    ->  -
                # "+10 points from"  ->  -
                # "-10 points from"  ->  -
                if multiplier < 0 and amount < 0:
                    multiplier = +1
                transactions.append({
                    'amount': amount * multiplier,
                    'currency_name': currency_name,
                    'user_agent_id': ctx.author.id,
                    'user_id': word.id
                })
        if not transactions:
            raise discord.UserInputError("No users specified.")
        if len(transactions) == 1:
            human_count = "transaction"
        else:
            human_count = f"{len(transactions)} transactions"
        description = '\n'.join(map(game.format_transaction, transactions))
        m = await ctx.send(embed=make_embed(
            color=colors.EMBED_ASK,
            title=f"Authorize {human_count}?",
            description=description
        ))
        response = await react_yes_no(ctx, m)
        reason = ' '.join(reason)
        if reason:
            for t in transactions:
                t['reason'] = reason
        await m.edit(embed=make_embed(
            color=YES_NO_EMBED_COLORS[response],
            title=f"{human_count.capitalize()} {YES_NO_HUMAN_RESULT[response]}",
            description=description
        ))
        if response == 'y':
            for transaction in transactions:
                await game.transact(transaction)
        await game.wait_delete_if_illegal(m)

    @commands.Cog.listener()
    async def on_message(self, message):
        try:
            if message.author.bot:
                return # Ignore bots.
            prefix = await self.bot.get_prefix(message)
            if type(prefix) is list:
                prefix = tuple(prefix)
            if message.content.startswith(prefix):
                return # Ignore commands.
            ctx = await self.bot.get_context(message)
            game = get_game(ctx)
            if message.channel.id == game.transaction_channel.id:
                content = message.content.strip()
                await message.delete()
                words = []
                for word in content.split():
                    try:
                        words.append(await commands.MemberConverter().convert(ctx, word))
                    except:
                        try:
                            words.append(float(word))
                        except:
                            words.append(word)
                try:
                    await invoke_command(ctx, 'transact', *words)
                except:
                    m = await ctx.send(embed=make_embed(
                        color=colors.EMBED_ERROR,
                        title="Error parsing transaction",
                        description=f"Check spelling/capitalization or try an explicit `!transact` command.\n```\n{content}\n```"
                    ))
                    await game.wait_delete_if_illegal(m)
        except:
            pass



def setup(bot):
    bot.add_cog(Transactions(bot))
