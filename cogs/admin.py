import asyncio
import io
import os
import sys
import traceback
from subprocess import PIPE

from . import get_extensions
from discord.ext import commands

from constants import colors
from database import get_db
from utils import l, make_embed, YES_NO_EMBED_COLORS, YES_NO_HUMAN_RESULT, react_yes_no, is_bot_admin, report_error


async def reload_extensions(ctx, *extensions):
    if '*' in extensions:
        title = "Reloading all extensions"
    elif len(extensions) > 1:
        title = "Reloading extensions"
    else:
        title = f"Reloading `{extensions[0]}`"
    embed = make_embed(color=colors.EMBED_INFO, title=title)
    m = await ctx.send(embed=embed)
    color = colors.EMBED_SUCCESS
    description = ''
    if "*" in extensions:
        extensions = get_extensions()
    for extension in extensions:
        ctx.bot.unload_extension('cogs.' + extension)
        try:
            ctx.bot.load_extension('cogs.' + extension)
            description += f"Successfully loaded `{extension}`.\n"
        except:
            color = colors.EMBED_ERROR
            description += f"Failed to load `{extension}`.\n"
            _, exc, _ = sys.exc_info()
            if not isinstance(exc, ImportError):
                await report_error(ctx, exc, *extensions)
    description += "Done."
    await m.edit(embed=make_embed(
        color=color,
        title=title.replace("ing", "ed"),
        description=description
    ))


class Admin:
    """Admin-only commands."""

    def __init__(self, bot):
        self.bot = bot
        self.__local_check = is_bot_admin

    @commands.command(aliases=['die', 'q', 'quit'])
    async def shutdown(self, ctx):
        """Shut down the bot.

        This command will ask the user for confirmation first. To bypass this, use the `shutdown!` command.
        """
        await self.shutdown_(ctx)

    @commands.command(name='shutdown!', aliases=['die!', 'q!', 'quit!'], hidden=True)
    async def shutdown_noconfirm(self, ctx):
        """Shut down the bot without asking for confirmation.

        See `shutdown` for more details.
        """
        await self.shutdown_(ctx, True)

    async def shutdown_(self, ctx, noconfirm=False):
        if noconfirm:
            response = 'y'
        else:
            m = await ctx.send(embed=make_embed(
                color=colors.EMBED_ASK,
                title="Shutdown?",
                description="This action may be difficult to undo without phsyical or remote access to the host machine. Are you sure?",
            ))
            response = await react_yes_no(ctx, m)
        if response == 'y':
            title = "Shutting down\N{HORIZONTAL ELLIPSIS}"
        else:
            title = f"Shutdown {YES_NO_HUMAN_RESULT[response]}"
        await (ctx.send if noconfirm else m.edit)(embed=make_embed(
            color=colors.EMBED_INFO if noconfirm else YES_NO_EMBED_COLORS[response],
            title=title
        ))
        if response is 'y':
            l.info(f"Shutting down at the command of {ctx.author.display_name}...")
            await self.bot.logout()

    @commands.command()
    async def update(self, ctx):
        """Run `git pull` to update the bot."""
        subproc = await asyncio.create_subprocess_exec('git', 'pull', stdout=PIPE)
        embed = make_embed(color=colors.EMBED_INFO, title="Running `git pull`")
        m = await ctx.send(embed=embed)
        returncode = await subproc.wait()
        embed.color = colors.EMBED_ERROR if returncode else colors.EMBED_SUCCESS
        stdout, stderr = await subproc.communicate()
        fields = []
        if stdout:
            embed.add_field(
                name="Stdout",
                value=f"```\n{stdout.decode('utf-8')}\n```",
                inline=False
            )
        if stderr:
            embed.add_field(
                name="Stderr",
                value=f"```\n{stderr.decode('utf-8')}\n```",
                inline=False
            )
        if not (stdout or stderr):
            embed.description = "`git pull` completed."
        await m.edit(embed=embed)
        await self.reload_(ctx, "*")

    @commands.command(aliases=['r'])
    async def reload(self, ctx, *, extensions: str = '*'):
        """Reload an extension.

        Use `reload *` to reload all extensions.

        This command is automatically run by `update`.
        """
        await reload_extensions(ctx, *extensions.split())


def setup(bot):
    bot.add_cog(Admin(bot))
    # cog = Admin(bot)
    # cog.admins.__docstring__ = cog.admins.__docstring__.format(bot.app_info.owner.mention)
    # bot.add_cog(cog)
