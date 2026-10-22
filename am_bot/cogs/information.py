"""Keep the information-channel posts in sync with the JSON file.

Dyno messages already in those channels are left alone. This cog posts
its own copies, then edits those copies when information_messages.json
changes. A hidden marker on each embed is how a restart finds the post
again. Reaction roles look the posted ids up by message key.
"""

import asyncio
import copy
import json
import logging
import os
import pathlib
import tempfile

import discord
from discord.ext import commands

from ..constants import (
    COMMUNITY_INFO_CHANNEL_ID,
    GREETINGS_CHANNEL_ID,
    RULES_AND_GUIDELINES_CHANNEL_ID,
    TERMS_AND_CONDITIONS_CHANNEL_ID,
)


logger = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = 600
HISTORY_LIMIT = 100
MESSAGES_PATH = (
    pathlib.Path(__file__).parent.resolve() / "information_messages.json"
)
INFORMATION_CHANNEL_IDS = {
    RULES_AND_GUIDELINES_CHANNEL_ID,
    COMMUNITY_INFO_CHANNEL_ID,
    TERMS_AND_CONDITIONS_CHANNEL_ID,
    GREETINGS_CHANNEL_ID,
}
# Role mentions in the embeds should still render. Empty message content
# means those mentions do not ping anyone.
ALLOWED_MENTIONS = discord.AllowedMentions(
    everyone=False, users=False, roles=True
)

# Zero-width marker. Visible footer/description text is unchanged.
MARKER_START = "\u200b\u200b\u200c"
MARKER_END = "\u200c\u200b\u200b"
MARKER_ZERO = "\u200b"
MARKER_ONE = "\u2060"


def encode_marker(key: str) -> str:
    bits = "".join(f"{byte:08b}" for byte in key.encode())
    body = "".join(MARKER_ONE if bit == "1" else MARKER_ZERO for bit in bits)
    return f"{MARKER_START}{body}{MARKER_END}"


def decode_marker(text: str | None) -> str | None:
    if not text or MARKER_START not in text:
        return None
    start = text.find(MARKER_START)
    end = text.find(MARKER_END, start + len(MARKER_START))
    if end < 0:
        return None
    body = text[start + len(MARKER_START) : end]
    bits = []
    for char in body:
        if char == MARKER_ONE:
            bits.append("1")
        elif char == MARKER_ZERO:
            bits.append("0")
        else:
            return None
    if not bits or len(bits) % 8:
        return None
    raw = bytes(
        int("".join(bits[index : index + 8]), 2)
        for index in range(0, len(bits), 8)
    )
    try:
        return raw.decode()
    except UnicodeDecodeError:
        return None


def strip_marker(text: str | None) -> str | None:
    if text is None or MARKER_START not in text:
        return text
    start = text.find(MARKER_START)
    end = text.find(MARKER_END, start + len(MARKER_START))
    if end < 0:
        return text
    return text[:start] + text[end + len(MARKER_END) :]


def author_name(embed: dict) -> str | None:
    return (embed.get("author") or {}).get("name")


def _clean_url(url: str | None) -> str | None:
    if not url:
        return None
    return url.split("?", 1)[0]


def stamp_embed(embed: dict, key: str) -> dict:
    """Return a copy of an embed with the message key hidden in it."""
    stamped = copy.deepcopy(embed)
    marker = encode_marker(key)
    footer = stamped.get("footer")
    if footer and footer.get("text"):
        footer["text"] = footer["text"] + marker
        return stamped
    stamped["description"] = (stamped.get("description") or "") + marker
    return stamped


def embed_signature(embed: dict) -> dict:
    """Comparable embed contents, ignoring Discord's extra fields."""
    author = embed.get("author") or {}
    footer = embed.get("footer") or {}
    fields = [
        {
            "name": field.get("name"),
            "value": field.get("value"),
            "inline": bool(field.get("inline", False)),
        }
        for field in embed.get("fields") or []
    ]
    return {
        "title": embed.get("title"),
        "description": strip_marker(embed.get("description")),
        "color": embed.get("color"),
        "author": {
            "name": author.get("name"),
            "icon_url": _clean_url(author.get("icon_url")),
        },
        "footer": {
            "text": strip_marker(footer.get("text")),
            "icon_url": _clean_url(footer.get("icon_url")),
        },
        "fields": fields,
    }


