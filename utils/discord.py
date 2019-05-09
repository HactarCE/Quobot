from typing import List, Tuple
import asyncio
import discord

from constants import emoji, strings


# https://birdie0.github.io/discord-webhooks-guide/other/field_limits.html
MAX_EMBEDS = 10
MAX_EMBED_FIELDS = 25
MAX_EMBED_VALUE = 1024
MAX_EMBED_TOTAL = 6000


def fake_mention(user):
    return f"{user.name}#{user.discriminator}"


def embed_field(name, value, inline=False):
    """Make an embed field."""
    return {
        'name': name,
        'value': value,
        'inline': inline,
    }


def _split_text(p: str, max_len: int) -> Tuple[str, str]:
    """Split text given some maximum length.

    This function will try to split at paragraph boundaries ('\n\n'), then at
    linebreaks ('\n'), then at spaces (' '), and at a last resort between words.
    """
    if len(p) < max_len:
        return p
    i = p.rfind('\n\n', 0, max_len)
    if i == -1:
        i = p.rfind('\n', 0, max_len)
    if i == -1:
        i = p.rfind(' ', 0, max_len)
    if i == -1:
        i = max_len - 1
    return p[:i], p[i:].strip()


def split_embed(embed: discord.Embed) -> List[discord.Embed]:
    """Split an embed as needed in order to avoid hitting Discord's size limits.

    This function does not account for embed titles or descriptions; only
    fields. Inline fields that are too long will be made non-inline.
    """
    footer = embed.footer or ''
    empty_embed = discord.Embed(color=embed.color)
    embeds = [discord.Embed(color=embed.color, title=embed.title)]
    length = len(embed.title)
    field_stack = [{
        'name': field.name.strip(),
        'value': field.value.strip(),
        'inline': field.inline,
    } for field in reversed(embed.fields)]
    while field_stack:
        field = field_stack.pop()
        name = field['name']
        value = field['value']
        if value and len(value) >= MAX_EMBED_VALUE:
            former, latter = _split_text(value, MAX_EMBED_VALUE)
            latter_name = name
            if not name.endswith(strings.CONTINUED):
                latter_name += strings.CONTINUED
            # This is a LIFO stack, so push the latter field first.
            field_stack.append({
                'name': latter_name,
                'value': latter,
                'inline': False
            })
            field_stack.append({
                'name': name,
                'value': former,
                'inline': False,
            })
        else:
            field_length = len(name or '') + len(value or '')
            length += field_length
            too_many_fields = len(embeds[-1].fields) >= MAX_EMBED_FIELDS
            # Subtract footer and some extra wiggle room
            too_big_embed = length >= MAX_EMBED_TOTAL - len(footer) - 10
            if too_many_fields or too_big_embed:
                embeds.append(empty_embed.copy())
            embeds[-1].add_field(**field)
    if len(embeds) == 1:
        embeds[-1].set_footer(text=footer)
    else:
        if footer:
            footer += f" ({{}}/{len(embeds)})"
        else:
            footer = f"{{}}/{len(embeds)}"
        for i, embed in enumerate(embeds):
            embed.set_footer(text=footer.format(i + 1))
    return embeds


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
        if isinstance(user, discord.abc.User):
            return user.display_name.lower()
        else:
            return user
    return sorted(user_list, key=key)
