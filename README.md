# Quobot

A bot for the Nomic game on the Quonauts Discord server

## Setup

1. Install Python 3.6 or higher.
2. Install Discord.py 1.5 or higher.
3. Create a [Discord bot account](https://discord.com/developers/applications) and enable the server members intent under "Privileged Gateway Events".
4. Create a file `data/config.json` with the following contents:

```json
{
    "daemon": false,
    "dev": true,
    "token": "<bot_token>",
    "prefix": "!",
    "github_name": "Quobot",
    "github_email": "<user_email>@users.noreply.github.com"
}
```

(Obviously adjust parameters as appropriate; these are just some defaults.)

5. Run `python3 main.py` to start the bot.

## GitHub repo

To store the gamestate in GitHub, there's a bit more work involved.

1. Select or create a GitHub account for the bot.
2. Create an RSA key pair with the GitHub account's noreply email address: `ssh-keygen -t rsa -C "<user_email>@users.noreply.github.com"` (You can leave the passphrase blank.)
3. [Add the key to the bot's account.](https://help.github.com/en/enterprise/2.15/user/articles/adding-a-new-ssh-key-to-your-github-account)
4. Test the key: `ssh -T git@github.com`.
5. Create a GitHub repository for the bot (will be shared for all games using the same bot).
6. Add the following keys to `data/config.json`:

```json
    "github_email": "<github_email>@users.noreply.github.com",
    "github_repo": "<UserOrOrganizationName>/<RepositoryName>",
```

7. Invoke `!git init` in your server.
