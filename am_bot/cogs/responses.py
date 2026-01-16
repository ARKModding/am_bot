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
            # Grab command info from JSON.
            command = COMMANDS[message.content[0]][message.content[1:]]

            # Prepare the list of commands to send.
            to_send = []
            if "commands" in command:
                # Handle multiple commands,
                # grab the list of commands defined by `commands`.
                commands_list = command["commands"].split(", ")
                for current_command in commands_list:
                    if current_command in COMMANDS[message.content[0]]:
                        to_send.append(
                            COMMANDS[message.content[0]][current_command]
                        )
            else:
                to_send.append(command)
            
            logger.info(f"Executing response command: {message.content}")

            # Send messages.
            for command_to_send in to_send:
                final_cmd = command_to_send
                if "duplicate" in final_cmd:
                    # Handle duplicate commands,
                    # grab original defined by `duplicate`.
                    final_cmd = COMMANDS[message.content[0]][
                        final_cmd["duplicate"]]
                if "embed" in final_cmd:
                    await message.channel.send(
                        embed=discord.Embed.from_dict(final_cmd["embed"])
                    )
                elif "content" in final_cmd:
                    await message.channel.send(content=final_cmd["content"])
