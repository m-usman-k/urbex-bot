import discord
import os
from discord.ext import commands, tasks
import aiosqlite
from utils.database import DB_PATH, update_user_balance, get_setting
from utils.logger import log_event
import logging
from datetime import datetime, timedelta

logger = logging.getLogger('boosters')

class Boosters(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reward_boosters.start()

    def cog_unload(self):
        self.reward_boosters.cancel()

    @tasks.loop(hours=24) # Check daily
    async def reward_boosters(self):
        # Current date for comparison
        today = datetime.now()
        
        # Reward amount from environment variables
        reward = int(os.getenv('COINS_NITRO_MONTHLY', 100))

        async with aiosqlite.connect(DB_PATH) as db:
            # Fetch all users who are currently boosting any guild the bot is in
            for guild in self.bot.guilds:
                if not guild: continue
                
                # Iterate through members (ensure chunked)
                if not guild.chunked: await guild.chunk()
                
                for member in guild.members:
                    if member.premium_since:
                        # Check last reward date from database
                        async with db.execute("SELECT last_boost_reward FROM users WHERE user_id = ?", (member.id,)) as cursor:
                            row = await cursor.fetchone()
                        
                        last_reward = row[0] if row and row[0] else None
                        
                        # Reward if it's been > 30 days or never rewarded
                        should_reward = False
                        if last_reward is None:
                            should_reward = True
                        else:
                            last_reward_dt = datetime.fromisoformat(last_reward)
                            if today - last_reward_dt >= timedelta(days=30):
                                should_reward = True
                        
                        if should_reward:
                            logger.info(f"Rewarding {member} for monthly boost.")
                            await update_user_balance(member.id, reward, "Monthly Nitro Boost Reward")
                            await db.execute("UPDATE users SET last_boost_reward = ? WHERE user_id = ?", (today.isoformat(), member.id))
                            await db.commit()
                            
                            try:
                                embed_dm = discord.Embed(title="Nitro Boost Reward", color=discord.Color.purple())
                                embed_dm.description = f"Here is your monthly bonus of **`{reward}`** coins for boosting the server!\nKeep up the great work!"
                                embed_dm.set_footer(text="The Urbex Factory | Modern Urbex Community")
                                await member.send(embed=embed_dm)
                            except:
                                pass
                                
                            # Log the reward
                            await log_event(self.bot, 'economy', "Monthly Booster Reward", 
                                            f"**User**: {member.mention}\n**Amount**: {reward}",
                                            color=discord.Color.purple())

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Detect new boost
        if not before.premium_since and after.premium_since:
            logger.info(f"{after} started boosting!")
            # Reward immediately from environment variables
            reward = int(os.getenv('COINS_NITRO_INITIAL', 100))
            await update_user_balance(after.id, reward, "Initial Nitro Boost Reward")
            try:
                embed_dm = discord.Embed(title="Thanks for Boosting!", color=discord.Color.purple())
                embed_dm.description = f"Since you started boosting, you've been rewarded with **`{reward}`** coins.\nWe appreciate your support!"
                embed_dm.set_footer(text="The Urbex Factory | Modern Urbex Community")
                await after.send(embed=embed_dm)
            except:
                pass
            
            # Log the reward
            await log_event(self.bot, 'economy', "Initial Booster Reward", 
                            f"**User**: {after.mention}\n**Amount**: {reward}",
                            color=discord.Color.purple())

async def setup(bot):
    await bot.add_cog(Boosters(bot))
