"""Shared pytest fixtures and mock utilities for Discord bot testing."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


def make_mock_user(
    user_id: int = 123456789,
    name: str = "TestUser",
    discriminator: str = "0001",
    bot: bool = False,
    display_name: str | None = None,
) -> MagicMock:
    """Create a mock Discord User."""
    user = MagicMock()
    user.id = user_id
    user.name = name
    user.discriminator = discriminator
    user.bot = bot
    user.display_name = display_name or name
    user.mention = f"<@{user_id}>"
    user.__str__ = lambda self: f"{name}#{discriminator}"
    return user


def make_mock_member(
    user_id: int = 123456789,
    name: str = "TestUser",
    discriminator: str = "0001",
    bot: bool = False,
    display_name: str | None = None,
    guild: MagicMock | None = None,
    roles: list | None = None,
) -> MagicMock:
    """Create a mock Discord Member (extends User with guild-related attrs)."""
    member = make_mock_user(user_id, name, discriminator, bot, display_name)
    # Don't auto-create guild to avoid circular reference
    member.guild = guild
    member.roles = roles or []
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    member.avatar_url_as = MagicMock(
        return_value=f"https://cdn.discordapp.com/avatars/{user_id}/test.png?size=128"
    )
    return member


def make_mock_role(
    role_id: int = 111111111,
    name: str = "TestRole",
    members: list | None = None,
) -> MagicMock:
    """Create a mock Discord Role."""
    role = MagicMock()
    role.id = role_id
    role.name = name
    role.members = members or []
    return role


def make_mock_channel(
    channel_id: int = 999999999,
    name: str = "test-channel",
    guild: MagicMock | None = None,
    channel_type: str = "text",
) -> MagicMock:
    """Create a mock Discord TextChannel."""
    channel = MagicMock()
    channel.id = channel_id
    channel.name = name
    channel.guild = guild
    channel.type = channel_type
    channel.send = AsyncMock()
    channel.fetch_message = AsyncMock()
    channel.purge = AsyncMock(return_value=[])
    channel.history = MagicMock()
    channel.set_permissions = AsyncMock()
    channel.edit = AsyncMock()

    # Create permissions mock
    permissions = MagicMock()
    permissions.read_messages = True
    permissions.manage_messages = True
    channel.permissions_for = MagicMock(return_value=permissions)

    return channel


def make_mock_guild(
    guild_id: int = 153690873186484224,
    name: str = "Test Guild",
    members: list | None = None,
    text_channels: list | None = None,
    premium_subscription_count: int = 5,
) -> MagicMock:
    """Create a mock Discord Guild."""
    guild = MagicMock()
    guild.id = guild_id
    guild.name = name
    guild.members = members or []
    guild.text_channels = text_channels or []
    guild.premium_subscription_count = premium_subscription_count
    guild.get_role = MagicMock()
    guild.get_channel = MagicMock()
    guild.fetch_member = AsyncMock()
    guild.system_channel = make_mock_channel(name="system-channel")
    # Create a simple bot member without recursive guild reference
    bot_member = make_mock_user(user_id=999999, name="BotUser", bot=True)
    bot_member.add_roles = AsyncMock()
    bot_member.remove_roles = AsyncMock()
    guild.me = bot_member
    return guild


def make_mock_message(
    message_id: int = 888888888,
    content: str = "Test message",
    author: MagicMock | None = None,
    channel: MagicMock | None = None,
    guild: MagicMock | None = None,
    embeds: list | None = None,
    reference: MagicMock | None = None,
    reactions: list | None = None,
) -> MagicMock:
    """Create a mock Discord Message."""
    message = MagicMock()
    message.id = message_id
    message.content = content
    message.clean_content = content
    message.author = author or make_mock_member()
    message.channel = channel or make_mock_channel()
    message.guild = guild or make_mock_guild()
    message.embeds = embeds or []
    message.reference = reference
    message.reactions = reactions or []
    message.delete = AsyncMock()
    message.add_reaction = AsyncMock()
    message.clear_reactions = AsyncMock()
    message.jump_url = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message_id}"
    return message


def make_mock_embed(
    title: str = "Test Embed",
    description: str = "Test description",
    fields: list | None = None,
    color: int = 0x00FF00,
) -> MagicMock:
    """Create a mock Discord Embed."""
    embed = MagicMock()
    embed.title = title
    embed.description = description
    embed.color = color

    # Create field mocks
    mock_fields = []
    if fields:
        for field_data in fields:
            field = MagicMock()
            field.name = field_data.get("name", "")
            field.value = field_data.get("value", "")
            field.inline = field_data.get("inline", False)
            mock_fields.append(field)
    embed.fields = mock_fields

    return embed


def make_mock_bot(
    user_id: int = 999999,
    name: str = "TestBot",
) -> MagicMock:
    """Create a mock Discord Bot."""
    bot = MagicMock()
    bot.user = make_mock_user(user_id=user_id, name=name, bot=True)
    bot.get_channel = MagicMock()
    bot.get_guild = MagicMock()
    bot.get_cog = MagicMock()
    bot.get_emoji = MagicMock()
    bot.fetch_channel = AsyncMock()
    bot.fetch_guild = AsyncMock()
    bot.add_cog = AsyncMock()
    bot.process_commands = AsyncMock()
    bot.loop = asyncio.new_event_loop()
    return bot


def make_mock_reaction_payload(
    user_id: int = 123456789,
    message_id: int = 888888888,
    channel_id: int = 999999999,
    guild_id: int = 153690873186484224,
    emoji_name: str = "⭐",
    emoji_id: int | None = None,
    member: MagicMock | None = None,
) -> MagicMock:
    """Create a mock RawReactionActionEvent payload."""
    payload = MagicMock()
    payload.user_id = user_id
    payload.message_id = message_id
    payload.channel_id = channel_id
    payload.guild_id = guild_id
    payload.emoji = MagicMock()
    payload.emoji.name = emoji_name
    payload.emoji.id = emoji_id
    payload.member = member or make_mock_member(user_id=user_id)
    return payload


def make_mock_voice_state(
    channel: MagicMock | None = None,
) -> MagicMock:
    """Create a mock VoiceState."""
    state = MagicMock()
    state.channel = channel
    return state


@pytest.fixture
def mock_bot():
    """Fixture that provides a mock Discord bot."""
    return make_mock_bot()


@pytest.fixture
def mock_guild():
    """Fixture that provides a mock Discord guild."""
    return make_mock_guild()


@pytest.fixture
def mock_channel():
    """Fixture that provides a mock Discord text channel."""
    return make_mock_channel()


@pytest.fixture
def mock_member():
    """Fixture that provides a mock Discord member."""
    return make_mock_member()


@pytest.fixture
def mock_message():
    """Fixture that provides a mock Discord message."""
    return make_mock_message()
