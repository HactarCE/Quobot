from typing import List
from discord.ext import commands
import discord

from constants import colors, strings
from nomic.game import get_game
from utils import l
import utils


class ActivePlayers(commands.Cog):
    """Commands for tracking active players."""

    name = "Active players"

    def __init__(self, bot):
        self.bot = bot

    async def record_activity(self, guild, user):
        game = get_game(guild)
        # Don't bother updating the player activity if they've been active
        # in the last ten minutes.
        diffs = game.activity_diffs
        if user not in diffs or diffs.get(user) > 60 * 10:
            game.record_activity(user)
            await game.save()
            l.info(f"Recorded activity for {utils.discord.fake_mention(user)!r} on {guild.name!r}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            await self.record_activity(message.guild, message.author)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if not user.bot:
            await self.record_activity(reaction.message.guild, user)

    @commands.group('active')
    async def active_players(self, ctx):
        """Track active players."""
        if ctx.invoked_subcommand is None:
            await utils.discord.invoke_command(ctx, 'active list')

    async def _list_players(self, ctx, users: List[discord.Member] = None, only_active: bool = False):
        game = get_game(ctx.guild)
        activity_diffs = game.activity_diffs
        hour_diffs = {k: v // (60 * 60) for k, v in activity_diffs.items()}
        cutoff = game.flags.player_activity_cutoff
        never_seen = max(0, cutoff, *hour_diffs.values()) + 1
        if not users:
            users = hour_diffs.keys()
        if only_active:
            users = (u for u in users if hour_diffs[u] <= cutoff)
        users = utils.discord.sort_users(set(users))
        users.sort(key=lambda u: hour_diffs.get(u, never_seen))
        active_count = 0
        inactive_count = 0
        active_text = ''
        inactive_text = ''
        for u in users:
            diff = hour_diffs.get(u)
            if diff is None:
                last_seen_text = "never"
            elif diff < 2:
                last_seen_text = "very recently"
            else:
                last_seen_text = f"about {utils.format_hours(diff)} ago"
            active = diff is not None and diff <= cutoff
            line = f"{u.mention} was last seen **{last_seen_text}**.\n"
            if active:
                active_count += 1
                active_text += line
            else:
                inactive_count += 1
                inactive_text += line
        active_count = f" ({active_count})" if active_count else ""
        inactive_count = f" ({inactive_count})" if inactive_count else ""
        embed = discord.Embed(
            color=colors.INFO,
        ).add_field(
            name=f"Active players{active_count}",
            value=active_text or strings.EMPTY_LIST,
            inline=False,
        )
        if inactive_text:
            embed.add_field(
                name=f"Inactive players{inactive_count}",
                value=inactive_text,
                inline=False,
            )
        embeds = utils.discord.split_embed(embed)
        for embed in embeds:
            await ctx.send(embed=embed)

    @active_players.command('listall', aliases=['la'])
    async def active_players_list_all(self, ctx):
        """List all tracked players, both active and inactive."""
        await self._list_players(ctx)

    @active_players.command('list', aliases=['l', 'ls'])
    async def active_players_list_active(self, ctx, *users: discord.Member):
        """List the specified players, or all active players."""
        await self._list_players(ctx, users, not users)

    @active_players.command('cutoff', aliases=['limit', 'threshold'])
    async def active_cutoff(self, ctx, new_cutoff_in_hours: int = None):
        """Set or view the player activity cutoff time.

        `new_cutoff_in_hours`, if specified, must be an integer number of hours.
        """
        game = get_game(ctx)
        description = f"The player activity cutoff is currently **{utils.format_hours(game.flags.player_activity_cutoff)}**."
        if new_cutoff_in_hours is None:
            if await utils.discord.is_admin(ctx):
                description += f" Use `{ctx.prefix}{ctx.invoked_with} [new_cutoff_in_hours]` to change it."
            await ctx.send(embed=discord.Embed(
                color=colors.INFO,
                title="Player activity cutoff",
                description=description,
            ))
        else:
            new_cutoff = new_cutoff_in_hours
            description += f" Change it to **{utils.format_hours(new_cutoff)}**?"
            m = await ctx.send(embed=discord.Embed(
                color=colors.INFO,
                title="Change player activity cutoff?",
                description=description,
            ))
            response = await utils.discord.get_confirm(ctx, m)
            if response == 'y':
                game.flags.player_activity_cutoff = new_cutoff
                await game.save()
            await m.edit(embed=discord.Embed(
                color=colors.YESNO[response],
                title=f"Player activity cutoff change {strings.YESNO[response]}",
            ))


def setup(bot):
    bot.add_cog(ActivePlayers(bot))
