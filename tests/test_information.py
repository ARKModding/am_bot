"""Tests for the information-channel posts."""

import asyncio
import copy
import json
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from am_bot.cogs.information import (
    MARKER_END,
    MARKER_ONE,
    MARKER_START,
    MARKER_ZERO,
    InformationCog,
    decode_marker,
    default_state_path,
    embed_signature,
    encode_marker,
    find_in_history,
    load_message_specs,
    load_state,
    marker_from_embeds,
    message_needs_update,
    save_state,
    stamp_embed,
    strip_marker,
    validate_specs,
)
from am_bot.cogs.role_assignment import ASSIGNABLE_ROLES
from am_bot.constants import (
    COMMUNITY_INFO_CHANNEL_ID,
    GREETINGS_CHANNEL_ID,
    RULES_AND_GUIDELINES_CHANNEL_ID,
    TERMS_AND_CONDITIONS_CHANNEL_ID,
)
from tests.conftest import (
    make_mock_bot,
    make_mock_channel,
    make_mock_message,
    make_mock_user,
)


BOT_ID = 999999
RULES_CHANNEL = RULES_AND_GUIDELINES_CHANNEL_ID
TERMS_CHANNEL = TERMS_AND_CONDITIONS_CHANNEL_ID


def rules_spec(description="Be nice"):
    return {
        "key": "rules",
        "channel_id": RULES_CHANNEL,
        "embeds": [
            {
                "description": description,
                "color": 1093364,
                "author": {
                    "name": "Rules",
                    "icon_url": "https://example.com/a.png",
                },
                "footer": {
                    "text": "Staff",
                    "icon_url": "https://example.com/a.png",
                },
            }
        ],
    }


def guidelines_spec():
    return {
        "key": "guidelines",
        "channel_id": RULES_CHANNEL,
        "embeds": [
            {
                "description": "Be civil",
                "color": 1093364,
                "author": {"name": "Guidelines"},
                "footer": {"text": "Staff"},
            }
        ],
    }


def terms_spec():
    return {
        "key": "terms",
        "channel_id": TERMS_CHANNEL,
        "embeds": [
            {
                "description": "Read this\u200b",
                "color": 1093364,
                "title": "Terms",
                "author": {"name": "Terms"},
            }
        ],
    }


def write_specs(path, specs):
    path.write_text(json.dumps({"messages": specs}))


def not_found():
    response = MagicMock(status=404)
    response.reason = "Not Found"
    return discord.NotFound(response, "missing")


def bot_message(message_id, spec, *, stamp=True, author_id=BOT_ID, content=""):
    embed = spec["embeds"][0]
    if stamp:
        embed = stamp_embed(embed, spec["key"])
    message = make_mock_message(
        message_id=message_id,
        content=content,
        embeds=[discord.Embed.from_dict(embed)],
        author=make_mock_user(user_id=author_id, name="Bot", bot=True),
    )
    message.edit = AsyncMock()
    return message


def sent_message(message_id):
    message = make_mock_message(
        message_id=message_id,
        content="",
        author=make_mock_user(user_id=BOT_ID, name="Bot", bot=True),
    )
    message.edit = AsyncMock()
    return message


def channel_with(messages, channel_id=RULES_CHANNEL, name="rules"):
    channel = make_mock_channel(channel_id=channel_id, name=name)

    async def history(*args, **kwargs):
        for message in messages:
            yield message

    channel.history = history
    channel.fetch_message = AsyncMock(side_effect=not_found())
    return channel


def make_cog(tmp_path, specs, channels):
    messages_path = tmp_path / "messages.json"
    write_specs(messages_path, specs)
    bot = make_mock_bot(user_id=BOT_ID)
    bot.get_channel.side_effect = lambda channel_id: channels.get(channel_id)
    cog = InformationCog(
        bot,
        messages_path=messages_path,
        state_path=tmp_path / "state.json",
    )
    return cog


