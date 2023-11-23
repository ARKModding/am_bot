import logging

import discord
from discord.ext.commands import Bot

from .cogs.greetings import GreetingsCog
from .cogs.invite_response import InviteResponseCog
from .cogs.responses import ResponsesCog
from .cogs.role_assignment import RoleAssignmentCog
from .cogs.server_stats import ServerStatsCog
from .cogs.workshop import WorkshopCog


logger = logging.getLogger(__name__)
intents = discord.Intents.default()
intents.members = True


class ARKBot(Bot):
    def __init__(self, command_prefix, **kwargs):
        super(ARKBot, self).__init__(command_prefix=command_prefix, intents=intents, **kwargs)
        self.add_cog(GreetingsCog())
        self.add_cog(InviteResponseCog(self))
        self.add_cog(ResponsesCog(self))
        self.add_cog(RoleAssignmentCog(self))
        self.add_cog(ServerStatsCog(self))
        self.add_cog(WorkshopCog(self))

    async def on_ready(self):
        logger.info(f'Logged on as {self.user}!')
        logger.info(f'Starting Tasks...')

        self.loop.create_task(self.get_cog('RoleAssignmentCog').reset_reactions())
        self.loop.create_task(self.get_cog('ServerStatsCog').update_server_stats())
        self.loop.create_task(self.get_cog('WorkshopCog').text_cleanup_task())

    async def on_message(self, message):
        logger.info(f'Message from {message.author}: {message.content}')
        if message.author.id == self.user.id:
            return
        await self.process_commands(message)
