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
        channel: discord.TextChannel = self.bot.get_channel(
            STARBOARD_TEXT_CHANNEL_ID
        )
        async for message in channel.history(limit=None):
            if self._last_message is None:
                self._last_message = message
            if not message.embeds or not message.embeds[0].fields:
                logger.warning(
                    f"Starboard message {message.id} missing embeds"
                )
                continue
            found = channel_id_pattern.findall(
                message.embeds[0].fields[0].value
            )
            if not found:
                logger.warning(
                    f"Starboard message {message.id}: unable to parse source"
                )
                continue
            self._starred_message_ids.add(int(found[0]))

        logger.info(
            f"Starboard initialized: {len(self._starred_message_ids)} "
            f"existing entries loaded"
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ):
        # Skip reactions that don't qualify
        if payload.channel_id == STARBOARD_TEXT_CHANNEL_ID:
            return
        if payload.member.id == self.bot.user.id:
            return
        if payload.message_id in self._starred_message_ids:
            return
        if payload.emoji.name != "⭐":
            return

        # Check if message has enough stars
        channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
        message: discord.Message = await channel.fetch_message(
            payload.message_id
        )
        count = 0
        for reaction in message.reactions:
            if reaction.emoji == "⭐":
                count += 1
                if count >= REACTION_LIMIT:
                    break
        else:
            return

        # Create starboard entry
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
        self._starred_message_ids.add(message.id)
        self._last_message = await starboard_channel.send(
            embed=discord.Embed.from_dict(embed)
        )
        await self._last_message.add_reaction("⭐")

        logger.info(
            f"New starboard entry: message {message.id} by {message.author}"
        )

