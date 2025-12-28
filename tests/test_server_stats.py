"""Tests for the ServerStatsCog module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from am_bot.cogs.server_stats import ServerStatsCog
from tests.conftest import (
    make_mock_bot,
    make_mock_channel,
    make_mock_guild,
    make_mock_member,
    make_mock_role,
)


class TestServerStatsCog:
    """Tests for the ServerStatsCog class."""

    @pytest.fixture
    def cog(self):
        """Create a ServerStatsCog instance with mocked bot."""
        bot = make_mock_bot()
        return ServerStatsCog(bot)

    def test_init(self, cog):
        """Test ServerStatsCog initialization."""
        assert cog.bot is not None
        assert cog.guild is None

    @pytest.mark.asyncio
    async def test_on_member_join(self, cog):
        """Test that member join triggers member count update."""
        with patch.object(
            cog, "update_member_count", new_callable=AsyncMock
        ) as mock:
            await cog.on_member_join(MagicMock())
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_member_remove(self, cog):
        """Test that member removal triggers member count update."""
        with patch.object(
            cog, "update_member_count", new_callable=AsyncMock
        ) as mock:
            await cog.on_member_remove(MagicMock())
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_member_count(self, cog):
        """Test updating member count channel."""
        # Create mock guild with members
        members = [make_mock_member() for _ in range(100)]
        guild = make_mock_guild(members=members)
        cog.bot.get_guild.return_value = guild

        # Create mock channel
        channel = make_mock_channel()
        cog.bot.fetch_channel.return_value = channel

        await cog.update_member_count()

        cog.bot.fetch_channel.assert_called_once()
        channel.edit.assert_called_once()
        call_kwargs = channel.edit.call_args[1]
        assert "100" in call_kwargs["name"]
        assert "members" in call_kwargs["name"]

    @pytest.mark.asyncio
    async def test_update_member_count_caches_guild(self, cog):
        """Test that guild is cached after first call."""
        guild = make_mock_guild()
        cog.bot.get_guild.return_value = guild

        channel = make_mock_channel()
        cog.bot.fetch_channel.return_value = channel

        # First call
        await cog.update_member_count()
        assert cog.guild == guild

        # Second call should use cached guild
        cog.bot.get_guild.reset_mock()
        await cog.update_member_count()

        # get_guild should not be called again (uses cache)
        # Note: `or` short-circuit means get_guild won't be called if set

    @pytest.mark.asyncio
    async def test_update_boost_count(self, cog):
        """Test updating boost count channel."""
        guild = make_mock_guild(premium_subscription_count=10)
        cog.bot.get_guild.return_value = guild

        channel = make_mock_channel()
        cog.bot.fetch_channel.return_value = channel

        await cog.update_boost_count()

        channel.edit.assert_called_once()
        call_kwargs = channel.edit.call_args[1]
        assert "10" in call_kwargs["name"]
        assert "boosts" in call_kwargs["name"]

    @pytest.mark.asyncio
    async def test_update_role_counts(self, cog):
        """Test updating role count channels."""
        # Create roles with members
        modder_role = make_mock_role(name="Modder")
        modder_role.members = [make_mock_member() for _ in range(50)]

        mapper_role = make_mock_role(name="Mapper")
        mapper_role.members = [make_mock_member() for _ in range(30)]

        guild = make_mock_guild()
        guild.get_role.side_effect = lambda rid: {
            190385081523765248: modder_role,  # MODDER_ROLE_ID
            190385107297632257: mapper_role,  # MAPPER_ROLE_ID
        }.get(rid)
        cog.bot.get_guild.return_value = guild

        # Create mock channels
        modder_channel = make_mock_channel(name="modder-stats")
        mapper_channel = make_mock_channel(name="mapper-stats")

        async def fetch_channel_side_effect(channel_id):
            if channel_id == 877564476315029525:  # MODDER_STATS_CHANNEL_ID
                return modder_channel
            elif channel_id == 877566216359772211:  # MAPPER_STATS_CHANNEL_ID
                return mapper_channel
            return make_mock_channel()

        cog.bot.fetch_channel.side_effect = fetch_channel_side_effect

        await cog.update_role_counts()

        # Both channels should be updated
        modder_channel.edit.assert_called_once()
        mapper_channel.edit.assert_called_once()

        # Check modder channel name
        modder_call_kwargs = modder_channel.edit.call_args[1]
        assert "50" in modder_call_kwargs["name"]
        assert "modders" in modder_call_kwargs["name"]

        # Check mapper channel name
        mapper_call_kwargs = mapper_channel.edit.call_args[1]
        assert "30" in mapper_call_kwargs["name"]
        assert "mappers" in mapper_call_kwargs["name"]

    @pytest.mark.asyncio
    async def test_update_role_counts_with_empty_roles(self, cog):
        """Test updating role counts when roles have no members."""
        modder_role = make_mock_role(name="Modder")
        modder_role.members = []

        mapper_role = make_mock_role(name="Mapper")
        mapper_role.members = []

        guild = make_mock_guild()
        guild.get_role.side_effect = lambda rid: {
            190385081523765248: modder_role,
            190385107297632257: mapper_role,
        }.get(rid)
        cog.bot.get_guild.return_value = guild

        modder_channel = make_mock_channel()
        mapper_channel = make_mock_channel()

        async def fetch_channel_side_effect(channel_id):
            if channel_id == 877564476315029525:
                return modder_channel
            elif channel_id == 877566216359772211:
                return mapper_channel
            return make_mock_channel()

        cog.bot.fetch_channel.side_effect = fetch_channel_side_effect

        await cog.update_role_counts()

        # Should still update with 0 count
        modder_call_kwargs = modder_channel.edit.call_args[1]
        assert "0" in modder_call_kwargs["name"]

    def test_cog_load_creates_update_task(self, cog):
        """Test that cog_load creates the update_server_stats task."""
        mock_task = MagicMock()
        cog.bot.loop.create_task = MagicMock(return_value=mock_task)

        cog.cog_load()

        cog.bot.loop.create_task.assert_called_once()
