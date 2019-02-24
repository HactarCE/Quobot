import discord
from discord.ext import commands

from cogs.utils import is_meta, guilds_data, get_guild_data, formal_print_user
from utils import is_bot_admin


class Quonauts:
    def __init__(self, bot):
        self.bot = bot
        # self.__local_check = is_bot_admin

    @commands.group()
    @commands.check(is_bot_admin)
    async def meta(self, ctx):
        """Mark a channel as meta, allowing bot commands such as `!ping`."""
        if ctx.invoked_subcommand is None:
            # TODO display command help
            await ctx.send("Subcommands: `add`, `remove`, `list`")

    @meta.command('add')
    async def add_meta(self, ctx):
        # TODO
        pass

    @meta.command('remove')
    async def remove_meta(self, ctx):
        # TODO
        pass

    @meta.command('list')
    async def list_meta(self, ctx):
        # TODO
        category_id = ctx.channel.category_id
        guild_data = get_guild_data(ctx.guild)
        if 'categories' not in guild_data:
            guild_data['categories'] = {}
        if 'meta' not in guild_data['categories']:
            guild_data['categories']['meta'] = []
        meta_list = guild_data['categories']['meta']
        if category_id in meta_list:
            meta_list.remove(category_id)
            guilds_data.save()
            await ctx.send(f"Set channel category '{ctx.channel.category.name}' ({category_id}) as no longer meta.")
        else:
            meta_list.append(category_id)
            guilds_data.save()
            await ctx.send(f"Set channel category '{ctx.channel.category.name}' ({category_id}) as meta.")


def setup(bot):
    bot.add_cog(Quonauts(bot))
