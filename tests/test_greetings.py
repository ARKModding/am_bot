"""Tests for the GreetingsCog module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from am_bot.cogs.greetings import GreetingsCog
from tests.conftest import make_mock_channel, make_mock_guild, make_mock_member


class TestGreetingsCog:
    """Tests for the GreetingsCog class."""

    @pytest.fixture
    def cog(self):
        """Create a GreetingsCog instance."""
        return GreetingsCog()

    def test_init(self, cog):
        """Test GreetingsCog initialization."""
        assert cog._last_member is None

    @pytest.mark.asyncio
    async def test_on_member_join_with_system_channel(self, cog):
        """Test welcome message is sent when member joins."""
        member = make_mock_member(user_id=12345, name="NewUser")
        guild = make_mock_guild()
        member.guild = guild
        channel = make_mock_channel()
        guild.system_channel = channel

        await cog.on_member_join(member)

        channel.send.assert_called_once()
        call_args = channel.send.call_args[0][0]
        assert member.mention in call_args
        assert "Welcome" in call_args

    @pytest.mark.asyncio
    async def test_on_member_join_no_system_channel(self, cog):
        """Test no error when guild has no system channel."""
        member = make_mock_member()
        guild = make_mock_guild()
        guild.system_channel = None
        member.guild = guild

        # Should not raise
        await cog.on_member_join(member)

    @pytest.mark.asyncio
    async def test_hello_command_first_time(self, cog):
        """Test hello command with no previous interaction."""
        ctx = MagicMock()
        ctx.send = AsyncMock()
        ctx.author = make_mock_member(name="TestUser")

        await cog.hello(cog, ctx)

        ctx.send.assert_called_once()
        call_args = ctx.send.call_args[0][0]
        assert "Hello TestUser." in call_args
        assert "familiar" not in call_args.lower()

    @pytest.mark.asyncio
    async def test_hello_command_same_member_twice(self, cog):
        """Test hello command when same member says hello twice."""
        ctx = MagicMock()
        ctx.send = AsyncMock()
        member = make_mock_member(user_id=12345, name="TestUser")
        ctx.author = member

        # First hello
        await cog.hello(cog, ctx)

        # Reset mock for second call
        ctx.send.reset_mock()

        # Second hello from same member
        await cog.hello(cog, ctx)

        ctx.send.assert_called_once()
        call_args = ctx.send.call_args[0][0]
        assert "familiar" in call_args.lower()

    @pytest.mark.asyncio
    async def test_hello_command_different_member(self, cog):
        """Test hello command with different members."""
        ctx = MagicMock()
        ctx.send = AsyncMock()

        # First member
        member1 = make_mock_member(user_id=12345, name="User1")
        ctx.author = member1
        await cog.hello(cog, ctx)

        ctx.send.reset_mock()

        # Different member
        member2 = make_mock_member(user_id=67890, name="User2")
        ctx.author = member2
        await cog.hello(cog, ctx)

        ctx.send.assert_called_once()
        call_args = ctx.send.call_args[0][0]
        assert "Hello User2." in call_args
        assert "familiar" not in call_args.lower()

    @pytest.mark.asyncio
    async def test_hello_command_with_specific_member(self, cog):
        """Test hello command targeting a specific member."""
        ctx = MagicMock()
        ctx.send = AsyncMock()
        ctx.author = make_mock_member(user_id=12345, name="Sender")

        target_member = make_mock_member(user_id=67890, name="TargetUser")

        await cog.hello(cog, ctx, member=target_member)

        ctx.send.assert_called_once()
        call_args = ctx.send.call_args[0][0]
        assert "Hello TargetUser." in call_args

    @pytest.mark.asyncio
    async def test_hello_tracks_last_member(self, cog):
        """Test that _last_member is updated after hello command."""
        ctx = MagicMock()
        ctx.send = AsyncMock()
        member = make_mock_member(user_id=12345, name="TrackedUser")
        ctx.author = member

        assert cog._last_member is None

        await cog.hello(cog, ctx)

        assert cog._last_member is member
