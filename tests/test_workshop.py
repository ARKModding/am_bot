"""Tests for the WorkshopCog module."""

from unittest.mock import MagicMock

import pytest

from am_bot.cogs.workshop import WorkshopCog
from tests.conftest import (
    make_mock_bot,
    make_mock_channel,
    make_mock_guild,
    make_mock_member,
    make_mock_role,
    make_mock_voice_state,
)


class TestWorkshopCog:
    """Tests for the WorkshopCog class."""

    @pytest.fixture
    def cog(self):
        """Create a WorkshopCog instance with mocked bot."""
        bot = make_mock_bot()
        return WorkshopCog(bot)

    def test_init(self, cog):
        """Test WorkshopCog initialization."""
        assert cog.bot is not None

    @pytest.mark.asyncio
    async def test_on_voice_state_update_join_workshop(self, cog):
        """Test joining workshop voice channel adds role and permissions."""
        workshop_voice_id = 770198004053311490
        workshop_text_id = 770198077943971880
        workshop_role_id = 770207045357797378

        # Create mock role
        mock_role = make_mock_role(
            role_id=workshop_role_id, name="AMC Workshop"
        )

        # Create mock guild
        guild = make_mock_guild()
        guild.get_role.return_value = mock_role

        # Create mock text channel
        text_channel = make_mock_channel(channel_id=workshop_text_id)
        guild.get_channel.return_value = text_channel

        # Create member
        member = make_mock_member()
        member.guild = guild

        # Create voice states
        before = make_mock_voice_state(channel=None)  # Not in workshop before

        after_channel = make_mock_channel(channel_id=workshop_voice_id)
        after = make_mock_voice_state(channel=after_channel)

        await cog.on_voice_state_update(member, before, after)

        # Should add workshop role
        guild.get_role.assert_called_once_with(workshop_role_id)
        member.add_roles.assert_called_once_with(mock_role)

        # Should set channel permissions
        guild.get_channel.assert_called_once_with(channel_id=workshop_text_id)
        text_channel.set_permissions.assert_called_once_with(
            member, view_channel=True
        )

    @pytest.mark.asyncio
    async def test_on_voice_state_update_leave_workshop(self, cog):
        """Test leaving workshop voice channel removes permissions."""
        workshop_voice_id = 770198004053311490
        workshop_text_id = 770198077943971880

        # Create mock guild
        guild = make_mock_guild()

        # Create mock text channel
        text_channel = make_mock_channel(channel_id=workshop_text_id)
        guild.get_channel.return_value = text_channel

        # Create member
        member = make_mock_member()
        member.guild = guild

        # Create voice states - was in workshop, now not
        before_channel = make_mock_channel(channel_id=workshop_voice_id)
        before = make_mock_voice_state(channel=before_channel)

        after = make_mock_voice_state(channel=None)

        await cog.on_voice_state_update(member, before, after)

        # Should remove channel permissions
        guild.get_channel.assert_called_once_with(channel_id=workshop_text_id)
        text_channel.set_permissions.assert_called_once_with(
            member, overwrite=None
        )

    @pytest.mark.asyncio
    async def test_on_voice_state_update_switch_to_other_channel(self, cog):
        """Test switching from workshop to another channel removes perms."""
        workshop_voice_id = 770198004053311490
        workshop_text_id = 770198077943971880

        guild = make_mock_guild()
        text_channel = make_mock_channel(channel_id=workshop_text_id)
        guild.get_channel.return_value = text_channel

        member = make_mock_member()
        member.guild = guild

        # Was in workshop
        before_channel = make_mock_channel(channel_id=workshop_voice_id)
        before = make_mock_voice_state(channel=before_channel)

        # Now in different channel
        after_channel = make_mock_channel(channel_id=99999)
        after = make_mock_voice_state(channel=after_channel)

        await cog.on_voice_state_update(member, before, after)

        # Should remove permissions
        text_channel.set_permissions.assert_called_once_with(
            member, overwrite=None
        )

    @pytest.mark.asyncio
    async def test_on_voice_state_update_switch_from_other_to_workshop(
        self, cog
    ):
        """Test switching from another channel to workshop adds permissions."""
        workshop_voice_id = 770198004053311490
        workshop_text_id = 770198077943971880
        workshop_role_id = 770207045357797378

        mock_role = make_mock_role(role_id=workshop_role_id)
        guild = make_mock_guild()
        guild.get_role.return_value = mock_role
        text_channel = make_mock_channel(channel_id=workshop_text_id)
        guild.get_channel.return_value = text_channel

        member = make_mock_member()
        member.guild = guild

        # Was in different channel
        before_channel = make_mock_channel(channel_id=99999)
        before = make_mock_voice_state(channel=before_channel)

        # Now in workshop
        after_channel = make_mock_channel(channel_id=workshop_voice_id)
        after = make_mock_voice_state(channel=after_channel)

        await cog.on_voice_state_update(member, before, after)

        # Should add role and permissions
        member.add_roles.assert_called_once()
        text_channel.set_permissions.assert_called_once_with(
            member, view_channel=True
        )

    @pytest.mark.asyncio
    async def test_on_voice_state_update_unrelated_channel(self, cog):
        """Test that unrelated channel changes do nothing."""
        guild = make_mock_guild()
        member = make_mock_member()
        member.guild = guild

        # Switching between two unrelated channels
        before_channel = make_mock_channel(channel_id=11111)
        before = make_mock_voice_state(channel=before_channel)

        after_channel = make_mock_channel(channel_id=22222)
        after = make_mock_voice_state(channel=after_channel)

        await cog.on_voice_state_update(member, before, after)

        # Nothing should happen
        member.add_roles.assert_not_called()
        guild.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_voice_state_update_same_channel(self, cog):
        """Test that staying in the same channel does nothing."""
        workshop_voice_id = 770198004053311490

        guild = make_mock_guild()
        member = make_mock_member()
        member.guild = guild

        # Same channel before and after (e.g., mute/unmute)
        channel = make_mock_channel(channel_id=workshop_voice_id)
        before = make_mock_voice_state(channel=channel)
        after = make_mock_voice_state(channel=channel)

        await cog.on_voice_state_update(member, before, after)

        # Nothing should happen (already has permissions)
        member.add_roles.assert_not_called()

    def test_cog_load_creates_cleanup_task(self, cog):
        """Test that cog_load creates the text_cleanup_task."""
        mock_task = MagicMock()
        cog.bot.loop.create_task = MagicMock(return_value=mock_task)

        cog.cog_load()

        cog.bot.loop.create_task.assert_called_once()
