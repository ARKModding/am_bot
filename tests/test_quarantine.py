"""Tests for the QuarantineCog module."""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import (
    make_mock_bot,
    make_mock_channel,
    make_mock_guild,
    make_mock_member,
    make_mock_message,
)


# Set environment variables before importing the module
@pytest.fixture(autouse=True)
def setup_env():
    """Set up environment variables for tests."""
    with patch.dict(
        os.environ,
        {
            "QUARANTINE_HONEYPOT_CHANNEL_ID": "123456789",
            "QUARANTINE_ROLE_ID": "987654321",
            "SPAM_SIMILARITY_THRESHOLD": "0.85",
            "SPAM_CHANNEL_THRESHOLD": "3",
            "MESSAGE_HISTORY_SECONDS": "3600",
            "SPAM_MIN_MESSAGE_LENGTH": "20",
        },
    ):
        yield


class TestMessageRecord:
    """Tests for the MessageRecord dataclass."""

    def test_message_record_creation(self):
        """Test creating a MessageRecord."""
        from am_bot.cogs.quarantine import MessageRecord

        now = datetime.now(timezone.utc)
        record = MessageRecord(
            content="test message content",
            channel_id=123456789,
            timestamp=now,
        )
        assert record.content == "test message content"
        assert record.channel_id == 123456789
        assert record.timestamp == now