def message_signature(content: str | None, embeds: list) -> dict:
    return {
        "content": content or "",
        "embeds": [embed_signature(embed) for embed in embeds],
    }


def message_needs_update(message: discord.Message, spec: dict) -> bool:
    actual = message_signature(
        message.content, [embed.to_dict() for embed in message.embeds]
    )
    desired = message_signature(spec.get("content") or "", spec["embeds"])
    return actual != desired


def marker_from_embeds(embeds: list) -> str | None:
    for embed in embeds:
        footer = (embed.get("footer") or {}).get("text")
        key = decode_marker(footer)
        if key:
            return key
        key = decode_marker(embed.get("description"))
        if key:
            return key
    return None


def _can_carry_marker(embed: dict) -> bool:
    footer = (embed.get("footer") or {}).get("text")
    if footer:
        return True
    return bool(embed.get("description"))


def validate_specs(specs: list) -> None:
    keys = set()
    authors: dict = {}
    for spec in specs:
        key = spec.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError("information message key is missing")
        if key in keys:
            raise ValueError(f"Duplicate information message key {key}")
        keys.add(key)
        channel_id = spec.get("channel_id")
        if channel_id not in INFORMATION_CHANNEL_IDS:
            raise ValueError(f"Unexpected channel {channel_id} for {key}")
        embeds = spec.get("embeds")
        if not isinstance(embeds, list) or not embeds:
            raise ValueError(f"{key} has no embeds")
        if not _can_carry_marker(embeds[0]):
            raise ValueError(
                f"{key} needs footer text or a description to carry its id"
            )
        name = author_name(embeds[0])
        if not name:
            raise ValueError(f"{key} embed is missing an author name")
        authors.setdefault(channel_id, []).append(name)
    for channel_id, names in authors.items():
        if len(names) != len(set(names)):
            raise ValueError(
                f"Author names in channel {channel_id} must be unique"
            )


def load_message_specs(path: pathlib.Path | None = None) -> list:
    path = path or MESSAGES_PATH
    specs = json.loads(path.read_text())["messages"]
    validate_specs(specs)
    return specs


def default_state_path() -> pathlib.Path:
    raw = os.getenv("INFORMATION_STATE_PATH")
    if raw:
        return pathlib.Path(raw)
    return (
        pathlib.Path(tempfile.gettempdir()) / "am_bot_information_state.json"
    )


def load_state(path: pathlib.Path) -> dict:
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return {}
    except OSError:
        logger.warning(f"Ignoring unreadable information state at {path}")
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"Ignoring unreadable information state at {path}")
        return {}
    if not isinstance(data, dict):
        return {}
    cleaned = {}
    for key, value in data.items():
        try:
            cleaned[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return cleaned


def save_state(path: pathlib.Path, state: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2) + "\n")
    except OSError:
        logger.warning(f"Could not persist information message ids to {path}")


def _bot_id(message) -> int | None:
    return getattr(getattr(message, "author", None), "id", None)


def _embed_dicts(message) -> list:
    return [embed.to_dict() for embed in message.embeds]


def find_in_history(
    spec: dict, channel_specs: list, messages: list, bot_id: int, state: dict
):
    """Find the bot post for this spec inside an already-fetched history."""
    key = spec["key"]
    stored = state.get(key)
    if stored is not None:
        for message in messages:
            if message.id == stored and _bot_id(message) == bot_id:
                return message

    marked = []
    for message in messages:
        if _bot_id(message) != bot_id or not message.embeds:
            continue
        if marker_from_embeds(_embed_dicts(message)) == key:
            marked.append(message)
    if marked:
        if len(marked) > 1:
            logger.warning(
                f"Found {len(marked)} posts for {key}; "
                f"keeping {marked[0].id}"
            )
        return marked[0]
    return _match_by_author(spec, channel_specs, messages, bot_id)


