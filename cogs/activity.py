from typing import Iterator
from discord.ext import commands
import discord

from constants import colors, strings
from nomic.game import get_game
from utils import l
import utils


class PlayerActivity(commands.Cog):
    """Commands for tracking active players."""

    name = "Player activity"

    def __init__(self, bot):
        self.bot = bot

    async def record_activity(self, ctx, user):
        game = get_game(ctx)
        # Don't bother updating the player activity if they've been active
        # in the last ten minutes.
        diffs = game.activity_diffs
        if user not in diffs or diffs.get(user) > 60 * 10:
            async with game:
                game.record_activity(user)
                l.info(f"Recorded activity for {utils.discord.fake_mention(user)!r} on {game.guild.name!r}")
                await game.save()

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            await self.record_activity(message.guild, message.author)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if not user.bot:
            await self.record_activity(reaction.message.guild, user)

    async def _list_players(self, ctx, users: Iterator[discord.abc.User] = None):
        game = get_game(ctx)
        users = set(users)
        users = utils.discord.sort_users(users)
        diffs = game.activity_diffs
        # Sort users, putting users that have never been seen at the bottom.
        diff_if_never_seen = max(diffs.values()) + 1
        users.sort(key=lambda u: diffs.get(u, diff_if_never_seen))
        active_count = 0
        inactive_count = 0
        active_text = ''
        inactive_text = ''
        for u in users:
            if u not in diffs:
                last_seen_text = "never"
            else:
                hours = diffs.get(u) // 3600
                if hours < 2:
                    last_seen_text = "very recently"
                else:
                    last_seen_text = f"about {utils.format_hours(hours)} ago"
            line = f"{u.mention} was last seen **{last_seen_text}**.\n"
            if game.is_active(u):
                active_count += 1
                active_text += line
            else:
                inactive_count += 1
                inactive_text += line
        active_count = f" ({active_count})" if active_count else ""
        inactive_count = f" ({inactive_count})" if inactive_count else ""
        embed = discord.Embed(
            color=colors.INFO,
        )
        if active_text:
            embed.add_field(
                name=f"Active players{active_count}",
                value=active_text,
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

    @commands.group('activity')
    async def activity(self, ctx):
        """Track active players."""
        if ctx.invoked_subcommand is None:
            await utils.discord.invoke_command(ctx, 'activity list')

    @activity.command('list', aliases=['l', 'ls', 'of'])
    async def active_players_list_all(self, ctx, *users: discord.abc.User):
        """List all tracked players, both active and inactive."""
        await self._list_players(ctx, users or get_game(ctx).player_activity.keys())

    @activity.command('active')
    async def activity_active(self, ctx):
        """List all active players."""
        game = get_game(ctx)
        await self._list_players(ctx, filter(game.is_active, game.player_activity))

    @activity.command('inactive')
    async def activity_inactive(self, ctx):
        """List all inactive players."""
        game = get_game(ctx)
        await self._list_players(ctx, filter(game.is_inactive, game.player_activity))

    @commands.command('active')
    async def active(self, ctx):
        """List all active players. See `activity active`."""
        await utils.discord.invoke_command(ctx, 'activity active')

    @commands.command('inactive')
    async def inactive(self, ctx):
        """List all inactive players. See `activity inactive`."""
        await utils.discord.invoke_command(ctx, 'activity inactive')

    @activity.command('cutoff', aliases=['limit', 'threshold'])
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
                async with game:
                    game.flags.player_activity_cutoff = new_cutoff
                    await game.save()
            await m.edit(embed=discord.Embed(
                color=colors.YESNO[response],
                title=f"Player activity cutoff change {strings.YESNO[response]}",
            ))


def setup(bot):
    bot.add_cog(PlayerActivity(bot))
