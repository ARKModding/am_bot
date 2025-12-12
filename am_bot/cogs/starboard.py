import logging
import re
from datetime import datetime, timezone

import discord
from discord.ext import commands

from ..constants import GUILD_ID, STARBOARD_TEXT_CHANNEL_ID


logger = logging.getLogger(__name__)
channel_id_pattern = re.compile(rf"discord\.com/channels/{GUILD_ID}/\d+/(\d+)")
REACTION_LIMIT = 5


class StarboardCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot
        self._starred_message_ids = set()
        self._last_message = None

    @commands.Cog.listener()
    async def on_ready(self):
        logger.debug("StarboardCog On Ready!")
        logger.debug("Loading Starboard Messages...")
        channel: discord.TextChannel = self.bot.get_channel(
            STARBOARD_TEXT_CHANNEL_ID
        )
        logger.debug(f"Found Starboard Channel: {channel}")
        async for message in channel.history(limit=None):
            if self._last_message is None:
                self._last_message = message
                logger.debug(f"Last Message: {self._last_message}")
            if not message.embeds or not message.embeds[0].fields:
                logger.warning(
                    f"Message in Starboard channel missing embeds: {message}"
                )
                continue
            found = channel_id_pattern.findall(
                message.embeds[0].fields[0].value
            )
            if not found:
                logger.warning(
                    f"Message in Starboard channel, unable to parse related "
                    f"channel id. Message: {message}"
                )
                continue
            logger.debug(f"Found Existing Starboard Message ID: {found[0]}")
            self._starred_message_ids.add(int(found[0]))
        logger.debug(f"Starred Message IDs: {self._starred_message_ids}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ):
        logger.debug(
            f"Payload Received. Channel ID: {payload.channel_id}, "
            f"Member ID: {payload.member.id}, "
            f"Message ID: {payload.message_id}, Emoji: {payload.emoji.name}"
        )
        if payload.channel_id == STARBOARD_TEXT_CHANNEL_ID:
            logger.debug("Reaction in Starboard channel. Ignoring.")
            return
        if payload.member.id == self.bot.user.id:
            logger.debug("Reaction is from self. Ignoring.")
            return
        if payload.message_id in self._starred_message_ids:
            logger.debug("Already on starboard. Ignoring")
            return
        if payload.emoji.name != "⭐":
            logger.debug("Reaction not ⭐. Ignoring.")
            return

        # Reaction is star, and not already on starboard. Check for eligibility
        channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
        message: discord.Message = await channel.fetch_message(
            payload.message_id
        )
        count = 0
        for reaction in message.reactions:
            logger.debug(f"Reaction: {reaction}, Emoji: {reaction.emoji}")
            if reaction.emoji == "⭐":
                count += 1
                logger.debug(f"Found ⭐ reaction. Count: {count}")
                if count >= REACTION_LIMIT:
                    logger.debug("Enough star reactions for starboard.")
                    break
        else:
            logger.debug("Not enough star reactions")
            return

        # Enough to become a new starboard message.
        starboard_channel: discord.TextChannel = self.bot.get_channel(
            STARBOARD_TEXT_CHANNEL_ID
        )
        avatar_url = str(
            payload.member.avatar_url_as(static_format="png", size=128)
        )
        embed = {
            "author": {
                "name": str(payload.member),
                "icon_url": avatar_url,
                "proxy_icon_url": avatar_url.replace("?size=128", ""),
            },
            "fields": [
                {
                    "name": "\u200b",
                    "value": f"**[Click to jump to message!]"
                    f"({message.jump_url})**",
                    "inline": False,
                }
            ],
            "color": (
                3375061
                if self._last_message.embeds[0].color == 16769024
                else 16769024
            ),
            "timestamp": datetime.utcnow()
            .replace(tzinfo=timezone.utc)
            .isoformat(),
            "type": "rich",
            "description": message.clean_content,
        }
        logger.debug(f"Embed: {embed}")
        self._starred_message_ids.add(message.id)
        logger.debug("Creating Starboard Message...")
        self._last_message = await starboard_channel.send(
            embed=discord.Embed.from_dict(embed)
        )
        logger.debug("Adding Star reaction to new Starboard Message...")
        await self._last_message.add_reaction("⭐")
        logger.debug("Starboard Message Election complete!")
