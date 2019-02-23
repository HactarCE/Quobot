import discord
from discord.ext import commands

from cogs.utils import is_bot_admin, is_meta, guilds_data, get_guild_data, formal_print_user


class Management:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def doerror(self, ctx):
        raise Exception("this is an error! yikes!")

    async def on_guild_join(self, guild):
        """This event fires when the bot joins a guild."""
        print(f"Joined {guild.name} with {guild.member_count} users!")

    @commands.command()
    @commands.check(is_bot_admin)
    async def initserver(self, ctx):
        get_guild_data(ctx.guild)
        await ctx.send(f"Added server '{guild.name}' ({guild.id}) to database.")

    @commands.command()
    @commands.check(is_meta)
    async def ping(self, ctx):
        """Ping the bot."""
        await ctx.send("Pong!")

    @commands.group()
    @commands.check(is_bot_admin)
    async def admins(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Subcommands: `add <user>`, `remove <user>`, `list`")

    @admins.command('add')
    async def add_admin(self, ctx, member: commands.MemberConverter):
        """Add another user as a bot admin."""
        guild_data = get_guild_data(ctx.guild)
        admin_list = guild_data['admins'] = guild_data.get('admins', [])
        already_admin = member.id in admin_list
        if not already_admin:
            admin_list.append(member.id)
            guilds_data.save()
        await ctx.send(f"{formal_print_user(member)} is {'already' if already_admin else 'now'} an admin.")

    @admins.command('remove')
    async def remove_admin(self, ctx, member: commands.MemberConverter):
        guild_data = get_guild_data(ctx.guild)
        admin_list = guild_data['admins'] = guild_data.get('admins', [])
        already_not_admin = member.id not in admin_list
        if not already_not_admin:
            admin_list.remove(member.id)
            guilds_data.save()
        await ctx.send(f"{formal_print_user(member)} is {'already' if already_not_admin else 'now'} not an admin.")

    @admins.command('list')
    async def list_admins(self, ctx):
        guild_data = get_guild_data(ctx.guild)
        admin_list = guild_data['admins'] = guild_data.get('admins', [])
        if admin_list:
            user_list = map(self.bot.get_user, admin_list)
            user_list = map(formal_print_user, user_list)
            user_list = sorted(list(user_list))
        else:
            user_list = ['(nobody)']
        await ctx.send("**Current bot admins:**\n" + '\n'.join(user_list) + "\n... plus anyone with the server-wide 'Administrator' permission.")

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

    @commands.group(invoke_without_command=True)
    @commands.check(is_bot_admin)
    async def foo(self, ctx):
        """
        A sub command group, Showing how sub command groups can be made.
        """
        await ctx.send("try my subcommand")

    @foo.command(aliases=['an_alias'])
    @commands.check(is_bot_admin)
    async def bar(self, ctx):
        """
        I have an alias!, I also belong to command 'foo'
        """
        await ctx.send("foo bar!")


def setup(bot):
    bot.remove_command('help')
    bot.add_cog(Management(bot))
