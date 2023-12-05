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
        logger.debug("Updating Member Count...")
        self.guild = self.guild or self.bot.get_guild(GUILD_ID)
        logger.debug(f"Guild: {self.guild}")
        channel = await self.bot.fetch_channel(MEMBERS_COUNT_CHANNEL_ID)
        logger.debug(f"Member Count Channel: {channel}")
        member_count = len(self.guild.members)
        logger.debug(f"Member Count: {member_count}")
        await channel.edit(name=f"🔹┇{member_count}︲members")
        logger.debug("Member Count Channel Updated!")

    async def update_boost_count(self):
        logger.debug("Updating Boost Count...")
        self.guild = self.guild or self.bot.get_guild(GUILD_ID)
        logger.debug(f"Guild: {self.guild}")
        channel = await self.bot.fetch_channel(BOOSTS_COUNT_CHANNEL_ID)
        logger.debug(f"Boost Count Channel: {channel}")
        logger.debug(f"Boost Count: {self.guild.premium_subscription_count}")
        await channel.edit(
            name=f"🔸┇{self.guild.premium_subscription_count}︲boosts"
        )
        logger.debug("Boost Count Channel Updated!")

    async def update_role_counts(self):
        logger.debug("Updating Role Counts...")
        self.guild = self.guild or self.bot.get_guild(GUILD_ID)
        logger.debug(f"Guild: {self.guild}")
        modder_channel = await self.bot.fetch_channel(MODDER_STATS_CHANNEL_ID)
        logger.debug(f"Modder Count Channel: {modder_channel}")
        modder_role = self.guild.get_role(MODDER_ROLE_ID)
        logger.debug(f"Modder Role: {modder_role}")
        modder_member_count = len(modder_role.members)
        logger.debug(f"Modder Member Count: {modder_member_count}")
        await modder_channel.edit(name=f"🔸┇{modder_member_count}︲modders")
        logger.debug("Modder Count Channel Updated!")

        mapper_channel = await self.bot.fetch_channel(MAPPER_STATS_CHANNEL_ID)
        logger.debug("Getting Mapper Role...")
        mapper_role = self.guild.get_role(MAPPER_ROLE_ID)
        logger.debug(f"Mapper Role: {mapper_role}")
        mapper_member_count = len(mapper_role.members)
        logger.debug(f"Mapper Member Count: {mapper_member_count}")
        await mapper_channel.edit(name=f"🔹┇{mapper_member_count}︲mappers")
        logger.debug("Mapper Count Channel Updated!")

    async def update_server_stats(self):
        await asyncio.sleep(60)
        logger.debug("Updating Server Stats...")
        await self.update_member_count()
        await self.update_role_counts()
        while True:
            await self.update_boost_count()
            logger.debug("Server Stats updated! Sleeping 10 minutes...")
            await asyncio.sleep(600)
