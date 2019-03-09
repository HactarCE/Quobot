import asyncio

from discord.ext import commands

from constants import colors
from utils import make_embed, react_yes_no, YES_NO_EMBED_COLORS, YES_NO_HUMAN_RESULT


async def display_designated_channel(ctx, channel_name, current_channel):
    if current_channel is None:
        description = f"There is currently no {channel_name}. Use `{ctx.command.qualified_name} set [channel]` to set one."
    else:
        description = f"The current {channel_name} {current_channel.mention}. Use `{ctx.command.qualified_name} set [channel]` to change it or `{ctx.command.qualified_name} reset` to remove it."
    await ctx.send(embed=make_embed(
        color=colors.EMBED_INFO,
        title=channel_name.capitalize(),
        description=description
    ))

async def undesignate_channel(ctx, channel_name, current_channel, *, deleter, remove_warning=''):
    if current_channel is None:
        await ctx.send(embed=make_embed(
            color=colors.EMBED_INFO,
            title=channel_name.capitalize(),
            description=f"There already is no {channel_name}."
        ))
    else:
        m = await ctx.send(embed=make_embed(
            color=colors.EMBED_ASK,
            title=f"Reset {channel_name}?",
            description=f"Are you sure you want to reset the {channel_name}? {remove_warning}"
        ))
        response = await react_yes_no(ctx, m)
        if response == 'y':
            deleter()
        await m.edit(embed=make_embed(
            color=YES_NO_EMBED_COLORS[response],
            title=f"{channel_name.capitalize()} reset {YES_NO_HUMAN_RESULT[response]}",
            description=f"There is now no {channel_name}" if response == 'y' else None
        ))

async def designate_channel(ctx, channel_name, current_channel, *, new_channel, setter, change_warning=''):
    if current_channel and new_channel.id == current_channel.id:
        await ctx.send(embed=make_embed(
            color=colors.EMBED_INFO,
            title=channel_name.capitalize(),
            description=f"{current_channel.mention} is already the {channel_name}."
        ))
    else:
        if current_channel is None:
            description = f"Set {new_channel.mention} as the {channel_name}?"
        else:
            description = f"Change the {channel_name} from {current_channel.mention} to {new_channel.mention}? {change_warning}"
        m = await ctx.send(embed=make_embed(
            color=colors.EMBED_INFO,
            title=f"Set {channel_name}?",
            description=description
        ))
        response = await react_yes_no(ctx, m)
        if response == 'y':
            setter(new_channel)
            description = f"The {channel_name} is now {new_channel.mention}."
        else:
            description = None
        title = f"{channel_name.capitalize()} change {YES_NO_HUMAN_RESULT[response]}"
        await m.edit(embed=make_embed(
            color=YES_NO_EMBED_COLORS[response],
            title=title,
            description=description
        ))




# # TODO Do I want to follow through with this?

# def channel_designation_command(command_name, command_args, command_kwargs, *, parent_command=commands, getter, **kwargs):
#     """Keyword arguments:

#     - command_name
#     - command_args
#     - command_kwargs
#     - *
#     - parent_command (optional; defaults to discord.ext.commands)
#     - channel_name (human-friendly string)
#     - getter (function)
#     - setter (function taking one arg)
#     - deleter (function)
#     - change_warning (human-friendly string; optional)
#     - remove_warning (human-friendly string; optional; defaults to same as change_warning)
#     """
#     if 'change_warning' in kwargs and 'remove_warning' not in kwargs:
#         kwargs['remove_warning'] = kwargs['change_warning']
#     group = parent_command.add_command(commands.group())
