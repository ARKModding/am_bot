import logging
import os
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands


logger = logging.getLogger(__name__)

QUARANTINE_HONEYPOT_CHANNEL_ID = int(os.getenv("QUARANTINE_HONEYPOT_CHANNEL_ID", 0))
QUARANTINE_ROLE_ID = int(os.getenv("QUARANTINE_ROLE_ID", 0))


class QuarantineCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages
        if message.author.bot:
            return

        # Only act on messages in the honeypot channel
        if message.channel.id != QUARANTINE_HONEYPOT_CHANNEL_ID:
            return

        if QUARANTINE_HONEYPOT_CHANNEL_ID == 0 or QUARANTINE_ROLE_ID == 0:
            logger.warning(
                "Quarantine honeypot or role ID not configured. Skipping."
            )
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

        # Delete the honeypot message first
        try:
            await message.delete()
            logger.debug(f"Deleted honeypot message from {member}")
        except discord.errors.Forbidden:
            logger.warning(f"Could not delete honeypot message from {member}")
        except discord.errors.NotFound:
            logger.debug("Honeypot message already deleted")

        # Assign the quarantine role
        quarantine_role = guild.get_role(QUARANTINE_ROLE_ID)
        if quarantine_role is None:
            logger.error(
                f"Quarantine role {QUARANTINE_ROLE_ID} not found in guild."
            )
            return

        try:
            await member.add_roles(
                quarantine_role, reason="Triggered quarantine honeypot"
            )
            logger.info(f"Assigned quarantine role to {member} ({member.id})")
        except discord.errors.Forbidden:
            logger.error(
                f"Bot lacks permission to assign quarantine role to {member}"
            )
            return

        # Delete messages from the last hour across all text channels
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        deleted_count = 0

        for channel in guild.text_channels:
            try:
                # Check if bot has permission to read and manage messages
                permissions = channel.permissions_for(guild.me)
                if not permissions.read_messages or not permissions.manage_messages:
                    logger.debug(
                        f"Skipping channel {channel.name} - insufficient permissions"
                    )
                    continue

                # Use purge with a check function for efficiency
                deleted = await channel.purge(
                    limit=None,
                    check=lambda m: m.author.id == member.id,
                    after=one_hour_ago,
                    reason=f"Quarantine purge for {member}",
                )
                deleted_count += len(deleted)
                if deleted:
                    logger.debug(
                        f"Deleted {len(deleted)} messages from {channel.name}"
                    )

            except discord.errors.Forbidden:
                logger.debug(
                    f"Cannot purge messages in {channel.name} - forbidden"
                )
            except discord.errors.HTTPException as e:
                logger.warning(
                    f"HTTP error purging messages in {channel.name}: {e}"
                )

        logger.info(
            f"Quarantine complete for {member} ({member.id}). "
            f"Deleted {deleted_count} messages from the last hour."
        )

