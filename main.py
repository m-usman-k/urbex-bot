import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
logger = logging.getLogger('bot')

from utils.database import init_db

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Initialize Bot
class UrbexBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        # Initialize Database
        try:
            await init_db()
            logger.info('Database initialized.')
        except Exception as e:
            logger.error(f'Failed to initialize database: {e}')

        # Load Cogs
        initial_extensions = [
            'cogs.economy',
            'cogs.forms',
            'cogs.admin',
            'cogs.shop',
            'cogs.boosters',
            'cogs.general'
        ]
        
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f'Successfully loaded extension {extension}')
            except Exception as e:
                logger.error(f'Failed to load extension {extension}. Error: {e}')

        # Sync Slash Commands
        try:
            guild_id = os.getenv('GUILD_ID')
            if guild_id and guild_id.strip():
                try:
                    guild = discord.Object(id=int(guild_id))
                    self.tree.clear_commands(guild=guild)
                    self.tree.copy_global_to(guild=guild)
                    # Remove stale global commands to prevent guild/global duplicates.
                    self.tree.clear_commands(guild=None)
                    await self.tree.sync()
                    synced = await self.tree.sync(guild=guild)
                    logger.info(f'Synced {len(synced)} commands to Guild ID: {guild_id}')
                except ValueError:
                    logger.warning(f"Invalid GUILD_ID: '{guild_id}'. Syncing globally...")
                    synced = await self.tree.sync()
                    logger.info(f'Synced {len(synced)} commands globally.')
            else:
                synced = await self.tree.sync()
                logger.info(f'Synced {len(synced)} commands globally.')
        except Exception as e:
            logger.error(f'Failed to sync commands: {e}')

    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception):
        if isinstance(error, discord.app_commands.MissingPermissions):
            if interaction.response.is_done():
                await interaction.followup.send("Je hebt geen toegang tot deze commando.", ephemeral=True)
            else:
                await interaction.response.send_message("Je hebt geen toegang tot deze commando.", ephemeral=True)
            return

        logger.error(f"Unhandled app command error: {error}")
        if interaction.response.is_done():
            await interaction.followup.send("Er ging iets mis bij het uitvoeren van dit commando.", ephemeral=True)
        else:
            await interaction.response.send_message("Er ging iets mis bij het uitvoeren van dit commando.", ephemeral=True)

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info('------')

async def main():
    bot = UrbexBot()
    async with bot:
          await bot.start(TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal error: {e}")
