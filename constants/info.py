from database import get_db


CONFIG = get_db('config')

DAEMON = CONFIG.get('daemon', False)
DEV = CONFIG.get('dev', False)
TOKEN = CONFIG.get('token')
COMMAND_PREFIX = CONFIG.get('prefix', '!')

GITHUB_EMAIL = CONFIG.get('github_email')
GITHUB_REPO = CONFIG.get('github_repo')
GITHUB_REPO_LINK = f'https://github.com/{GITHUB_REPO}'

NAME = "Quobot"
with open('VERSION') as f:
    VERSION = f.read().strip()

DESCRIPTION = "A bot for the Nomic game on the Quonauts Discord server"

ABOUT_TEXT = f"""\
{NAME} is an open source Discord bot created using \
[discord.py](https://github.com/Rapptz/discord.py) for the \
Quonauts Nomic server.
"""

AUTHOR = "HactarCE"
AUTHOR_LINK = f"https://github.com/{AUTHOR}"
GITHUB_LINK = f"{AUTHOR_LINK}/{NAME}"
