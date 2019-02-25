import asyncio
from os import path

import discord
from discord.ext import commands

from constants import colors
from database import DATA_DIR, get_db
from utils import make_embed, YES_NO_EMBED_COLORS, YES_NO_HUMAN_RESULT, react_yes_no, is_bot_admin, invoke_command, mutget, mutset

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

def get_proposals(ctx):
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
        await invoke_command(ctx, 'proposal refresh', proposal_num)


class Proposals:
    def __init__(self, bot):
        self.bot = bot

    @commands.group(aliases=['pr', 'prop'])
    async def proposal(self, ctx):
        """Manage various systems pertaining to proposals."""
        if ctx.invoked_subcommand is None:
            await invoke_command_help(ctx)

    @proposal.group('channel')
    @commands.check(is_bot_admin)
    async def proposal_channel(self, ctx):
        """Manage the proposal channel."""
        if ctx.invoked_subcommand is ctx.command:
            proposal_channel = get_proposal_channel(ctx)
            if proposal_channel is None:
                description = f"There is currently no proposal channel. Use `{ctx.command.qualified_name} set [channel]` to set one."
            else:
                description = f"The current proposal channel {proposal_channel.mention}. Use `{ctx.command.qualified_name} set [channel]` to change it or `{ctx.command.qualified_name} reset` to remove it."
            await ctx.send(embed=make_embed(
                color=colors.EMBED_INFO,
                title="Proposal channel",
                description=description
            ))

    @proposal_channel.command('reset')
    async def reset_proposal_channel(self, ctx):
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

    @proposal_channel.command('set')
    async def set_proposal_channel(self, ctx, channel: commands.TextChannelConverter=None):
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

    @proposal.command('submit', aliases=['sub'], rest_is_raw=True)
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
    async def refresh_proposal(self, ctx, *proposal_nums: int):
        """Refresh one or more proposal messages.

        This is mostly useful for fixing minor glitches, or if voting rules have
        changed.
        """
        success = False
        for proposal_num in proposal_nums:
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
            try:
                await m.edit(embed=make_embed(
                    color=colors.EMBED_INFO,
                    title=f"#{proposal.get('n')}",
                    description=proposal.get('content'),
                    fields=fields,
                    footer=f"Proposed by {ctx.bot.get_user(proposal.get('author')).mention}"
                ))
                success = True
            except:
                pass
        if ctx.command.qualified_name == 'proposal refresh':
            if not proposal_nums:
                await invoke_command_help(ctx)
            elif success:
                await ctx.message.add_reaction('\N{THUMBS UP SIGN}')

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

    async def remove_proposals(self, ctx, proposal_nums):
        """Remove a number of proposals.

        proposal_nums -- Either a list of integers or the string 'all'
        """
        proposal_amount = 'ALL' if proposal_nums == 'all' else len(proposal_nums)
        proposal_pluralized = f"proposal{'s' * (len(proposal_nums) != 1)}"
        for i in range(1 + (get_proposal_count(ctx) >= 10)):
            description = [
                "Are you sure? This cannot be undone.",
                "No seriously, this is permanent. Are you sure about this?"
            ][i]
            embed = make_embed(
                color=colors.EMBED_ASK,
                title=f"Remove {proposal_amount} {proposal_pluralized}?",
                description=description
            )
            if i == 0:
                m = await ctx.send(embed=embed)
            else:
                await m.clear_reactions()
                await m.edit(embed=embed)
            response = await react_yes_no(ctx, m)
            if response != 'y':
                await m.edit(embed=make_embed(
                    color=YES_NO_EMBED_COLORS[response],
                    title=f"Proposal removal {YES_NO_HUMAN_RESULT[response]}"
                ))
                return
        if proposal_nums == 'all':
            proposal_nums = list(range(1, get_proposal_count(ctx) + 1))
        human_proposals = f"{len(proposal_nums)} proposal{'s' * (len(proposal_nums) != 1)}"
        title = f"Removing {human_proposals}\N{HORIZONTAL ELLIPSIS}"
        await m.edit(embed=make_embed(
            color=colors.EMBED_INFO,
            title=title,
            description="Removing proposals\N{HORIZONTAL ELLIPSIS}"
        ))
        number_sequence = list(range(1, get_proposal_count(ctx) + 1))
        proposals = get_proposals(ctx)
        for n in proposal_nums:
            proposal = proposals.get(str(n))
            if proposal:
                del proposals[str(n)]
                number_sequence.remove(n)
                try:
                    message = await get_proposal_channel(ctx).get_message(proposal.get('message'))
                    await message.delete()
                except:
                    pass
        set_proposal_count(ctx, len(number_sequence))
        if number_sequence:
            await m.edit(embed=make_embed(
                color=colors.EMBED_INFO,
                title=title,
                description="Renumbering remaining proposals\N{HORIZONTAL ELLIPSIS}"
            ))
            moved_proposals = []
            for i in range(len(number_sequence)):
                old_num = str(number_sequence[i])
                new_num = str(i + 1)
                if old_num != new_num:
                    proposals[new_num] = proposals[old_num]
                    del proposals[old_num]
                    proposals[new_num]['n'] = new_num
                    moved_proposals.append(new_num)
            guilds_data.save()
            await invoke_command(ctx, 'proposal refresh', *moved_proposals)
        else:
            guilds_data.save()
        await m.edit(embed=make_embed(
            color=colors.EMBED_SUCCESS,
            title=f"Removed {human_proposals}"
        ))

    @proposal.command('removeall', aliases=['deleteall'])
    async def proposal_removeall(self, ctx):
        """Remove all proposals."""
        await self.remove_proposals(ctx, 'all')

    @proposal.command('remove', aliases=['del', 'delete', 'rm'])
    @commands.check(is_bot_admin)
    async def proposal_remove(self, ctx, *proposal_nums: int):
        """Remove one or more proposals (and renumber subsequent ones accordingly)."""
        if proposal_nums:
            await self.remove_proposals(ctx, proposal_nums)
        else:
            await invoke_command_help(ctx)

    # @proposal.command()
    # async def mark_proposal(self, ctx, marking, *proposal_nums: int):


def setup(bot):
    bot.add_cog(Proposals(bot))
