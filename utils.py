import logging
import traceback

import discord
from discord.ext import commands

from constants import emoji, colors

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

async def react_yes_no(ctx, m, timeout=30):
    """Recieve a yes/no response to a message via reaction.

    Returns 'y' for an affirmative response, 'n' for a negative response, and
    't' for a timeout."""
    # TODO Allow user to type '!confirm'/'!y' or '!cancel'/'!n' in addition to reactions
    emojis = [emoji.CONFIRM, emoji.CANCEL]
    emoji_letters = {emoji.CONFIRM: 'y', emoji.CANCEL: 'n'}
    for emoji in emojis:
        await m.add_reaction(emoji)
    try:
        reaction, _ = await ctx.bot.wait_for(
            'reaction_add',
            check=lambda reaction, user: (
                reaction.emoji in emoji_letters
                and reaction.message.id == m.id
                and user == ctx.message.author
            ),
            timeout=timeout,
        )
        result = emoji_letters[reaction]
    except asyncio.TimeoutError:
        result = 't'
    for emoji in emojis:
        await m.remove_reaction(emojii, ctx.me)
    return result


async def is_bot_admin(ctx):
    if await ctx.bot.is_owner(ctx.author):
        return True
    try:
        if ctx.message.author.guild_permissions.administrator:
            return True
    except:
        pass
    try:
        if ctx.message.author.id in get_guild_data(ctx.guild)['admins']:
            return True
    except:
        pass
    return False


async def report_error(bot, ctx, exc, *args, **kwargs):
    if ctx:
        if isinstance(ctx.channel, discord.DMChannel):
            guild_name = "N/A"
            channel_name = f"DM"
        elif isinstance(ctx.channel, discord.GroupChannel):
            guild_name = "N/A"
            channel_name = f"Group with {len(ctx.channel.recipients)} members (id={ctx.channel.id})"
        else:
            guild_name = ctx.guild.name
            channel_name = f"#{ctx.channel.name}"
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
    fields += [
        ("Args", f"```\n{repr(args)}\n```" if args else "None", True),
        ("Keyword Args", f"```\n{repr(kwargs)}\n```" if kwargs else "None", True),
        ("Traceback", f"```\n{tb.replace('```', '` ` `')}\n```"),
    ]
    await bot.app_info.owner.send(
        embed=make_embed(
            color=colors.EMBED_ERROR,
            title="Error",
            description=f"`{str(exc)}`",
            fields=fields,
        )
    )
