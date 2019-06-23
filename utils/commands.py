from discord.ext import commands
from typing import Awaitable, Callable, Optional
import discord

from constants import colors, strings
import utils


async def desig_chan_show(ctx: commands.Context,
                          name: str,
                          channel: Optional[discord.TextChannel]):
    """Inform the user about a designated channel if they did not invoke a
    subcommand of this one.
    """
    if channel:
        description = f"The current {name} is {channel.mention}. You can use `{ctx.command.qualified_name} set [channel]` to change it, or `{ctx.command.qualified_name} unset` to reset it."
    else:
        description = f"There currently is no {name}. You can use `{ctx.command.qualified_name} set [channel]` to set one."
    await ctx.send(embed=discord.Embed(
        color=colors.INFO,
        title=name.capitalize(),
        description=description,
    ))


async def desig_chan_set(ctx: commands.Context,
                         name: str,
                         *,
                         old_channel: Optional[discord.TextChannel],
                         new_channel: Optional[discord.TextChannel],
                         extra_warning: str = '',
                         callback: Callable[[commands.Context, Optional[discord.TextChannel]], Awaitable[None]]):
    """Set or unset a designated channel (with user confirmation).

    If `new_channel` is specified, prompt to set the channel. If `new_channel`
    is None, prompt to unset the channel. Either way, if the change is
    confirmed, call `await callback(ctx, new_channel)` and return True; if it is
    not confirmed, return False.
    """
    if old_channel == new_channel:
        if old_channel:
            description = f"The {name} is already {new_channel.mention}."
        else:
            description = f"There already is no {name}."
        await ctx.send(embed=discord.Embed(
            color=colors.ERROR,
            title=name.capitalize(),
            description=description,
        ))
        return
    if old_channel:
        if new_channel:
            title_verb = "Change"
            description = f"Change the {name} from {old_channel.mention} to {new_channel.mention}?"
        else:
            title_verb = "Unset"
            description = f"Unset the {name} (currently {old_channel.mention})?"
        if extra_warning:
            description += " " + extra_warning
    else:
        title_verb = "Set"
        description = f"Set the {name} to {new_channel.mention}?"
    m, response = await utils.discord.get_confirm_embed(
        ctx,
        title=f"{title_verb} {name}?",
        description=description,
    )
    if response == 'y':
        if new_channel:
            description = f"The {name} is now {new_channel.mention}."
        else:
            description = f"There is now no {name}."
    else:
        description = None
    if response == 'y':
        await callback(ctx, new_channel)
    await m.edit(embed=discord.Embed(
        color=colors.YESNO[response],
        title=f"{name.capitalize()} change {strings.YESNO[response]}",
        description=description,
    ))
    return response == 'y'
