"""Tests for the InviteResponseCog module."""

from unittest.mock import MagicMock, patch

import pytest

from am_bot.cogs.invite_response import InviteResponseCog
from tests.conftest import (
    make_mock_bot,
    make_mock_channel,
    make_mock_embed,
    make_mock_message,
)


class TestInviteResponseCog:
    """Tests for the InviteResponseCog class."""

    @pytest.fixture
    def cog(self):
        """Create an InviteResponseCog instance with mocked bot."""
        bot = make_mock_bot()
        return InviteResponseCog(bot)

    def test_init(self, cog):
        """Test InviteResponseCog initialization."""
        assert cog.bot is not None

    def test_parse_embed_email_with_backticks(self, cog):
        """Test parsing email from embed with backticks."""
        embed = make_mock_embed(
            fields=[{"name": "Email", "value": "`test@example.com`"}]
        )

        result = cog._parse_embed_email(embed)
        assert result == "test@example.com"

    def test_parse_embed_email_without_backticks(self, cog):
        """Test parsing email from embed without backticks."""
        embed = make_mock_embed(
            fields=[{"name": "Email", "value": "test@example.com"}]
        )

        result = cog._parse_embed_email(embed)
        assert result == "test@example.com"

    def test_parse_embed_email_no_email_field(self, cog):
        """Test parsing when no Email field exists."""
        embed = make_mock_embed(
            fields=[{"name": "Other", "value": "Some value"}]
        )

        result = cog._parse_embed_email(embed)
        assert result is None

    def test_parse_embed_email_empty_fields(self, cog):
        """Test parsing when embed has no fields."""
        embed = make_mock_embed(fields=[])

        result = cog._parse_embed_email(embed)
        assert result is None

    @pytest.mark.asyncio
    async def test_on_message_ignores_self(self, cog):
        """Test that bot ignores its own messages."""
        message = make_mock_message()
        message.author.id = cog.bot.user.id

        with patch("am_bot.cogs.invite_response.send_email") as mock_send:
            await cog.on_message(message)
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_ignores_wrong_channel(self, cog):
        """Test that messages in wrong channel are ignored."""
        message = make_mock_message()
        message.author.id = 12345
        message.channel.id = 99999  # Not the invite help channel

        with patch(
            "am_bot.cogs.invite_response.INVITE_HELP_TEXT_CHANNEL_ID", 88888
        ):
            with patch("am_bot.cogs.invite_response.send_email") as mock_send:
                await cog.on_message(message)
                mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_ignores_no_reference(self, cog):
        """Test that non-reply messages are ignored."""
        message = make_mock_message()
        message.author.id = 12345
        message.reference = None

        with patch(
            "am_bot.cogs.invite_response.INVITE_HELP_TEXT_CHANNEL_ID",
            message.channel.id,
        ):
            with patch("am_bot.cogs.invite_response.send_email") as mock_send:
                await cog.on_message(message)
                mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_ignores_empty_content(self, cog):
        """Test that messages with no content are ignored."""
        message = make_mock_message(content="")
        message.author.id = 12345
        message.reference = MagicMock()
        message.reference.channel_id = message.channel.id
        message.reference.resolved = None
        message.reference.message_id = 123

        with patch(
            "am_bot.cogs.invite_response.INVITE_HELP_TEXT_CHANNEL_ID",
            message.channel.id,
        ):
            with patch("am_bot.cogs.invite_response.send_email") as mock_send:
                await cog.on_message(message)
                mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_sends_email_from_embed(self, cog):
        """Test that email is sent when replying to embed message."""
        channel = make_mock_channel()

        # Create referenced message with embed
        referenced_embed = make_mock_embed(
            description="User's help request here",
            fields=[{"name": "Email", "value": "`user@example.com`"}],
        )
        referenced_message = make_mock_message(embeds=[referenced_embed])

        # Create reply message
        message = make_mock_message(
            content="Here is my response",
            channel=channel,
        )
        message.author.id = 12345
        message.author.display_name = "StaffMember"
        message.reference = MagicMock()
        message.reference.channel_id = channel.id
        message.reference.resolved = referenced_message
        message.reference.message_id = referenced_message.id

        with patch(
            "am_bot.cogs.invite_response.INVITE_HELP_TEXT_CHANNEL_ID",
            channel.id,
        ):
            with patch("am_bot.cogs.invite_response.send_email") as mock_send:
                await cog.on_message(message)

                mock_send.assert_called_once()
                call_args = mock_send.call_args
                assert call_args[0][0] == "user@example.com"
                assert (
                    "ARK Modding Discord Staff Response"
                    in call_args[1]["subject"]
                )
                assert "Here is my response" in call_args[1]["body_txt"]
                assert "StaffMember" in call_args[1]["body_txt"]

    @pytest.mark.asyncio
    async def test_on_message_fetches_unresolved_reference(self, cog):
        """Test that unresolved references are fetched."""
        channel = make_mock_channel()

        # Create referenced message with embed
        referenced_embed = make_mock_embed(
            description="User's help request",
            fields=[{"name": "Email", "value": "`fetched@example.com`"}],
        )
        referenced_message = make_mock_message(embeds=[referenced_embed])
        channel.fetch_message.return_value = referenced_message

        # Create reply message with unresolved reference
        message = make_mock_message(
            content="Staff response",
            channel=channel,
        )
        message.author.id = 12345
        message.author.display_name = "Staff"
        message.reference = MagicMock()
        message.reference.channel_id = channel.id
        message.reference.resolved = None  # Not resolved
        message.reference.message_id = 777777

        with patch(
            "am_bot.cogs.invite_response.INVITE_HELP_TEXT_CHANNEL_ID",
            channel.id,
        ):
            with patch("am_bot.cogs.invite_response.send_email") as mock_send:
                await cog.on_message(message)

                channel.fetch_message.assert_called_once_with(777777)
                mock_send.assert_called_once()
                assert mock_send.call_args[0][0] == "fetched@example.com"

    @pytest.mark.asyncio
    async def test_on_message_handles_legacy_plain_text(self, cog):
        """Test fallback to legacy plain text format."""
        channel = make_mock_channel()

        # Create referenced message with plain text (legacy format)
        # The regex pattern expects "Email: " at the start of the line
        legacy_content = """Email: legacy@example.com
Line 2
Line 3
Line 4
Line 5
Line 6
Line 7
Help request content
More content here"""
        referenced_message = make_mock_message(
            content=legacy_content, embeds=[]
        )

        # Create reply message
        message = make_mock_message(
            content="Response to legacy",
            channel=channel,
        )
        message.author.id = 12345
        message.author.display_name = "Staff"
        message.reference = MagicMock()
        message.reference.channel_id = channel.id
        message.reference.resolved = referenced_message
        message.reference.message_id = referenced_message.id

        with patch(
            "am_bot.cogs.invite_response.INVITE_HELP_TEXT_CHANNEL_ID",
            channel.id,
        ):
            with patch("am_bot.cogs.invite_response.send_email") as mock_send:
                await cog.on_message(message)

                mock_send.assert_called_once()
                assert mock_send.call_args[0][0] == "legacy@example.com"

    @pytest.mark.asyncio
    async def test_on_message_no_email_found(self, cog):
        """Test that no email is sent when email not found."""
        channel = make_mock_channel()

        # Referenced message with no email
        referenced_message = make_mock_message(
            content="No email here", embeds=[]
        )

        message = make_mock_message(
            content="Response",
            channel=channel,
        )
        message.author.id = 12345
        message.reference = MagicMock()
        message.reference.channel_id = channel.id
        message.reference.resolved = referenced_message
        message.reference.message_id = referenced_message.id

        with patch(
            "am_bot.cogs.invite_response.INVITE_HELP_TEXT_CHANNEL_ID",
            channel.id,
        ):
            with patch("am_bot.cogs.invite_response.send_email") as mock_send:
                await cog.on_message(message)
                mock_send.assert_not_called()
