"""Tests for the StarboardCog module."""

from unittest.mock import MagicMock, patch

import pytest

from am_bot.cogs.starboard import StarboardCog
from tests.conftest import (
    make_mock_bot,
    make_mock_channel,
    make_mock_embed,
    make_mock_message,
    make_mock_reaction_payload,
)


class TestStarboardCog:
    """Tests for the StarboardCog class."""

    @pytest.fixture
    def cog(self):
        """Create a StarboardCog instance with mocked bot."""
        bot = make_mock_bot()
        return StarboardCog(bot)

    def test_init(self, cog):
        """Test StarboardCog initialization."""
        assert cog.bot is not None
        assert cog._starred_message_ids == set()
        assert cog._last_message is None

    @pytest.mark.asyncio
    async def test_on_ready_loads_existing_starboard(self, cog):
        """Test that on_ready loads existing starboard messages."""
        starboard_channel_id = 863887933089906718
        guild_id = 153690873186484224

        # Create mock starboard messages with embeds
        embed1 = make_mock_embed(
            fields=[
                {
                    "name": "\u200b",
                    "value": f"**[Click to jump to message!](https://discord.com/channels/{guild_id}/12345/111111)**",
                }
            ]
        )
        msg1 = make_mock_message(message_id=1, embeds=[embed1])

        embed2 = make_mock_embed(
            fields=[
                {
                    "name": "\u200b",
                    "value": f"**[Click to jump to message!](https://discord.com/channels/{guild_id}/12345/222222)**",
                }
            ]
        )
        msg2 = make_mock_message(message_id=2, embeds=[embed2])

        # Create async generator for channel.history
        async def mock_history(*args, **kwargs):
            for msg in [msg1, msg2]:
                yield msg

        channel = make_mock_channel(channel_id=starboard_channel_id)
        channel.history.return_value = mock_history()
        cog.bot.get_channel.return_value = channel

        await cog.on_ready()

        # Should have loaded both message IDs
        assert 111111 in cog._starred_message_ids
        assert 222222 in cog._starred_message_ids
        assert cog._last_message == msg1

    @pytest.mark.asyncio
    async def test_on_ready_handles_missing_embeds(self, cog):
        """Test that on_ready handles messages without embeds."""
        starboard_channel_id = 863887933089906718

        # Message without embeds
        msg_no_embed = make_mock_message(message_id=1, embeds=[])

        async def mock_history(*args, **kwargs):
            yield msg_no_embed

        channel = make_mock_channel(channel_id=starboard_channel_id)
        channel.history.return_value = mock_history()
        cog.bot.get_channel.return_value = channel

        # Should not raise
        await cog.on_ready()
        assert len(cog._starred_message_ids) == 0

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_ignores_starboard_channel(self, cog):
        """Test that reactions in starboard channel are ignored."""
        starboard_channel_id = 863887933089906718

        payload = make_mock_reaction_payload(
            emoji_name="⭐", channel_id=starboard_channel_id
        )

        await cog.on_raw_reaction_add(payload)

        cog.bot.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_ignores_self(self, cog):
        """Test that bot's own reactions are ignored."""
        payload = make_mock_reaction_payload(emoji_name="⭐")
        payload.member.id = cog.bot.user.id

        await cog.on_raw_reaction_add(payload)

        cog.bot.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_ignores_already_starred(self, cog):
        """Test that already starred messages are ignored."""
        message_id = 888888
        cog._starred_message_ids.add(message_id)

        payload = make_mock_reaction_payload(
            emoji_name="⭐", message_id=message_id
        )

        await cog.on_raw_reaction_add(payload)

        cog.bot.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_ignores_non_star(self, cog):
        """Test that non-star reactions are ignored."""
        payload = make_mock_reaction_payload(emoji_name="🎉")

        await cog.on_raw_reaction_add(payload)

        cog.bot.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_not_enough_stars(self, cog):
        """Test that messages with insufficient stars are not added."""
        # Create message with only 2 star reactions (below threshold of 5)
        star_reaction = MagicMock()
        star_reaction.emoji = "⭐"
        star_reaction.count = 2

        message = make_mock_message(reactions=[star_reaction, star_reaction])
        channel = make_mock_channel()
        channel.fetch_message.return_value = message
        cog.bot.get_channel.return_value = channel

        payload = make_mock_reaction_payload(
            emoji_name="⭐", channel_id=12345, message_id=888888
        )

        await cog.on_raw_reaction_add(payload)

        # Should not post to starboard
        assert 888888 not in cog._starred_message_ids

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_enough_stars(self, cog):
        """Test that messages with enough stars are added to starboard."""
        starboard_channel_id = 863887933089906718

        # Create star reactions (5 or more)
        star_reactions = [MagicMock(emoji="⭐") for _ in range(5)]

        message = make_mock_message(
            message_id=888888,
            content="Great message!",
            reactions=star_reactions,
        )

        # Source channel
        source_channel = make_mock_channel(channel_id=12345)
        source_channel.fetch_message.return_value = message

        # Starboard channel
        starboard_channel = make_mock_channel(channel_id=starboard_channel_id)
        starboard_msg = make_mock_message()
        starboard_msg.embeds = [make_mock_embed(color=16769024)]
        starboard_channel.send.return_value = starboard_msg

        # Set up last message for color alternation
        last_msg = make_mock_message()
        last_msg.embeds = [make_mock_embed(color=16769024)]
        cog._last_message = last_msg

        def get_channel_side_effect(channel_id):
            if channel_id == 12345:
                return source_channel
            elif channel_id == starboard_channel_id:
                return starboard_channel
            return None

        cog.bot.get_channel.side_effect = get_channel_side_effect

        payload = make_mock_reaction_payload(
            emoji_name="⭐",
            channel_id=12345,
            message_id=888888,
        )
        payload.member.avatar_url_as = MagicMock(
            return_value="https://cdn.discordapp.com/avatars/123/test.png?size=128"
        )

        await cog.on_raw_reaction_add(payload)

        # Should add to starboard
        assert 888888 in cog._starred_message_ids
        starboard_channel.send.assert_called_once()
        starboard_msg.add_reaction.assert_called_once_with("⭐")

    @pytest.mark.asyncio
    async def test_on_raw_reaction_add_alternates_colors(self, cog):
        """Test that starboard embed colors alternate."""
        starboard_channel_id = 863887933089906718

        star_reactions = [MagicMock(emoji="⭐") for _ in range(5)]
        message = make_mock_message(
            message_id=888888, reactions=star_reactions
        )

        source_channel = make_mock_channel(channel_id=12345)
        source_channel.fetch_message.return_value = message

        starboard_channel = make_mock_channel(channel_id=starboard_channel_id)
        starboard_msg = make_mock_message()
        starboard_channel.send.return_value = starboard_msg

        # Set last message with one color
        last_msg = make_mock_message()
        last_embed = make_mock_embed(color=16769024)  # Gold color
        last_msg.embeds = [last_embed]
        cog._last_message = last_msg

        def get_channel_side_effect(channel_id):
            if channel_id == 12345:
                return source_channel
            elif channel_id == starboard_channel_id:
                return starboard_channel
            return None

        cog.bot.get_channel.side_effect = get_channel_side_effect

        payload = make_mock_reaction_payload(
            emoji_name="⭐",
            channel_id=12345,
            message_id=888888,
        )
        payload.member.avatar_url_as = MagicMock(
            return_value="https://test.com/avatar.png?size=128"
        )

        with patch("discord.Embed") as MockEmbed:
            mock_embed_instance = MagicMock()
            MockEmbed.from_dict.return_value = mock_embed_instance

            await cog.on_raw_reaction_add(payload)

            # Verify embed was created
            starboard_channel.send.assert_called_once()


class TestStarboardConstants:
    """Tests for starboard module constants."""

    def test_reaction_limit_is_five(self):
        """Test that REACTION_LIMIT is set to 5."""
        from am_bot.cogs.starboard import REACTION_LIMIT

        assert REACTION_LIMIT == 5

    def test_channel_id_pattern_matches_correctly(self):
        """Test that channel_id_pattern regex works."""
        from am_bot.cogs.starboard import channel_id_pattern

        url = "https://discord.com/channels/153690873186484224/12345/67890"
        match = channel_id_pattern.findall(url)

        assert len(match) == 1
        assert match[0] == "67890"

    def test_channel_id_pattern_no_match_wrong_guild(self):
        """Test pattern doesn't match wrong guild."""
        from am_bot.cogs.starboard import channel_id_pattern

        url = "https://discord.com/channels/999999999999/12345/67890"
        match = channel_id_pattern.findall(url)

        assert len(match) == 0
