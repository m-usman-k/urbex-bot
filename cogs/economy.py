import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from datetime import datetime, timedelta, timezone
from utils.database import get_user_balance, update_user_balance, get_user_stats, DB_PATH, get_setting, add_xp

class HistoryPagination(discord.ui.View):
    def __init__(self, target, bot):
        super().__init__(timeout=60)
        self.target = target
        self.bot = bot
        self.page = 0
        self.per_page = 5 # Show 5 to keep it readable, can be 10

    async def get_page_data(self):
        offset = self.page * self.per_page
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT amount, reason, timestamp FROM transactions WHERE user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?", 
                (self.target.id, self.per_page, offset)
            ) as cursor:
                return await cursor.fetchall()

    async def get_total_pages(self):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM transactions WHERE user_id = ?", (self.target.id,)) as cursor:
                count = await cursor.fetchone()
                return (count[0] + self.per_page - 1) // self.per_page if count else 1

    async def create_embed(self):
        data = await self.get_page_data()
        total = await self.get_total_pages()
        
        embed = discord.Embed(title=f"🕒 Transacties: {self.target.display_name}", color=discord.Color.blue())
        if not data:
            embed.description = "Geen (verdere) transacties gevonden."
        else:
            for amount, reason, timestamp in data:
                prefix = "💰 +" if amount > 0 else "💳 -"
                try:
                    dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                except ValueError:
                    dt = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
                
                ts = int(dt.timestamp())
                embed.add_field(
                    name=f"{prefix} {abs(amount)} Coins", 
                    value=f"**Reden**: {reason}\n**Tijd**: <t:{ts}:R>", 
                    inline=False
                )
        
        embed.set_footer(text=f"Pagina {self.page + 1} van {max(1, total)} • The Urbex Factory")
        return embed

    @discord.ui.button(label="Vorige", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=await self.create_embed(), view=self)
        else:
            await interaction.response.send_message("Je bent al op de eerste pagina.", ephemeral=True)

    @discord.ui.button(label="Volgende", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        total = await self.get_total_pages()
        if self.page < total - 1:
            self.page += 1
            await interaction.response.edit_message(embed=await self.create_embed(), view=self)
        else:
            await interaction.response.send_message("Er zijn geen volgende pagina's.", ephemeral=True)

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _check_commands_channel(self, interaction: discord.Interaction):
        chan_id = await get_setting('commands_channel')
        if chan_id and interaction.channel_id != int(chan_id) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(f"Gebruik dit commando in <#{chan_id}>.", ephemeral=True)
            return False
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        now = datetime.now()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT last_message_reward FROM users WHERE user_id = ?", (message.author.id,)) as cursor:
                row = await cursor.fetchone()

            last_reward = row[0] if row and row[0] else None
            if last_reward:
                last_reward_dt = datetime.fromisoformat(last_reward)
                if now - last_reward_dt < timedelta(minutes=30):
                    return

            await update_user_balance(message.author.id, 1, "Activiteit beloning (30 min)")
            await add_xp(message.author.id, 5)
            await db.execute(
                "UPDATE users SET last_message_reward = ? WHERE user_id = ?",
                (now.isoformat(), message.author.id),
            )
            await db.commit()

    @app_commands.command(name="profile", description="Bekijk je Urbex profiel en statistieken")
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        if not await self._check_commands_channel(interaction):
            return
        
        await interaction.response.defer()
        member = member or interaction.user
        stats = await get_user_stats(member.id)
        
        if not stats:
            return await interaction.followup.send(embed=discord.Embed(description="Geen gebruikersdata gevonden.", color=discord.Color.red()), ephemeral=True)

        embed = discord.Embed(title=f"Profiel van {member.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=member.display_avatar.url)
        
        current_level = stats['level']
        current_xp = stats['xp']
        xp_needed = (current_level * 100) + 50
        xp_percent = min(100, int((current_xp / xp_needed) * 100))
        filled = xp_percent // 10
        progress_bar = "[" + "=" * filled + "-" * (10 - filled) + "]"
        
        embed.add_field(name="Level & XP", value=f"**Level `{current_level}`**\n`{current_xp}/{xp_needed}` XP\n`{progress_bar}`", inline=False)
        embed.add_field(name="Wallet", value=f"**`{stats['balance']}`** Coins", inline=True)
        embed.add_field(name="Totaal verdiend", value=f"**`{stats['total_earned']}`** Coins", inline=True)
        embed.add_field(name="Goedgekeurde inzendingen", value=f"**`{stats['submissions']}`**", inline=True)
        
        embed.set_footer(text="The Urbex Factory Explorer", icon_url=self.bot.user.display_avatar.url)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="daily", description="Claim je dagelijkse coin beloning")
    async def daily(self, interaction: discord.Interaction):
        if not await self._check_commands_channel(interaction):
            return

        user_id = interaction.user.id
        
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
        
        last_daily = row[0] if row and row[0] else None
        now = datetime.now()
        
        if last_daily:
            last_dt = datetime.fromisoformat(last_daily)
            if now < last_dt + timedelta(days=1):
                next_claim = last_dt + timedelta(days=1)
                return await interaction.response.send_message(embed=discord.Embed(
                    description=f"Je hebt je daily al geclaimd. Probeer opnieuw <t:{int(next_claim.timestamp())}:R>.",
                    color=discord.Color.red()
                ), ephemeral=True)
        
        import os
        reward = int(os.getenv('COINS_DAILY', 10))
            
        new_balance = await update_user_balance(user_id, reward, "Daily Reward")
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (now.isoformat(), user_id))
            await db.commit()
            
        embed = discord.Embed(title="Daily geclaimd", color=discord.Color.green())
        embed.description = f"Je hebt **`{reward}`** coins ontvangen.\nNieuw saldo: **`{new_balance}`**"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="balance", description="Bekijk je huidige coin saldo")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        if not await self._check_commands_channel(interaction):
            return
        
        await interaction.response.defer()
        member = member or interaction.user
        balance = await get_user_balance(member.id)
        
        embed = discord.Embed(
            title="💰 Coin Balance",
            description=f"{member.mention} heeft momenteel **`{balance}`** coins.",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="leaderboard", description="Bekijk de top verdieners")
    @app_commands.choices(category=[
        app_commands.Choice(name="Coins", value="balance"),
        app_commands.Choice(name="XP", value="level")
    ])
    async def leaderboard(self, interaction: discord.Interaction, category: str = "balance"):
        if not await self._check_commands_channel(interaction):
            return

        async with aiosqlite.connect(DB_PATH) as db:
            if category == "balance":
                async with db.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10") as cursor:
                    top_users = await cursor.fetchall()
                    title = "Top verdieners"
                    unit = "coins"
            else:
                async with db.execute("SELECT user_id, level FROM users ORDER BY level DESC, xp DESC LIMIT 10") as cursor:
                    top_users = await cursor.fetchall()
                    title = "Top explorers"
                    unit = "Level"

        if not top_users:
            return await interaction.response.send_message(embed=discord.Embed(description="Nog geen gebruikers in de leaderboard.", color=discord.Color.red()))

        description = ""
        for i, (user_id, value) in enumerate(top_users, 1):
            user = self.bot.get_user(user_id)
            user_name = user.name if user else f"User {user_id}"
            val_str = f"{value:,}" if isinstance(value, int) else value
            description += f"**{i}.** {user_name} - **`{val_str}`** {unit}\n"

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="history", description="Bekijk je complete transactiegeschiedenis")
    async def history(self, interaction: discord.Interaction, member: discord.Member = None):
        if not await self._check_commands_channel(interaction):
            return

        target = member or interaction.user
        if member and member.id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Je hebt geen toegang tot deze commando.", ephemeral=True)

        await interaction.response.defer()
        view = HistoryPagination(target, self.bot)
        embed = await view.create_embed()
        
        if not embed.fields and not embed.description:
            return await interaction.followup.send("Geen transactiegeschiedenis gevonden.", ephemeral=True)

        await interaction.followup.send(embed=embed, view=view, ephemeral=member is not None and member.id != interaction.user.id)

async def setup(bot):
    await bot.add_cog(Economy(bot))
