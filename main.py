#!/usr/bin/env python3

import asyncio
import logging
from os import path
from pathlib import Path

import discord
from discord.ext import commands

from cogs import get_extensions
from constants import colors, info
from database import DATA_DIR, get_db, TOKEN_FILE_PATH, get_token
from utils import l, LOG_SEP, make_embed, report_error


try:
    import discord
except ImportError:
    print("Discord.py is required. See the README for instructions on installing it.")
    exit(1)


async def run():
    try:
        token = get_token()
    except:
        print(f"Please specify a bot token in {TOKEN_FILE_PATH}.")
        exit(1)
    config = get_db('config')
    bot = Bot(config=config,
              description=config.get('description'))
    try:
        # bot.loop.create_task(bot.load_all_extensions())
        await bot.start(token)
    except KeyboardInterrupt:
        await bot.logout()


LOG_LEVEL_API = logging.WARNING
LOG_LEVEL_BOT = logging.INFO
LOG_FMT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"


if info.DEV:
    logging.basicConfig(format=LOG_FMT)
else:
    logging.basicConfig(format=LOG_FMT, filename='bot.log')
logging.getLogger('discord').setLevel(LOG_LEVEL_API)
l.setLevel(LOG_LEVEL_BOT)


COMMAND_PREFIX = '!'


class Bot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(
            command_prefix=commands.when_mentioned_or(COMMAND_PREFIX),
            case_insensitive=True,
            description=kwargs.pop('description'),
            status=discord.Status.dnd
        )
        self.app_info = None
        self.cogs_loaded = set()
        self.config = kwargs.pop('config')

    async def on_connect(self):
        l.info(f"Connected as {self.user}.")
        await self.change_presence(status=discord.Status.idle)

    async def on_ready(self):
        self.app_info = await self.application_info()
        l.info(LOG_SEP)
        l.info(f"Logged in as: {self.user.name}")
        l.info(f"Using discord.py version: {discord.__version__}")
        l.info(f"Owner: {self.app_info.owner}")
        l.info(f"Template Maker: SourSpoon / Spoon#7805")
        l.info(LOG_SEP)
        await self.load_all_extensions()
        await self.change_presence(status=discord.Status.online)

    async def on_resumed(self):
        l.info("Resumed session.")
        await self.change_presence(status=discord.status.online)

    async def load_all_extensions(self, reload=False):
        """
        Attempts to load all .py files in cogs/ as cog extensions. Returns a
        dictionary which maps cog names to a boolean value (True = successfully
        loaded; False = not successfully loaded).
        """
        succeeded = {}
        for extension in get_extensions():
            try:
                if reload or extension not in self.cogs_loaded:
                    self.load_extension(f'cogs.{extension}')
                    l.info(f"Loaded extension '{extension}'")
                    self.cogs_loaded.add(extension)
                    succeeded[extension] = True
            except Exception as e:
                error = f"{extension}\n {type(e).__name__} : {e}"
                l.error(f"Failed to load extension '{error}'")
                succeeded[extension] = False
        if succeeded:
            l.info(LOG_SEP)
        return succeeded

    # async def get_owner(self):
        # return self.owner_id
        # return self.application_info().owner

    async def on_guild_join(self, guild):
        """This event triggers when the bot joins a guild."""
        l.info(f"Joined {guild.name} with {guild.member_count} users!")

    async def on_message(self, message):
        """This event triggers on every message received by the bot. Including ones that it sent itself."""
        if message.author.bot:
            return # Ignore all bots.
        await self.process_commands(message)

    async def on_command_error(self, ctx, exc, *args, **kwargs):
        command_name = ctx.command.qualified_name if ctx.command else "unknown command"
        l.error(f"'{str(exc)}' encountered while executing '{command_name}' (args: {args}; kwargs: {kwargs})")
        if isinstance(exc, commands.UserInputError):
            if isinstance(exc, commands.MissingRequiredArgument):
                description = f"Missing required argument `{exc.param.name}`."
            elif isinstance(exc, commands.TooManyArguments):
                description = "Too many arguments."
            elif isinstance(exc, commands.BadArgument):
                description = f"Bad argument:\n```\n{str(exc)}\n```"
            else:
                description = f"Bad user input."
            description += f"\n\nRun `{COMMAND_PREFIX}help {command_name}` to view the required arguments."
        elif isinstance(exc, commands.CommandNotFound):
            # description = f"Could not find command `{ctx.invoked_with.split()[0]}`."
            return
        elif isinstance(exc, commands.CheckFailure):
            if isinstance(exc, commands.NoPrivateMessage):
                description = "Cannot be run in a private message channel."
            elif isinstance(exc, commands.MissingPermissions) or isinstance(exc, commands.BotMissingPermissions):
                if isinstance(exc, commands.MissingPermissions):
                    description = "You don't have permission to do that."
                elif isinstance(exc, commands.BotMissingPermissions):
                    description = "I don't have permission to do that."
                missing_perms = "\n".join(exc.missing_perms)
                description += f" Missing:\n```\n{missing_perms}\n```"
            else:
                # description = "Command check failed."
                return
        elif isinstance(exc, commands.DisabledCommand):
            description = "That command is disabled."
        elif isinstance(exc, commands.CommandOnCooldown):
            description = "That command is on cooldown."
        else:
            description = "Sorry, something went wrong.\n\nA team of highly trained monkeys has been dispatched to deal with the situation."
            await report_error(ctx, exc.original, *args, **kwargs)
        await ctx.send(embed=make_embed(
            color=colors.EMBED_ERROR,
            title="Error",
            description=description
        ))


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