class TestMarkers:
    def test_round_trip(self):
        for key in ("rules", "user-roles", "terms"):
            assert decode_marker(encode_marker(key)) == key

    def test_zero_width_space_already_in_the_text_is_left_alone(self):
        text = "hello\u200b"
        stamped = text + encode_marker("terms")
        assert decode_marker(stamped) == "terms"
        assert strip_marker(stamped) == text
        assert strip_marker(None) is None
        assert strip_marker("plain") == "plain"
        assert decode_marker("plain") is None
        assert decode_marker(MARKER_START + MARKER_ONE) is None
        garbage = MARKER_START + (MARKER_ONE * 8) + MARKER_END
        assert decode_marker(garbage) is None
        assert decode_marker(MARKER_START + "x" + MARKER_END) is None
        assert decode_marker(MARKER_START + MARKER_ZERO + MARKER_END) is None
        assert strip_marker("Staff" + MARKER_START) == "Staff" + MARKER_START

    def test_stamp_does_not_change_the_visible_embed(self):
        spec = rules_spec()
        stamped = stamp_embed(spec["embeds"][0], "rules")
        assert embed_signature(spec["embeds"][0]) == embed_signature(stamped)
        assert decode_marker(stamped["footer"]["text"]) == "rules"

        terms = terms_spec()
        stamped_terms = stamp_embed(terms["embeds"][0], "terms")
        assert embed_signature(terms["embeds"][0]) == embed_signature(
            stamped_terms
        )
        assert decode_marker(stamped_terms["description"]) == "terms"
        assert marker_from_embeds([stamped_terms]) == "terms"

    def test_query_string_on_an_icon_is_ignored(self):
        spec = rules_spec()
        message = bot_message(1, spec)
        message.embeds[0].set_footer(
            text=message.embeds[0].footer.text,
            icon_url="https://example.com/a.png?size=128",
        )
        assert message_needs_update(message, spec) is False


class TestMessageFile:
    def test_shipped_posts_match_the_role_config(self):
        specs = load_message_specs()
        keys = [spec["key"] for spec in specs]
        assert keys == [
            "rules",
            "guidelines",
            "community-info",
            "user-roles",
            "terms",
            "greetings",
        ]
        by_key = {spec["key"]: spec for spec in specs}
        assert by_key["rules"]["channel_id"] == RULES_AND_GUIDELINES_CHANNEL_ID
        assert by_key["guidelines"]["channel_id"] == RULES_CHANNEL
        assert (
            by_key["community-info"]["channel_id"] == COMMUNITY_INFO_CHANNEL_ID
        )
        assert by_key["user-roles"]["channel_id"] == COMMUNITY_INFO_CHANNEL_ID
        assert by_key["terms"]["channel_id"] == TERMS_AND_CONDITIONS_CHANNEL_ID
        assert by_key["greetings"]["channel_id"] == GREETINGS_CHANNEL_ID

        for spec in specs:
            for embed in spec["embeds"]:
                stamped = discord.Embed.from_dict(
                    stamp_embed(embed, spec["key"])
                ).to_dict()
                assert embed_signature(embed) == embed_signature(stamped)

        for role in ASSIGNABLE_ROLES.values():
            spec = by_key[role["message_key"]]
            assert role["channel_id"] == spec["channel_id"]
            assert "message_id" not in role

    def test_validate_specs_rejects_bad_messages(self):
        good = rules_spec()
        with pytest.raises(ValueError):
            validate_specs([{**good, "key": ""}])
        with pytest.raises(ValueError):
            validate_specs([good, {**guidelines_spec(), "key": "rules"}])
        with pytest.raises(ValueError):
            validate_specs([{**good, "channel_id": 1}])
        with pytest.raises(ValueError):
            validate_specs([{**good, "embeds": []}])
        bare = copy.deepcopy(good)
        bare["embeds"] = [{"author": {"name": "Rules"}}]
        with pytest.raises(ValueError):
            validate_specs([bare])
        nameless = copy.deepcopy(good)
        nameless["embeds"][0]["author"] = {}
        with pytest.raises(ValueError):
            validate_specs([nameless])
        twin = guidelines_spec()
        twin["embeds"][0]["author"]["name"] = "Rules"
        with pytest.raises(ValueError):
            validate_specs([good, twin])


