import asyncio
import discord

from constants import emoji


def fake_mention(user):
    return f"{user.name}#{user.discriminator}"


def embed_field(name, value, inline=False):
    """Make an embed field."""
    return {
        'name': name,
        'value': value,
        'inline': inline,
    }


# def make_embed(*, fields=[], footer_text=None, **kwargs):
#     """Makes an embed.

#     fields=[] -- An array of lists/tuples, each taking one of the following forms:
#                  (value)
#                  (name, value)
#                  (name, value, inline)
#     *
#     footer_text=None -- The embed's footer, if any
#     **kwargs -- Any other arguments are passed to discord.Embed()
#     """
#     embed = discord.Embed(**kwargs)
#     for field in fields:
#         field = list(field)
#         if len(field) < 2:
#             field.insert(0, None)
#         if len(field) < 3:
#             field.append(False)
#         name, value, inline = field
#         embed.add_field(name=name, value=value, inline=inline)
#     if footer_text:
#         embed.set_footer(text=footer_text)
#     return embed


async def get_confirm(ctx, m, timeout=30):
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


async def is_admin(ctx):
    if await ctx.bot.is_owner(ctx.author):
        return True
    try:
        if ctx.author.guild_permissions.administrator:
            return True
    except AttributeError:
        pass
    return False


async def invoke_command(ctx, command_name_to_invoke, *args, **kwargs):
    await ctx.invoke(ctx.bot.get_command(command_name_to_invoke), *args, **kwargs)


def sort_users(user_list):
    def key(user):
        if isinstance(user, discord.User):
            return user.display_name.lower()
        else:
            return user
    return sorted(user_list, key=key)
