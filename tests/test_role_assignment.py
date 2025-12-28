"""Tests for the RoleAssignmentCog module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import (
    make_mock_bot,
    make_mock_guild,
    make_mock_member,
    make_mock_reaction_payload,
    make_mock_role,
)


class TestRoleAssignmentCog:
    """Tests for the RoleAssignmentCog class."""

    @pytest.fixture
    def mock_roles(self):
        """Mock the ASSIGNABLE_ROLES dictionary."""
        return {
            "📋": {
                "name": "Jobs Board",
                "channel_id": 123456,
                "role_id": 111111,
                "message_id": 999999,
            },
            "1️⃣": {
                "name": "Modder",
                "channel_id": 234567,
                "role_id": 222222,
                "message_id": 888888,
            },
            "2️⃣": {
                "name": "Mapper",
                "channel_id": 234567,
                "role_id": 333333,
                "message_id": 888888,
            },
            "cpp": {
                "name": "C++",
                "emoji_id": 444444,
                "channel_id": 123456,
                "role_id": 555555,
                "message_id": 999999,
            },
        }

    @pytest.fixture
    def cog(self, mock_roles):
        """Create a RoleAssignmentCog instance with mocked bot and roles."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            from am_bot.cogs.role_assignment import RoleAssignmentCog

            bot = make_mock_bot()
            return RoleAssignmentCog(bot)

    def test_init(self, cog):
        """Test RoleAssignmentCog initialization."""
        assert cog.bot is not None

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_ignores_self(self, cog, mock_roles):
        """Test that bot ignores its own reactions."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            payload = make_mock_reaction_payload(emoji_name="📋")
            payload.member.id = cog.bot.user.id

            await cog.on_raw_reaction_add(payload)

            payload.member.add_roles.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_ignores_unknown_emoji(
        self, cog, mock_roles
    ):
        """Test that unknown emojis are ignored."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            payload = make_mock_reaction_payload(emoji_name="🎉")

            await cog.on_raw_reaction_add(payload)

            payload.member.add_roles.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_ignores_wrong_message(
        self, cog, mock_roles
    ):
        """Test that reactions on wrong messages are ignored."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            payload = make_mock_reaction_payload(
                emoji_name="📋", message_id=777777  # Wrong message ID
            )

            await cog.on_raw_reaction_add(payload)

            payload.member.add_roles.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_adds_role(self, cog, mock_roles):
        """Test that correct role is added on reaction."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            mock_role = make_mock_role(role_id=111111, name="Jobs Board")
            guild = make_mock_guild()
            guild.get_role.return_value = mock_role

            payload = make_mock_reaction_payload(
                emoji_name="📋", message_id=999999
            )
            payload.member.guild = guild

            await cog.on_raw_reaction_add(payload)

            guild.get_role.assert_called_once_with(111111)
            payload.member.add_roles.assert_called_once_with(mock_role)

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_modder_triggers_stats_update(
        self, cog, mock_roles
    ):
        """Test that Modder role triggers stats update."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            mock_role = make_mock_role(role_id=222222, name="Modder")
            guild = make_mock_guild()
            guild.get_role.return_value = mock_role

            mock_stats_cog = MagicMock()
            mock_stats_cog.update_role_counts = AsyncMock()
            cog.bot.get_cog.return_value = mock_stats_cog

            payload = make_mock_reaction_payload(
                emoji_name="1️⃣", message_id=888888
            )
            payload.member.guild = guild

            await cog.on_raw_reaction_add(payload)

            cog.bot.get_cog.assert_called_with("ServerStatsCog")
            mock_stats_cog.update_role_counts.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_mapper_triggers_stats_update(
        self, cog, mock_roles
    ):
        """Test that Mapper role triggers stats update."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            mock_role = make_mock_role(role_id=333333, name="Mapper")
            guild = make_mock_guild()
            guild.get_role.return_value = mock_role

            mock_stats_cog = MagicMock()
            mock_stats_cog.update_role_counts = AsyncMock()
            cog.bot.get_cog.return_value = mock_stats_cog

            payload = make_mock_reaction_payload(
                emoji_name="2️⃣", message_id=888888
            )
            payload.member.guild = guild

            await cog.on_raw_reaction_add(payload)

            mock_stats_cog.update_role_counts.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_no_stats_cog(self, cog, mock_roles):
        """Test handling when ServerStatsCog is not loaded."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            mock_role = make_mock_role(role_id=222222, name="Modder")
            guild = make_mock_guild()
            guild.get_role.return_value = mock_role

            cog.bot.get_cog.return_value = None

            payload = make_mock_reaction_payload(
                emoji_name="1️⃣", message_id=888888
            )
            payload.member.guild = guild

            # Should not raise
            await cog.on_raw_reaction_add(payload)
            payload.member.add_roles.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_remove_ignores_unknown_emoji(
        self, cog, mock_roles
    ):
        """Test that unknown emojis are ignored on removal."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            payload = make_mock_reaction_payload(emoji_name="🎉")

            await cog.on_raw_reaction_remove(payload)

            cog.bot.fetch_guild.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_remove_ignores_wrong_message(
        self, cog, mock_roles
    ):
        """Test that reactions on wrong messages are ignored on removal."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            payload = make_mock_reaction_payload(
                emoji_name="📋", message_id=777777
            )

            await cog.on_raw_reaction_remove(payload)

            cog.bot.fetch_guild.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_remove_removes_role(self, cog, mock_roles):
        """Test that correct role is removed on reaction removal."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            mock_role = make_mock_role(role_id=111111, name="Jobs Board")
            guild = make_mock_guild()
            guild.get_role.return_value = mock_role
            member = make_mock_member()
            guild.fetch_member.return_value = member
            cog.bot.fetch_guild.return_value = guild

            payload = make_mock_reaction_payload(
                emoji_name="📋",
                message_id=999999,
                user_id=12345,
                guild_id=guild.id,
            )

            await cog.on_raw_reaction_remove(payload)

            cog.bot.fetch_guild.assert_called_once_with(guild.id)
            guild.fetch_member.assert_called_once_with(12345)
            guild.get_role.assert_called_once_with(111111)
            member.remove_roles.assert_called_once_with(mock_role)

    @pytest.mark.asyncio
    async def test_on_raw_reaction_remove_modder_triggers_stats(
        self, cog, mock_roles
    ):
        """Test that Modder role removal triggers stats update."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            mock_role = make_mock_role(role_id=222222, name="Modder")
            guild = make_mock_guild()
            guild.get_role.return_value = mock_role
            member = make_mock_member()
            guild.fetch_member.return_value = member
            cog.bot.fetch_guild.return_value = guild

            mock_stats_cog = MagicMock()
            mock_stats_cog.update_role_counts = AsyncMock()
            cog.bot.get_cog.return_value = mock_stats_cog

            payload = make_mock_reaction_payload(
                emoji_name="1️⃣",
                message_id=888888,
                guild_id=guild.id,
            )

            await cog.on_raw_reaction_remove(payload)

            mock_stats_cog.update_role_counts.assert_called_once()

    def test_cog_load_creates_reset_reactions_task(self, cog, mock_roles):
        """Test that cog_load creates the reset_reactions task."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            mock_task = MagicMock()
            cog.bot.loop.create_task = MagicMock(return_value=mock_task)

            cog.cog_load()

            cog.bot.loop.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_remove_no_stats_cog(self, cog, mock_roles):
        """Test removal handling when ServerStatsCog is not loaded."""
        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            mock_role = make_mock_role(role_id=222222, name="Modder")
            guild = make_mock_guild()
            guild.get_role.return_value = mock_role
            member = make_mock_member()
            guild.fetch_member.return_value = member
            cog.bot.fetch_guild.return_value = guild

            cog.bot.get_cog.return_value = None

            payload = make_mock_reaction_payload(
                emoji_name="1️⃣",
                message_id=888888,
                guild_id=guild.id,
            )

            # Should not raise
            await cog.on_raw_reaction_remove(payload)
            member.remove_roles.assert_called_once()
