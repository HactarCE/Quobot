from discord.ext import commands
from typing import List, Optional
import asyncio
import discord

from cogs.general import invoke_command_help
from constants import colors, emoji, info
import nomic
import utils
from utils import l


class ProposalConverter(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.startswith('#'):
            argument = argument[1:]
        try:
            proposal = nomic.get_game(ctx).get_proposal(int(argument))
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

    @commands.group('proposals', aliases=['p', 'pr', 'prop', 'proposal'])
    async def proposals(self, ctx):
        if ctx.invoked_subcommand is None:
            await invoke_command_help(ctx)

    ########################################
    # CHANNEL COMMANDS
    ########################################

    @proposals.group('channel', aliases=['chan'])
    @commands.check(utils.discord.is_admin)
    async def channel(self, ctx):
        await utils.commands.desig_chan_show(
            ctx,
            "proposals channel",
            nomic.get_game(ctx).proposals_channel
        )

    @channel.command('set')
    async def set_channel(self, ctx, new_channel: discord.TextChannel = None):
        await utils.commands.desig_chan_set(
            ctx,
            "proposals channel",
            old_channel=nomic.get_game(ctx).proposals_channel,
            new_channel=new_channel or ctx.channel,
            callback=self._set_channel_callback,
        )

    @channel.command('unset', aliases=['reset'])
    async def unset_channel(self, ctx):
        await utils.commands.desig_chan_set(
            ctx,
            "proposals channel",
            old_channel=nomic.get_game(ctx).proposals_channel,
            new_channel=None,
            callback=self._set_channel_callback,
        )

    async def _set_channel_callback(self, ctx, new_channel=None):
        async with nomic.get_game(ctx) as game:
            game.proposals_channel = new_channel
            await game.save()

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

    async def _clean_channel(self, ctx, limit):
        await asyncio.sleep(3)  # Avoid ghost messages.
        game = nomic.get_game(ctx)
        if not game.proposals_channel:
            await ctx.send(embed=discord.Embed(
                color=colors.ERROR,
                title="No proposals channel",
            ))
            return
        message_iter = game.proposals_channel.history(limit=limit or None)
        proposal_message_ids = set(p.message_id for p in game.proposals)
        unwanted_messages = message_iter.filter(lambda m: m.id not in proposal_message_ids)
        try:
            await game.proposals_channel.delete_messages(await unwanted_messages.flatten())
        except discord.HTTPException:
            l.warn("Suppressing HTTPException while cleaning proposals channel")

    ########################################
    # MODIFYING PROPOSAL CONTENT
    ########################################

    @proposals.command('submit', aliases=['sub'], rest_is_raw=True)
    async def submit_proposal__submit(self, ctx, *, content: str):
        """Submit a proposal.

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
        """Submit a proposal. See `proposal submit`."""
        await self._submit_proposal(ctx, content)

    @commands.Cog.listener()
    async def on_message(self, message):
        try:
            if message.author.bot:
                return  # Ignore bots.
            ctx = await self.bot.get_context(message)
            if message.channel == nomic.get_game(ctx).proposals_channel:
                prefix = await self.bot.get_prefix(message)
                if type(prefix) is list:
                    prefix = tuple(prefix)
                if message.content.startswith(prefix):
                    return  # Ignore commands.
                await message.delete()
                await self._submit_proposal(ctx, message.content)
        except Exception:
            if info.DEV:
                raise
            else:
                l.warn(f"Suppressing exception in {self.__class__.__name__}.on_message() listener")

    async def _submit_proposal(self, ctx, content: str):
        game = nomic.get_game(ctx)
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
                ctx, title="Write the contents of your new proposal here:",
            )
            if response != 'y':
                await utils.discord.edit_embed_for_response(
                    m, response, title_format="Proposal submission {}"
                )
                return
        m, response = await utils.discord.get_confirm_embed(
            ctx, title="Submit new proposal?", description=content,
        )
        if response == 'y':
            async with game:
                new_proposal = nomic.Proposal(
                    game=game,
                    n=len(game.proposals) + 1,
                    author=ctx.author,
                    content=content,
                )
                game.proposals.append(new_proposal)
                # Game.repost_proposal() saves the gamestate so we don't have
                # to do that here.
                await game.repost_proposal(len(game.proposals))
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
            # TODO test this path
            raise commands.CheckFailure("You cannot edit someone else's proposal")
        game = nomic.get_game(ctx)
        new_content = new_content.strip()
        if not new_content:
            if ctx.channel == game.proposals_channel:
                await ctx.send(embed=discord.Embed(
                    color=colors.ERROR,
                    title="Use another channel",
                    description=f"Either include the new contents within the same message as the command, or use another channel to edit a proposal.",
                ), delete_after=5)
                return
            await ctx.send(embed=discord.Embed(
                color=colors.INFO,
                title=f"Current contents of proposal #{proposal.n}",
                content=f'```\n{proposal.content}\n```'
            ))
            m, response, new_content = await utils.discord.query_content(
                ctx, title="Write the new contents for proposal #{proposal.n} here:",
            )
            if response != 'y':
                await utils.discord.edit_embed_for_response(
                    m, response, title_format="Proposal edit {}"
                )
                return
        m, response = await utils.discord.get_confirm_embed(
            ctx,
            title=f"Replace contents of proposal #{proposal.n}?",
            description=new_content,
        )
        if response == 'y':
            async with game:
                proposal.content = new_content
                await game.refresh_proposal(proposal.n)
                await game.save()
        if ctx.channel.id == game.proposals_channel.id:
            await m.delete()
        else:
            await utils.discord.edit_embed_for_response(
                m, response,
                title_format=f"Edit to proposal #{proposal.n} {{}}",
                description=new_content,
            )

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
        proposals channel.
        """
        vote_type = vote_type.lower()
        if amount is None:
            amount = 1
        user = user or ctx.author
        if not (await utils.discord.is_admin(ctx) or ctx.author == user):
            raise commands.CheckFailure("You aren't allowed to change others' votes.")
        if vote_type not in nomic.VOTE_ALIASES:
            raise commands.UserInputError(f"Invalid vote type {vote_type!r}")
        vote_type = nomic.VOTE_ALIASES[vote_type]
        game = nomic.get_game(ctx)
        # TODO some function to do sorted(set(...)) on proposals/quantities
        # (maybe classmethod?)
        proposal_nums = sorted(set(p.n for p in proposals))
        proposals = [game.get_proposal(n) for n in proposal_nums]
        for proposal in proposals:
            if proposal.status != nomic.ProposalStatus.VOTING:
                raise discord.UserInputError(f"Cannot vote on proposal #{proposal.n} because it is closed for voting")
        async with game:
            failed = False
            for proposal in proposals:
                if not proposal.vote(user, vote_type, amount):
                    failed = True
            await game.refresh_proposal(*proposal_nums)
            await game.save()
        try:
            if failed:
                await ctx.message.add_reaction(emoji.FAILED)
            else:
                await ctx.message.add_reaction(emoji.SUCCESS)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if self.bot.get_user(payload.user_id).bot:
            return  # Ignore bots.
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        ctx = await self.bot.get_context(message)
        member = ctx.guild.get_member(payload.user_id)
        game = nomic.get_game(ctx)
        if game.proposals_channel and payload.channel_id == game.proposals_channel.id:
            for proposal in game.proposals:
                if proposal.message_id == payload.message_id:
                    try:
                        vote_type = {
                            emoji.VOTE_FOR: 'for',
                            emoji.VOTE_AGAINST: 'against',
                            emoji.VOTE_ABSTAIN: 'abstain',
                        }[payload.emoji.name]
                        async with game:
                            proposal.vote(member, vote_type)
                            await game.refresh_proposal(proposal.n)
                            await game.save()
                    except Exception:
                        await ctx.message.remove_reaction(payload.emoji, member)

    ########################################
    # MODIFYING PROPOSAL STATUS
    ########################################

    @proposals.command('pass', rest_is_raw=True)
    async def pass_proposal_1(self, ctx,
                              proposals: commands.Greedy[ProposalConverter],
                              *, reason: str):
        """Mark one or more proposals as passed, and lock voting on them."""
        self._set_proposal_status(ctx, nomic.ProposalStatus.PASSED, proposals, reason)

    @proposals.command('fail', rest_is_raw=True)
    async def fail_proposal_1(self, ctx,
                              proposals: commands.Greedy[ProposalConverter],
                              *, reason: str):
        """Mark one or more proposals as failed, and lock voting on them."""
        self._set_proposal_status(ctx, nomic.ProposalStatus.FAILED, proposals, reason)

    @proposals.command('revote', aliases=['reopen'], rest_is_raw=True)
    async def revote_proposal_1(self, ctx,
                                proposals: commands.Greedy[ProposalConverter],
                                *, reason: str):
        """Reopen one or more proposals for voting."""
        self._set_proposal_status(ctx, nomic.ProposalStatus.VOTING, proposals, reason)

    @commands.command('pass', rest_is_raw=True)
    async def pass_proposal_2(self, ctx,
                              proposals: commands.Greedy[ProposalConverter],
                              *, reason: str):
        """Mark one or more proposals as passed, and lock voting on them. See `proposal pass`."""
        self._set_proposal_status(ctx, nomic.ProposalStatus.PASSED, proposals, reason)

    @commands.command('fail', rest_is_raw=True)
    async def fail_proposal_2(self, ctx,
                              proposals: commands.Greedy[ProposalConverter],
                              *, reason: str):
        """Mark one or more proposals as failed, and lock voting on them. See `proposal fail`."""
        self._set_proposal_status(ctx, nomic.ProposalStatus.FAILED, proposals, reason)

    @commands.command('revote', aliases=['reopen', 'restore'], rest_is_raw=True)
    async def revote_proposal_2(self, ctx,
                                proposals: commands.Greedy[ProposalConverter],
                                *, reason: str):
        """Reopen one or more proposals for voting. See `proposal revote`."""
        self._set_proposal_status(ctx, nomic.ProposalStatus.VOTING, proposals, reason)

    @commands.command('remove', aliases=['rm', 'del'], rest_is_raw=True)
    async def remove_proposal(self, ctx,
                              proposals: commands.Greedy[ProposalConverter],
                              *, reason: str):
        self._set_proposal_status(ctx, nomic.ProposalStatus.DELETED, proposals, reason)

    async def _set_proposal_status(self, ctx,
                                   new_status: nomic.ProposalStatus,
                                   proposals: List[nomic.Proposal],
                                   reason: str):
        if not proposals:
            await invoke_command_help(ctx)
            return
        game = nomic.get_game(ctx)
        proposal_nums = sorted(set(p.n for p in proposals))
        proposals = [game.get_proposal(n) for n in proposal_nums]
        try:
            async with game:
                for proposal in proposals:
                    proposal.status = new_status
                game.refresh_proposal(*proposal_nums)
                game.save()
            try:
                await ctx.message.add_reaction(emoji.SUCCESS)
            except Exception:
                pass
        except (TypeError, ValueError, discord.Forbidden) as exc:
            try:
                await ctx.message.add_reaction(emoji.FAILURE)
            except Exception:
                pass
            raise

    ########################################
    # MISCELLANEOUS COMMANDS
    ########################################

    @proposals.command('info', aliases=['age', 'i', 'stat', 'stats'])
    async def proposal_info(self, ctx, *proposals: ProposalConverter):
        game = nomic.get_game(ctx)
        proposal_nums = sorted(set(p.n for p in proposals))
        proposals = [game.get_proposal(n) for n in proposal_nums]
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
        game = nomic.get_game(ctx)
        try:
            async with game:
                if repost:
                    await game.repost_proposal(*(p.n for p in proposals))
                else:
                    await game.refresh_proposal(*(p.n for p in proposals))
            await ctx.message.add_reaction(emoji.SUCCESS)
        except (TypeError, ValueError, discord.Forbidden) as exc:
            await ctx.message.add_reaction(emoji.FAILURE)
            raise


def setup(bot):
    bot.add_cog(Proposals(bot))
