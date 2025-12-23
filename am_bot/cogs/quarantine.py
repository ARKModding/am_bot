import logging
import os
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands


logger = logging.getLogger(__name__)

QUARANTINE_HONEYPOT_CHANNEL_ID = int(
    os.getenv("QUARANTINE_HONEYPOT_CHANNEL_ID", 0)
)
QUARANTINE_ROLE_ID = int(os.getenv("QUARANTINE_ROLE_ID", 0))


class QuarantineCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot

    async def _delete_honeypot_message(self, message: discord.Message) -> None:
        """Delete the message that triggered the honeypot."""
        try:
            await message.delete()
            logger.debug(f"Deleted honeypot message from {message.author}")
        except discord.errors.Forbidden:
            logger.warning(
                f"Could not delete honeypot message from {message.author}"
            )
        except discord.errors.NotFound:
            logger.debug("Honeypot message already deleted")

    async def _assign_quarantine_role(
        self, member: discord.Member, guild: discord.Guild
    ) -> bool:
        """Assign quarantine role to member. Returns True on success."""
        quarantine_role = guild.get_role(QUARANTINE_ROLE_ID)
        if quarantine_role is None:
            logger.error(
                f"Quarantine role {QUARANTINE_ROLE_ID} not found in guild."
            )
            return False

        try:
            await member.add_roles(
                quarantine_role, reason="Triggered quarantine honeypot"
            )
            logger.info(f"Assigned quarantine role to {member} ({member.id})")
            return True
        except discord.errors.Forbidden:
            logger.error(
                f"Bot lacks permission to assign quarantine role to {member}"
            )
            return False

    async def _purge_member_messages(
        self, member: discord.Member, guild: discord.Guild
    ) -> int:
        """Purge messages from member in last hour. Returns deleted count."""
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        deleted_count = 0

        for channel in guild.text_channels:
            deleted_count += await self._purge_channel(
                channel, member, one_hour_ago
            )

        return deleted_count

    async def _purge_channel(
        self,
        channel: discord.TextChannel,
        member: discord.Member,
        after: datetime,
    ) -> int:
        """Purge messages from member in a single channel. Returns count."""
        try:
            permissions = channel.permissions_for(channel.guild.me)
            if (
                not permissions.read_messages
                or not permissions.manage_messages
            ):
                logger.debug(f"Skipping {channel.name} - no permissions")
                return 0

            deleted = await channel.purge(
                limit=None,
                check=lambda m: m.author.id == member.id,
                after=after,
                reason=f"Quarantine purge for {member}",
            )
            if deleted:
                logger.debug(
                    f"Deleted {len(deleted)} messages from {channel.name}"
                )
            return len(deleted)

        except discord.errors.Forbidden:
            logger.debug(f"Cannot purge in {channel.name} - forbidden")
        except discord.errors.HTTPException as e:
            logger.warning(f"HTTP error purging in {channel.name}: {e}")
        return 0

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id != QUARANTINE_HONEYPOT_CHANNEL_ID:
            return

        if QUARANTINE_HONEYPOT_CHANNEL_ID == 0 or QUARANTINE_ROLE_ID == 0:
            logger.warning("Quarantine IDs not configured. Skipping.")
            return

        member = message.author
        guild = message.guild

        if guild is None:
            logger.warning("Message not in a guild. Skipping.")
            return

        logger.info(
            f"Honeypot triggered by {member} ({member.id}) "
            f"in channel {message.channel.name}"
        )

        await self._delete_honeypot_message(message)

        if not await self._assign_quarantine_role(member, guild):
            return

        deleted_count = await self._purge_member_messages(member, guild)

        logger.info(
            f"Quarantine complete for {member} ({member.id}). "
            f"Deleted {deleted_count} messages from the last hour."
        )
