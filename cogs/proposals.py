from discord.ext import commands
import asyncio
import discord

from cogs.general import invoke_command_help
from constants import info, colors
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
            raise discord.CommandError(f"Unable to fetch proposal {argument!r}")
        except (TypeError, ValueError):
            pass
        raise discord.CommandError(f"Proposals must be referenced by integers, not whatever {argument!r} is")


class Proposals(commands.Cog):
    """Commands pertaining to proposals."""

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
    # PROPOSAL CONTENT
    ########################################

    @proposals.command('submit', aliases=['sub'], rest_is_raw=True)
    async def submit_proposal__submit(self, ctx, *, content: str):
        await self._submit_proposal(ctx, content)

    @commands.command('propose', rest_is_raw=True)
    async def submit_proposal__propose(self, ctx, *, content: str):
        await self._submit_proposal(ctx, content)

    @commands.Cog.listener()
    async def on_message(self, message):
        try:
            if message.author.bot:
                return  # Ignore bots.
            ctx = await self.bot.get_context(message)
            if message.channel == nomic.get_game(ctx).proposals_channel:
                await message.delete()
                prefix = await self.bot.get_prefix(message)
                if type(prefix) is list:
                    prefix = tuple(prefix)
                if message.content.startswith(prefix):
                    return  # Ignore commands.
                content = message.content.strip()
                await self._submit_proposal(ctx, content)
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
                m, response, title_format="Proposal submission {}", description=content,
            )

    @proposals.command('edit', rest_is_raw=True)
    async def edit_proposal(self, ctx, proposal: ProposalConverter, *, new_content: str):
        if not (utils.discord.is_admin(ctx) or ctx.author == proposal.author):
            raise commands.CheckFailure("You cannot edit someone else's proposal")

    ########################################
    # PROPOSAL INFO COMMANDS
    ########################################

    @proposals.command('info', aliases=['age', 'i', 'stat', 'stats'])
    async def proposal_info(self, ctx, *proposals: ProposalConverter):
        game = nomic.get_game(ctx)
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
            description += f"[#{proposal.n}]({proposal.discord_link})"
            description += f" \N{EN DASH} {age}"
            description += f" \N{EN DASH} **{proposal.votes_for}** for; **{proposal.votes_against}** against"
            if proposal.votes_abstain:
                description += f"; **{proposal.votes_abstain}** abstain"
            description += "\n"
        await utils.discord.send_split_embed(discord.Embed(
            color=colors.INFO,
            title=title,
            description=description,
        ))


def setup(bot):
    bot.add_cog(Proposals(bot))
