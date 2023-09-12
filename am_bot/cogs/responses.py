import json
import logging
import pathlib

import discord
from discord.ext import commands


logger = logging.getLogger(__name__)
COMMANDS = json.load(open(pathlib.Path(__file__).parent.resolve() / 'command_responses.json', 'rb'))


class ResponsesCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        logger.debug('Message Received')
        if message.author.id == self.bot.user.id:
            logger.debug('Message is from self, ignore.')
            return
        if not message.content:
            logger.debug('No Message Content. Ignoring.')
            return
        logger.debug(f'First Char: {message.content[0]}, Remaining Chars: {message.content[1:]}')
        if message.content[0] in COMMANDS and message.content[1:] in COMMANDS[message.content[0]]:
            logger.debug(f'Valid Response Command: {message.content}')
            command = COMMANDS[message.content[0]][message.content[1:]]
            logger.debug(f'Command: {command}')
            if 'duplicate' in command:
                # Handle duplicate commands, grab original defined by `duplicate`
                command = COMMANDS[message.content[0]][command['duplicate']]
            if 'embed' in command:
                logger.debug('Embed Response')
                await message.channel.send(embed=discord.Embed.from_dict(command['embed']))
            elif 'content' in command:
                logger.debug(f'Content Response')
                await message.channel.send(content=command['content'])
