import json
import logging
import pathlib
import re

import discord
from discord.ext import commands

from ..constants import INVITE_HELP_TEXT_CHANNEL_ID
from ..ses import send_email


logger = logging.getLogger(__name__)


class InviteResponseCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        logger.debug('Message Received')
        if message.author.id == self.bot.user.id:
            logger.debug('Message is from self, ignore.')
            return
        if message.channel.id != INVITE_HELP_TEXT_CHANNEL_ID:
            logger.debug('Message is not in Invite Help channel, ignore.')
            return
        if message.reference is None or message.reference.channel_id != INVITE_HELP_TEXT_CHANNEL_ID:
            logger.debug('Message reference is invalid. Ignore.')
            return
        if not message.content:
            logger.debug('No Message Content. Ignoring.')
            return
        referenced: discord.Message = message.reference.resolved if message.reference.resolved is not None else \
            await message.channel.fetch_message(message.reference.message_id)

        logger.warning(referenced.content)
        email_pattern = re.compile(r'Email: (.*)')
        match = email_pattern.match(referenced.content)
        if not match:
            logger.debug('Email not found in referenced message.')
        logger.debug(f'Email found for referenced message: {match.group(1)}')
        help_request = '\n'.join(referenced.content.split('\n')[7:])
        body_txt = f'Your Message: {help_request}\n\nARK Modding Discord Staff Response:\n\n' \
                   f'{message.author.display_name}: {message.content}'
        body_html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Helvetica, Arial, sans-serif;
                }}
                pre {{
                    white-space: pre-wrap;       /* css-3 */
                    white-space: -moz-pre-wrap;  /* Mozilla, since 1999 */
                    white-space: -pre-wrap;      /* Opera 4-6 */
                    white-space: -o-pre-wrap;    /* Opera 7 */
                    word-wrap: break-word;       /* Internet Explorer 5.5+ */
                    background-color:  ccc;
                    border: 1px solid black;
                    border-radius: 3px;
                    padding: 3px;
                }}
                #moderator-name {{
                    color:  red;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <h1>ARK Modding Discord Staff Response</h1>
            <pre>{help_request}</pre>
            <h4>Staff Response</h4>
            <p><span id="moderator-name">{message.author.display_name}</span>: {message.content}</p>
        </body>
        </html>
        """
        send_email(match.group(1), subject="ARK Modding Discord Staff Response",
                   body_txt=body_txt, body_html=body_html)
