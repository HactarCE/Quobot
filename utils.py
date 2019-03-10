import asyncio
import logging
import traceback

import discord
from discord.ext import commands

from constants import colors, emoji, info


l = logging.getLogger('bot')

LOG_SEP = '-' * 20


def make_embed(*, fields=[], footer_text=None, **kwargs):
    """Makes an embed.

    fields=[] -- An array of lists/tuples, each taking one of the following forms:
                 (value)
                 (name, value)
                 (name, value, inline)
    *
    footer_text=None -- The embed's footer, if any
    **kwargs -- Any other arguments are passed to discord.Embed()
    """
    embed = discord.Embed(**kwargs)
    for field in fields:
        field = list(field)
        if len(field) < 2:
            field.insert(0, None)
        if len(field) < 3:
            field.append(False)
        name, value, inline = field
        embed.add_field(name=name, value=value, inline=inline)
    if footer_text:
        embed.set_footer(text=footer_text)
    return embed


YES_NO_EMBED_COLORS = {
    'y': colors.EMBED_CONFIRM,
    'n': colors.EMBED_CANCEL,
    't': colors.EMBED_TIMEOUT,
}
YES_NO_HUMAN_RESULT = {
    'y': 'confirmed',
    'n': 'cancelled',
    't': 'timed out',
}

async def react_yes_no(ctx, m, timeout=30):
    """Recieve a yes/no response to a message via reaction.

    Returns 'y' for an affirmative response, 'n' for a negative response, and
    't' for a timeout."""
    # TODO Allow user to type '!confirm'/'!y' or '!cancel'/'!n' in addition to reactions
    emojis = [emoji.CONFIRM, emoji.CANCEL]
    for e in emojis:
        await m.add_reaction(e)
    try:
        reaction, _ = await ctx.bot.wait_for(
            'reaction_add',
            check=lambda reaction, user: (
                reaction.emoji in emojis
                and reaction.message.id == m.id
                and user == ctx.author
            ),
            timeout=timeout,
        )
        result = {
            emoji.CONFIRM: 'y',
            emoji.CANCEL: 'n',
        }[reaction.emoji]
    except asyncio.TimeoutError:
        result = 't'
    for e in emojis:
        await m.remove_reaction(e, ctx.me)
    return result


async def is_bot_admin(ctx):
    if await ctx.bot.is_owner(ctx.author):
        return True
    try:
        if ctx.author.guild_permissions.administrator:
            return True
    except:
        pass
    # try:
    #     if ctx.author.id in get_guild_data(ctx.guild)['admins']:
    #         return True
    # except:
    #     pass
    return False


async def report_error(ctx, exc, *args, **kwargs):
    if info.DEV:
        for entry in traceback.format_tb(exc.__traceback__):
            for line in entry.splitlines():
                l.error(line)
        l.error('')
    else:
        if ctx:
            if isinstance(ctx.channel, discord.DMChannel):
                guild_name = "N/A"
                channel_name = f"DM"
            elif isinstance(ctx.channel, discord.GroupChannel):
                guild_name = "N/A"
                channel_name = f"Group with {len(ctx.channel.recipients)} members (id={ctx.channel.id})"
            else:
                guild_name = ctx.guild.name
                channel_name = f"{ctx.channel.mention}"
            user = ctx.author
            fields = [
                ("Guild", guild_name, True),
                ("Channel", channel_name, True),
                ("User", f"{user} (A.K.A. {user.display_name})"),
                ("Message Content", f"{ctx.message.content}"),
            ]
        else:
            fields = []
        tb = ''.join(traceback.format_tb(exc.__traceback__))
        tb = f"```\n{tb.replace('```', '` ` `')}"
        if len(tb) > 1000:
            tb = tb[:1000] + '\n```(truncated)'
        else:
            tb += '\n```'
        fields += [
            ("Args", f"```\n{repr(args)}\n```" if args else "None", True),
            ("Keyword Args", f"```\n{repr(kwargs)}\n```" if kwargs else "None", True),
            ("Traceback", tb),
        ]
        await ctx.bot.app_info.owner.send(embed=make_embed(
            color=colors.EMBED_ERROR,
            title="Error",
            description=f"`{str(exc)}`",
            fields=fields,
        ))


