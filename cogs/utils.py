from database import get_db

guilds_data = get_db('guilds')

def get_guild_data(guild):
    guild_id = str(guild.id)
    if guild_id not in guilds_data:
        guilds_data[guild_id] = {}
        guilds_data.save()
    return guilds_data[guild_id]

async def is_meta(ctx):
    try:
        return ctx.message.channel.category_id in get_guild_data(ctx.guild)['categories']['meta']
    except:
        print('dunno')
        pass
    return True

def formal_print_user(user):
    # TODO replace with user.mention, and use in embed so it doesn't ping
    return f'{user.name}#{user.discriminator} ({user.id})'

def setup(bot):
    pass