class TestStateFile:
    def test_missing_state_is_empty(self, tmp_path):
        assert load_state(tmp_path / "absent.json") == {}

    def test_loads_ids(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text('{"rules": 15, "nope": "x"}')
        assert load_state(path) == {"rules": 15}

    def test_ignores_corrupt_state(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("{")
        assert load_state(path) == {}
        path.write_text("[]")
        assert load_state(path) == {}

    def test_ignores_unreadable_state(self, tmp_path):
        path = tmp_path / "state.json"
        with patch.object(
            pathlib.Path, "read_text", side_effect=PermissionError("no")
        ):
            assert load_state(path) == {}

    def test_save_failure_is_logged(self, tmp_path):
        path = tmp_path / "nested" / "state.json"
        with patch.object(pathlib.Path, "mkdir", side_effect=OSError("no")):
            save_state(path, {"rules": 1})
        assert not path.exists()

    def test_default_path_honors_the_environment(self, monkeypatch):
        monkeypatch.setenv("INFORMATION_STATE_PATH", "/tmp/custom-info.json")
        assert default_state_path() == pathlib.Path("/tmp/custom-info.json")
        monkeypatch.delenv("INFORMATION_STATE_PATH")
        assert default_state_path().name == "am_bot_information_state.json"


class TestSync:
    @pytest.mark.asyncio
    async def test_posts_missing_messages_in_order(self, tmp_path):
        channel = channel_with([])
        first = sent_message(11)
        second = sent_message(12)
        channel.send = AsyncMock(side_effect=[first, second])
        cog = make_cog(
            tmp_path,
            [rules_spec(), guidelines_spec()],
            {RULES_CHANNEL: channel},
        )

        await cog.sync_all()

        assert channel.send.await_count == 2
        first_embed = channel.send.await_args_list[0].kwargs["embeds"][0]
        second_embed = channel.send.await_args_list[1].kwargs["embeds"][0]
        assert first_embed.author.name == "Rules"
        assert decode_marker(first_embed.footer.text) == "rules"
        assert second_embed.author.name == "Guidelines"
        mentions = channel.send.await_args.kwargs["allowed_mentions"]
        assert mentions.roles is True
        assert mentions.everyone is False
        assert cog.message_ids == {"rules": 11, "guidelines": 12}
        saved = json.loads((tmp_path / "state.json").read_text())
        assert saved == {"rules": 11, "guidelines": 12}

    @pytest.mark.asyncio
    async def test_leaves_a_current_post_alone(self, tmp_path):
        spec = rules_spec()
        existing = bot_message(20, spec)
        channel = channel_with([existing])
        cog = make_cog(tmp_path, [spec], {RULES_CHANNEL: channel})

        await cog.sync_all()

        channel.send.assert_not_called()
        existing.edit.assert_not_called()
        assert cog.message_ids["rules"] == 20

    @pytest.mark.asyncio
    async def test_edits_when_the_text_changes(self, tmp_path):
        spec = rules_spec("Be nice")
        existing = bot_message(21, spec)
        existing.embeds[0].description = "Out of date"
        channel = channel_with([existing])
        cog = make_cog(
            tmp_path, [rules_spec("Be nicer")], {RULES_CHANNEL: channel}
        )

        await cog.sync_all()

        channel.send.assert_not_called()
        existing.edit.assert_awaited_once()
        edited = existing.edit.await_args.kwargs["embeds"][0]
        assert edited.description.startswith("Be nicer")
        assert cog.message_ids["rules"] == 21

    @pytest.mark.asyncio
    async def test_reuses_an_unstamped_post_with_the_same_author(
        self, tmp_path
    ):
        spec = rules_spec()
        existing = bot_message(22, spec, stamp=False)
        channel = channel_with([existing])
        cog = make_cog(tmp_path, [spec], {RULES_CHANNEL: channel})

        await cog.sync_all()

        channel.send.assert_not_called()
        existing.edit.assert_not_called()
        assert cog.message_ids["rules"] == 22

    @pytest.mark.asyncio
    async def test_does_not_adopt_dyno_messages(self, tmp_path):
        spec = rules_spec()
        dyno = bot_message(23, spec, stamp=False, author_id=168274283414421504)
        channel = channel_with([dyno])
        channel.send = AsyncMock(return_value=sent_message(24))
        cog = make_cog(tmp_path, [spec], {RULES_CHANNEL: channel})

        await cog.sync_all()

        channel.send.assert_awaited_once()
        assert cog.message_ids["rules"] == 24

    @pytest.mark.asyncio
    async def test_fetches_a_stored_id_outside_history(self, tmp_path):
        spec = rules_spec()
        existing = bot_message(30, spec)
        channel = channel_with([])
        channel.fetch_message = AsyncMock(return_value=existing)
        cog = make_cog(tmp_path, [spec], {RULES_CHANNEL: channel})
        cog.state = {"rules": 30}

        await cog.sync_all()

        channel.fetch_message.assert_awaited_once_with(30)
        channel.send.assert_not_called()
        assert cog.message_ids["rules"] == 30

    @pytest.mark.asyncio
    async def test_posts_again_when_the_stored_message_is_gone(self, tmp_path):
        spec = rules_spec()
        channel = channel_with([])
        channel.send = AsyncMock(return_value=sent_message(31))
        cog = make_cog(tmp_path, [spec], {RULES_CHANNEL: channel})
        cog.state = {"rules": 99}

        await cog.sync_all()

        channel.send.assert_awaited_once()
        assert cog.message_ids["rules"] == 31

    @pytest.mark.asyncio
    async def test_ignores_a_stored_message_from_someone_else(self, tmp_path):
        spec = rules_spec()
        stranger = bot_message(40, spec, author_id=5)
        channel = channel_with([])
        channel.fetch_message = AsyncMock(return_value=stranger)
        channel.send = AsyncMock(return_value=sent_message(41))
        cog = make_cog(tmp_path, [spec], {RULES_CHANNEL: channel})
        cog.state = {"rules": 40}

        await cog.sync_all()

        channel.send.assert_awaited_once()
        assert cog.message_ids["rules"] == 41

    @pytest.mark.asyncio
    async def test_keeps_the_oldest_duplicate(self, tmp_path):
        spec = rules_spec()
        older = bot_message(50, spec)
        newer = bot_message(51, spec)
        channel = channel_with([older, newer])
        cog = make_cog(tmp_path, [spec], {RULES_CHANNEL: channel})

        await cog.sync_all()

        channel.send.assert_not_called()
        assert cog.message_ids["rules"] == 50

    @pytest.mark.asyncio
    async def test_fetches_a_channel_that_is_not_cached(self, tmp_path):
        spec = rules_spec()
        channel = channel_with([])
        channel.send = AsyncMock(return_value=sent_message(60))
        cog = make_cog(tmp_path, [spec], {})
        cog.bot.get_channel.side_effect = None
        cog.bot.get_channel.return_value = None
        cog.bot.fetch_channel = AsyncMock(return_value=channel)

        await cog.sync_all()

        cog.bot.fetch_channel.assert_awaited_once_with(RULES_CHANNEL)
        channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_one_channel_failing_does_not_skip_the_other(self, tmp_path):
        terms = terms_spec()
        terms_channel = channel_with(
            [], channel_id=TERMS_CHANNEL, name="terms"
        )
        terms_channel.send = AsyncMock(return_value=sent_message(70))

        def get_channel(channel_id):
            if channel_id == RULES_CHANNEL:
                raise RuntimeError("rules down")
            return terms_channel

        cog = make_cog(tmp_path, [rules_spec(), terms], {})
        cog.bot.get_channel.side_effect = get_channel

        await cog.sync_all()

        terms_channel.send.assert_awaited_once()
        assert cog.message_ids == {"terms": 70}

    @pytest.mark.asyncio
    async def test_one_message_failing_does_not_skip_the_next(self, tmp_path):
        channel = channel_with([])
        channel.send = AsyncMock(
            side_effect=[RuntimeError("nope"), sent_message(81)]
        )
        cog = make_cog(
            tmp_path,
            [rules_spec(), guidelines_spec()],
            {RULES_CHANNEL: channel},
        )

        await cog.sync_all()

        assert channel.send.await_count == 2
        assert cog.message_ids == {"guidelines": 81}

    @pytest.mark.asyncio
    async def test_warns_when_history_is_truncated(self, tmp_path):
        spec = rules_spec()
        channel = channel_with([bot_message(1, spec, author_id=5)])
        channel.send = AsyncMock(return_value=sent_message(90))
        cog = make_cog(tmp_path, [spec], {RULES_CHANNEL: channel})

        with patch("am_bot.cogs.information.HISTORY_LIMIT", 1):
            await cog.sync_all()

        channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sends_configured_message_content(self, tmp_path):
        spec = rules_spec()
        spec["content"] = "hello"
        channel = channel_with([])
        channel.send = AsyncMock(return_value=sent_message(91))
        cog = make_cog(tmp_path, [spec], {RULES_CHANNEL: channel})

        await cog.sync_all()

        assert channel.send.await_args.kwargs["content"] == "hello"

    @pytest.mark.asyncio
    async def test_sync_forever_sets_ready_after_a_failure(self, tmp_path):
        cog = make_cog(tmp_path, [rules_spec()], {})
        cog.sync_all = AsyncMock(side_effect=RuntimeError("boom"))

        async def fake_sleep(seconds):
            raise asyncio.CancelledError

        with patch("am_bot.cogs.information.asyncio.sleep", fake_sleep):
            with pytest.raises(asyncio.CancelledError):
                await cog.sync_forever()

        assert cog.ready.is_set()

    def test_cog_load_and_unload(self, tmp_path):
        cog = make_cog(tmp_path, [rules_spec()], {})
        task = MagicMock()
        cog.bot.loop.create_task = MagicMock(return_value=task)

        cog.cog_load()
        created = cog.bot.loop.create_task.call_args.args[0]
        created.close()
        cog.cog_unload()

        cog.bot.loop.create_task.assert_called_once()
        task.cancel.assert_called_once()

    def test_two_unstamped_copies_are_not_guessed(self):
        spec = rules_spec()
        first = bot_message(1, spec, stamp=False)
        second = bot_message(2, spec, stamp=False)
        assert (
            find_in_history(spec, [spec], [first, second], BOT_ID, {}) is None
        )

    def test_stored_id_in_history_is_used(self):
        spec = rules_spec()
        existing = bot_message(30, spec)
        found = find_in_history(
            spec, [spec], [existing], BOT_ID, {"rules": 30}
        )
        assert found is existing

    def test_a_marked_post_for_another_key_is_not_adopted(self):
        spec = rules_spec()
        other = bot_message(1, guidelines_spec())
        other.embeds[0].set_author(name="Rules")
        assert find_in_history(spec, [spec], [other], BOT_ID, {}) is None

    def test_duplicate_author_names_are_not_guessed(self):
        spec = rules_spec()
        twin = guidelines_spec()
        twin["embeds"][0]["author"]["name"] = "Rules"
        existing = bot_message(1, spec, stamp=False)
        assert (
            find_in_history(spec, [spec, twin], [existing], BOT_ID, {}) is None
        )

    def test_missing_author_name_is_not_matched(self):
        spec = {"key": "x", "embeds": [{"description": "hi"}]}
        assert find_in_history(spec, [spec], [], BOT_ID, {}) is None

    @pytest.mark.asyncio
    async def test_warns_when_posting_beside_another_bot_message(
        self, tmp_path
    ):
        spec = rules_spec()
        other = bot_message(8, guidelines_spec())
        channel = channel_with([other])
        channel.send = AsyncMock(return_value=sent_message(9))
        cog = make_cog(tmp_path, [spec], {RULES_CHANNEL: channel})

        await cog.sync_all()

        channel.send.assert_awaited_once()
        assert cog.message_ids["rules"] == 9
