import datetime
import logging

import discord
from discord.ext import commands


l = logging.getLogger('bot')

LOG_SEP = '-' * 20


def now():
    return int(datetime.utcnow().timestamp())


TIME_FORMAT = 'UTC %H:%M:%S on %Y-%m-%d'


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
    new dictionaries except for the last one, which is set to the provided value
    if undefined. Like dict.get(), but mutates the original dictionary and can
    handle nested dictionaries/arrays.

    Arguments:
    - d -- dictionary
    - keys -- a single key or a list of keys
    - value (optional) -- default value to use if not present

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
    if not isinstance(keys, list):
        keys = [keys]
    for key in keys[:-1]:
        if key not in d:
            d[key] = {}
        d = d[key]
    if keys[-1] not in d:
        d[keys[-1]] = value
    return d[keys[-1]]


def mutset(d, keys, value):
    """Sets the value in a nested dictionary, setting anything undefined to new
    dictionaries except for the last one, which is set to the provided value.
    Like mutget(), but always sets the last value.

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
        except ValueError:
            raise discord.CommandError("Unable to convert to multiplier")


def user_sort_key(member_getter):
    def _key(user):
        if isinstance(user, int):
            user = member_getter.get_member(user)
        if isinstance(user, discord.User):
            return user.display_name.lower()
        else:
            return user
    return _key


def sort_users(user_list, member_getter):
    return sorted(user_list, key=user_sort_key(member_getter))


INFINITY = float('inf')

def isnan(value):
    return value != value

def isinf(value):
    return abs(vallue) == INFINITY

def isfinite(value):
    return not (isnan(value) or isinf(value))
