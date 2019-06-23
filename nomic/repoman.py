from asyncio.subprocess import PIPE
from datetime import datetime
from os import mkdir, path
from typing import Tuple
import asyncio

from .base import BaseGame
from constants import info
from repository import RepoBranch
from utils import l


README_TEXT = f"""\
# {{game.guild.name}}

This is the GitHub repository for the {{game.guild.name}} Nomic game. This
repository contains the entire game state, automatically updated at regular
intervals; however, it may take up to an hour before it is updated. Do NOT
manually commit to this repository; it should be managed entirely by
[{info.NAME}]({info.GITHUB_LINK}).

Below are links to the current game rules, proposals, and logs.

* [**Rules**](rules.md)
* [**Proposals**](proposals.md)
* [**Logs**](logs)

_Last updated {{last_updated}}_
"""


class GameRepoManager(BaseGame):

    ready = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.repo = RepoBranch(self.repo_name)

    async def setup(self):
        async with self:
            if not self.ready:
                # Test SSH connection
                _, ssh_stderr = await (await asyncio.create_subprocess_exec(
                    'ssh', '-T', 'git@github.com',
                    stdout=PIPE, stderr=PIPE,
                )).communicate()
                if "success" in ssh_stderr.decode().lower():
                    l.info("Successfully authenticated to GitHub")
                else:
                    l.error("Unable to authenticate to GitHub")
                    l.error("See README for instructions")
                    l.error(f"`ssh -T git@github.com` stderr: {ssh_stderr.decode()!r}")
                    exit(1)
                # Initialize repository branch
                l.info(f"Initializing repository branch for {self.guild.name}")
                await self.repo.setup()
                l.info(f"Loading data files for {self.guild.name}")
                self.load_guild_data()
                if not path.isdir(self.get_file('data')):
                    mkdir(self.get_file('data'))
                if not path.isdir(self.get_file('logs')):
                    mkdir(self.get_file('logs'))
                l.info(f"{self.guild.name} is ready!")
                self.ready = True

    @classmethod
    async def is_ready(cls, ctx):
        return cls(ctx).ready

    @property
    def repo_name(self):
        return 'guild_' + str(self.guild.id)

    def get_file(self, relative_path: str) -> str:
        return self.repo.get_file(relative_path)

    def get_db(self, db_name) -> str:
        return self.repo.get_db(path.join('data', db_name))

    async def stage_files(self, *files):
        """Stage some files."""
        self.assert_locked()
        await self.repo.exec('git', 'add', *files)

    async def commit(self, *files, msg):
        """Stage and commit some files."""
        self.assert_locked()
        await self.stage_files(*files)
        await self.repo.exec('git', 'commit', '-m', msg)

    async def commit_all(self, msg="Added latest game data"):
        """Commit all files."""
        self.assert_locked()
        await self.commit('--all', msg=msg)

    async def push(self):
        """Push commits."""
        self.assert_locked()
        await self.repo.push()

    async def update_readme(self):
        """Update the repository's README.md."""
        self.assert_locked()
        with open(self.get_file('README.md'), 'w') as f:
            f.write(README_TEXT.format(
                game=self,
                last_updated=datetime.utcnow().strftime('UTC %Y-%m-%d %H:%M')
            ))

    async def periodic_update(self):
        self.assert_locked()
        await self.update_readme()
        await self.commit_all()
        await self.push()

    async def get_last_log_file(self) -> str:
        """Return the complete path to data/last_log."""
        self.assert_locked()
        return self.get_file(path.join('data', 'last_log'))

    async def get_last_log(self) -> Tuple[int, int]:
        """Return a tuple of integers (year, month, day) of the last logged
        event. If there was no events have been found, return (0, 0, 0).
        """
        self.assert_locked()
        try:
            with open(await self.get_last_log_file()) as f:
                t = tuple(int(line) for line in f)
                if len(t) == 3:
                    return t
        except FileNotFoundError:
            pass
        return 0, 0, 0

    async def update_last_log(self, year, month, day):
        """Update data/last_log."""
        self.assert_locked()
        with open(await self.get_last_log_file(), 'w') as f:
            f.write(f'{year}\n{month}\n{day}')

    async def log(self, log_text: str, link_to_commit: bool = False):
        """Add `log_text` to the log.

        If `link_to_commit` is True, include a link to the last commit.
        """

        self.assert_locked()
        timestamp = datetime.utcnow()
        last_year, last_month, last_day = await self.get_last_log()
        new_month, new_day = False, False
        if (timestamp.year, timestamp.month) != (last_year, last_month):
            new_month = True
            new_day = True
        elif timestamp.day != last_day:
            new_day = True
        year_month = timestamp.strftime('%Y_%m')

        logfile_md = path.join('logs', year_month + '.md')
        with open(self.get_file(logfile_md), 'a') as f:
            if new_month:
                f.write(f"# {timestamp.strftime('%Y-%m')}")
                f.write('\n')
            if new_day:
                f.write('\n')
                f.write(f"## {timestamp.strftime('%Y-%m-%d')}")
                f.write('\n\n')
            f.write(f"* `{timestamp.strftime('%H:%M:%S')}` ")
            f.write(log_text)
            if link_to_commit:
                f.write(f" ([diff]({await self.repo.get_commit_link()}))")
            f.write('\n')

        await self.update_last_log(timestamp.year, timestamp.month, timestamp.day)
