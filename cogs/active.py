from datetime import datetime
from typing import Optional
import asyncio

from discord.ext import commands
import discord

from constants import colors
from nomic.game import get_game
from utils import make_embed, YES_NO_EMBED_COLORS, YES_NO_HUMAN_RESULT, react_yes_no, invoke_command, format_hour_interval, member_sort_key


def get_hourly_timestamp():
    return int(datetime.utcnow().timestamp() // 3600)


class ActivePlayers(commands.Cog):
    """Tracking active players."""

    def __init__(self, bot):
        self.bot = bot

    def last_seen_diff(self, ctx, user):
        this_hour = get_hourly_timestamp()
        last_seen_hour = get_game(ctx).player_last_seen.get(str(user.id))
        if last_seen_hour is None:
            return None
        return this_hour - last_seen_hour

    def is_active(self, ctx, user):
        last_seen_diff = self.last_seen_diff(ctx, user)
        if last_seen_diff is None:
            return None
        return last_seen_diff <= get_game(ctx).active_cutoff

    def update_last_seen(self, ctx, user):
        if self.last_seen_diff(ctx, user) != 0:
            game = get_game(ctx)
            game.player_last_seen[str(user.id)] = get_hourly_timestamp()
            game.save()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        self.update_last_seen(await self.bot.get_context(message), message.author)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return
        self.update_last_seen(await self.bot.get_context(reaction.message), user)

    @commands.group('active')
    async def active_users(self, ctx):
        if ctx.invoked_subcommand is None:
            await invoke_command(ctx, 'active list')

    @active_users.command('listall', aliases=['la'])
    async def list_all_users(self, ctx):
        """List all tracked users."""
        await invoke_command(ctx, 'active list', *map(ctx.guild.get_member, map(int, get_game(ctx).player_last_seen.keys())))

    @active_users.command('list', aliases=['l', 'ls'])
    async def list_active_users(self, ctx, *users: discord.Member):
        """List only users that are active (or those specified)."""
        game = get_game(ctx)
        description = ''
        users = list(users)
        if not users:
            for user_id in game.player_last_seen:
                try:
                    user = ctx.guild.get_member(int(user_id))
                    if self.is_active(ctx, user):
                        users.append(user)
                except:
                    pass
        users = sorted(sorted(users,
                              key=member_sort_key(ctx)),
                       key=lambda member: self.last_seen_diff(ctx, member) or 1e9)
        for user in users:
            last_seen = self.last_seen_diff(ctx, user)
            if last_seen is None:
                last_seen_text = "never"
            elif last_seen < 2:
                last_seen_text = "very recently"
            else:
                last_seen_text = f"about {format_hour_interval(self.last_seen_diff(ctx, user))} ago"
            description += f"{user.mention} was last seen **{last_seen_text}**"
            if self.is_active(ctx, user):
                description += " _(active)_"
            else:
                description += " _(inactive)_"
            description += "\n"
        await ctx.send(embed=make_embed(
            color=colors.EMBED_INFO,
            title=f"Active users ({len(users)})",
            description=description
        ))

    @active_users.command('cutoff', aliases=['limit', 'threshold'])
    async def active_cutoff(self, ctx, new_cutoff: int=None):
        """Set or view the the active user cutoff time period.

        `new_cutoff` must be specified as an integer number of hours.
        """
        game = get_game(ctx)
        description = f"The current active user cutoff is **{format_hour_interval(game.active_cutoff)}**."
        if new_cutoff is None:
            await ctx.send(embed=make_embed(
                color=colors.EMBED_INFO,
                title="Active user cutoff time",
                description=description
            ))
            return
        description += f" Change it to **{format_hour_interval(new_cutoff)}**?"
        m = await ctx.send(embed=make_embed(
            color=colors.EMBED_ASK,
            title="Change active user cutoff time?",
            description=description
        ))
        response = await react_yes_no(ctx, m)
        if response == 'y':
            game.active_cutoff = new_cutoff
            game.save()
        await m.edit(embed=make_embed(
            color=YES_NO_EMBED_COLORS[response],
            title=f"Active user cutoff time change {YES_NO_HUMAN_RESULT[response]}"
        ))


def setup(bot):
    bot.add_cog(ActivePlayers(bot))
