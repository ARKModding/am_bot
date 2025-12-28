"""Tests for the main bot module."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from tests.conftest import make_mock_message, make_mock_user


class TestARKBot:
    """Tests for the ARKBot class."""

    @pytest.fixture
    def bot(self):
        """Create an ARKBot instance."""
        with patch("am_bot.bot.discord.Intents") as mock_intents:
            mock_intents.default.return_value = MagicMock()
            from am_bot.bot import ARKBot

            return ARKBot(command_prefix="!")

    def test_init(self, bot):
        """Test ARKBot initialization."""
        assert bot.command_prefix == "!"

    @pytest.mark.asyncio
    async def test_on_ready(self):
        """Test on_ready event."""
        # Create a fully mocked bot for on_ready test
        from am_bot.bot import ARKBot

        with patch.object(
            ARKBot, "user", new_callable=PropertyMock
        ) as mock_user:
            mock_user.return_value = make_mock_user(name="TestBot", bot=True)

            with patch("am_bot.bot.discord.Intents") as mock_intents:
                mock_intents.default.return_value = MagicMock()
                bot = ARKBot(command_prefix="!")

            with patch.object(
                bot, "add_cogs", new_callable=AsyncMock
            ) as mock_add_cogs:
                await bot.on_ready()
                mock_add_cogs.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_ignores_self(self):
        """Test that bot ignores its own messages."""
        from am_bot.bot import ARKBot

        mock_user = make_mock_user(user_id=999999, name="TestBot", bot=True)

        with patch.object(
            ARKBot, "user", new_callable=PropertyMock
        ) as mock_user_prop:
            mock_user_prop.return_value = mock_user

            with patch("am_bot.bot.discord.Intents") as mock_intents:
                mock_intents.default.return_value = MagicMock()
                bot = ARKBot(command_prefix="!")

            message = make_mock_message()
            message.author.id = 999999  # Same as bot

            with patch.object(
                bot, "process_commands", new_callable=AsyncMock
            ) as mock_process:
                await bot.on_message(message)
                mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_processes_other_messages(self):
        """Test that bot processes other users' messages."""
        from am_bot.bot import ARKBot

        mock_user = make_mock_user(user_id=999999, name="TestBot", bot=True)

        with patch.object(
            ARKBot, "user", new_callable=PropertyMock
        ) as mock_user_prop:
            mock_user_prop.return_value = mock_user

            with patch("am_bot.bot.discord.Intents") as mock_intents:
                mock_intents.default.return_value = MagicMock()
                bot = ARKBot(command_prefix="!")

            message = make_mock_message()
            message.author.id = 12345  # Different from bot

            with patch.object(
                bot, "process_commands", new_callable=AsyncMock
            ) as mock_process:
                await bot.on_message(message)
                mock_process.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_add_cogs(self, bot):
        """Test that add_cogs adds all expected cogs."""
        with patch.object(
            bot, "add_cog", new_callable=AsyncMock
        ) as mock_add_cog:
            await bot.add_cogs()

            # Should add 7 cogs
            assert mock_add_cog.call_count == 7

            # Get the cog classes that were added
            cog_types = [
                call[0][0].__class__.__name__
                for call in mock_add_cog.call_args_list
            ]

            assert "GreetingsCog" in cog_types
            assert "InviteResponseCog" in cog_types
            assert "QuarantineCog" in cog_types
            assert "ResponsesCog" in cog_types
            assert "RoleAssignmentCog" in cog_types
            assert "ServerStatsCog" in cog_types
            assert "WorkshopCog" in cog_types


class TestBotIntents:
    """Tests for bot intents configuration."""

    def test_intents_include_members(self):
        """Test that members intent is enabled."""
        from am_bot.bot import intents

        assert intents.members is True

    def test_intents_include_message_content(self):
        """Test that message_content intent is enabled."""
        from am_bot.bot import intents

        assert intents.message_content is True


class TestBotImports:
    """Tests for bot module imports and structure."""

    def test_arkbot_is_exported_from_package(self):
        """Test that ARKBot is exported from the am_bot package."""
        from am_bot import ARKBot

        assert ARKBot is not None

    def test_package_version_exists(self):
        """Test that package has a version."""
        from am_bot import __version__

        assert __version__ is not None
        assert isinstance(__version__, str)
