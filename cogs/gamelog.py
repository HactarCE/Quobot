from datetime import datetime
from discord.ext import commands
from typing import Optional
import discord

from constants import colors, info
import nomic
import utils


class GameLog(commands.Cog):
    """Commands for viewing and interacting with game logs."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(aliases=['l', 'log', 'logging'], invoke_without_command=True, rest_is_raw=True)
    async def logs(self, ctx, *, comment):
        """Link to the game's log files or record a comment in the log.

        When invoked with no argument (`!log`), link to the game's log files.

        When invoked with text (e.g. `!log This was a triumph`), add that as a
        comment in the log files.
        """
        game = nomic.Game(ctx)
        if comment:
            # m, response = await utils.discord.get_confirm_embed(
            #     ctx,
            #     title="Record comment in log?",
            #     description=comment,
            # )
            # if response != 'y':
            #     await utils.discord.edit_embed_for_response(
            #         m, response, title_fomat="Comment {}"
            #     )
            #     return
            async with game:
                await game.log(f"{utils.discord.fake_mention(ctx.author)} commented: **{comment.strip()}**")
            # await m.edit(embed=discord.Embed(
            await ctx.send(embed=discord.Embed(
                color=colors.SUCCESS,
                title="Comment recorded",
                description=comment,
            ))
        else:
            now = datetime.utcnow()
            tree_dir = f'{info.GITHUB_REPO_LINK}/tree/{game.repo.name}/logs'
            blob_dir = f'{info.GITHUB_REPO_LINK}/blob/{game.repo.name}/logs'
            filename = now.strftime('%Y_%m') + '.md'
            header = now.strftime('%Y-%m-%d')
            description = f"Use `{ctx.prefix}{ctx.invoked_with} <comment>` to record a comment in the logs.\n\n"
            description += f"\N{BULLET} [Today's log]({blob_dir}/{filename}#{header})\n"
            # description += f"\N{BULLET} [This month's log file]({blob_dir}/{filename})\n"
            description += f"\N{BULLET} [Directory of all log files]({tree_dir})\n"
            description += "\nThe log might take a little while to update."
            await ctx.send(embed=discord.Embed(
                color=colors.INFO,
                title="Game logs",
                description=description,
            ))

    ########################################
    # CHANNEL COMMANDS
    ########################################

    @logs.group('channel', aliases=['chan'], invoke_without_command=True)
    @commands.check(utils.discord.is_admin)
    @commands.check(nomic.Game.is_ready)
    async def channel(self, ctx):
        """Manage the logs channel."""
        await utils.commands.desig_chan_show(
            ctx,
            "logs channel",
            nomic.Game(ctx).logs_channel
        )

    @channel.command('set')
    async def set_channel(self, ctx, new_channel: discord.TextChannel = None):
        """Set the logs channel."""
        await utils.commands.desig_chan_set(
            ctx,
            "logs channel",
            old_channel=nomic.Game(ctx).logs_channel,
            new_channel=new_channel or ctx.channel,
            callback=self._set_channel_callback,
        )

    @channel.command('unset', aliases=['reset'])
    async def unset_channel(self, ctx):
        """Unset the logs channel."""
        await utils.commands.desig_chan_set(
            ctx,
            "logs channel",
            old_channel=nomic.Game(ctx).logs_channel,
            new_channel=None,
            callback=self._set_channel_callback,
        )

    async def _set_channel_callback(self, ctx, new_channel: Optional[discord.TextChannel] = None):
        async with nomic.Game(ctx) as game:
            game.logs_channel = new_channel
            game.save()


def setup(bot):
    bot.add_cog(GameLog(bot))
