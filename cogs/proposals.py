from discord.ext import commands
from io import StringIO
from typing import List, Optional
import asyncio
import discord

from cogs.general import invoke_command_help
from constants import colors, emoji, info, strings
import nomic
import utils
from utils import l


class ProposalConverter(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.startswith('%'):
            argument = argument[1:]
        try:
            proposal = nomic.Game(ctx).get_proposal(int(argument))
            if proposal:
                return proposal
            raise commands.UserInputError(f"Unable to fetch proposal {argument!r}")
        except (TypeError, ValueError):
            pass
        raise commands.UserInputError(f"Proposals must be referenced by integers, not whatever {argument!r} is")


class Proposals(commands.Cog):
    """Commands pertaining to proposals and voting."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return nomic.Game(ctx).ready

    @commands.group('proposals', aliases=['p', 'pr', 'prop', 'proposal'], invoke_without_command=True)
    async def proposals(self, ctx):
        """Manage proposals."""
        await invoke_command_help(ctx)

    ########################################
    # CHANNEL COMMANDS
    ########################################

    @proposals.group('channel', aliases=['chan'], invoke_without_command=True)
    @commands.check(utils.discord.is_admin)
    async def channel(self, ctx):
        """Manage the proposals channel."""
        await utils.commands.desig_chan_show(
            ctx,
            "proposals channel",
            nomic.Game(ctx).proposals_channel
        )

    @channel.command('set')
    async def set_channel(self, ctx, new_channel: discord.TextChannel = None):
        """Set the proposals channel."""
        await utils.commands.desig_chan_set(
            ctx,
            "proposals channel",
            old_channel=nomic.Game(ctx).proposals_channel,
            new_channel=new_channel or ctx.channel,
            callback=self._set_channel_callback,
        )

    @channel.command('unset', aliases=['reset'])
    async def unset_channel(self, ctx):
        """Unset the proposals channel."""
        await utils.commands.desig_chan_set(
            ctx,
            "proposals channel",
            old_channel=nomic.Game(ctx).proposals_channel,
            new_channel=None,
            callback=self._set_channel_callback,
        )

    async def _set_channel_callback(self, ctx, new_channel: Optional[discord.TextChannel] = None):
        async with nomic.Game(ctx) as game:
            game.proposals_channel = new_channel
            game.save()

    @channel.command('clean')
    async def clean_channel__channel(self, ctx, limit: int = 100):
        """Clean non-proposal messages from the proposals channel.

        limit -- Number of messages to search (0 = all)
        """
        await self._clean_channel(ctx, limit)

    @proposals.command('clean')
    async def clean_channel__proposals(self, ctx, limit: int = 100):
        """See `proposals channel clean`."""
        await self._clean_channel(ctx, limit)

    async def _clean_channel(self, ctx, limit: int = 100):
        await asyncio.sleep(1)  # Avoid ghost messages.
        game = nomic.Game(ctx)
        if not game.proposals_channel:
            await ctx.send(embed=discord.Embed(
                color=colors.ERROR,
                title="No proposals channel",
            ))
            return
        message_iter = game.proposals_channel.history(limit=limit or None)
        proposal_message_ids = set(p.message_id for p in game.proposals)
        unwanted_messages = message_iter.filter(lambda m: m.id not in proposal_message_ids)
        await utils.discord.safe_bulk_delete(await unwanted_messages.flatten())
        if ctx.channel == game.proposals_channel:
            try:
                await ctx.message.delete()
            except discord.NotFound:
                pass

    ########################################
    # MODIFYING PROPOSAL CONTENT
    ########################################

    @proposals.command('submit', aliases=['sub'], rest_is_raw=True)
    async def submit_proposal__submit(self, ctx, *, content: str):
        """Submit a new proposal.

        Example usage:
        ```
        !propose Players recieve 5 points when their proposal is passed.
        ```
        Alternatively, you can simply send a message into the proposals channel:
        ```
        Players recieve 5 points when their proposal is passed.
        ```
        """
        await self._submit_proposal(ctx, content)

    @commands.command('propose', rest_is_raw=True)
    async def submit_proposal__propose(self, ctx, *, content: str):
        """Submit a new proposal. See `proposal submit`."""
        await self._submit_proposal(ctx, content)

    @commands.Cog.listener()
    async def on_message(self, message):
        try:
            if message.author.bot:
                return  # Ignore bots.
            ctx = await self.bot.get_context(message)
            if not nomic.Game(ctx).ready:
                return
            if message.channel == nomic.Game(ctx).proposals_channel:
                prefix = await self.bot.get_prefix(message)
                if type(prefix) is list:
                    prefix = tuple(prefix)
                if message.content.startswith(prefix):
                    return  # Ignore commands.
                await message.delete()
                if message.content in strings.CONFIRM_MSGS + strings.CANCEL_MSGS:
                    return  # Ignore confirmations/cancellations.
                await self._submit_proposal(ctx, message.content)
        except Exception:
            if info.DEV:
                raise
            else:
                l.warn(f"Suppressing exception in {self.__class__.__name__}.on_message() listener")

    async def _submit_proposal(self, ctx, content: str):
        game = nomic.Game(ctx)
        if ctx.message.attachments:
            content = (await ctx.message.attachments[0].read()).decode().strip()
        else:
            content = content.strip()
        if not content:
            if ctx.channel == game.proposals_channel:
                await ctx.send(embed=discord.Embed(
                    color=colors.ERROR,
                    title="Command not needed",
                    description=f"Just write your proposal contents in {game.proposals_channel.mention}.",
                ), delete_after=5)
                return
            m, response, content = await utils.discord.query_content(
                ctx, allow_file=True,
                title="Write the contents of your new proposal here, or attach a file:",
            )
            if response != 'y':
                await utils.discord.edit_embed_for_response(
                    m, response, title_format="Proposal submission {}"
                )
                return
        self._check_proposal_content(content)
        m, response = await utils.discord.get_confirm_embed(
            ctx, title="Submit new proposal?", description=content,
        )
        if response == 'y':
            async with game:
                proposal = await game.add_proposal(
                    author=ctx.author, content=content,
                )
                await game.log_proposal_submit(ctx.author, proposal)
        if ctx.channel.id == game.proposals_channel.id:
            await m.delete()
        else:
            await utils.discord.edit_embed_for_response(
                m, response,
                title_format="Proposal submission {}",
                description=content,
            )

    @proposals.command('edit', rest_is_raw=True)
    async def edit_proposal(self, ctx, proposal: ProposalConverter, *, new_content: str):
        """Edit the contents of a proposal.

        Example usage:
        ```
        !proposal edit 23 Players recieve 5 points when their proposal is passed.
        ```
        Alternatively, you can send the new contents of the proposal in another message:
        ```
        !proposal edit 23
        ``````
        Players recieve 5 points when their proposal is passed.
        ```
        """
        if not (await utils.discord.is_admin(ctx) or ctx.author == proposal.author):
            raise commands.UserInputError("You cannot edit someone else's proposal")
        game = nomic.Game(ctx)
        if ctx.message.attachments:
            new_content = (await ctx.message.attachments[0].read()).decode().strip()
        else:
            new_content = new_content.strip()
        if not new_content:
            if ctx.channel == game.proposals_channel:
                await ctx.send(embed=discord.Embed(
                    color=colors.ERROR,
                    title="Use another channel",
                    description=f"Either include the new contents within the same message as the command, attach the new contents as a file, or use another channel to edit a proposal.",
                ), delete_after=5)
                return
            await ctx.send(embed=discord.Embed(
                color=colors.INFO,
                title=f"Current contents of {proposal}",
                description=discord.utils.escape_markdown(proposal.content),
            ))
            m, response, new_content = await utils.discord.query_content(
                ctx, allow_file=True,
                title=f"Write the new contents for {proposal} here, or attach a file:",
            )
            if response != 'y':
                await utils.discord.edit_embed_for_response(
                    m, response, title_format="Proposal edit {}"
                )
                return
        self._check_proposal_content(new_content)
        m, response = await utils.discord.get_confirm_embed(
            ctx,
            title=f"Replace contents of {proposal}?",
            description=new_content,
        )
        if response == 'y':
            async with game:
                await proposal.set_content(new_content)
                await game.log_proposal_change_content(ctx.author, proposal)
        if ctx.channel.id == game.proposals_channel.id:
            await m.delete()
        else:
            await utils.discord.edit_embed_for_response(
                m, response,
                title_format=f"Edit to {proposal} {{}}",
                description=new_content,
            )

    def _check_proposal_content(self, content):
        if len(content) > 1000:
            raise commands.UserInputError(f"Proposal content must be 1000 characters or smaller; {len(content)} is too many.")

    ########################################
    # VOTING
    ########################################

    @commands.command('vote')
    async def vote(self, ctx,
                   user: Optional[discord.abc.User],
                   amount: Optional[utils.discord.MultiplierConverter],
                   vote_type: str,
                   proposals: commands.Greedy[ProposalConverter]):
        """Vote on a proposal.

        user (optional)   -- The user whose votes to modify (defaults to command invoker)
        amount (optional) -- Amount of times to vote (defaults to `1x`)
        vote_type         -- See below
        proposals         -- Proposals on which to vote

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
        proposals channel.
        """
        vote_type = vote_type.lower()
        if amount is None:
            amount = 1
        user = user or ctx.author
        if not (await utils.discord.is_admin(ctx) or ctx.author == user):
            raise commands.UserInputError("You aren't allowed to change others' votes.")
        if vote_type not in nomic.VOTE_ALIASES:
            raise commands.UserInputError(f"Invalid vote type {vote_type!r}")
        vote_type = nomic.VOTE_ALIASES[vote_type]
        vote_func = {
            'for': nomic.Proposal.vote_for,
            'against': nomic.Proposal.vote_against,
            'abstain': nomic.Proposal.vote_abstain,
            'remove': nomic.Proposal.vote_remove,
        }[vote_type]
        game = nomic.Game(ctx)
        proposals = sorted(set(proposals))
        for proposal in proposals:
            if proposal.status != nomic.ProposalStatus.VOTING:
                raise commands.UserInputError(f"Cannot vote on {proposal} because it is closed for voting")
        failed = False
        async with game:
            for proposal in proposals:
                old_amount = proposal.votes.get(user)
                if await vote_func(proposal, user, amount):
                    new_amount = proposal.votes.get(user)
                    await game.log_proposal_vote(
                        ctx.author, proposal, user,
                        old_amount, new_amount,
                    )
                else:
                    failed = True
        try:
            if failed:
                await ctx.message.add_reaction(emoji.FAILED)
            else:
                await ctx.message.add_reaction(emoji.SUCCESS)
        except Exception:
            pass
        await self._clean_channel(ctx)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if self.bot.get_user(payload.user_id).bot:
            return  # Ignore bots.
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        ctx = await self.bot.get_context(message)
        member = ctx.guild.get_member(payload.user_id)
        game = nomic.Game(ctx)
        if game.proposals_channel and payload.channel_id == game.proposals_channel.id:
            for proposal in game.proposals:
                if proposal.message_id == payload.message_id:
                    if payload.emoji.name in emoji.VOTES:
                        vote_func = {
                            emoji.VOTE_FOR: proposal.vote_for,
                            emoji.VOTE_AGAINST: proposal.vote_against,
                            emoji.VOTE_ABSTAIN: proposal.vote_abstain_or_remove,
                        }[payload.emoji.name]
                        async with game:
                            old_amount = proposal.votes.get(member)
                            await vote_func(member)
                            new_amount = proposal.votes.get(member)
                            await game.log_proposal_vote(
                                member, proposal, member,
                                old_amount, new_amount,
                            )
                    elif payload.emoji.name in (emoji.PASS, emoji.FAIL, emoji.DELETE, emoji.REOPEN, 'pass', 'fail', 'delete', 'reopen'):
                        new_status = {
                            emoji.PASS: nomic.ProposalStatus.PASSED,
                            emoji.FAIL: nomic.ProposalStatus.FAILED,
                            emoji.DELETE: nomic.ProposalStatus.DELETED,
                            emoji.REOPEN: nomic.ProposalStatus.VOTING,
                            'pass': nomic.ProposalStatus.PASSED,
                            'fail': nomic.ProposalStatus.FAILED,
                            'delete': nomic.ProposalStatus.DELETED,
                            'reopen': nomic.ProposalStatus.VOTING,
                        }[payload.emoji.name]
                        async with game:
                            await proposal.set_status(new_status)
                            await game.log_proposal_change_status(member, proposal)
                    else:
                        await ctx.message.remove_reaction(payload.emoji, member)

    ########################################
    # MODIFYING PROPOSAL STATUS
    ########################################

    @proposals.command('pass')
    async def pass_proposal_1(self, ctx,
                              proposals: commands.Greedy[ProposalConverter]):
        """Mark one or more proposals as passed, and lock voting on them.

        Alternatively, you can react to the proposal with :white_check_mark:.
        """
        await self._set_proposal_status(ctx, nomic.ProposalStatus.PASSED, proposals)

    @proposals.command('fail')
    async def fail_proposal_1(self, ctx,
                              proposals: commands.Greedy[ProposalConverter]):
        """Mark one or more proposals as failed, and lock voting on them.

        Alternatively, you can react to the proposal with :no_entry_sign:.
        """
        await self._set_proposal_status(ctx, nomic.ProposalStatus.FAILED, proposals)

    @proposals.command('revote', aliases=['reopen'])
    async def revote_proposal_1(self, ctx,
                                proposals: commands.Greedy[ProposalConverter]):
        """Reopen one or more proposals for voting.

        Alternatively, you can react to the proposal with :ballot_box:.
        """
        await self._set_proposal_status(ctx, nomic.ProposalStatus.VOTING, proposals)

    @proposals.command('remove', aliases=['del', 'delete', 'rm'])
    async def remove_proposal_1(self, ctx,
                                proposals: commands.Greedy[ProposalConverter]):
        """Mark one or more proposals as deleted.

        Alternatively, you can react to the proposal with :wastebasket:.
        """
        await self._set_proposal_status(ctx, nomic.ProposalStatus.DELETED, proposals)

    @commands.command('pass')
    async def pass_proposal_2(self, ctx,
                              proposals: commands.Greedy[ProposalConverter]):
        """Mark one or more proposals as passed, and lock voting on them. See `proposal pass`."""
        await self._set_proposal_status(ctx, nomic.ProposalStatus.PASSED, proposals)

    @commands.command('fail')
    async def fail_proposal_2(self, ctx,
                              proposals: commands.Greedy[ProposalConverter]):
        """Mark one or more proposals as failed, and lock voting on them. See `proposal fail`."""
        await self._set_proposal_status(ctx, nomic.ProposalStatus.FAILED, proposals)

    @commands.command('revote', aliases=['reopen', 'restore'])
    async def revote_proposal_2(self, ctx,
                                proposals: commands.Greedy[ProposalConverter]):
        """Reopen one or more proposals for voting. See `proposal revote`."""
        await self._set_proposal_status(ctx, nomic.ProposalStatus.VOTING, proposals)

    @commands.command('remove', aliases=['rm', 'del'])
    async def remove_proposal_2(self, ctx,
                                proposals: commands.Greedy[ProposalConverter]):
        """Mark one or more proposals as deleted. See `proposal remove`."""
        await self._set_proposal_status(ctx, nomic.ProposalStatus.DELETED, proposals)

    async def _set_proposal_status(self, ctx,
                                   new_status: nomic.ProposalStatus,
                                   proposals: List[nomic.Proposal]):
        if not proposals:
            await invoke_command_help(ctx)
            return
        game = nomic.Game(ctx)
        proposal = sorted(set(proposals))
        try:
            async with game:
                for proposal in proposals:
                    await proposal.set_status(new_status)
                    await game.log_proposal_change_status(ctx.author, proposal)
            try:
                await ctx.message.add_reaction(emoji.SUCCESS)
            except Exception:
                pass
        except (TypeError, ValueError, discord.Forbidden):
            try:
                await ctx.message.add_reaction(emoji.FAILURE)
            except Exception:
                pass
            raise
        await self._clean_channel(ctx)

    ########################################
    # MISCELLANEOUS COMMANDS
    ########################################

    @proposals.command('permadel')
    async def permadel_proposal(self, ctx, proposal: ProposalConverter):
        """Permanently delete the most recent proposal.

        WARNING: This **cannot** be undone.
        """
        if not (await utils.discord.is_admin(ctx) or ctx.author == proposal.author):
            raise commands.UserInputError("You cannot permanently delete someone else's proposal")
        game = nomic.Game(ctx)
        if proposal.n != len(game.proposals):
            raise commands.UserInputError("Can only permanently delete most recent proposal")
        m, response = await utils.discord.get_confirm_embed(
            ctx,
            title=f"Permanently delete {proposal}?",
            content="This cannot be undone.",
        )
        await utils.discord.edit_embed_for_response(
            m, response, title_format="Permanent proposal deletion {}"
        )
        if response == 'y':
            async with game:
                await game.permadel_proposal(proposal)
                await game.log_proposal_permadel(ctx.author, proposal)
        await self._clean_channel(ctx)

    @proposals.command('info', aliases=['age', 'i', 'stat', 'stats'])
    async def proposal_info(self, ctx, *proposals: ProposalConverter):
        game = nomic.Game(ctx)
        proposals = sorted(set(proposals))
        if not proposals:
            title = "Pending proposals"
            for proposal in game.proposals:
                if proposal.status == nomic.ProposalStatus.VOTING:
                    proposals.append(proposal)
        else:
            title = "Proposals"
        if not proposals:
            raise commands.UserInputError("There are no open proposals; please specify at least one proposal")
        description = ''
        for proposal in proposals:
            age = utils.format_time_interval(
                proposal.timestamp,
                utils.now(),
                include_seconds=False,
            )
            description += f"**[#{proposal.n}]({proposal.discord_link})**"
            description += f" \N{EN DASH} **{age}**"
            description += f" \N{EN DASH} **{proposal.votes_for}** for; **{proposal.votes_against}** against"
            if proposal.votes_abstain:
                description += f"; **{proposal.votes_abstain}** abstain"
            description += "\n"
        await utils.discord.send_split_embed(ctx, discord.Embed(
            color=colors.INFO,
            title=title,
            description=description,
        ))

    @proposals.command('download', aliases=['dl'])
    async def download_proposal(self, ctx, *proposals: ProposalConverter):
        """Download the raw content of one or more proposals."""
        proposals = sorted(set(proposals))
        if not proposals:
            await invoke_command_help(ctx)
            return
        title = "Proposal download"
        description = "Proposal"
        if len(proposals) != 1:
            title += "s"
            description += "s"
        description += ' ' + ', '.join(str(p.n) for p in proposals)
        await ctx.send(files=[
            discord.File(StringIO(p.content),
                         f"proposal_{p.n}.md")
            for p in proposals
        ])

    @proposals.command('link', aliases=['ln'])
    async def link_proposal(self, ctx, *proposals: ProposalConverter):
        """Link to one or more proposals."""
        proposals = sorted(set(proposals))
        if not proposals:
            await invoke_command_help(ctx)
            return
        description = ''
        for p in proposals:
            description += f"**%{p.n}**"
            description += f" \N{EN DASH} **[on Discord]({p.discord_link})**"
            description += f" \N{EN DASH} **[on GitHub]({p.github_link})**"
            description += "\n"
        await ctx.send(embed=discord.Embed(
            color=colors.INFO,
            title="Proposal links",
            description=description,
        ))

    @proposals.command('refresh', aliases=['rf'])
    async def refresh_proposal(self, ctx, *proposals: ProposalConverter):
        """Refresh one or more proposal messages.

        This is mostly useful for fixing minor glitches, or if voting rules have
        changed.
        """
        await self.refresh_repost_proposal(ctx, proposals, False)

    @proposals.command('repost', aliases=['rp'])
    @commands.check(utils.discord.is_admin)
    async def repost_proposal(self, ctx, *proposals: ProposalConverter):
        """Repost one or more proposal messages (and all subsequent ones).

        This command may repost potentially hundreds of messages, depending on
        how many proposals there are. USE IT WISELY.
        """
        await self.refresh_repost_proposal(ctx, proposals, True)

    async def refresh_repost_proposal(self, ctx,
                                      proposals: List[nomic.Proposal],
                                      repost: bool):
        game = nomic.Game(ctx)
        try:
            async with game:
                if repost:
                    await game.repost_proposal(*proposals)
                else:
                    await game.refresh_proposal(*proposals)
            await ctx.message.add_reaction(emoji.SUCCESS)
        except (TypeError, ValueError, discord.Forbidden):
            await ctx.message.add_reaction(emoji.FAILURE)
        await self._clean_channel(ctx)


def setup(bot):
    bot.add_cog(Proposals(bot))
