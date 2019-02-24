import asyncio
import os
import sys
import io
import traceback

from . import get_extensions
from discord.ext import commands
from subprocess import PIPE
from constants import colors, emoji, info
from utils import l, make_embed, react_yes_no, is_bot_admin, report_error


class Admin:
    """Admin-only commands."""

    def __init__(self, bot):
        self.bot = bot
        self.__local_check = is_bot_admin

    @commands.command(aliases=['die', 'q', 'quit'])
    async def shutdown(self, ctx):
        """Shuts down the bot.

        This command will ask the user for confirmation first. To bypass this, use the `shutdown!` command.
        """
        await self.shutdown_(ctx)

    @commands.command(name='shutdown!', aliases=['die!', 'q!', 'quit!'], hidden=True)
    async def shutdown_noconfirm(self, ctx):
        """Shuts down the bot without asking for confirmation.

        See `shutdown` for more details.
        """
        await self.shutdown_(ctx, True)

    async def shutdown_(self, ctx, noconfirm=False):
        if noconfirm:
            result = 'y'
        else:
            m = await ctx.send(
                embed=make_embed(
                    color=colors.EMBED_ASK,
                    title="Shutdown?",
                    description="This action may be difficult to undo without phsyical or remote access to the host machine. Are you sure?",
                )
            )
            result = await react_yes_no(ctx, m)
        await (ctx.send if noconfirm else m.edit)(
            embed=make_embed(
                color={
                    'y': colors.EMBED_INFO if noconfirm else colors.EMBED_CONFIRM,
                    'n': colors.EMBED_CANCEL,
                    't': colors.EMBED_TIMEOUT,
                }[result],
                title={
                    'y': "Shutting down...",
                    'n': "Shutdown cancelled.",
                    't': "Shutdown timed out.",
                }[result],
            )
        )
        if result is 'y':
            l.info(
                f"Shutting down at the command of {ctx.message.author.display_name}..."
            )
            await self.bot.logout()

    @commands.command()
    async def update(self, ctx):
        """Runs `git pull` to update the bot."""
        subproc = await asyncio.create_subprocess_exec('git', 'pull', stdout=PIPE)
        embed = make_embed(color=colors.EMBED_INFO, title="Running `git pull`")
        m = await ctx.send(embed=embed)
        returncode = await subproc.wait()
        embed.color = colors.EMBED_ERROR if returncode else colors.EMBED_SUCCESS
        stdout, stderr = await subproc.communicate()
        fields = []
        if stdout:
            embed.add_field(
                name="Stdout", value=f"```\n{stdout.decode('utf-8')}\n```", inline=False
            )
        if stderr:
            embed.add_field(
                name="Stderr", value=f"```\n{stderr.decode('utf-8')}\n```", inline=False
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
        await self.reload_(ctx, *extensions.split())

    async def reload_(self, ctx, *extensions):
        if '*' in extensions:
            title = "Reloading all extensions"
        elif len(extensions) > 1:
            title = "Reloading extensions"
        else:
            title = f"Reloading `{extensions[0]}`"
        embed = make_embed(color=colors.EMBED_INFO, title=title)
        m = await ctx.send(embed=embed)
        color = colors.EMBED_SUCCESS
        description = ""
        if "*" in extensions:
            extensions = get_extensions()
        for extension in extensions:
            self.bot.unload_extension('cogs.' + extension)
            try:
                self.bot.load_extension('cogs.' + extension)
                description += f"Successfully loaded `{extension}`.\n"
            except:
                color = colors.EMBED_ERROR
                description += f"Failed to load `{extension}`.\n"
                _, exc, _ = sys.exc_info()
                if not isinstance(exc, ImportError):
                    await report_error(self.bot, ctx, exc, *extensions)
        description += "Done."
        await m.edit(embed=make_embed(
            color=color,
            title=title.replace("ing", "ed"),
            description=description
        ))

    @commands.group()
    async def admins(self, ctx):
        if ctx.invoked_subcommand is None:
            # TODO display command help
            await ctx.send("Subcommands: `add <user>`, `remove <user>`, `list`")

    @admins.command('add')
    async def add_admin(self, ctx, member: commands.MemberConverter):
        """Add another user as a bot admin."""
        guild_data = get_guild_data(ctx.guild)
        admin_list = guild_data['admins'] = guild_data.get('admins', [])
        already_admin = member.id in admin_list
        if not already_admin:
            admin_list.append(member.id)
            guilds_data.save()
        await ctx.send(f"{formal_print_user(member)} is {'already' if already_admin else 'now'} an admin.")

    @admins.command('remove')
    async def remove_admin(self, ctx, member: commands.MemberConverter):
        guild_data = get_guild_data(ctx.guild)
        admin_list = guild_data['admins'] = guild_data.get('admins', [])
        already_not_admin = member.id not in admin_list
        if not already_not_admin:
            admin_list.remove(member.id)
            guilds_data.save()
        await ctx.send(f"{formal_print_user(member)} is {'already' if already_not_admin else 'now'} not an admin.")

    @admins.command('list')
    async def list_admins(self, ctx):
        guild_data = get_guild_data(ctx.guild)
        admin_list = guild_data['admins'] = guild_data.get('admins', [])
        if admin_list:
            user_list = map(self.bot.get_user, admin_list)
            user_list = map(formal_print_user, user_list)
            user_list = sorted(list(user_list))
        else:
            user_list = ['(nobody)']
        await ctx.send("**Current bot admins:**\n" + '\n'.join(user_list) + "\n... plus anyone with the server-wide 'Administrator' permission.")



def setup(bot):
    bot.add_cog(Admin(bot))
