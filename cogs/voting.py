import asyncio
from os import path

import discord
from discord.ext import commands

from constants import colors
from database import DATA_DIR, get_db
from utils import make_embed, react_yes_no, YES_NO_EMBED_COLORS, YES_NO_HUMAN_RESULT, is_bot_admin, mutget, mutset

from cogs.general import invoke_command_help

def get_vote_log_file(ctx):
    return path.join(DATA_DIR, f'vote_log_{ctx.guild.id}.log')

guilds_data = get_db('guilds')

# def get_guild_data(ctx):
#     return mutget(guilds_data, [str(ctx.guild.id)], {})

def guild_mutget(ctx, keys, *args):
    return mutget(guilds_data, [str(ctx.guild.id)] + keys, *args)

def guild_get(ctx, *args):
    return guild_mutget(ctx, [], {}).get(*args)

def guild_mutset(ctx, keys, *args):
    return mutset(guilds_data, [str(ctx.guild.id)] + keys, *args)

def get_proposal_list(ctx):
    return guild_mutget(ctx, ['proposals'], {})

def get_proposal(ctx, proposal_num):
    return guild_mutget(ctx, ['proposals', str(proposal_num)])

def get_proposal_channel(ctx):
    try:
        return ctx.guild.get_channel(int(guild_get(ctx, 'proposal_channel')))
    except:
        return None

def get_proposal_count(ctx):
    return guild_mutget(ctx, ['proposal_count'], 0)

def set_proposal_count(ctx, new_count):
    guild_mutset(ctx, ['proposal_count'], new_count)

async def format_user_list(ctx, user_ids):
    mention_list = []
    for user_id in user_ids:
        mention_list.append(await ctx.bot.get_user(int(user_id)))
    return '\n'.join(mention_list) or "(none)"

async def submit_proposal(ctx, content):
    if get_proposal_channel(ctx) is None:
        await ctx.send(embed=make_embed(
            color=colors.EMBED_ERROR,
            title="Cannot submit proposal",
            description="There is no proposals channel"
        ))
        return
    m = await ctx.send(embed=make_embed(
        color=colors.EMBED_ASK,
        title="Submit new proposal?",
        description=content
    ))
    response = await react_yes_no(ctx, m)
    if ctx.channel.id == get_proposal_channel(ctx).id:
        await m.delete()
    else:
        await m.edit(embed=make_embed(
            color=YES_NO_EMBED_COLORS[response],
            title=f"Proposal submission {YES_NO_HUMAN_RESULT[response]}"
        ))
    if response == 'y':
        proposal_num = get_proposal_count(ctx) + 1
        set_proposal_count(ctx, proposal_num)
        m = await get_proposal_channel(ctx).send(embed=make_embed(
            color=colors.EMBED_INFO,
            title=f"Preparing proposal #{proposal_num}\N{HORIZONTAL ELLIPSIS}"
        ))
        guild_mutset(ctx, ['proposals', str(proposal_num)], {
            'n': proposal_num,
            'author': ctx.author.id,
            'content': content,
            'message': m.id,
            'votes': {
                'for': [],
                'against': [],
                'abstain': [],
            },
        })
        guilds_data.save()
        await ctx.invoke(ctx.bot.get_command('proposal refresh'), proposal_num=proposal_num)


