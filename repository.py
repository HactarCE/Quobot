from asyncio.subprocess import PIPE
from os import path
import asyncio
import logging
import shutil

from constants import info
from database import DATA_DIR, DB, get_db
from utils import l


git_log = logging.getLogger('git')
git_log.setLevel(logging.DEBUG)


REPOS_DIR = DATA_DIR

REPO_LINK = f'git@github.com:{info.GITHUB_REPO}'


if not info.GITHUB_EMAIL and info.GITHUB_REPO:
    l.error("Must specify GitHub email address and GitHub repository in configuration file")
    exit(1)


_lock = asyncio.Lock()


def _bail_out(activity):
    l.error(f"Error while {activity}; shutting down bot to avoid further damage")
    exit(1)


class RepoBranch:

    def __init__(self, branch_name):
        self.name = branch_name
        self.path = path.join(REPOS_DIR, self.name)

    async def setup(self):
        async with _lock:
            if not path.isdir(self.path) and self.name != 'master':
                async with RepoBranch('master') as master:
                    results = await master.exec_multi(
                        ['git', 'branch', self.name],
                        ['git', 'checkout', self.name],
                        ['git', 'push', '--set-upstream', 'origin', self.name],
                    )
                # if results[1] or results[2]:
                #     _bail_out(f"creating branch {self.name!r}")
                await self._clone()
            else:
                await self.pull()
            return self.path

    async def __aenter__(self):
        if self.name == 'master':
            if path.isdir(self.path):
                self._delete_folder()
            await self._clone()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.name == 'master':
            self._delete_folder()

    @property
    def exists(self):
        return path.isdir(self.path)

    def _delete_folder(self):
        """Delete this branch's folder (the branch remains in the repo)."""
        shutil.rmtree(self.path)

    def _git_log_output(self, stdout, stderr):
        for line in stdout.decode().splitlines():
            git_log.debug(line)
        for line in stderr.decode().splitlines():
            git_log.debug(line)

    async def _clone(self):
        """Clone this branch (and only this branch)."""
        git_log.info(f"Cloning {REPO_LINK} (branch {self.name})")
        subproc = await asyncio.create_subprocess_exec(
            'git', 'clone', '-b', self.name, '--single-branch', REPO_LINK, self.name,
            cwd=REPOS_DIR, stdout=PIPE, stderr=PIPE,
        )
        self._git_log_output(*await subproc.communicate())
        if await subproc.wait():
            _bail_out(f"cloning branch {self.name!r}")

    async def exec(self, *command, log_output=True, **kwargs):
        """Execute a command in this branch and return the
        asyncio.subprocess.Process instance.
        """
        git_log.info(f"Executing {command} in repository branch {self.name}")
        subproc = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.path, stdout=PIPE, stderr=PIPE,
            **kwargs,
        )
        if log_output:
            self._git_log_output(*await subproc.communicate())
        return subproc

    async def exec_multi(self, *commands, **kwargs):
        """Execute commands in this branch and return a list of returncodes."""
        results = []
        for command in commands:
            results.append(await (await self.exec(*command, **kwargs)).wait())
        return results

    async def exec_output(self, *command, assert_success=False, **kwargs) -> str:
        """Execute a command in this branch and return the stdout."""
        proc = await self.exec(*command, **kwargs, log_output=False)
        if await proc.wait():
            self._bail_out(f"executing {' '.join(command)!r}")
        return tuple(map(bytes.decode, await proc.communicate()))

    async def pull(self) -> str:
        """Execute `git pull` and return a tuple (stdout_data, stderr_data).

        Bail out on nonzero return code.
        """
        return await self.exec_output('git', 'pull', assert_success=True)

    async def push(self) -> str:
        """Execute `git push` and return a tuple (stdout_data, stderr_data).

        Bail out on nonzero return code.
        """
        return await self.exec_output('git', 'push', assert_success=True)

    async def get_status(self, *files, porcelain=True) -> str:
        """Execute `git status --porcelain` (optionally with files) and return a
        tuple (stdout_data, stderr_data).

        Bail out on nonzero return code.
        """
        if porcelain:
            files = ('--porcelain',) + files
        return await self.exec_output('git', 'status', *files, assert_success=True)

    async def is_clean(self, *files) -> bool:
        """Return whether the working state is clean, using
        RepoBranch.get_status().
        """
        return not any(await self.get_status(*files))

    async def is_ahead(self) -> bool:
        """Return whether the local clone is ahead of the remote, using `git log
        origin/<branch>..HEAD`."""
        return any(await self.exec_output('git', 'log', f'origin/{self.name}..HEAD'))

    async def get_commit_hash(self) -> str:
        """Return the result of `git rev-parse HEAD`.

        Bail out on nonzero return code.
        """
        return (await self.exec_output('git', 'rev-parse', 'HEAD', assert_success=True))[0].strip()

    async def get_commit_link(self) -> str:
        """Return a GitHub link to the last commit."""
        hash = await self.get_commit_hash()
        return f'{info.GITHUB_REPO_LINK}/commit/{hash}'

    def get_file(self, relative_path: str) -> str:
        """Return the absolute path to a file inside this branch."""
        return path.join(self.path, relative_path)

    def get_db(self, db_name: str) -> DB:
        """Return a DB inside this branch."""
        return get_db(self.get_file(db_name))
