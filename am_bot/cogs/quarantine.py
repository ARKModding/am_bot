import asyncio
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import discord
from discord import app_commands
from discord.ext import commands

from am_bot.constants import (
    QUARANTINE_HONEYPOT_CHANNEL_ID,
    QUARANTINE_ROLE_ID,
    STAFF_ROLE_ID,
)


logger = logging.getLogger(__name__)

# Spam detection configuration
# Minimum similarity ratio (0.0 to 1.0) to consider messages as duplicates
SPAM_SIMILARITY_THRESHOLD = float(os.getenv("SPAM_SIMILARITY_THRESHOLD", 0.85))
# Number of similar messages across different channels to trigger quarantine
SPAM_CHANNEL_THRESHOLD = int(os.getenv("SPAM_CHANNEL_THRESHOLD", 3))
# Message history retention in seconds (default 1 hour)
MESSAGE_HISTORY_SECONDS = int(os.getenv("MESSAGE_HISTORY_SECONDS", 3600))
# Minimum message length to consider for spam detection (ignore short messages)
SPAM_MIN_MESSAGE_LENGTH = int(os.getenv("SPAM_MIN_MESSAGE_LENGTH", 20))

# Internal constants (not configurable)
_MAX_MESSAGES_PER_USER = 50
_MAX_CONTENT_LENGTH = 200
_CLEANUP_INTERVAL_SECONDS = 300


@dataclass
class MessageRecord:
    """Record of a user's message for spam detection."""

    content: str  # Stored lowercase for efficient comparison
    channel_id: int
    timestamp: datetime


class QuarantineCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot
        # user_id -> list of MessageRecord
        self.message_history: dict[int, list[MessageRecord]] = defaultdict(
            list
        )
        self._cleanup_task: asyncio.Task | None = None

    def cog_load(self) -> None:
        """Start the periodic cleanup task when cog is loaded."""
        self._cleanup_task = self.bot.loop.create_task(
            self._periodic_cleanup()
        )

    def cog_unload(self) -> None:
        """Cancel the cleanup task when cog is unloaded."""
        if self._cleanup_task:
            self._cleanup_task.cancel()

    async def _periodic_cleanup(self) -> None:
        """Periodically clean up old messages from all users."""
        await asyncio.sleep(60)  # Initial delay
        while True:
            try:
                self._cleanup_old_messages()
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
            await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)

    def _cleanup_old_messages(self) -> None:
        """Clean up old messages from all users."""
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=MESSAGE_HISTORY_SECONDS
        )
        users_to_remove = []

        for user_id, messages in self.message_history.items():
            self.message_history[user_id] = [
                msg for msg in messages if msg.timestamp > cutoff
            ]
            if not self.message_history[user_id]:
                users_to_remove.append(user_id)

        for user_id in users_to_remove:
            del self.message_history[user_id]

        if users_to_remove:
            logger.debug(
                f"Cleaned up history for {len(users_to_remove)} users"
            )

    def _record_message(self, message: discord.Message) -> None:
        """Record a message in the user's history."""
        # Store lowercase and truncated for memory efficiency
        content = message.content[:_MAX_CONTENT_LENGTH].lower()

        record = MessageRecord(
            content=content,
            channel_id=message.channel.id,
            timestamp=datetime.now(timezone.utc),
        )

        user_history = self.message_history[message.author.id]
        user_history.append(record)

        # Enforce max messages per user (remove oldest if over limit)
        if len(user_history) > _MAX_MESSAGES_PER_USER:
            self.message_history[message.author.id] = user_history[
                -_MAX_MESSAGES_PER_USER:
            ]

    def _get_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity ratio between two lowercase strings."""
        return SequenceMatcher(None, text1, text2).ratio()

    def _detect_cross_channel_spam(
        self, user_id: int, new_content: str, current_channel_id: int
    ) -> bool:
        """
        Detect if a user is spamming similar messages across channels.

        Returns True if spam is detected.
        """
        content = new_content.strip()
        if not content:
            return False

        # Skip short messages to avoid false positives (e.g., "lol", "ok")
        if len(content) < SPAM_MIN_MESSAGE_LENGTH:
            return False

        history = self.message_history.get(user_id, [])
        if not history:
            return False

        # Lowercase once for all comparisons
        content_lower = content.lower()

        # Find channels where similar messages were posted
        spam_channels: set[int] = set()

        for record in history:
            # Skip messages from the same channel
            if record.channel_id == current_channel_id:
                continue

            # Quick length check - very different lengths can't be similar
            len_ratio = (
                len(content_lower) / len(record.content)
                if record.content
                else 0
            )
            if len_ratio < 0.5 or len_ratio > 2.0:
                continue

            similarity = self._get_similarity(content_lower, record.content)
            if similarity >= SPAM_SIMILARITY_THRESHOLD:
                spam_channels.add(record.channel_id)
                logger.debug(
                    f"Similar message found in channel {record.channel_id} "
                    f"(similarity: {similarity:.2%})"
                )

        # Include current channel in the count
        total_channels = len(spam_channels) + 1

        if total_channels >= SPAM_CHANNEL_THRESHOLD:
            logger.info(
                f"Cross-channel spam detected for user {user_id}: "
                f"similar messages in {total_channels} channels"
            )
            return True

        return False

    async def _assign_quarantine_role(
        self, member: discord.Member, guild: discord.Guild, reason: str
    ) -> bool:
        """Assign quarantine role to member. Returns True on success."""
        if QUARANTINE_ROLE_ID == 0:
            logger.warning("Quarantine role ID not configured.")
            return False

        quarantine_role = guild.get_role(QUARANTINE_ROLE_ID)
        if quarantine_role is None:
            logger.error(
                f"Quarantine role {QUARANTINE_ROLE_ID} not found in guild."
            )
            return False

        try:
            await member.add_roles(quarantine_role, reason=reason)
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

        # Purge from regular text channels
        for channel in guild.text_channels:
            deleted_count += await self._purge_channel(
                channel, member, one_hour_ago
            )

        # Purge from voice channel text chats
        for voice_channel in guild.voice_channels:
            deleted_count += await self._purge_channel(
                voice_channel, member, one_hour_ago
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

    async def _handle_quarantine(
        self, message: discord.Message, reason: str
    ) -> None:
        """Handle quarantining a user: assign role and purge messages."""
        member = message.author
        guild = message.guild

        logger.info(
            f"Quarantine triggered for {member} ({member.id}): {reason}"
        )

        # Delete the triggering message
        try:
            await message.delete()
        except (discord.errors.Forbidden, discord.errors.NotFound):
            pass

        if not await self._assign_quarantine_role(member, guild, reason):
            return

        deleted_count = await self._purge_member_messages(member, guild)

        # Clear their message history from memory
        if member.id in self.message_history:
            del self.message_history[member.id]

        logger.info(
            f"Quarantine complete for {member} ({member.id}). "
            f"Deleted {deleted_count} messages from the last hour."
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages and DMs
        if message.author.bot or message.guild is None:
            return

        # Check 1: Honeypot channel trigger
        if message.channel.id == QUARANTINE_HONEYPOT_CHANNEL_ID:
            if QUARANTINE_HONEYPOT_CHANNEL_ID != 0:
                await self._handle_quarantine(
                    message, "Triggered quarantine honeypot"
                )
                return

        # Check 2: Cross-channel spam detection
        if self._detect_cross_channel_spam(
            message.author.id, message.content, message.channel.id
        ):
            await self._handle_quarantine(
                message, "Cross-channel spam detected"
            )
            return

        # Record the message for future spam detection
        self._record_message(message)

    def _is_staff(self, member: discord.Member) -> bool:
        """Check if a member has the staff role."""
        if STAFF_ROLE_ID == 0:
            return False
        return any(role.id == STAFF_ROLE_ID for role in member.roles)

    @app_commands.command(
        name="quarantine",
        description="Quarantine a user and purge their recent messages",
    )
    @app_commands.describe(
        member="The member to quarantine", reason="Reason for the quarantine"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def quarantine_command(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str | None = None,
    ) -> None:
        """Slash command for staff to manually quarantine a user."""
        # Check if user has staff role
        if not self._is_staff(interaction.user):
            await interaction.response.send_message(
                "You must be staff to use this command.", ephemeral=True
            )
            return

        reason = reason or "Manual quarantine by staff"
        full_reason = f"{reason} (by {interaction.user})"

        # Don't allow quarantining bots
        if member.bot:
            await interaction.response.send_message(
                "Cannot quarantine bots.", ephemeral=True
            )
            return

        # Don't allow self-quarantine
        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "You cannot quarantine yourself.", ephemeral=True
            )
            return

        # Defer the response since purging may take time
        await interaction.response.defer(ephemeral=True)

        logger.info(
            f"Manual quarantine initiated for {member} ({member.id}) "
            f"by {interaction.user} ({interaction.user.id}): {reason}"
        )

        success = await self._assign_quarantine_role(
            member, interaction.guild, full_reason
        )

        if not success:
            await interaction.followup.send(
                "Failed to assign quarantine role. Check bot permissions.",
                ephemeral=True,
            )
            return

        deleted_count = await self._purge_member_messages(
            member, interaction.guild
        )

        # Clear their message history from memory
        if member.id in self.message_history:
            del self.message_history[member.id]

        logger.info(
            f"Manual quarantine complete for {member} ({member.id}). "
            f"Deleted {deleted_count} messages from the last hour."
        )

        await interaction.followup.send(
            f"✅ Quarantined {member.mention}.\n"
            f"Deleted {deleted_count} messages from the last hour.\n"
            f"Reason: {reason}",
            ephemeral=True,
        )
