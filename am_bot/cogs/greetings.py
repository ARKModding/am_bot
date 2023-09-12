import logging

import discord
from discord.ext import commands


logger = logging.getLogger(__name__)


class GreetingsCog(commands.Cog):
    def __init__(self):
        self._last_member = None

    @commands.Cog.listener()
    async def on_member_join(self, member):
        logger.debug(f'Member joined guild: {member}')
        channel = member.guild.system_channel
        if channel is not None:
            await channel.send(f'Welcome {member.mention}!')

    @commands.command()
    async def hello(self, ctx, *, member: discord.Member = None):
        """Says Hello"""
        logger.debug('HELLO')
        member = member or ctx.author
        if self._last_member is None or self._last_member.id != member.id:
            await ctx.send(f'Hello {member.name}.')
        else:
            await ctx.send(f'Hello {member.name}... This feels familiar.')
        self._last_member = member
