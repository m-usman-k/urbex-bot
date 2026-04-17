import discord
import aiosqlite
from utils.database import get_setting, DB_PATH
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
        # Save to Database
        async with aiosqlite.connect(DB_PATH) as db:
            c_val = color.value if hasattr(color, 'value') else int(color)
            await db.execute(
                "INSERT INTO activity_logs (log_type, title, description, color) VALUES (?, ?, ?, ?)",
                (log_type, title, description, c_val)
            )
            await db.commit()

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
