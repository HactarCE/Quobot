from typing import Optional

import discord
from discord.ext import commands

from constants import colors
from database import get_db
from utils import make_embed, react_yes_no, YES_NO_EMBED_COLORS, YES_NO_HUMAN_RESULT, is_bot_admin

guilds_data = get_db('guilds')

def get_guild_data(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id not in guilds_data:
        guilds_data[guild_id] = {}
    return guilds_data[guild_id]

def get_vote_channel(ctx):
    channel_id = get_guild_data(ctx).get('vote_channel')
    try:
        return ctx.bot.get_channel(int(channel_id))
    except:
        return None


class Proposals:
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    @commands.check(is_bot_admin)
    async def votechannel(self, ctx):
        """Manage the vote channel."""
        if ctx.invoked_subcommand is None:
            vote_channel = get_vote_channel(ctx)
            if vote_channel is None:
                description = "There is currently no vote channel. Use `votechannel set [channel]` to set one."
            else:
                description = f"The current vote channel {vote_channel.mention}. Use `votechannel set [channel]` to change it or `votechannel reset` to remove it."
            await ctx.send(embed=make_embed(
                color=colors.EMBED_INFO,
                title="Vote channel",
                description=description
            ))

    @votechannel.command('reset')
    async def reset_votechannel(self, ctx):
        """Reset the vote channel."""
        vote_channel = get_vote_channel(ctx)
        if vote_channel is None:
            await ctx.send(embed=make_embed(
                color=colors.EMBED_INFO,
                title="Vote channel",
                description="There already is no vote channel."
            ))
        else:
            m = await ctx.send(embed=make_embed(
                color=colors.EMBED_ASK,
                title="Reset vote channel?",
                description="Are you sure you want to reset the vote channel? This could seriously mess up any existing proposals."
            ))
            response = await react_yes_no(ctx, m)
            if response == 'y':
                del get_guild_data(ctx)['vote_channel']
                guilds_data.save()
            await m.edit(embed=make_embed(
                color=YES_NO_EMBED_COLORS[response],
                title=f"Vote channel reset {YES_NO_HUMAN_RESULT[response]}",
                description="There is now no vote channel" if response == 'y' else None
            ))

    @votechannel.command('set')
    async def set_votechannel(self, ctx, channel: commands.TextChannelConverter=None):
        """Set the vote channel.

        If no argument is supplied, then the current channel will be used.
        """
        vote_channel = get_vote_channel(ctx)
        new_vote_channel = channel or ctx.channel
        if vote_channel and new_vote_channel.id == vote_channel.id:
            await ctx.send(embed=make_embed(
                color=colors.EMBED_INFO,
                title="Vote channel",
                description=f"{vote_channel.mention} is already the vote channel."
            ))
        else:
            if vote_channel is None:
                description = f"Set {new_vote_channel.mention} as the vote channel?"
            else:
                description = f"Change the vote channel from {vote_channel.mention} to {new_vote_channel.mention}? This could seriously mess up any existing proposals."
            m = await ctx.send(embed=make_embed(
                color=colors.EMBED_INFO,
                title=f"Set vote channel?",
                description=description
            ))
            response = await react_yes_no(ctx, m)
            if response == 'y':
                get_guild_data(ctx)['vote_channel'] = str(new_vote_channel.id)
                guilds_data.save()
                description = f"The vote channel is now {new_vote_channel.mention}."
            else:
                description = None
            title = f"Vote channel change {YES_NO_HUMAN_RESULT[response]}"
            await m.edit(embed=make_embed(
                color=YES_NO_EMBED_COLORS[response],
                title=title,
                description=description
            ))


def setup(bot):
    bot.add_cog(Proposals(bot))
