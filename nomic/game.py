import asyncio
from datetime import datetime

from discord.ext import commands
import discord

from constants import colors, emoji
from utils import mutget, mutset, lazy_mutget, make_embed, format_discord_color, member_sort_key
import database
import nomic.logging


VOTE_TYPES = ('for', 'against', 'abstain')

TIME_FORMAT = 'UTC %H:%M:%S on %Y-%m-%d'

games = {}

def get_game(ctx):
    return lazy_mutget(games, [ctx.guild.id], lambda: Game(ctx))

class Game:
    def __init__(self, ctx):
        self.guild = ctx.guild
        self.guilds_database = database.get_db('guilds')
        self.guild_data = mutget(self.guilds_database, [str(self.guild.id)], {})

    def save(self):
        self.guilds_database.save()

    def _rule_property(key, default_value=None, *,
                       getter_func=lambda self, x: x, setter_func=lambda self, x: x):
        def get_val(self):
            return getter_func(self, mutget(self.guild_data, [key], default_value))
        def set_val(self, value):
            mutset(self.guild_data, [key], setter_func(self, value))
            # self.save()
        def del_val(self):
            del self.guild_data[key]
            # self.save()
        return property(get_val, set_val, del_val)

    def _add_rule_property(key, *args, **kwargs):
        setattr(Game, key, Game._rule_property(key, *args, **kwargs))

    def _try_get_channel(self, channel_id):
        try:
            return self.guild.get_channel(int(channel_id))
        except:
            return None

    def get_proposal(self, n):
        proposal = self.proposals.get(str(n))
        if proposal:
            return proposal
        else:
            raise commands.UserInputError(f"Proposal #{n} does not exist.")

    async def wait_delete_if_illegal(self, *messages):
        if messages and messages[0].channel.id in (self.proposal_channel and self.proposal_channel.id,
                                                   self.transaction_channel and self.transaction_channel.id):
            await asyncio.sleep(5)
            await messages[0].channel.delete_messages(messages)

    async def submit_proposal(self, ctx, content):
        self.proposal_count += 1
        m = await self.proposal_channel.send(embed=make_embed(
            color=colors.EMBED_INFO,
            title=f"Preparing proposal #{self.proposal_count}\N{HORIZONTAL ELLIPSIS}"
        ))
        timestamp = datetime.utcnow()
        mutset(self.guild_data, ['proposals', str(self.proposal_count)], {
            'n': self.proposal_count,
            'author': ctx.author.id,
            'content': content,
            'message': m.id,
            # 'status' can be 'voting', 'passed', or 'failed'
            'status': 'voting',
            'votes': {
                'for': {},
                'against': {},
                'abstain': {},
            },
            'timestamp': timestamp.timestamp(),
        })
        self.save()
        nomic.logging.add_to_proposal_log(self.guild,
            timestamp=timestamp,
            event_name='submit',
            user_id=ctx.author.id,
            proposal_number=self.proposal_count
        )
        await self.refresh_proposal(self.proposal_count)

    async def refresh_proposal(self, *proposal_nums):
        """Returns a tuple (succeeded, failed), where each element is a list of
        proposal numbers that were either successfully or unsuccessfully
        refreshed."""
        succeeded = []
        failed = []
        need_to_save = False
        for proposal_num in proposal_nums:
            # try:
                proposal = self.get_proposal(proposal_num)
                try:
                    m = await self.proposal_channel.get_message(int(proposal.get('message')))
                except:
                    m = None
                fields = []
                for vote_type in VOTE_TYPES:
                    votes = mutget(proposal, ['votes', vote_type])
                    vote_lines = []
                    total_vote_count = 0
                    for user_id in sorted(votes.keys(), key=member_sort_key(self.guild)):
                        vote_count = votes.get(user_id)
                        if vote_count:
                            member = self.guild.get_member(int(user_id))
                            if member:
                                line = member.mention
                                if vote_count != 1:
                                    line += f" ({vote_count}x)"
                                vote_lines.append(line)
                                total_vote_count += vote_count
                    field_name = vote_type.capitalize()
                    if total_vote_count:
                        field_name += f" ({total_vote_count})"
                    fields.append((field_name, '\n'.join(vote_lines) or "(none)", True))
                if not self.allow_abstain_vote:
                    del fields[-1]
                member = self.guild.get_member(proposal.get('author'))
                status = proposal.get('status')
                pass_fail_text = ''
                if status != 'voting':
                    pass_fail_text = "   \N{EM DASH}   "
                    pass_fail_text += status.capitalize()
                timestamp = datetime.fromtimestamp(proposal.get('timestamp'))
                embed = make_embed(
                    color={
                        'voting': colors.EMBED_INFO,
                        'passed': colors.EMBED_SUCCESS,
                        'failed': colors.EMBED_ERROR,
                    }[status],
                    title=f"Proposal #{proposal.get('n')}{pass_fail_text}",
                    description=proposal.get('content'),
                    fields=fields,
                    footer_text=f"Submitted at {timestamp.strftime(TIME_FORMAT)} by {member.name}#{member.discriminator}"
                )
                if m is None:
                    m = await self.proposal_channel.send(embed=embed)
                    proposal['message'] = m.id
                    need_to_save = True
                else:
                    await m.edit(embed=embed)
                await m.clear_reactions()
                if status == 'voting':
                    await m.add_reaction(emoji.VOTE_FOR)
                    await m.add_reaction(emoji.VOTE_AGAINST)
                    if self.allow_abstain_vote:
                        await m.add_reaction(emoji.VOTE_ABSTAIN)
                succeeded.append(proposal_num)
            # except:
            #     failed.append(proposal_num)
        if need_to_save:
            self.save()
        return (succeeded, failed)

    async def repost_proposal(self, *proposal_nums):
        try:
            start = min(map(int, proposal_nums))
            if not 1 <= start <= self.proposal_count:
                raise Exception()
        except:
            raise commands.UserInputError("Bad proposal numbers(s).")
        end = self.proposal_count + 1
        for proposal_num in range(start, end):
            proposal = self.get_proposal(proposal_num)
            try:
                await (await self.proposal_channel.get_message(proposal['message'])).delete()
            except:
                pass
            proposal['message'] = None
        await self.refresh_proposal(*range(start, end))

    async def remove_proposal(self, user, *proposal_nums, reason='', m=None):
        if m:
            human_proposals = f"{len(proposal_nums)} proposal{'s' * (len(proposal_nums) != 1)}"
            title = f"Removing {human_proposals}\N{HORIZONTAL ELLIPSIS}"
            await m.edit(embed=make_embed(
                color=colors.EMBED_INFO,
                title=title,
                description="Removing proposals\N{HORIZONTAL ELLIPSIS}"
            ))
        number_sequence = list(range(1, self.proposal_count + 1))
        for proposal_num in proposal_nums:
            proposal = self.get_proposal(proposal_num)
            del self.proposals[str(proposal_num)]
            number_sequence.remove(proposal_num)
            nomic.logging.add_to_proposal_log(self.guild,
                event_name='remove_proposal',
                user_id=user.id,
                proposal_number=proposal_num,
                reason=reason,
            )
            try:
                message = await self.proposal_channel.get_message(proposal.get('message'))
                await message.delete()
            except:
                pass
        self.proposal_count = len(number_sequence)
        if number_sequence:
            if m:
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
                    self.proposals[new_num] = self.proposals[old_num]
                    del self.proposals[old_num]
                    self.proposals[new_num]['n'] = new_num
                    moved_proposals.append(new_num)
                    nomic.logging.add_to_proposal_log(self.guild,
                        event_name='renumber',
                        user_id=user.id,
                        proposal_number=old_num,
                        new_number=new_num,
                    )
            self.save()
            await self.refresh_proposal(*moved_proposals)
        else:
            self.save()
        if m:
            await m.edit(embed=make_embed(
                color=colors.EMBED_SUCCESS,
                title=f"Removed {human_proposals}"
            ))

    async def vote(self, *, proposal_num, vote_type, user_id, user_agent_id=None, count=1, reason=''):
        """Add/change a vote to a proposal.

        *
        proposal_num  -- Number of the proposal
        vote_type     -- One of ('for', 'against', 'abstain', 'remove')
        user_id       -- User whose vote is being added/changed
        user_agent_id -- User doing the changing (defaults to same as user)
        count         -- Amount of timse to vote (defaults to 1)

        You should usually put this in a try-catch.
        """
        user_id = str(user_id)
        if count < 1:
            raise commands.UserInputError("Invalid vote count.")
        if count > 1 and not self.allow_multi_vote:
            raise commands.UserInputError("Multivoting is not allowed.")
        if vote_type == 'abstain' and not self.get_allow_abstain:
            raise commands.UserInputError("Abstaining is not allowed.")
        proposal = self.get_proposal(proposal_num)
        if proposal.get('status') != 'voting':
            raise commands.UserInputError("Voting is closed for this proposal.")
        votes = proposal.get('votes')
        voting_users = set().union(*(votes.get(k).keys() for k in VOTE_TYPES))
        if vote_type == 'remove':
            for k in VOTE_TYPES:
                if user_id in votes.get(k):
                    del votes.get(k)[user_id]
        elif vote_type in VOTE_TYPES:
            if user_id in votes.get(vote_type):
                if self.allow_multi_vote:
                    votes.get(vote_type)[user_id] += count
                else:
                    raise commands.UserInputError("Voting multiple times on one proposal is not allowed.")
            elif user_id in voting_users:
                if self.allow_change_vote:
                    for k in VOTE_TYPES:
                        kvotes = votes.get(k)
                        if user_id in kvotes:
                            kvotes[user_id] -= 1
                            if kvotes[user_id] == 0:
                                del kvotes[user_id]
                else:
                    raise commands.UserInputError("Changing votes is not allowed.")
            else:
                votes.get(vote_type)[user_id] = count
        else:
            raise commands.UserInputError("Invalid vote type.")
        self.save()
        nomic.logging.add_to_vote_log(self.guild,
            vote_type=vote_type,
            agent_id=user_agent_id,
            user_id=user_id,
            proposal_number=proposal_num,
            vote_count=count,
            reason=reason,
        )
        await self.refresh_proposal(proposal_num)

    async def set_proposal_status(self, user, new_status, *proposal_nums, reason=''):
        succeeded = []
        failed = []
        for proposal_num in proposal_nums:
            try:
                self.get_proposal(proposal_num)['status'] = new_status
                nomic.logging.add_to_proposal_log(self.guild,
                    event_name='set_' + new_status,
                    user_id=user.id,
                    proposal_number=proposal_num,
                    reason=reason,
                )
                succeeded.append(proposal_num)
            except:
                failed.append(proposal_num)
        self.save()
        await self.refresh_proposal(*proposal_nums)
        return (succeeded, failed)

    def get_currency(self, name):
        name = name.lower()
        if name in self.currencies:
            return self.currencies[name]
        for c in self.currencies.values():
            if name in c['aliases']:
                return c
        return None

    def add_currency(self, name, color, aliases=[]):
        for s in [name] + aliases:
            if self.get_currency(s):
                raise commands.UserInputError(f"The name {s} is already taken by another currency.")
        self.currencies[name] = {
            'name': name,
            'color': format_discord_color(color),
            'aliases': aliases,
            'players': {}
        }
        self.save()

    def get_transaction(self, n):
        return self.transactions[n - 1]

    def format_transaction(self, transaction, include_total=False):
        s = "**"
        amt = transaction['amount']
        if amt >= 0:
            s += "+"
        s += f"{amt} {transaction['currency_name']}**"
        s += " to " if amt >= 0 else " from "
        s += self.guild.get_member(transaction['user_id']).mention
        if include_total:
            player_amounts = self.currencies[transaction['currency_name']]['players']
            player_total = player_amounts.get(str(transaction['user_id']), 0)
            s += f" (now {player_total})"
        if transaction.get('reason'):
            s += f" {transaction.get('reason')}"
        return s

    async def transact(self, transaction, reason=''):
        amount        = transaction['amount']
        currency_name = transaction['currency_name']
        user_id       = transaction['user_id']
        user_agent_id = transaction['user_agent_id']
        timestamp     = datetime.utcnow()
        currency = self.get_currency(currency_name)
        user_agent = self.guild.get_member(user_agent_id)
        mutget(currency, ['players', str(user_id)], 0)
        currency['players'][str(user_id)] += amount
        m = await self.transaction_channel.send(embed=make_embed(
            color=int(currency.get('color')[1:], 16) or colors.EMBED_INFO,
            description=self.format_transaction(transaction, include_total=True),
            footer_text=f"Authorized at {timestamp.strftime(TIME_FORMAT)} by {user_agent.name}#{user_agent.discriminator}"
        ))
        self.transaction_messages.append(m.id)
        self.save()
        nomic.logging.add_to_transaction_log(self.guild,
            timestamp=timestamp,
            currency=currency_name,
            agent_id=user_agent_id,
            recipient_id=user_id,
            amt=amount,
            reason=reason,
        )


Game._add_rule_property('allow_abstain_vote', False)
Game._add_rule_property('allow_change_vote', False)
Game._add_rule_property('allow_multi_vote', False)
Game._add_rule_property('proposal_count', 0)
Game._add_rule_property('proposals', {})
Game._add_rule_property('proposal_channel', None,
                        getter_func=Game._try_get_channel,
                        setter_func=lambda self, channel: channel.id)
Game._add_rule_property('transaction_messages', [])
Game._add_rule_property('transaction_channel', None,
                        getter_func=Game._try_get_channel,
                        setter_func=lambda self, channel: channel.id)
Game._add_rule_property('currencies', {})
Game._add_rule_property('player_last_seen', {})
