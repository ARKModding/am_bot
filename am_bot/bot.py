import logging

import discord
from discord.ext.commands import Bot

from .cogs.greetings import GreetingsCog
from .cogs.invite_response import InviteResponseCog
from .cogs.quarantine import QuarantineCog
from .cogs.responses import ResponsesCog
from .cogs.role_assignment import RoleAssignmentCog
from .cogs.server_stats import ServerStatsCog
from .cogs.workshop import WorkshopCog
from .constants import GUILD_ID


logger = logging.getLogger(__name__)
intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class ARKBot(Bot):
    def __init__(self, command_prefix, **kwargs):
        super(ARKBot, self).__init__(
            command_prefix=command_prefix, intents=intents, **kwargs
        )

    async def on_ready(self):
        logger.info(f"Logged on as {self.user}!")
        logger.info("Starting Tasks...")
        await self.add_cogs()
        guild = discord.Object(id=GUILD_ID) 
        
        try:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(f"Synced {len(synced)} slash command(s) to guild {GUILD_ID}")
        except discord.HTTPException as e:
            logger.error(f"Failed to sync slash commands: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error during sync: {e}")

        logger.info("Bot is fully ready!")

    async def on_message(self, message):
        logger.info(f"Message from {message.author}: {message.content}")
        if message.author.id == self.user.id:
            return
        await self.process_commands(message)

    async def add_cogs(self):
        await self.add_cog(GreetingsCog())
        await self.add_cog(InviteResponseCog(self))
        await self.add_cog(QuarantineCog(self))
        await self.add_cog(ResponsesCog(self))
        await self.add_cog(RoleAssignmentCog(self))
        await self.add_cog(ServerStatsCog(self))
        await self.add_cog(WorkshopCog(self))
