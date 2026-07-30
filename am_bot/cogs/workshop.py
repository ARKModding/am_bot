import asyncio
import logging
from datetime import datetime, timedelta, timezone

from discord.ext import commands

from ..constants import (
    WORKSHOP_ROLE_ID,
    WORKSHOP_TEXT_CHANNEL_ID,
    WORKSHOP_VOICE_CHANNEL_ID,
)


logger = logging.getLogger(__name__)
CLEANUP_INTERVAL_SECONDS = 600
PURGE_AGE = timedelta(days=1)


class WorkshopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_load(self) -> None:
        self.bot.loop.create_task(self.text_cleanup_task())

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if (
            before.channel is None
            or before.channel.id != WORKSHOP_VOICE_CHANNEL_ID
        ) and (
            after.channel is not None
            and after.channel.id == WORKSHOP_VOICE_CHANNEL_ID
        ):
            # Member joined workshop voice channel
            logger.info(f"{member} joined AMC Workshop voice channel")
            await member.add_roles(member.guild.get_role(WORKSHOP_ROLE_ID))
            channel = member.guild.get_channel(WORKSHOP_TEXT_CHANNEL_ID)
            await channel.set_permissions(member, view_channel=True)
        elif (
            before.channel is not None
            and before.channel.id == WORKSHOP_VOICE_CHANNEL_ID
        ) and (
            after.channel is None
            or after.channel.id != WORKSHOP_VOICE_CHANNEL_ID
        ):
            # Member left workshop voice channel
            logger.info(f"{member} left AMC Workshop voice channel")
            channel = member.guild.get_channel(WORKSHOP_TEXT_CHANNEL_ID)
            await channel.set_permissions(member, overwrite=None)

    async def text_cleanup_task(self):
        await asyncio.sleep(10)
        while True:
            try:
                await self.purge_old_messages()
            except Exception:
                logger.exception("Workshop text cleanup failed")
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

    async def purge_old_messages(self) -> None:
        channel = self.bot.get_channel(WORKSHOP_TEXT_CHANNEL_ID)
        if channel is None:
            channel = await self.bot.fetch_channel(WORKSHOP_TEXT_CHANNEL_ID)

        cutoff = datetime.now(timezone.utc) - PURGE_AGE
        purged = await channel.purge(before=cutoff)
        logger.info(f"Workshop text cleanup removed {len(purged)} messages")
