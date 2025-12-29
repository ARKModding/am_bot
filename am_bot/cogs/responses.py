import json
import logging
import pathlib

import discord
from discord.ext import commands


logger = logging.getLogger(__name__)
COMMANDS = json.load(
    open(
        pathlib.Path(__file__).parent.resolve() / "command_responses.json",
        "rb",
    )
)


class ResponsesCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id == self.bot.user.id:
            return
        if not message.content:
            return

        if (
            message.content[0] in COMMANDS
            and message.content[1:] in COMMANDS[message.content[0]]
        ):
            command = COMMANDS[message.content[0]][message.content[1:]]
            if "duplicate" in command:
                # Handle duplicate commands,
                # grab original defined by `duplicate`
                command = COMMANDS[message.content[0]][command["duplicate"]]

            logger.info(f"Executing response command: {message.content}")

            if "embed" in command:
                await message.channel.send(
                    embed=discord.Embed.from_dict(command["embed"])
                )
            elif "content" in command:
                await message.channel.send(content=command["content"])

