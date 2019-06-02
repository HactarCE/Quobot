from discord.ext import commands
from typing import List, Tuple
import asyncio
import discord

from constants import colors, emoji, strings


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


def embed_happened_footer(past_participle: str, user: discord.abc.User):
    return {
        'text': f"{past_participle} by {fake_mention(user)}",
        'icon_url': user.avatar_url,
    }


def _split_text(p: str, max_len: int) -> Tuple[str, str]:
    """Split text given some maximum length.

    This function will try to split at paragraph boundaries ('\n\n'), then at
    linebreaks ('\n'), then at spaces (' '), and at a last resort between words.
    """
    if len(p) < max_len:
        return p, None
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

    Inline fields that are too long will be made non-inline.
    """
    description = embed.description
    empty_embed = discord.Embed(color=embed.color)
    embeds = [discord.Embed(color=embed.color, title=embed.title)]
    while description:
        embeds[-1].description, description = _split_text(description, 2048)
        embeds.append(empty_embed.copy())
    length = len(embed.title) + len(embed.description)
    # TODO test handling of description
    field_stack = [{
        'name': field.name.strip(),
        'value': field.value.strip(),
        'inline': field.inline,
        'continued': False,
    } for field in reversed(embed.fields)]
    if not field_stack:
        del embeds[-1]
    while field_stack:
        field = field_stack.pop()
        name = field['name']
        value = field['value']
        if value and len(value) >= MAX_EMBED_VALUE:
            former, latter = _split_text(value, MAX_EMBED_VALUE)
            # This is a LIFO stack, so push the latter field first.
            field_stack.append({
                'name': name,
                'value': latter,
                'inline': False,
                'continued': True,
            })
            field_stack.append({
                'name': name,
                'value': former,
                'inline': False,
                'continued': field['continued']
            })
        else:
            field_length = len(name or '') + len(value or '')
            length += field_length
            too_many_fields = len(embeds[-1].fields) >= MAX_EMBED_FIELDS
            # Subtract footer and some extra wiggle room
            too_big_embed = length >= MAX_EMBED_TOTAL - len(embed.footer) - 10
            if too_many_fields or too_big_embed:
                embeds.append(empty_embed.copy())
                length = field_length
            if field['continued']:
                # if embed.fields:
                #     field['name'] = '\N{ZERO WIDTH SPACE}'
                # else:
                    field['name'] += strings.CONTINUED
            del field['continued']
            embeds[-1].add_field(**field)
    if len(embeds) == 1:
        embeds[0].set_footer(text=embed.footer.text, icon_url=embed.footer.icon_url)
        embeds[0].url = embed.url
        embeds[0].timestamp = embed.timestamp
    else:
        if embed.footer:
            footer_icon_url = embed.footer.icon_url
            footer_text = embed.footer.text + f" ({{}}/{len(embeds)})"
        else:
            footer_icon_url = embed.footer
            footer_text = {'text': f"{{}}/{len(embeds)}"}
        for i, new_embed in enumerate(embeds):
            new_embed.set_footer(
                text=footer_text.format(i + 1),
                icon_url=footer_icon_url,
            )
            new_embed.url = embed.url
            new_embed.timestamp = embed.timestamp
    return embeds


async def send_split_embed(ctx: commands.Context, big_embed: discord.Embed, *, typing: bool = True):
    embeds = split_embed(big_embed)
    if typing and len(embeds) > 1:
        async with ctx.typing():
            for embed in embeds[:-1]:
                await ctx.send(embed=embed)
        await ctx.send(embed=embeds[-1])
    else:
        for embed in embeds:
            await ctx.send(embed=embed)


async def get_confirm(ctx, m, *, timeout=30):
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


async def get_confirm_embed(ctx, *, timeout=30, **kwargs):
    """Send an embed, call `get_confirm()`, and return a tuple `(message,
    response)`.
    """
    m = await ctx.send(embed=discord.Embed(color=colors.ASK, **kwargs))
    return (m, await get_confirm(ctx, m, timeout=timeout))


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


def print_embed(embed):
    print()
    print(f"BEGIN EMBED (length {len(embed)})")
    for attr in ('title', 'type', 'description', 'url', 'timestamp', 'color'):
        print(f"  {attr}={getattr(embed, attr)!r}")
    print("  fields=[")
    for field in embed.fields:
        print(repr(field))
    print("  ]")
    print("END EMBED")
    print()


class MeOrMemberConverter(commands.Converter):
    async def convert(self, ctx, argument):
        if argument == 'me':
            return ctx.author
        return await commands.MemberConverter().convert(ctx, argument)


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