class Proposals:
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def proposal(self, ctx):
        """Manage various systems pertaining to proposals."""
        if ctx.invoked_subcommand is None:
            await invoke_command_help(ctx)

    @proposal.group('channel')
    @commands.check(is_bot_admin)
    async def proposalchannel(self, ctx):
        """Manage the proposal channel."""
        if ctx.invoked_subcommand is ctx.command:
            proposal_channel = get_proposal_channel(ctx)
            if proposal_channel is None:
                description = "There is currently no proposal channel. Use `proposal channel set [channel]` to set one."
            else:
                description = f"The current proposal channel {proposal_channel.mention}. Use `proposal channel set [channel]` to change it or `proposal channel reset` to remove it."
            await ctx.send(embed=make_embed(
                color=colors.EMBED_INFO,
                title="Proposal channel",
                description=description
            ))

    @proposalchannel.command('reset')
    async def reset_proposalchannel(self, ctx):
        """Reset the proposal channel."""
        proposal_channel = get_proposal_channel(ctx)
        if proposal_channel is None:
            await ctx.send(embed=make_embed(
                color=colors.EMBED_INFO,
                title="Proposal channel",
                description="There already is no proposal channel."
            ))
        else:
            m = await ctx.send(embed=make_embed(
                color=colors.EMBED_ASK,
                title="Reset proposal channel?",
                description="Are you sure you want to reset the proposal channel? This could seriously mess up any existing proposals."
            ))
            response = await react_yes_no(ctx, m)
            if response == 'y':
                del guild_mutget(ctx, [], {})['proposal_channel']
                guilds_data.save()
            await m.edit(embed=make_embed(
                color=YES_NO_EMBED_COLORS[response],
                title=f"Proposal channel reset {YES_NO_HUMAN_RESULT[response]}",
                description="There is now no proposal channel" if response == 'y' else None
            ))

    @proposalchannel.command('set')
    async def set_proposalchannel(self, ctx, channel: commands.TextChannelConverter=None):
        """Set the proposal channel.

        If no argument is supplied, then the current channel will be used.
        """
        proposal_channel = get_proposal_channel(ctx)
        new_proposal_channel = channel or ctx.channel
        if proposal_channel and new_proposal_channel.id == proposal_channel.id:
            await ctx.send(embed=make_embed(
                color=colors.EMBED_INFO,
                title="Proposal channel",
                description=f"{proposal_channel.mention} is already the proposal channel."
            ))
        else:
            if proposal_channel is None:
                description = f"Set {new_proposal_channel.mention} as the proposal channel?"
            else:
                description = f"Change the proposal channel from {proposal_channel.mention} to {new_proposal_channel.mention}? This could seriously mess up any existing proposals."
            m = await ctx.send(embed=make_embed(
                color=colors.EMBED_INFO,
                title=f"Set proposal channel?",
                description=description
            ))
            response = await react_yes_no(ctx, m)
            if response == 'y':
                guild_mutset(ctx, ['proposal_channel'], str(new_proposal_channel.id))
                guilds_data.save()
                description = f"The proposal channel is now {new_proposal_channel.mention}."
            else:
                description = None
            title = f"Proposal channel change {YES_NO_HUMAN_RESULT[response]}"
            await m.edit(embed=make_embed(
                color=YES_NO_EMBED_COLORS[response],
                title=title,
                description=description
            ))

    @commands.command('propose', rest_is_raw=True)
    async def submit_proposal__propose(self, ctx, *, content):
        """Submit a proposal. See `proposal submit`."""
        await submit_proposal(ctx, content.strip())

    @proposal.command('submit', rest_is_raw=True)
    async def submit_proposal__proposal_submit(self, ctx, *, content):
        """Submit a proposal.

        Example usage:
        ```
        !propose Players recieve 5 points when their proposal is passed.
        ```

        Alternatively, you can simply send a message into the proposal channel:
        ```
        Players recieve 5 points when their proposal is passed.
        ```
        """
        await submit_proposal(ctx, content.strip())

    @proposal.command('refresh')
    async def refresh_proposal(self, ctx, proposal_num: int):
        """Refresh a proposal message.

        This is mostly useful for fixing minor glitches, or if voting rules have
        changed.
        """
        proposal = get_proposal(ctx, str(proposal_num))
        if proposal is None:
            return
        # await asyncio.sleep(5) # Give time for Discord to process the message.
        m = await get_proposal_channel(ctx).get_message(int(proposal.get('message')))
        fields = []
        for s in ["For", "Against", "Abstain"]:
            fields.append((s, await format_user_list(ctx, mutget(proposal, ['votes', s.lower()], [])), True))
        if not guild_mutget(ctx, ['allow_abstain'], False):
            del fields[-1]
        await m.edit(embed=make_embed(
            color=colors.EMBED_INFO,
            title=f"#{proposal.get('n')}",
            description=proposal.get('content'),
            fields=fields,
            footer=f"Proposed by {ctx.bot.get_user(proposal.get('author')).mention}"
        ))

    async def on_message(self, message):
        try:
            if message.author.bot:
                return # Ignore all bots.
            prefix = await self.bot.get_prefix(message)
            if type(prefix) is list:
                prefix = tuple(prefix)
            if message.content.startswith(prefix):
                return
            if message.channel.id == get_proposal_channel(message).id:
                content = message.content.strip()
                await message.delete()
                await submit_proposal(await self.bot.get_context(message), content)
        except:
            pass


def setup(bot):
    bot.add_cog(Proposals(bot))
