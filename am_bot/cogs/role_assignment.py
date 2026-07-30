import asyncio
import json
import logging
import pathlib

import discord
from discord.ext import commands


logger = logging.getLogger(__name__)
ASSIGNABLE_ROLES = json.load(
    open(
        pathlib.Path(__file__).parent.resolve() / "assignable_roles.json", "rb"
    )
)
RESET_INTERVAL_SECONDS = 600
ADD_REACTION_ATTEMPTS = 3
ADD_REACTION_RETRY_SECONDS = 5


def entries_by_message(assignable_roles: dict) -> dict:
    """Group the role config by the message its reactions belong on."""
    grouped = {}
    for emoji, role_details in assignable_roles.items():
        key = (role_details["channel_id"], role_details["message_id"])
        grouped.setdefault(key, []).append((emoji, role_details))
    return grouped


def holds_only_expected(message: discord.Message, expected: dict) -> bool:
    """Whether a message carries just the bot's own expected reactions."""
    if len(message.reactions) != len(expected):
        return False
    return all(
        str(reaction.emoji) in expected and reaction.me and reaction.count == 1
        for reaction in message.reactions
    )


class RoleAssignmentCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot

    def cog_load(self) -> None:
        self.bot.loop.create_task(self.reset_reactions())

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ):
        """Add role"""
        if payload.member.id == self.bot.user.id:
            return
        if payload.emoji.name not in ASSIGNABLE_ROLES:
            return
        emoji = payload.emoji.name
        if (
            "message_id" in ASSIGNABLE_ROLES[emoji]
            and payload.message_id != ASSIGNABLE_ROLES[emoji]["message_id"]
        ):
            return

        role_name = ASSIGNABLE_ROLES[emoji]["name"]
        logger.info(f"Adding {role_name} role to {payload.member}")
        await payload.member.add_roles(
            payload.member.guild.get_role(ASSIGNABLE_ROLES[emoji]["role_id"])
        )
        if role_name in ["Modder", "Mapper"]:
            server_stats_cog = self.bot.get_cog("ServerStatsCog")
            if server_stats_cog:
                await server_stats_cog.update_role_counts()

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Remove role"""
        if payload.emoji.name not in ASSIGNABLE_ROLES:
            return
        emoji = payload.emoji.name
        if (
            "message_id" in ASSIGNABLE_ROLES[emoji]
            and payload.message_id != ASSIGNABLE_ROLES[emoji]["message_id"]
        ):
            return

        guild = await self.bot.fetch_guild(payload.guild_id)
        member = await guild.fetch_member(payload.user_id)
        role_name = ASSIGNABLE_ROLES[emoji]["name"]
        logger.info(f"Removing {role_name} role from {member}")
        await member.remove_roles(
            guild.get_role(ASSIGNABLE_ROLES[emoji]["role_id"])
        )
        if role_name in ["Modder", "Mapper"]:
            server_stats_cog = self.bot.get_cog("ServerStatsCog")
            if server_stats_cog:
                await server_stats_cog.update_role_counts()

    async def reset_reactions(self):
        await asyncio.sleep(10)
        while True:
            try:
                await self.reset_all_reactions()
            except Exception:
                logger.exception("Reaction role reset cycle failed")
            await asyncio.sleep(RESET_INTERVAL_SECONDS)

    async def reset_all_reactions(self) -> None:
        emoji_count = 0
        message_count = 0

        for (channel_id, message_id), entries in entries_by_message(
            ASSIGNABLE_ROLES
        ).items():
            try:
                emoji_count += await self.reset_message_reactions(
                    channel_id, message_id, entries
                )
            except Exception:
                logger.exception(
                    f"Failed to reset reactions on message {message_id}"
                )
                continue
            message_count += 1

        logger.info(
            f"Reaction role reset complete: {emoji_count} reactions on "
            f"{message_count} messages"
        )

    async def reset_message_reactions(
        self, channel_id: int, message_id: int, entries: list
    ) -> int:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)
        message = await channel.fetch_message(message_id)

        expected = {}
        for emoji, role_details in entries:
            reaction = emoji
            if "emoji_id" in role_details:
                reaction = self.bot.get_emoji(role_details["emoji_id"])
                if reaction is None:
                    logger.error(
                        f"Emoji {role_details['emoji_id']} for the "
                        f"{role_details['name']} role is unavailable"
                    )
                    continue
            expected[str(reaction)] = reaction

        if holds_only_expected(message, expected):
            return len(expected)

        # clear_reactions() emits one bulk-removal event. Removing each user
        # individually would instead fire on_raw_reaction_remove and strip the
        # roles those reactions just granted.
        await message.clear_reactions()

        added = 0
        for reaction in expected.values():
            if await self.add_reaction(message, reaction):
                added += 1
        return added

    async def add_reaction(self, message: discord.Message, reaction) -> bool:
        """Add a reaction, riding out transient Discord API failures."""
        for attempt in range(1, ADD_REACTION_ATTEMPTS + 1):
            try:
                await message.add_reaction(reaction)
                return True
            except discord.DiscordServerError as e:
                logger.warning(
                    f"Attempt {attempt} to add {reaction} to message "
                    f"{message.id} failed: {e}"
                )
                if attempt < ADD_REACTION_ATTEMPTS:
                    await asyncio.sleep(ADD_REACTION_RETRY_SECONDS * attempt)

        logger.error(
            f"Could not add {reaction} to message {message.id}; retrying "
            f"in {RESET_INTERVAL_SECONDS}s"
        )
        return False
