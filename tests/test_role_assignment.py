"""Tests for the RoleAssignmentCog module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from am_bot.cogs.role_assignment import (
    ADD_REACTION_ATTEMPTS,
    RESET_INTERVAL_SECONDS,
    entries_by_message,
)
from tests.conftest import (
    make_mock_bot,
    make_mock_channel,
    make_mock_guild,
    make_mock_member,
    make_mock_message,
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


def make_mock_custom_emoji(emoji_id: int = 444444, name: str = "cpp"):
    """Create a mock custom Emoji that renders like the real thing."""
    emoji = MagicMock()
    emoji.id = emoji_id
    emoji.name = name
    emoji.__str__ = lambda self: f"<:{name}:{emoji_id}>"
    return emoji


def make_mock_reaction(emoji, count: int = 1, me: bool = True):
    """Create a mock Reaction already present on a message."""
    reaction = MagicMock()
    reaction.emoji = emoji
    reaction.count = count
    reaction.me = me
    return reaction


def make_server_error():
    """Create the 503 discord.py raises when the API is unavailable."""
    response = MagicMock()
    response.status = 503
    response.reason = "Service Unavailable"
    return discord.DiscordServerError(response, "503 Service Unavailable")


class TestResetReactions:
    """Tests for the periodic reaction reset."""

    @pytest.fixture
    def mock_roles(self):
        """Two messages worth of assignable roles."""
        return {
            "📋": {
                "name": "Jobs Board",
                "channel_id": 123456,
                "role_id": 111111,
                "message_id": 999999,
            },
            "cpp": {
                "name": "C++",
                "emoji_id": 444444,
                "channel_id": 123456,
                "role_id": 555555,
                "message_id": 999999,
            },
            "1️⃣": {
                "name": "Modder",
                "channel_id": 234567,
                "role_id": 222222,
                "message_id": 888888,
            },
        }

    @pytest.fixture
    def cog(self):
        """Create a RoleAssignmentCog with a mocked bot."""
        from am_bot.cogs.role_assignment import RoleAssignmentCog

        return RoleAssignmentCog(make_mock_bot())

    def test_entries_by_message_groups_shared_messages(self, mock_roles):
        """Emoji on the same message are handled as one unit."""
        grouped = entries_by_message(mock_roles)

        assert list(grouped) == [(123456, 999999), (234567, 888888)]
        assert len(grouped[(123456, 999999)]) == 2
        assert len(grouped[(234567, 888888)]) == 1

    @pytest.mark.asyncio
    async def test_clears_then_adds_when_users_have_reacted(
        self, cog, mock_roles
    ):
        """A user reaction triggers a clear and a re-add of both emoji."""
        emoji = make_mock_custom_emoji()
        cog.bot.get_emoji.return_value = emoji
        message = make_mock_message(
            message_id=999999,
            reactions=[make_mock_reaction("📋", count=3)],
        )
        channel = make_mock_channel(channel_id=123456)
        channel.fetch_message.return_value = message
        cog.bot.get_channel.return_value = channel

        added = await cog.reset_message_reactions(
            123456, 999999, entries_by_message(mock_roles)[(123456, 999999)]
        )

        assert added == 2
        message.clear_reactions.assert_awaited_once()
        assert message.add_reaction.await_count == 2

    @pytest.mark.asyncio
    async def test_leaves_untouched_message_alone(self, cog, mock_roles):
        """An already correct message is not cleared or re-added."""
        emoji = make_mock_custom_emoji()
        cog.bot.get_emoji.return_value = emoji
        message = make_mock_message(
            message_id=999999,
            reactions=[
                make_mock_reaction("📋"),
                make_mock_reaction(emoji),
            ],
        )
        channel = make_mock_channel(channel_id=123456)
        channel.fetch_message.return_value = message
        cog.bot.get_channel.return_value = channel

        added = await cog.reset_message_reactions(
            123456, 999999, entries_by_message(mock_roles)[(123456, 999999)]
        )

        assert added == 2
        message.clear_reactions.assert_not_awaited()
        message.add_reaction.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_fetching_uncached_channel(
        self, cog, mock_roles
    ):
        """An uncached channel is fetched rather than crashing the cycle."""
        cog.bot.get_channel.return_value = None
        channel = make_mock_channel(channel_id=234567)
        channel.fetch_message.return_value = make_mock_message(
            message_id=888888
        )
        cog.bot.fetch_channel.return_value = channel

        added = await cog.reset_message_reactions(
            234567, 888888, entries_by_message(mock_roles)[(234567, 888888)]
        )

        assert added == 1
        cog.bot.fetch_channel.assert_awaited_once_with(234567)

    @pytest.mark.asyncio
    async def test_skips_deleted_custom_emoji(self, cog, mock_roles):
        """A deleted custom emoji is skipped, not passed to add_reaction."""
        cog.bot.get_emoji.return_value = None
        message = make_mock_message(message_id=999999)
        channel = make_mock_channel(channel_id=123456)
        channel.fetch_message.return_value = message
        cog.bot.get_channel.return_value = channel

        added = await cog.reset_message_reactions(
            123456, 999999, entries_by_message(mock_roles)[(123456, 999999)]
        )

        assert added == 1
        message.add_reaction.assert_awaited_once_with("📋")

    @pytest.mark.asyncio
    async def test_add_reaction_retries_transient_failure(self, cog):
        """A 503 is retried rather than killing the cycle."""
        message = make_mock_message()
        message.add_reaction.side_effect = [make_server_error(), None]

        with patch("am_bot.cogs.role_assignment.asyncio.sleep", AsyncMock()):
            assert await cog.add_reaction(message, "📋") is True

        assert message.add_reaction.await_count == 2

    @pytest.mark.asyncio
    async def test_add_reaction_gives_up_after_max_attempts(self, cog):
        """A persistent 503 is reported but does not raise."""
        message = make_mock_message()
        message.add_reaction.side_effect = make_server_error()

        with patch("am_bot.cogs.role_assignment.asyncio.sleep", AsyncMock()):
            assert await cog.add_reaction(message, "📋") is False

        assert message.add_reaction.await_count == ADD_REACTION_ATTEMPTS

    @pytest.mark.asyncio
    async def test_one_bad_message_does_not_skip_the_others(
        self, cog, mock_roles
    ):
        """A failure on one message still leaves the rest reset."""
        healthy = make_mock_message(message_id=888888)
        channel = make_mock_channel()
        channel.fetch_message.return_value = healthy
        cog.bot.get_channel.return_value = channel
        cog.reset_message_reactions = AsyncMock(
            side_effect=[make_server_error(), 1]
        )

        with patch("am_bot.cogs.role_assignment.ASSIGNABLE_ROLES", mock_roles):
            await cog.reset_all_reactions()

        assert cog.reset_message_reactions.await_count == 2

    @pytest.mark.asyncio
    async def test_loop_survives_a_failed_cycle(self, cog):
        """A failed cycle is logged and the loop waits for the next one."""
        cog.reset_all_reactions = AsyncMock(side_effect=make_server_error())
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) > 2:
                raise asyncio.CancelledError

        with patch("am_bot.cogs.role_assignment.asyncio.sleep", fake_sleep):
            with pytest.raises(asyncio.CancelledError):
                await cog.reset_reactions()

        assert cog.reset_all_reactions.await_count == 2
        assert sleeps == [10, RESET_INTERVAL_SECONDS, RESET_INTERVAL_SECONDS]
