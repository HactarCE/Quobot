from datetime import datetime
from discord.ext import commands
import discord

from constants import colors, info
import nomic
import utils


class GameLog(commands.Cog):
    """Commands for viewing and interacting with game logs."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(aliases=['l', 'log', 'logging'], invoke_without_command=True, rest_is_raw=True)
    async def logs(self, ctx, *, comment):
        """Link to the game's log files or record a comment in the log.

        When invoked with no argument (`!log`), link to the game's log files.

        When invoked with text (e.g. `!log This was a triumph`), add that as a
        comment in the log files.
        """
        game = nomic.Game(ctx)
        if comment:
            m, response = await utils.discord.get_confirm_embed(
                ctx,
                title="Record comment in log?",
                description=comment,
            )
            if response != 'y':
                await utils.discord.edit_embed_for_response(
                    m, response, title_fomat="Comment {}"
                )
                return
            async with game:
                await game.log(f"{utils.discord.fake_mention(ctx.author)} commented: **{comment.strip()}**")
            await m.edit(embed=discord.Embed(
                color=colors.SUCCESS,
                title="Comment recorded",
                description=comment,
            ))
        else:
            now = datetime.utcnow()
            tree_dir = f'{info.GITHUB_REPO_LINK}/tree/{game.repo.name}/logs'
            blob_dir = f'{info.GITHUB_REPO_LINK}/blob/{game.repo.name}/logs'
            filename = now.strftime('%Y_%m') + '.md'
            header = now.strftime('%Y-%m-%d')
            description = f"Use `{ctx.prefix}{ctx.invoked_with} <comment>` to record a comment in the logs.\n\n"
            description += f"\N{BULLET} [Today's log]({blob_dir}/{filename}#{header})\n"
            # description += f"\N{BULLET} [This month's log file]({blob_dir}/{filename})\n"
            description += f"\N{BULLET} [Directory of all log files]({tree_dir})\n"
            description += "\nThe log might take a little while to update."
            await ctx.send(embed=discord.Embed(
                color=colors.INFO,
                title="Game logs",
                description=description,
            ))


def setup(bot):
    bot.add_cog(GameLog(bot))
