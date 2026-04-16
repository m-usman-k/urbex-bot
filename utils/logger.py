import discord
from utils.database import get_setting
import logging

logger = logging.getLogger('bot_logger')

LOG_TYPES = {
    'submissions': 'log_submissions',
    'economy': 'log_economy',
    'shop': 'log_shop',
    'admin': 'log_admin'
}

async def log_event(bot, log_type, title, description, color=discord.Color.blue(), fields=None, thumbnail=None):
    """
    Centralized logging function to send embeds to configured log channels.
    """
    setting_key = LOG_TYPES.get(log_type)
    if not setting_key:
        return

    channel_id = await get_setting(setting_key)
    if not channel_id:
        return

    try:
        channel = bot.get_channel(int(channel_id))
        if not channel:
            channel = await bot.fetch_channel(int(channel_id))
        
        if channel:
            embed = discord.Embed(title=title, description=description, color=color)
            if fields:
                for name, value, inline in fields:
                    embed.add_field(name=name, value=value, inline=inline)
            
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)
            
            await channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Failed to send log to channel {channel_id}: {e}")