def _match_by_author(spec: dict, channel_specs: list, messages: list, bot_id):
    name = author_name(spec["embeds"][0])
    if not name:
        return None
    names = [author_name(item["embeds"][0]) for item in channel_specs]
    if names.count(name) != 1:
        return None
    matches = []
    for message in messages:
        if _bot_id(message) != bot_id or not message.embeds:
            continue
        embeds = _embed_dicts(message)
        if marker_from_embeds(embeds):
            continue
        if author_name(embeds[0]) == name:
            matches.append(message)
    if len(matches) == 1:
        return matches[0]
    return None


def embeds_for(spec: dict) -> list:
    return [
        discord.Embed.from_dict(stamp_embed(embed, spec["key"]))
        for embed in spec["embeds"]
    ]


def content_for(spec: dict) -> str | None:
    return spec.get("content") or None


class InformationCog(commands.Cog):
    def __init__(
        self,
        bot: discord.ext.commands.Bot,
        *,
        messages_path: pathlib.Path | None = None,
        state_path: pathlib.Path | None = None,
    ):
        self.bot = bot
        self.messages_path = messages_path or MESSAGES_PATH
        self.state_path = state_path or default_state_path()
        self.state = load_state(self.state_path)
        self.message_ids: dict = {}
        self.ready = asyncio.Event()
        self._task = None

    def cog_load(self) -> None:
        self._task = self.bot.loop.create_task(self.sync_forever())

    def cog_unload(self) -> None:
        if self._task is not None:
            self._task.cancel()

    async def sync_forever(self) -> None:
        while True:
            try:
                await self.sync_all()
            except Exception:
                logger.exception("Information message sync failed")
            finally:
                self.ready.set()
            await asyncio.sleep(SYNC_INTERVAL_SECONDS)

    async def sync_all(self) -> None:
        specs = load_message_specs(self.messages_path)
        grouped: dict = {}
        for spec in specs:
            grouped.setdefault(spec["channel_id"], []).append(spec)
        for channel_id, channel_specs in grouped.items():
            try:
                await self.sync_channel(channel_id, channel_specs)
            except Exception:
                logger.exception(
                    f"Failed to sync information channel {channel_id}"
                )
        save_state(self.state_path, self.state)

    async def sync_channel(self, channel_id: int, specs: list) -> None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)
        history = []
        async for message in channel.history(
            limit=HISTORY_LIMIT, oldest_first=True
        ):
            history.append(message)
        if len(history) >= HISTORY_LIMIT:
            logger.warning(
                f"Channel {channel_id} history was truncated at "
                f"{HISTORY_LIMIT}"
            )
        for spec in specs:
            try:
                await self.sync_message(channel, spec, specs, history)
            except Exception:
                logger.exception(f"Failed to sync {spec['key']}")

    async def sync_message(
        self, channel, spec: dict, specs: list, history: list
    ) -> None:
        message = find_in_history(
            spec, specs, history, self.bot.user.id, self.state
        )
        if message is None and spec["key"] in self.state:
            message = await self.fetch_owned(channel, self.state[spec["key"]])
        if message is None:
            owned = [
                item for item in history if _bot_id(item) == self.bot.user.id
            ]
            if owned:
                logger.warning(
                    f"Posting a new {spec['key']} in #{channel.name} "
                    f"alongside {len(owned)} other bot message(s)"
                )
            message = await channel.send(
                content=content_for(spec),
                embeds=embeds_for(spec),
                allowed_mentions=ALLOWED_MENTIONS,
            )
            logger.info(f"Posted {spec['key']} ({message.id})")
        elif message_needs_update(message, spec):
            await message.edit(
                content=content_for(spec),
                embeds=embeds_for(spec),
                allowed_mentions=ALLOWED_MENTIONS,
            )
            logger.info(f"Updated {spec['key']} ({message.id})")
        else:
            logger.info(f"{spec['key']} is current ({message.id})")
        self.message_ids[spec["key"]] = message.id
        self.state[spec["key"]] = message.id

    async def fetch_owned(self, channel, message_id: int):
        try:
            message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden):
            return None
        if _bot_id(message) != self.bot.user.id:
            return None
        return message
