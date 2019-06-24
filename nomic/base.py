from discord.ext import commands
from typing import Union
import abc
import asyncio
import discord
import functools
import threading

from utils import l


@functools.total_ordering
class BaseGame(abc.ABC):
    """An abstract base class which enforces one-game-per-guild and manages
    logging, locking and GameFlags.

    This class does not implement saving/loading; that must be implemented by a
    subclass via the methods load() and save().
    """

    _games = {}

    def __init__(self, arg: Union[discord.Guild, commands.Context]):
        if isinstance(arg, commands.Context):
            self.guild = arg.guild
        else:
            self.guild = arg
        if not isinstance(self.guild, discord.Guild):
            raise TypeError(f"Can only get game from guild, not {arg!r}")
        self.__dict__ = self._games[self.guild.id] = self._games.get(self.guild.id, self.__dict__)
        # self._needs_save = False
        if not hasattr(self, '_lock'):
            self._lock = asyncio.Lock()

    def get_member(self, user_id: Union[int, discord.abc.User]) -> discord.Member:
        """Fetch a member of the game's guild from an ID, user, or member."""
        if isinstance(user_id, discord.Member):
            return user_id
        elif isinstance(user_id, discord.abc.User):
            return self.guild.get_member(user_id.id)
        else:
            return self.guild.get_member(user_id)

    def __enter__(self):
        raise RuntimeError("Use 'async with', not plain 'with'")

    def __exit__(self):
        raise RuntimeError("Use 'async with', not plain 'with'")

    async def __aenter__(self):
        await self._lock.acquire()
        self._owned_thread_id = threading.get_ident()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        # if self._needs_save:
        #     if exc_type:
        #         l.warn("Error occurred; not saving game")
        #     else:
        #         await self.save()
        #         self._needs_save = False
        self._owned_thread_id = None
        self._lock.release()

    # def need_save(self):
    #     self.assert_locked()
    #     self._needs_save = True

    def assert_locked(self):
        if not self._owned_thread_id == threading.get_ident():
            raise RuntimeError("Expected {self} to be locked by current thread, but it isn't")

    @abc.abstractmethod
    def load(self):
        ...

    @abc.abstractmethod
    def save(self):
        ...

    def __lt__(self, other):
        return self.guild.id < other.guild.id

    def __eq__(self, other):
        return self.guild.id < other.guild.id

    def __hash__(self, other):
        return hash(self.guild.id)
