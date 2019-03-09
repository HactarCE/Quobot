from typing import Optional
import asyncio

from discord.ext import commands
import discord

from cogs.general import invoke_command_help
from constants import colors, emoji
from nomic import command_templates
from nomic.game import get_game
from utils import make_embed, YES_NO_EMBED_COLORS, YES_NO_HUMAN_RESULT, react_yes_no, is_bot_admin, human_list, MultiplierConverter


class Voting:
    def __init__(self, bot):
        self.bot = bot

    @commands.group(aliases=['pr', 'prop', 'proposals'])
    async def proposal(self, ctx):
        """Manage various systems pertaining to proposals."""
        if ctx.invoked_subcommand is None:
            await invoke_command_help(ctx)

    @proposal.group('channel', aliases=['chan'])
    @commands.check(is_bot_admin)
    async def proposal_channel(self, ctx):
        """Manage the proposal channel."""
        if ctx.invoked_subcommand is ctx.command:
            await command_templates.display_designated_channel(
                ctx,
                "proposal channel",
                get_game(ctx).proposal_channel
            )

    @proposal_channel.command('reset')
    async def reset_proposal_channel(self, ctx):
        """Reset the proposal channel."""
        game = get_game(ctx)
        def deleter():
            del game.proposal_channel
            game.save()
        await command_templates.undesignate_channel(
            ctx,
            "proposal channel",
            get_game(ctx).proposal_channel,
            deleter=deleter,
            remove_warning="This could seriously mess up any existing proposals."
        )

    @proposal_channel.command('set')
    async def set_proposal_channel(self, ctx, channel: commands.TextChannelConverter=None):
        """Set the proposal channel.

        If no argument is supplied, then the current channel will be used.
        """
        game = get_game(ctx)
        def setter(new_channel):
            game.proposal_channel = new_channel
            game.save()
        await command_templates.designate_channel(
            ctx,
            "proposal channel",
            get_game(ctx).proposal_channel,
            new_channel=channel or ctx.channel,
            setter=setter,
            change_warning="This could seriously mess up any existing proposals."
        )

    @proposal.command('clean')
    async def clean_proposal_channel(self, ctx, limit: int=100):
        """Clean unwanted messages from the proposal channel.

        limit -- Number of messages to search (0 = all)
        """
        game = get_game(ctx)
        if not game.proposal_channel:
            return
        message_iter = game.proposal_channel.history(limit=limit or None)
        proposal_message_ids = set(p.get('message') for p in game.proposals.values())
        unwanted_messages = message_iter.filter(lambda m: m.id not in proposal_message_ids)
        await game.proposal_channel.delete_messages(await unwanted_messages.flatten())

    @proposal.command('refresh')
    async def refresh_proposal(self, ctx, *proposal_nums: int):
        """Refresh one or more proposal messages.

        This is mostly useful for fixing minor glitches, or if voting rules have
        changed.
        """
        if not proposal_nums:
            await invoke_command_help(ctx)
            return
        game = get_game(ctx)
        succeeded, failed = await game.refresh_proposal(*proposal_nums)
        description = ''
        if succeeded:
            if len(succeeded) == 1:
                description += f"Proposal {succeeded[0]} succeessfully refreshed.\n"
            else:
                description += f"{len(succeeded)}/{len(proposal_nums)} proposal messages succeessfully refreshed.\n"
        if failed:
            description += f"Proposal{'' if len(failed) == 1 else 's'} {human_list(map(str, failed))} failed.\n"
        m = await ctx.send(embed=make_embed(
            color=colors.EMBED_ERROR if failed else colors.EMBED_SUCCESS,
            title="Refreshed proposal messages",
            description=description
        ))
        await game.wait_delete_if_illegal(ctx.message, m)

    @proposal.command('repost')
    @commands.check(is_bot_admin)
    async def repost_proposal(self, ctx, *proposal_nums: int):
        """Repost one or more proposal messages (and all subsequent ones).

        This command may repost potentially hundreds of messages, depending on
        how many proposals there are. USE IT WISELY.
        """
        if not proposal_nums:
            await invoke_command_help(ctx)
            return
        game = get_game(ctx)
        await game.repost_proposal(*proposal_nums)
        await game.wait_delete_if_illegal(ctx.message)

    async def _submit_proposal(self, ctx, content):
        game = get_game(ctx)
        m = await ctx.send(embed=make_embed(
            color=colors.EMBED_ASK,
            title="Submit new proposal?",
            description=content
        ))
        response = await react_yes_no(ctx, m)
        if ctx.channel.id == game.proposal_channel.id:
            await m.delete()
        else:
            await m.edit(embed=make_embed(
                color=YES_NO_EMBED_COLORS[response],
                title=f"Proposal submission {YES_NO_HUMAN_RESULT[response]}"
            ))
        if response != 'y':
            return
        await game.submit_proposal(ctx, content.strip())

    @commands.command('propose', rest_is_raw=True)
    async def submit_proposal__propose(self, ctx, *, content):
        """Submit a proposal. See `proposal submit`."""
        await self._submit_proposal(ctx, content.strip())

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
        await self._submit_proposal(ctx, content.strip())

    async def on_message(self, message):
        try:
            if message.author.bot:
                return # Ignore bots.
            prefix = await self.bot.get_prefix(message)
            if type(prefix) is list:
                prefix = tuple(prefix)
            if message.content.startswith(prefix):
                return # Ignore commands.
            ctx = await self.bot.get_context(message)
            if message.channel.id == get_game(ctx).proposal_channel.id:
                content = message.content.strip()
                await message.delete()
                await self._submit_proposal(ctx, content)
        except:
            pass

    @proposal.command('remove', aliases=['del', 'delete', 'rm'], rest_is_raw=True)
    @commands.check(is_bot_admin)
    async def proposal_remove(self, ctx, proposal_nums: commands.Greedy[int], *, reason):
        """Remove one or more proposals (and renumber subsequent ones accordingly).

        proposal_nums -- A list of proposal numbers to remove
        reason -- Justification for removal (applies to all proposals removed)
        """
        if not proposal_nums:
            await invoke_command_help(ctx)
            return
        game = get_game(ctx)
        proposal_amount = 'ALL' if proposal_nums == 'all' else len(proposal_nums)
        proposal_pluralized = f"proposal{'s' * (len(proposal_nums) != 1)}"
        for i in range(1 + (game.proposal_count >= 10)):
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
        # if proposal_nums == 'all':
        #     proposal_nums = list(range(1, game.proposal_count + 1))
        game = get_game(ctx)
        await game.remove_proposal(ctx.author, *proposal_nums, reason=reason, m=m)
        await game.wait_delete_if_illegal(ctx.message, m)

    async def _set_proposal_statuses(self, ctx, new_status, proposal_nums, reason=''):
        if not proposal_nums:
            await invoke_command_help(ctx)
            return
        game = get_game(ctx)
        succeeded, failed = await game.set_proposal_status(ctx.author, new_status, *proposal_nums, reason=reason)
        if succeeded:
            await ctx.message.add_reaction(emoji.SUCCESS)
        if failed:
            await ctx.message.add_reaction(emoji.FAILURE)
        await game.wait_delete_if_illegal(ctx.message)

    @proposal.command('revote', rest_is_raw=True)
    async def revote_proposal(self, ctx, proposal_nums: commands.Greedy[int], *, reason=''):
        """Reopen one or more proposals for voting."""
        await self._set_proposal_statuses(ctx, 'voting', proposal_nums, reason)

    @proposal.command('pass', rest_is_raw=True)
    async def pass_proposal(self, ctx, proposal_nums: commands.Greedy[int], *, reason=''):
        """Mark one or more proposals as passed, and lock voting on them."""
        await self._set_proposal_statuses(ctx, 'passed', proposal_nums, reason)

    @proposal.command('fail', rest_is_raw=True)
    async def fail(self, ctx, proposal_nums: commands.Greedy[int], *, reason=''):
        """Mark one or more proposals as failed, and lock voting on them."""
        await self._set_proposal_statuses(ctx, 'failed', proposal_nums, reason)

    @commands.command('revote', rest_is_raw=True)
    async def revote_proposal2(self, ctx, proposal_nums: commands.Greedy[int], *, reason=''):
        """Reopen one or more proposals for voting. See `proposal revote`."""
        await self._set_proposal_statuses(ctx, 'voting', proposal_nums, reason)

    @commands.command('pass', rest_is_raw=True)
    async def pass_proposal2(self, ctx, proposal_nums: commands.Greedy[int], *, reason=''):
        """Mark one or more proposals as passed, and lock voting on them. See `proposal pass`."""
        await self._set_proposal_statuses(ctx, 'passed', proposal_nums, reason)

    @commands.command('fail', rest_is_raw=True)
    async def fail_proposal2(self, ctx, proposal_nums: commands.Greedy[int], *, reason=''):
        """Mark one or more proposals as failed, and lock voting on them. See `proposal fail`."""
        await self._set_proposal_statuses(ctx, 'failed', proposal_nums, reason)

    @commands.command('vote', rest_is_raw=True)
    async def vote(self, ctx, user: Optional[discord.User], amount: Optional[MultiplierConverter], vote_type: str, proposal_nums: commands.Greedy[int], *, reason=''):
        """Vote on a proposal.

        user (optional)   -- The user whose votes to modify (defaults to command invoker)
        amount (optional) -- Amount of times to vote (defaults to `1x`)
        vote_type         -- See below
        proposal_nums     -- IDs of proposals on which to vote
        reason (optional) -- Justification for vote (applies to all votes)

        Valid vote types:
        - `for` (aliases: `+`)
        - `against` (aliases: `-`)
        - `abstain`
        - `remove` (aliases: `del`, `delete`, `rm`)

        Example usages:
        ```
        !vote for 14 16
        !vote 2x against 11
        !vote @SomeUser remove 12
        !vote 3x @SomeUser for 13 15 20
        ```
        Alternatively, you can simply react to a proposal message in the
        proposal channel.
        """
        # User input errors will be handled and displayed to the user elsewhere.
        vote_type = vote_type.lower()
        if amount is None:
            amount = 1
        user = user or ctx.author
        if user.id != self.bot.user.id and not await is_bot_admin(ctx):
            raise commands.MissingPermissions("You aren't allowed to change others' votes.")
        if vote_type in ('for', '+'):
            vote_type = 'for'
        elif vote_type in ('against', '-'):
            vote_type = 'against'
        elif vote_type in ('abstain'):
            vote_type = 'abstain'
        elif vote_type in ('remove', 'del', 'delete', 'rm'):
            vote_type = 'remove'
        else:
            raise commands.UserInputError("Invalid vote type.")
        game = get_game(ctx)
        for proposal_num in proposal_nums:
            await game.vote(
                proposal_num=proposal_num,
                vote_type=vote_type,
                user_id=user.id,
                user_agent_id=ctx.author.id,
                count=amount,
                reason=reason,
            )
        await ctx.message.add_reaction(emoji.SUCCESS)
        await game.wait_delete_if_illegal(ctx.message)

    async def on_raw_reaction_add(self, payload):
        ctx = await self.bot.get_context(await self.bot.get_channel(payload.channel_id).get_message(payload.message_id))
        game = get_game(ctx)
        if game.proposal_channel and payload.channel_id != game.proposal_channel.id:
            return
        if ctx.bot.get_user(payload.user_id).bot:
            return
        for proposal in game.proposals.values():
            if proposal.get('message') == payload.message_id:
                try:
                    vote_type = {
                        emoji.VOTE_FOR: 'for',
                        emoji.VOTE_AGAINST: 'against',
                        emoji.VOTE_ABSTAIN: 'abstain',
                    }[payload.emoji.name]
                    await game.vote(
                        proposal_num=proposal['n'],
                        vote_type=vote_type,
                        user_id=payload.user_id,
                    )
                except:
                    await ctx.message.remove_reaction(payload.emoji, ctx.guild.get_member(payload.user_id))


def setup(bot):
    bot.add_cog(Voting(bot))
