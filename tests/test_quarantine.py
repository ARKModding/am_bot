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
    make_mock_role,
)


# Set environment variables before importing the module
@pytest.fixture(autouse=True)
def setup_env():
    """Set up environment variables for tests."""
    with patch.dict(
        os.environ,
        {
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
            from datetime import datetime, timezone

            from am_bot.cogs.quarantine import MessageRecord

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


class TestQuarantineSlashCommand:
    """Tests for the /quarantine slash command."""

    @pytest.fixture
    def cog(self):
        """Create a QuarantineCog instance with mocked bot."""
        from am_bot.cogs.quarantine import QuarantineCog

        bot = make_mock_bot()
        return QuarantineCog(bot)

    @pytest.fixture
    def staff_role(self):
        """Create a mock staff role."""
        return make_mock_role(role_id=322496447687819264, name="Staff")

    @pytest.fixture
    def mock_interaction(self, staff_role):
        """Create a mock Discord interaction with a staff user."""
        from unittest.mock import AsyncMock

        interaction = MagicMock()
        interaction.user = make_mock_member(
            user_id=11111, name="StaffUser", roles=[staff_role]
        )
        interaction.guild = make_mock_guild()
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    def test_is_staff_returns_true_for_staff_member(self, cog, staff_role):
        """Test _is_staff returns True when member has staff role."""
        with patch("am_bot.cogs.quarantine.STAFF_ROLE_ID", 322496447687819264):
            member = make_mock_member(roles=[staff_role])
            assert cog._is_staff(member) is True

    def test_is_staff_returns_false_for_non_staff(self, cog):
        """Test _is_staff returns False when member lacks staff role."""
        with patch("am_bot.cogs.quarantine.STAFF_ROLE_ID", 322496447687819264):
            other_role = make_mock_role(role_id=999999, name="Other")
            member = make_mock_member(roles=[other_role])
            assert cog._is_staff(member) is False

    def test_is_staff_returns_false_when_not_configured(self, cog, staff_role):
        """Test _is_staff returns False when STAFF_ROLE_ID is 0."""
        with patch("am_bot.cogs.quarantine.STAFF_ROLE_ID", 0):
            member = make_mock_member(roles=[staff_role])
            assert cog._is_staff(member) is False

    @pytest.mark.asyncio
    async def test_quarantine_command_rejects_non_staff(self, cog):
        """Test command rejects users without staff role."""
        from unittest.mock import AsyncMock

        with patch("am_bot.cogs.quarantine.STAFF_ROLE_ID", 322496447687819264):
            interaction = MagicMock()
            interaction.user = make_mock_member(user_id=11111, roles=[])
            interaction.response = MagicMock()
            interaction.response.send_message = AsyncMock()

            target = make_mock_member(user_id=22222)

            await cog.quarantine_command.callback(
                cog, interaction, target, None
            )

            interaction.response.send_message.assert_called_once()
            call_args = interaction.response.send_message.call_args
            assert "must be staff" in call_args[0][0]
            assert call_args[1]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_quarantine_command_rejects_bots(
        self, cog, mock_interaction
    ):
        """Test that the command rejects attempts to quarantine bots."""
        with patch("am_bot.cogs.quarantine.STAFF_ROLE_ID", 322496447687819264):
            target = make_mock_member(user_id=22222, bot=True)

            await cog.quarantine_command.callback(
                cog, mock_interaction, target, None
            )

            mock_interaction.response.send_message.assert_called_once()
            call_args = mock_interaction.response.send_message.call_args
            assert "Cannot quarantine bots" in call_args[0][0]
            assert call_args[1]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_quarantine_command_rejects_self(
        self, cog, mock_interaction
    ):
        """Test that the command rejects self-quarantine."""
        with patch("am_bot.cogs.quarantine.STAFF_ROLE_ID", 322496447687819264):
            # Target is the same as the invoker
            target = make_mock_member(user_id=11111, name="StaffUser")
            mock_interaction.user.id = 11111

            await cog.quarantine_command.callback(
                cog, mock_interaction, target, None
            )

            mock_interaction.response.send_message.assert_called_once()
            call_args = mock_interaction.response.send_message.call_args
            assert "cannot quarantine yourself" in call_args[0][0]
            assert call_args[1]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_quarantine_command_fails_without_role(
        self, cog, mock_interaction
    ):
        """Test command handles missing quarantine role."""
        with (
            patch("am_bot.cogs.quarantine.STAFF_ROLE_ID", 322496447687819264),
            patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 0),
        ):
            target = make_mock_member(user_id=22222)

            await cog.quarantine_command.callback(
                cog, mock_interaction, target, None
            )

            mock_interaction.response.defer.assert_called_once()
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            assert "Failed to assign quarantine role" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_quarantine_command_success(self, cog, mock_interaction):
        """Test successful quarantine via slash command."""
        with (
            patch("am_bot.cogs.quarantine.STAFF_ROLE_ID", 322496447687819264),
            patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 98765),
        ):
            target = make_mock_member(user_id=22222, name="BadUser")
            mock_role = MagicMock()
            mock_interaction.guild.get_role.return_value = mock_role
            mock_interaction.guild.text_channels = []

            await cog.quarantine_command.callback(
                cog, mock_interaction, target, "Spamming in chat"
            )

            # Should defer and then follow up
            mock_interaction.response.defer.assert_called_once_with(
                ephemeral=True
            )
            mock_interaction.followup.send.assert_called_once()

            # Check the followup message
            call_args = mock_interaction.followup.send.call_args
            assert "Quarantined" in call_args[0][0]
            assert "Spamming in chat" in call_args[0][0]
            assert call_args[1]["ephemeral"] is True

            # Role should be assigned
            target.add_roles.assert_called_once()

    @pytest.mark.asyncio
    async def test_quarantine_command_default_reason(
        self, cog, mock_interaction
    ):
        """Test quarantine command with default reason."""
        with (
            patch("am_bot.cogs.quarantine.STAFF_ROLE_ID", 322496447687819264),
            patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 98765),
        ):
            target = make_mock_member(user_id=22222)
            mock_role = MagicMock()
            mock_interaction.guild.get_role.return_value = mock_role
            mock_interaction.guild.text_channels = []

            await cog.quarantine_command.callback(
                cog, mock_interaction, target, None
            )

            # Check the role was assigned with default reason
            target.add_roles.assert_called_once()
            call_kwargs = target.add_roles.call_args[1]
            assert "Manual quarantine by staff" in call_kwargs["reason"]

    @pytest.mark.asyncio
    async def test_quarantine_command_clears_message_history(
        self, cog, mock_interaction
    ):
        """Test that quarantine clears user's message history."""
        from am_bot.cogs.quarantine import MessageRecord

        with (
            patch("am_bot.cogs.quarantine.STAFF_ROLE_ID", 322496447687819264),
            patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 98765),
        ):
            target_id = 22222
            target = make_mock_member(user_id=target_id)
            mock_role = MagicMock()
            mock_interaction.guild.get_role.return_value = mock_role
            mock_interaction.guild.text_channels = []

            # Pre-populate some message history
            now = datetime.now(timezone.utc)
            cog.message_history[target_id] = [
                MessageRecord("test message", 100, now)
            ]

            await cog.quarantine_command.callback(
                cog, mock_interaction, target, None
            )

            # History should be cleared
            assert target_id not in cog.message_history

    @pytest.mark.asyncio
    async def test_quarantine_command_purges_messages(
        self, cog, mock_interaction
    ):
        """Test that quarantine purges messages from channels."""
        with (
            patch("am_bot.cogs.quarantine.STAFF_ROLE_ID", 322496447687819264),
            patch("am_bot.cogs.quarantine.QUARANTINE_ROLE_ID", 98765),
        ):
            target = make_mock_member(user_id=22222)
            mock_role = MagicMock()
            mock_interaction.guild.get_role.return_value = mock_role

            # Set up channels with messages to purge
            channel1 = make_mock_channel(channel_id=111)
            channel1.guild = mock_interaction.guild
            channel1.purge.return_value = [MagicMock() for _ in range(3)]

            channel2 = make_mock_channel(channel_id=222)
            channel2.guild = mock_interaction.guild
            channel2.purge.return_value = [MagicMock() for _ in range(2)]

            mock_interaction.guild.text_channels = [channel1, channel2]

            await cog.quarantine_command.callback(
                cog, mock_interaction, target, None
            )

            # Check followup reports correct message count
            call_args = mock_interaction.followup.send.call_args
            assert "5 messages" in call_args[0][0]
