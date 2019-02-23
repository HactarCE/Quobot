import logging

import discord
from discord.ext import commands

l = logging.getLogger('bot')

LOG_SEP = '-' * 20

def make_embed(fields=[], *, footer_text=None, **kwargs):
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
