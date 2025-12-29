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
            cleared_messages = []
            emoji_count = 0

            for emoji, role_details in ASSIGNABLE_ROLES.items():
                channel = self.bot.get_channel(role_details["channel_id"])
                message = await channel.fetch_message(
                    role_details["message_id"]
                )
                if role_details["message_id"] not in cleared_messages:
                    await message.clear_reactions()
                    cleared_messages.append(role_details["message_id"])

                if "emoji_id" in role_details:
                    await message.add_reaction(
                        self.bot.get_emoji(role_details["emoji_id"])
                    )
                else:
                    await message.add_reaction(emoji)
                emoji_count += 1

            logger.info(
                f"Reaction role reset complete: {emoji_count} reactions on "
                f"{len(cleared_messages)} messages"
            )
            await asyncio.sleep(600)
