from database import get_db

guilds_data = get_db('guilds')

def get_guild_data(guild):
    id = str(guild.id)
    if id not in guilds_data:
        guilds_data[id] = {}
        guilds_data.save()
    return guilds_data[id]

async def is_bot_admin(ctx):
    if ctx.message.author.guild_permissions.administrator:
        return True
    try:
        return ctx.message.author.id in get_guild_data(ctx.guild)['admins']
    except:
        pass
    return False

async def is_meta(ctx):
    try:
        return ctx.message.channel.category_id in get_guild_data(ctx.guild)['categories']['meta']
    except:
        print('dunno')
        pass
    return True

def formal_print_user(user):
    return f'{user.name}#{user.discriminator} ({user.id})'

def setup(bot):
    pass
