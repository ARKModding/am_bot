import logging
import re
from datetime import datetime, timezone

import discord
from discord.ext import commands

from ..constants import GUILD_ID, STARBOARD_TEXT_CHANNEL_ID


logger = logging.getLogger(__name__)
channel_id_pattern = re.compile(rf'discord\.com/channels/{GUILD_ID}/\d+/(\d+)')
REACTION_LIMIT = 5


class SpamCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot
        self._potential_spam = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id == self.bot.user.id:
            return
        if 'http' in message.content:
            if message.author.id in self._potential_spam:
                if len(self._potential_spam[message.author.id]) > 2:
