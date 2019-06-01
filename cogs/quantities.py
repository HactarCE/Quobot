from discord.ext import commands
from datetime import datetime
import discord

from constants import colors
from cogs.general import invoke_command_help
from nomic.game import get_game
import utils


class Quantities(commands.Cog):
    """Commands pertaining to currencies and transactions."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group('quantities', aliases=['$', 'c', 'currencies', 'currency', 'q', 'quan', 'quantity'])
    async def quantities(self, ctx):
        """Manage game quantities."""
        if ctx.invoked_subcommand is None:
            await invoke_command_help(ctx)

    @quantities.group('channel', aliases=['chan'])
    @commands.check(utils.discord.is_admin)
    async def channel(self, ctx):
        await utils.commands.desig_chan_show(
            ctx,
            "quantities channel",
            get_game(ctx).quantities_channel
        )

    @channel.command('set')
    async def set_channel(self, ctx, new_channel: discord.TextChannel = None):
        await utils.commands.desig_chan_set(
            ctx,
            "quantities channel",
            old_channel=get_game(ctx).quantities_channel,
            new_channel=new_channel or ctx.channel,
            callback=self._set_channel_callback,
        )

    @channel.command('unset', aliases=['reset'])
    async def unset_channel(self, ctx):
        await utils.commands.desig_chan_set(
            ctx,
            "quantities channel",
            old_channel=get_game(ctx).quantities_channel,
            new_channel=None,
            callback=self._set_channel_callback,
        )

    async def _set_channel_callback(self, ctx, new_channel=None):
        async with get_game(ctx) as game:
            game.quantities_channel = new_channel
            await game.save()


def setup(bot):
    bot.add_cog(Quantities(bot))