class TestQuarantineCog:
    """Tests for the QuarantineCog class."""

    @pytest.fixture
    def cog(self):
        """Create a QuarantineCog instance with mocked bot."""
        from am_bot.cogs.quarantine import QuarantineCog

        bot = make_mock_bot()
        return QuarantineCog(bot)

    def test_init(self, cog):
        """Test QuarantineCog initialization."""
        assert cog.bot is not None
        assert cog.message_history is not None
        assert len(cog.message_history) == 0
        assert cog._cleanup_task is None

    def test_get_similarity_identical(self, cog):
        """Test similarity calculation for identical strings."""
        similarity = cog._get_similarity("hello world", "hello world")
        assert similarity == 1.0

    def test_get_similarity_different(self, cog):
        """Test similarity calculation for different strings."""
        similarity = cog._get_similarity("hello", "goodbye")
        assert similarity < 0.5

    def test_get_similarity_similar(self, cog):
        """Test similarity calculation for similar strings."""
        similarity = cog._get_similarity(
            "this is a test message about spam",
            "this is a test message about spam detection",
        )
        assert similarity > 0.7

    def test_record_message(self, cog):
        """Test recording a message in history."""
        message = make_mock_message(content="This is a test message")
        message.author.id = 12345

        cog._record_message(message)

        assert 12345 in cog.message_history
        assert len(cog.message_history[12345]) == 1
        assert (
            cog.message_history[12345][0].content == "this is a test message"
        )

    def test_record_message_truncates_long_content(self, cog):
        """Test that long messages are truncated."""
        long_content = "x" * 500
        message = make_mock_message(content=long_content)
        message.author.id = 12345

        cog._record_message(message)

        # Content should be truncated to 200 characters
        assert len(cog.message_history[12345][0].content) == 200

    def test_record_message_enforces_max_limit(self, cog):
        """Test that message history enforces max limit per user."""
        from am_bot.cogs.quarantine import _MAX_MESSAGES_PER_USER

        message = make_mock_message(content="Test message")
        message.author.id = 12345

        # Record more messages than the limit
        for i in range(_MAX_MESSAGES_PER_USER + 10):
            message.content = f"Message number {i}"
            cog._record_message(message)

        assert len(cog.message_history[12345]) == _MAX_MESSAGES_PER_USER

    def test_detect_cross_channel_spam_empty_content(self, cog):
        """Test spam detection returns False for empty content."""
        result = cog._detect_cross_channel_spam(12345, "", 99999)
        assert result is False

    def test_detect_cross_channel_spam_short_message(self, cog):
        """Test spam detection returns False for short messages."""
        result = cog._detect_cross_channel_spam(12345, "hi", 99999)
        assert result is False

    def test_detect_cross_channel_spam_no_history(self, cog):
        """Test spam detection returns False when no history exists."""
        result = cog._detect_cross_channel_spam(
            12345, "This is a longer test message for spam detection", 99999
        )
        assert result is False

    def test_detect_cross_channel_spam_detects_spam(self, cog):
        """Test spam detection detects cross-channel spam."""
        from am_bot.cogs.quarantine import MessageRecord

        user_id = 12345
        spam_message = (
            "This is definitely spam that should be detected across channels"
        )

        # Add similar messages to history from different channels
        now = datetime.now(timezone.utc)
        cog.message_history[user_id] = [
            MessageRecord(spam_message.lower(), 100, now),
            MessageRecord(spam_message.lower(), 200, now),
            MessageRecord(spam_message.lower(), 300, now),
        ]

        # Check a new message in a different channel
        result = cog._detect_cross_channel_spam(
            user_id, spam_message, 999  # Different channel
        )
        assert result is True

    def test_detect_cross_channel_spam_same_channel_not_spam(self, cog):
        """Test that same-channel messages don't trigger spam detection."""
        from am_bot.cogs.quarantine import MessageRecord

        user_id = 12345
        spam_message = (
            "This is definitely spam that should be detected across channels"
        )

        # Add messages to history from the SAME channel
        now = datetime.now(timezone.utc)
        cog.message_history[user_id] = [
            MessageRecord(spam_message.lower(), 100, now),
            MessageRecord(spam_message.lower(), 100, now),
            MessageRecord(spam_message.lower(), 100, now),
        ]

        # Check a new message in the same channel - should NOT be spam
        result = cog._detect_cross_channel_spam(user_id, spam_message, 100)
        assert result is False

    def test_detect_cross_channel_spam_different_lengths(self, cog):
        """Test spam detection skips messages with very different lengths."""
        from am_bot.cogs.quarantine import MessageRecord

        user_id = 12345
        now = datetime.now(timezone.utc)

        # Add a short message to history
        cog.message_history[user_id] = [
            MessageRecord("short", 100, now),
        ]

        # Check a much longer message - should not match due to length ratio
        long_message = "This is a very long message that should not match"
        result = cog._detect_cross_channel_spam(user_id, long_message, 200)
        assert result is False

    def test_cleanup_old_messages(self, cog):
        """Test cleanup of old messages."""
        from am_bot.cogs.quarantine import (
            MESSAGE_HISTORY_SECONDS,
            MessageRecord,
        )

        user_id = 12345
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(seconds=MESSAGE_HISTORY_SECONDS + 100)

        # Add old and new messages
        cog.message_history[user_id] = [
            MessageRecord("old message", 100, old_time),
            MessageRecord("new message", 200, now),
        ]

        cog._cleanup_old_messages()

        # Only new message should remain
        assert len(cog.message_history[user_id]) == 1
        assert cog.message_history[user_id][0].content == "new message"

    def test_cleanup_removes_empty_users(self, cog):
        """Test that cleanup removes users with no messages."""
        from am_bot.cogs.quarantine import (
            MESSAGE_HISTORY_SECONDS,
            MessageRecord,
        )

        user_id = 12345
        old_time = datetime.now(timezone.utc) - timedelta(
            seconds=MESSAGE_HISTORY_SECONDS + 100
        )

        # Add only old messages
        cog.message_history[user_id] = [
            MessageRecord("old message", 100, old_time),
        ]

        cog._cleanup_old_messages()

        # User should be removed entirely
        assert user_id not in cog.message_history

    @pytest.mark.asyncio
    async def test_assign_quarantine_role_no_role_configured(self, cog):
        """Test that quarantine role assignment fails when not configured."""
        with patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 0):
            member = make_mock_member()
            guild = make_mock_guild()
            result = await cog._assign_quarantine_role(
                member, guild, "test reason"
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_assign_quarantine_role_role_not_found(self, cog):
        """Test quarantine role assignment when role doesn't exist."""
        with patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 12345):
            member = make_mock_member()
            guild = make_mock_guild()
            guild.get_role.return_value = None

            result = await cog._assign_quarantine_role(
                member, guild, "test reason"
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_assign_quarantine_role_success(self, cog):
        """Test successful quarantine role assignment."""
        with patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 12345):
            member = make_mock_member()
            guild = make_mock_guild()
            mock_role = MagicMock()
            guild.get_role.return_value = mock_role

            result = await cog._assign_quarantine_role(
                member, guild, "test reason"
            )

            assert result is True
            member.add_roles.assert_called_once_with(
                mock_role, reason="test reason"
            )

    @pytest.mark.asyncio
    async def test_assign_quarantine_role_forbidden(self, cog):
        """Test quarantine role assignment when bot lacks permissions."""
        import discord

        with patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 12345):
            member = make_mock_member()
            member.add_roles.side_effect = discord.errors.Forbidden(
                MagicMock(), "Missing permissions"
            )
            guild = make_mock_guild()
            mock_role = MagicMock()
            guild.get_role.return_value = mock_role

            result = await cog._assign_quarantine_role(
                member, guild, "test reason"
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_purge_channel_success(self, cog):
        """Test successful channel purge."""
        # Create guild with proper me attribute
        guild = make_mock_guild()
        channel = make_mock_channel(guild=guild)
        channel.guild = guild

        member = make_mock_member()
        after = datetime.now(timezone.utc) - timedelta(hours=1)

        # Mock purge returning deleted messages
        deleted_messages = [MagicMock() for _ in range(5)]
        channel.purge.return_value = deleted_messages

        result = await cog._purge_channel(channel, member, after)
        assert result == 5

    @pytest.mark.asyncio
    async def test_purge_channel_no_permissions(self, cog):
        """Test channel purge when bot lacks permissions."""
        # Create guild with proper me attribute
        guild = make_mock_guild()
        channel = make_mock_channel(guild=guild)
        channel.guild = guild

        permissions = MagicMock()
        permissions.read_messages = False
        permissions.manage_messages = False
        channel.permissions_for.return_value = permissions

        member = make_mock_member()
        after = datetime.now(timezone.utc) - timedelta(hours=1)

        result = await cog._purge_channel(channel, member, after)
        assert result == 0

    @pytest.mark.asyncio
    async def test_on_message_ignores_bot_messages(self, cog):
        """Test that bot messages are ignored."""
        message = make_mock_message()
        message.author.bot = True

        # Should not raise and should return early
        await cog.on_message(message)
        # No quarantine action should be taken
        message.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_ignores_dms(self, cog):
        """Test that DMs are ignored."""
        message = make_mock_message()
        message.guild = None

        await cog.on_message(message)
        message.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_honeypot_trigger(self, cog):
        """Test honeypot channel triggers quarantine."""
        with (
            patch(
                "am_bot.cogs.quarantine.QUARANTINE_HONEYPOT_CHANNEL_ID", 12345
            ),
            patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 98765),
        ):
            message = make_mock_message()
            message.author.bot = False
            message.channel.id = 12345  # Honeypot channel

            guild = make_mock_guild()
            message.guild = guild
            mock_role = MagicMock()
            guild.get_role.return_value = mock_role

            await cog.on_message(message)

            # Message should be deleted
            message.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_records_normal_message(self, cog):
        """Test that normal messages are recorded in history."""
        with patch("am_bot.cogs.quarantine.QUARANTINE_HONEYPOT_CHANNEL_ID", 0):
            message = make_mock_message(
                content="This is a normal message to test"
            )
            message.author.bot = False
            message.author.id = 12345
            message.channel.id = 99999

            await cog.on_message(message)

            # Message should be recorded
            assert 12345 in cog.message_history
            assert len(cog.message_history[12345]) == 1

    def test_cog_unload_cancels_cleanup_task(self, cog):
        """Test that cog_unload cancels the cleanup task."""
        mock_task = MagicMock()
        cog._cleanup_task = mock_task

        cog.cog_unload()

        mock_task.cancel.assert_called_once()

    def test_cog_unload_handles_no_task(self, cog):
        """Test that cog_unload handles case when no task exists."""
        cog._cleanup_task = None

        # Should not raise
        cog.cog_unload()

    def test_cog_load_creates_cleanup_task(self, cog):
        """Test that cog_load creates the cleanup task."""
        mock_task = MagicMock()
        cog.bot.loop.create_task = MagicMock(return_value=mock_task)

        cog.cog_load()

        cog.bot.loop.create_task.assert_called_once()
        assert cog._cleanup_task == mock_task

    @pytest.mark.asyncio
    async def test_handle_quarantine_deletes_message(self, cog):
        """Test that handle_quarantine deletes the triggering message."""
        with patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 0):
            message = make_mock_message()
            message.author = make_mock_member(user_id=12345)
            message.guild = make_mock_guild()

            await cog._handle_quarantine(message, "test reason")

            message.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_quarantine_clears_user_history(self, cog):
        """Test that quarantine clears the user's message history."""
        with patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 98765):
            from am_bot.cogs.quarantine import MessageRecord
            from datetime import datetime, timezone

            member = make_mock_member(user_id=12345)
            guild = make_mock_guild()
            mock_role = MagicMock()
            guild.get_role.return_value = mock_role
            guild.text_channels = []  # No channels to purge

            message = make_mock_message()
            message.author = member
            message.guild = guild

            # Add some message history
            cog.message_history[12345] = [
                MessageRecord("test", 100, datetime.now(timezone.utc))
            ]

            await cog._handle_quarantine(message, "test reason")

            # User history should be cleared
            assert 12345 not in cog.message_history

    @pytest.mark.asyncio
    async def test_purge_member_messages(self, cog):
        """Test purging all messages from a member."""
        guild = make_mock_guild()
        channel1 = make_mock_channel(channel_id=111)
        channel1.guild = guild
        channel1.purge.return_value = [MagicMock(), MagicMock()]

        channel2 = make_mock_channel(channel_id=222)
        channel2.guild = guild
        channel2.purge.return_value = [MagicMock()]

        guild.text_channels = [channel1, channel2]
        member = make_mock_member()

        result = await cog._purge_member_messages(member, guild)

        assert result == 3  # 2 from channel1 + 1 from channel2

    @pytest.mark.asyncio
    async def test_purge_channel_http_exception(self, cog):
        """Test channel purge handles HTTP exceptions."""
        import discord

        guild = make_mock_guild()
        channel = make_mock_channel(guild=guild)
        channel.guild = guild
        channel.purge.side_effect = discord.errors.HTTPException(
            MagicMock(status=500), "Internal Server Error"
        )

        member = make_mock_member()
        after = datetime.now(timezone.utc) - timedelta(hours=1)

        result = await cog._purge_channel(channel, member, after)
        assert result == 0

    @pytest.mark.asyncio
    async def test_purge_channel_forbidden(self, cog):
        """Test channel purge handles Forbidden exception."""
        import discord

        guild = make_mock_guild()
        channel = make_mock_channel(guild=guild)
        channel.guild = guild
        channel.purge.side_effect = discord.errors.Forbidden(
            MagicMock(), "Missing access"
        )

        member = make_mock_member()
        after = datetime.now(timezone.utc) - timedelta(hours=1)

        result = await cog._purge_channel(channel, member, after)
        assert result == 0

    @pytest.mark.asyncio
    async def test_on_message_spam_detection_triggers_quarantine(self, cog):
        """Test that spam detection triggers quarantine."""
        from am_bot.cogs.quarantine import MessageRecord

        with (
            patch("am_bot.cogs.quarantine.QUARANTINE_HONEYPOT_CHANNEL_ID", 0),
            patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 98765),
        ):
            user_id = 12345
            spam_message = "This is definitely spam across channels"

            # Pre-populate history with similar messages
            now = datetime.now(timezone.utc)
            cog.message_history[user_id] = [
                MessageRecord(spam_message.lower(), 100, now),
                MessageRecord(spam_message.lower(), 200, now),
                MessageRecord(spam_message.lower(), 300, now),
            ]

            guild = make_mock_guild()
            mock_role = MagicMock()
            guild.get_role.return_value = mock_role
            guild.text_channels = []

            member = make_mock_member(user_id=user_id)
            message = make_mock_message(content=spam_message)
            message.author = member
            message.author.bot = False
            message.guild = guild
            message.channel.id = 999  # Different channel

            await cog.on_message(message)

            # Message should be deleted (quarantine triggered)
            message.delete.assert_called_once()
