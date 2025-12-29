import asyncio
import logging

import discord.ext.commands.bot
from discord.ext import commands

from ..constants import (
    BOOSTS_COUNT_CHANNEL_ID,
    GUILD_ID,
    MAPPER_ROLE_ID,
    MAPPER_STATS_CHANNEL_ID,
    MEMBERS_COUNT_CHANNEL_ID,
    MODDER_ROLE_ID,
    MODDER_STATS_CHANNEL_ID,
)


logger = logging.getLogger(__name__)


class ServerStatsCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.bot.Bot):
        self.bot = bot
        self.guild = None

    @commands.Cog.listener()
    async def on_member_join(self, _):
        await self.update_member_count()

    @commands.Cog.listener()
    async def on_member_remove(self, _):
        await self.update_member_count()

    def cog_load(self) -> None:
        self.bot.loop.create_task(self.update_server_stats())

    async def update_member_count(self):
        self.guild = self.guild or self.bot.get_guild(GUILD_ID)
        channel = await self.bot.fetch_channel(MEMBERS_COUNT_CHANNEL_ID)
        member_count = len(self.guild.members)
        await channel.edit(name=f"🔹┇{member_count}︲members")
        logger.info(f"Updated member count: {member_count}")

    async def update_boost_count(self):
        self.guild = self.guild or self.bot.get_guild(GUILD_ID)
        channel = await self.bot.fetch_channel(BOOSTS_COUNT_CHANNEL_ID)
        boost_count = self.guild.premium_subscription_count
        await channel.edit(name=f"🔸┇{boost_count}︲boosts")
        logger.debug(f"Updated boost count: {boost_count}")

    async def update_role_counts(self):
        self.guild = self.guild or self.bot.get_guild(GUILD_ID)

        modder_channel = await self.bot.fetch_channel(MODDER_STATS_CHANNEL_ID)
        modder_role = self.guild.get_role(MODDER_ROLE_ID)
        modder_count = len(modder_role.members)
        await modder_channel.edit(name=f"🔸┇{modder_count}︲modders")

        mapper_channel = await self.bot.fetch_channel(MAPPER_STATS_CHANNEL_ID)
        mapper_role = self.guild.get_role(MAPPER_ROLE_ID)
        mapper_count = len(mapper_role.members)
        await mapper_channel.edit(name=f"🔹┇{mapper_count}︲mappers")

        logger.info(f"Updated role counts: {modder_count} modders, {mapper_count} mappers")

    async def update_server_stats(self):
        await asyncio.sleep(60)
        await self.update_member_count()
        await self.update_role_counts()
        logger.info("Initial server stats update complete")
        while True:
            await self.update_boost_count()
            await asyncio.sleep(600)