async def invoke_command(ctx, command_name_to_invoke, *args, **kwargs):
    await ctx.invoke(ctx.bot.get_command(command_name_to_invoke), *args, **kwargs)


def format_time_interval(timestamp1, timestamp2=0, *, include_seconds=True):
    dt = int(abs(timestamp1 - timestamp2))
    dt, seconds = dt // 60, dt % 60
    dt, minutes = dt // 60, dt % 60
    dt, hours   = dt // 24, dt % 24
    days        = dt
    s = ''
    if days:
        s += f'{days}d'
    if days or hours:
        s += f'{hours}h'
    if days or hours or minutes or not include_seconds:
        s += f'{minutes}m'
    if include_seconds:
        s += f'{seconds}s'
    return s

def format_hour_interval(hourstamp1, hourstamp2=0):
    dt = int(abs(hourstamp1 - hourstamp2))
    dt, hours = dt // 24, dt % 24
    days      = dt
    s = ''
    if days:
        s += f'{days}d'
    s += f'{hours}h'
    return s


def human_list(words, oxford_comma=True):
    words = list(words)
    if len(words) == 0:
        return "(none)"
    elif len(words) == 1:
        return words[0]
    return ", ".join(words[:-1]) + ("," if oxford_comma else '') + " and " + words[-1]


def format_discord_color(color):
    s = color if isinstance(color, str) else color.value
    return f'#{hex(s)[2:]:0>6}'


def mutget(d, keys, value=None):
    """Returns the value in a nested dictionary, setting anything undefined to
    new dictionaries except for the last one, which is set to the provided
    value if undefined. Like dict.get(), but mutates the original dictionary and can handle
    nested dictionaries/arrays.

    Examples:

    my_dict = {'a': {}}
    ensure_dict(my_dict, ['a', 'b', 'c'], 4)
    # The return value is 4.
    # my_dict is now {'a': {'b': {'c': 4}}.

    my_dict = {'a': {'b': {'c': 17}}}
    ensure_dict(my_dict, ['a', 'b', 'c'], 4)
    # The return value is 17.
    # my_dict does not change.
    """
    if not keys:
        return d
    for key in keys[:-1]:
        if key not in d:
            d[key] = {}
        d = d[key]
    if keys[-1] not in d:
        d[keys[-1]] = value
    return d[keys[-1]]

def mutset(d, keys, value):
    """Sets the value in a nested dictionary, setting anything undefined to
    new dictionaries except for the last one, which is set to the provided
    value. Like mutget(), but always sets the last value.

    Examples:

    my_dict = {'a': {}}
    ensure_dict(my_dict, ['a', 'b', 'c'], 4)
    # my_dict is now {'a': {'b': {'c': 4}}.
    # This is the same as mutget().

    my_dict = {'a': {'b': {'c': 17}}}
    ensure_dict(my_dict, ['a', 'b', 'c'], 4)
    # my_dict is now {'a': {'b': 'c': 4}}.
    # This is NOT the same as mutget().
    """
    mutget(d, keys[:-1], {})[keys[-1]] = value

def lazy_mutget(d, keys, value_lambda):
    """Like mutget(), but value is a lambda that is only evaluated if there is
    no existing value."""
    d = mutget(d, keys[:-1])
    if keys[-1] not in d:
        mutset(d, [keys[-1]], value_lambda())
    return d[keys[-1]]


class MultiplierConverter(commands.Converter):
    async def convert(self, ctx, argument):
        s = argument.lower().strip()
        try:
            if s.startswith('x'):
                return int(s[1:])
            elif s.endswith('x'):
                return int(s[:-1])
            else:
                return int(s)
        except:
            raise discord.CommandError("Unable to convert to multiplier")


def member_sort_key(guild):
    def _key(user):
        try: return guild.get_member(int(user)).display_name.lower()
        except: pass
        try: return user.display_name.lower()
        except: pass
        try: return user.lower()
        except: pass
        return user
    return _key
