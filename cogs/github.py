from datetime import datetime, timedelta
from discord.ext import commands, tasks
import asyncio
import discord

from cogs.general import invoke_command_help
from constants import colors, emoji
from utils import l
import nomic
import utils


UPLOAD_INTERVAL = 30


class GitHub(commands.Cog):
    """Commands to manage the game's GitHub repository."""

    def __init__(self, bot):
        self.bot = bot
        for game in self.games:
            asyncio.run_coroutine_threadsafe(game.setup(bot.loop), bot.loop)
        self.upload_task_ready = False
        self.upload_task.start()

    @property
    def games(self):
        """An iterator for all Nomic games that this bot manages."""
        for guild in self.bot.guilds:
            game = nomic.Game(guild)
            if game.repo.exists:
                yield game

    @tasks.loop(seconds=0)
    async def upload_task(self):
        if self.upload_task_ready:
            l.info(f"Performing periodic upload")
            for game in self.games:
                if game.flags.auto_upload:
                    async with game:
                        await asyncio.shield(game.upload_all())
        else:
            self.upload_task_ready = True
        now = datetime.now()
        future = (now + timedelta(minutes=UPLOAD_INTERVAL + 1))
        minute = future.minute // UPLOAD_INTERVAL * UPLOAD_INTERVAL + 1
        future = future.replace(minute=minute, second=0, microsecond=0)
        l.info(f"Scheduling next upload at {future.strftime('%H:%M')}")
        self.upload_task.change_interval(seconds=(future - now).seconds)

    async def cog_check(self, ctx):
        return ctx.guild and await utils.discord.is_admin(ctx)

    def cog_unload(self):
        self.upload_task.cancel()

    @commands.group(aliases=['g', 'gh', 'git'], invoke_without_command=True)
    async def github(self, ctx):
        """Manage the game's GitHub repository."""
        await invoke_command_help(ctx)

    @github.command(name='init')
    async def github_init(self, ctx):
        """Initialize the GitHub repository branch for this server."""
        await nomic.Game(ctx).setup(self.bot.loop)
        await ctx.message.add_reaction(emoji.SUCCESS)

    @github.command(name='pull')
    @commands.check(nomic.Game.is_ready)
    async def github_pull(self, ctx):
        """Pull data from the remote branch."""
        async with nomic.Game(ctx) as game:
            output = '\n'.join(await game.repo.pull())
        await ctx.send(embed=discord.Embed(
            color=colors.SUCCESS,
            title="git pull",
            description=f"```{output}```",
        ))

    @github.command(name='upload')
    @commands.check(nomic.Game.is_ready)
    async def github_upload(self, ctx):
        """Commit and push all game data.

        This happens at regular intervals automatically.
        """
        async with nomic.Game(ctx) as game:
            if await game.repo.is_ahead() or not await game.repo.is_clean():
                await game.upload_all()
                await ctx.send(embed=discord.Embed(
                    color=colors.SUCCESS,
                    title="Committed and pushed latest game data to remote",
                ))
            else:
                await ctx.send(embed=discord.Embed(
                    color=colors.ERROR,
                    title="There is nothing to commit or push.",
                ))

    @github.command(name='push')
    @commands.check(nomic.Game.is_ready)
    async def github_push(self, ctx):
        """Push data to the remote branch."""
        async with nomic.Game(ctx) as game:
            if await game.repo.is_ahead():
                await ctx.send(embed=discord.Embed(
                    color=colors.SUCCESS,
                    title="Pushed latest game data to remote",
                ))
            else:
                await ctx.send(embed=discord.Embed(
                    color=colors.ERROR,
                    title="There is nothing to push.",
                ))

    @github.command(name='status', aliases=['st'])
    @commands.check(nomic.Game.is_ready)
    async def github_status(self, ctx):
        """Display the output of `git status`."""
        async with nomic.Game(ctx) as game:
            output = '\n'.join(await game.repo.get_status(porcelain=False))
        await ctx.send(embed=discord.Embed(
            color=colors.INFO,
            title="git status",
            description=f"```{output}```",
        ))


def setup(bot):
    bot.add_cog(GitHub(bot))
