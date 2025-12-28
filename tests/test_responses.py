"""Tests for the ResponsesCog module."""

from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_mock_bot, make_mock_message


class TestResponsesCog:
    """Tests for the ResponsesCog class."""

    @pytest.fixture
    def mock_commands(self):
        """Mock the COMMANDS dictionary."""
        return {
            "?": {
                "test": {
                    "content": "This is a test response",
                },
                "embed_test": {
                    "embed": {
                        "title": "Test Embed",
                        "description": "Test description",
                        "color": 123456,
                    },
                },
                "original": {
                    "content": "Original content",
                },
                "duplicate": {
                    "duplicate": "original",
                },
            },
            "!": {
                "cmd": {
                    "content": "Exclamation command",
                },
            },
        }

    @pytest.fixture
    def cog(self, mock_commands):
        """Create a ResponsesCog instance with mocked bot and commands."""
        with patch("am_bot.cogs.responses.COMMANDS", mock_commands):
            from am_bot.cogs.responses import ResponsesCog

            bot = make_mock_bot()
            return ResponsesCog(bot)

    @pytest.mark.asyncio
    async def test_on_message_ignores_self(self, cog):
        """Test that bot ignores its own messages."""
        message = make_mock_message(content="?test")
        message.author.id = cog.bot.user.id

        await cog.on_message(message)

        message.channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_ignores_empty_content(self, cog):
        """Test that bot ignores messages with no content."""
        message = make_mock_message(content="")
        message.author.id = 12345

        await cog.on_message(message)

        message.channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_content_response(self, cog, mock_commands):
        """Test that content-based commands send the correct response."""
        with patch("am_bot.cogs.responses.COMMANDS", mock_commands):
            message = make_mock_message(content="?test")
            message.author.id = 12345

            await cog.on_message(message)

            message.channel.send.assert_called_once()
            call_kwargs = message.channel.send.call_args[1]
            assert call_kwargs["content"] == "This is a test response"

    @pytest.mark.asyncio
    async def test_on_message_embed_response(self, cog, mock_commands):
        """Test that embed-based commands send the correct embed."""
        with patch("am_bot.cogs.responses.COMMANDS", mock_commands):
            import discord

            with patch.object(discord.Embed, "from_dict") as mock_from_dict:
                mock_embed = MagicMock()
                mock_from_dict.return_value = mock_embed

                message = make_mock_message(content="?embed_test")
                message.author.id = 12345

                await cog.on_message(message)

                message.channel.send.assert_called_once()
                call_kwargs = message.channel.send.call_args[1]
                assert call_kwargs["embed"] == mock_embed

    @pytest.mark.asyncio
    async def test_on_message_duplicate_command(self, cog, mock_commands):
        """Test that duplicate commands reference the original."""
        with patch("am_bot.cogs.responses.COMMANDS", mock_commands):
            message = make_mock_message(content="?duplicate")
            message.author.id = 12345

            await cog.on_message(message)

            message.channel.send.assert_called_once()
            call_kwargs = message.channel.send.call_args[1]
            assert call_kwargs["content"] == "Original content"

    @pytest.mark.asyncio
    async def test_on_message_different_prefix(self, cog, mock_commands):
        """Test commands with different prefixes."""
        with patch("am_bot.cogs.responses.COMMANDS", mock_commands):
            message = make_mock_message(content="!cmd")
            message.author.id = 12345

            await cog.on_message(message)

            message.channel.send.assert_called_once()
            call_kwargs = message.channel.send.call_args[1]
            assert call_kwargs["content"] == "Exclamation command"

    @pytest.mark.asyncio
    async def test_on_message_unknown_prefix(self, cog, mock_commands):
        """Test that unknown prefixes are ignored."""
        with patch("am_bot.cogs.responses.COMMANDS", mock_commands):
            message = make_mock_message(content="#unknown")
            message.author.id = 12345

            await cog.on_message(message)

            message.channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_unknown_command(self, cog, mock_commands):
        """Test that unknown commands are ignored."""
        with patch("am_bot.cogs.responses.COMMANDS", mock_commands):
            message = make_mock_message(content="?unknown")
            message.author.id = 12345

            await cog.on_message(message)

            message.channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_single_character(self, cog, mock_commands):
        """Test that single character messages are handled gracefully."""
        with patch("am_bot.cogs.responses.COMMANDS", mock_commands):
            message = make_mock_message(content="?")
            message.author.id = 12345

            await cog.on_message(message)

            # Should not crash, just not respond
            message.channel.send.assert_not_called()
