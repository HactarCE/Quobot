import discord
from discord.ext import commands


class Quonauts:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def initchannel(self, ctx, name):
        await ctx.send('NYI')


def setup(bot):
    bot.add_cog(Quonauts(bot))
