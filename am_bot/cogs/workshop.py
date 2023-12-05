import asyncio
import logging
from datetime import datetime, timedelta

from discord.ext import commands

from ..constants import (
    WORKSHOP_ROLE_ID,
    WORKSHOP_TEXT_CHANNEL_ID,
    WORKSHOP_VOICE_CHANNEL_ID,
)


logger = logging.getLogger(__name__)


class WorkshopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_load(self) -> None:
        self.bot.loop.create_task(self.text_cleanup_task())

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        logger.debug(
            f"Voice state activity:: Member: {member} "
            f"Before: {before}, After: {after}"
        )
        if (
            before.channel is None
            or before.channel.id != WORKSHOP_VOICE_CHANNEL_ID
        ) and (
            after.channel is not None
            and after.channel.id == WORKSHOP_VOICE_CHANNEL_ID
        ):
            # Add role for one-time join
            logger.debug(
                "Member joined AMC Workshop Voice Channel. "
                "Adding AMC Workshop role..."
            )
            await member.add_roles(member.guild.get_role(WORKSHOP_ROLE_ID))
            # Add member overwrite permissions to view text channel
            logger.debug("Adding member to text chat...")
            channel = member.guild.get_channel(
                channel_id=WORKSHOP_TEXT_CHANNEL_ID
            )
            await channel.set_permissions(member, view_channel=True)
        elif (
            before.channel is not None
            and before.channel.id == WORKSHOP_VOICE_CHANNEL_ID
        ) and (
            after.channel is None
            or after.channel.id != WORKSHOP_VOICE_CHANNEL_ID
        ):
            # Remove text channel member overwrite
            logger.debug(
                "Member has left AMC Workshop Voice Channel. "
                "Removing member from text chat..."
            )
            channel = member.guild.get_channel(
                channel_id=WORKSHOP_TEXT_CHANNEL_ID
            )
            await channel.set_permissions(member, overwrite=None)

    async def text_cleanup_task(self):
        await asyncio.sleep(10)
        logger.debug(
            "AMC Workshop Text Cleanup Task Starting. Fetching Channel..."
        )
        channel = await self.bot.fetch_channel(WORKSHOP_TEXT_CHANNEL_ID)
        logger.debug(f"Channel Fetched: {channel}")
        while True:
            purge_time = datetime.utcnow() - timedelta(days=1)
            logger.debug(f"Purging messages older than: {purge_time}")
            await channel.purge(before=purge_time)
            logger.debug("Sleeping 10 minutes...")
            await asyncio.sleep(600)
