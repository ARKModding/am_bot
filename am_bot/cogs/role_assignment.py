import asyncio
import json
import logging
import pathlib


import discord
from discord.ext import commands


logger = logging.getLogger(__name__)
ASSIGNABLE_ROLES = json.load(open(pathlib.Path(__file__).parent.resolve() / 'assignable_roles.json', 'rb'))


class RoleAssignmentCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Add role"""
        if payload.member.id == self.bot.user.id:
            logger.debug(f'Reaction from self. Ignore')
            return
        logger.debug(f'Reaction ADD Received. Payload: {payload}')
        if payload.emoji.name not in ASSIGNABLE_ROLES:
            logger.debug('Emoji not in ASSIGNABLE_ROLES. Skipping.')
            return
        emoji = payload.emoji.name
        if 'message_id' in ASSIGNABLE_ROLES[emoji] and payload.message_id != ASSIGNABLE_ROLES[emoji]['message_id']:
            logger.debug(f'Wrong Channel')
            return
        # Add Role (no need to check)
        logger.info(f'Adding {ASSIGNABLE_ROLES[emoji]["name"]} Role to {payload.member}')
        await payload.member.add_roles(payload.member.guild.get_role(ASSIGNABLE_ROLES[emoji]['role_id']))
        if ASSIGNABLE_ROLES[emoji]['name'] in ['Modder', 'Mapper']:
            server_stats_cog = self.bot.get_cog('ServerStatsCog')
            if server_stats_cog:
                await server_stats_cog.update_role_counts()

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Remove role"""
        logger.debug(f'Reaction REMOVE Received. Payload {payload}')
        if payload.emoji.name not in ASSIGNABLE_ROLES:
            logger.debug('Emoji not in ASSIGNABLE_ROLES. Skipping.')
            return
        emoji = payload.emoji.name
        if 'message_id' in ASSIGNABLE_ROLES[emoji] and payload.message_id != ASSIGNABLE_ROLES[emoji]['message_id']:
            logger.debug('Wrong Channel')
            return

        # Remove Role
        guild = await self.bot.fetch_guild(payload.guild_id)
        member = await guild.fetch_member(payload.user_id)
        logger.info(f'Removing {ASSIGNABLE_ROLES[emoji]["name"]} Role from {member}.')
        await member.remove_roles(guild.get_role(ASSIGNABLE_ROLES[emoji]['role_id']))
        if ASSIGNABLE_ROLES[emoji]['name'] in ['Modder', 'Mapper']:
            server_stats_cog = self.bot.get_cog('ServerStatsCog')
            if server_stats_cog:
                await server_stats_cog.update_role_counts()

    async def reset_reactions(self):
        await asyncio.sleep(10)
        while True:
            logger.debug('Resetting reactions for Reaction Roles...')
            cleared_messages = []
            for emoji, role_details in ASSIGNABLE_ROLES.items():
                logger.debug(f'Resetting Emoji: {emoji}')
                channel = self.bot.get_channel(role_details['channel_id'])
                message = await channel.fetch_message(role_details['message_id'])
                # Check if we have already reset reactions for this message, if not, clear them
                if role_details['message_id'] not in cleared_messages:
                    logger.debug(f'Message ID {role_details["message_id"]} has not been reset. Resetting...')
                    await message.clear_reactions()
                    cleared_messages.append(role_details['message_id'])
                # Add first reaction with this emoji.
                if 'emoji_id' in role_details:
                    # Custom Emoji
                    logger.debug(f'Adding custom Emoji Reaction {emoji} to Message ID {role_details["message_id"]}')
                    await message.add_reaction(self.bot.get_emoji(role_details['emoji_id']))
                else:
                    # Unicode Emoji
                    logger.debug(f'Adding Unicode Emoji Reaction {emoji} to Message ID {role_details["message_id"]}')
                    await message.add_reaction(emoji)
            logger.debug('Finished Reaction Role Reset. Sleeping 10 minutes...')
            await asyncio.sleep(600)
