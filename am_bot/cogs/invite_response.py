import logging
import re

import discord
from discord.ext import commands

from ..constants import INVITE_HELP_TEXT_CHANNEL_ID
from ..ses import send_email


logger = logging.getLogger(__name__)


class InviteResponseCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot

    def _parse_embed_email(self, embed: discord.Embed) -> str | None:
        """Extract email from an embed's Email field."""
        for field in embed.fields:
            if field.name == "Email":
                # Email is wrapped in backticks: `email@example.com`
                match = re.match(r"`(.+)`", field.value)
                if match:
                    return match.group(1)
                return field.value
        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore messages from self, wrong channel, or without proper reference
        if message.author.id == self.bot.user.id:
            return
        if message.channel.id != INVITE_HELP_TEXT_CHANNEL_ID:
            return
        if (
            message.reference is None
            or message.reference.channel_id != INVITE_HELP_TEXT_CHANNEL_ID
        ):
            return
        if not message.content:
            return

        referenced: discord.Message = (
            message.reference.resolved
            if message.reference.resolved is not None
            else await message.channel.fetch_message(
                message.reference.message_id
            )
        )

        # Parse email and help request from embed (new format)
        email = None
        help_request = None

        if referenced.embeds:
            embed = referenced.embeds[0]
            email = self._parse_embed_email(embed)
            help_request = embed.description
        else:
            # Fallback to legacy plain text format
            logger.debug(f"Legacy plain text format detected: {referenced.id}")
            email_pattern = re.compile(r"Email: (.*)")
            match = email_pattern.match(referenced.content)
            if match:
                email = match.group(1)
            help_request = "\n".join(referenced.content.split("\n")[7:])

        if not email or not help_request:
            logger.debug(f"Could not parse email/help request from message {referenced.id}")
            return

        logger.info(f"Sending invite help response to {email}")
        body_txt = (
            f"Your Message: {help_request}\n\n"
            f"ARK Modding Discord Staff Response:\n\n"
            f"{message.author.display_name}: {message.content}"
        )
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
            <p><span id="moderator-name">{message.author.display_name}</span>:
            {message.content}
            </p>
        </body>
        </html>
        """
        send_email(
            email,
            subject="ARK Modding Discord Staff Response",
            body_txt=body_txt,
            body_html=body_html,
        )
