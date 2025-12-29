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
            # Member left workshop voice channel
            logger.info(f"{member} left AMC Workshop voice channel")
            channel = member.guild.get_channel(
                channel_id=WORKSHOP_TEXT_CHANNEL_ID
            )
            await channel.set_permissions(member, overwrite=None)

    async def text_cleanup_task(self):
        await asyncio.sleep(10)
        channel = await self.bot.fetch_channel(WORKSHOP_TEXT_CHANNEL_ID)
        while True:
            purge_time = datetime.utcnow() - timedelta(days=1)
            await channel.purge(before=purge_time)
            await asyncio.sleep(600)

