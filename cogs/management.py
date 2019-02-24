import discord
from discord.ext import commands

from cogs.utils import is_meta, guilds_data, get_guild_data, formal_print_user
from utils import is_bot_admin


class Management:
    def __init__(self, bot):
        self.bot = bot
        # self.__local_check = is_bot_admin

    @commands.command()
    @commands.check(is_bot_admin)
    async def meta(self, ctx):
        """Set a channel as meta, allowing bot commands such as ping."""
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
            await ctx.send(f"Set channel '{ctx.channel.category.name}' ({category_id}) as no longer meta.")
        else:
            meta_list.append(category_id)
            guilds_data.save()
            await ctx.send(f"Set channel '{ctx.channel.category.name}' ({category_id}) as meta.")


def setup(bot):
    bot.add_cog(Management(bot))
