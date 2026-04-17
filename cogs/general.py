import discord
from discord.ext import commands
from discord import app_commands, ui
import aiosqlite
import os
from utils.database import get_setting, DB_PATH

class HelpDropdown(ui.Select):
    def __init__(self, bot, categories):
        self.bot = bot
        self.categories = categories
        options = [
            discord.SelectOption(label="Home", description="Back to the landing page", emoji="🏠"),
            discord.SelectOption(label="Earnings", description="How to earn coins", emoji="🪙"),
            discord.SelectOption(label="Economy", description="Coins and Leaderboards", emoji="💰"),
            discord.SelectOption(label="Submissions", description="Submit reviews and updates", emoji="📝"),
            discord.SelectOption(label="Shop", description="Open manual claim tickets", emoji="🛒"),
            discord.SelectOption(label="Boosters", description="Server boosting utilities", emoji="🚀"),
            discord.SelectOption(label="General", description="General utility commands", emoji="📖")
        ]
        if "Admin" in categories and categories["Admin"]:
            options.append(discord.SelectOption(label="Administration", description="Admin-only tools and setup", emoji="🛡️"))
        super().__init__(placeholder="Choose a category to view commands...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "Home":
            return await interaction.response.edit_message(embed=create_main_help_embed(self.bot), view=self.view)

        if self.values[0] == "Earnings":
            daily = int(os.getenv('COINS_DAILY', 10))
            review = int(os.getenv('COINS_REVIEW', 25))
            update = int(os.getenv('COINS_UPDATE', 5))
            boost_init = int(os.getenv('COINS_NITRO_INITIAL', 100))
            boost_month = int(os.getenv('COINS_NITRO_MONTHLY', 100))

            act_coins = int(os.getenv('COINS_ACTIVITY', 2))
            act_xp = int(os.getenv('XP_ACTIVITY', 5))
            act_int = int(os.getenv('ACTIVITY_INTERVAL_MINUTES', 60))

            embed = discord.Embed(
                title="🪙 Hoe kan ik verdienen?",
                description="Hieronder vind je de verschillende manieren om coins te verdienen in de community.",
                color=discord.Color.gold()
            )
            embed.add_field(name="📅 Daily Reward", value=f"Claim elke 24 uur **{daily} coins** met `/daily`.", inline=False)
            embed.add_field(name="⭐ Reviews", value=f"Verdien **{review} coins** per goedgekeurde review.", inline=False)
            embed.add_field(name="📍 Updates", value=f"Verdien **{update} coins** voor elke goedgekeurde locatie update.", inline=False)
            embed.add_field(name="🚀 Server Boosting", value=f"Verdien **{boost_init} coins** bij het starten van een boost en **{boost_month} coins** per maand!", inline=False)
            embed.add_field(name="✨ Activiteit", value=f"\nVerdien **{act_coins} coins** per **{act_int} minuten** door actief te zijn in de chat!", inline=False)
            
            embed.set_footer(text="The Urbex Factory | Economy System", icon_url=self.bot.user.display_avatar.url)
            return await interaction.response.edit_message(embed=embed, view=self.view)

        chosen = self.values[0]
        category_map = {
            "Economy": "Economy",
            "Submissions": "Forms",
            "Shop": "Shop",
            "Boosters": "Boosters",
            "General": "General",
            "Administration": "Admin"
        }
        
        cog_name = category_map.get(chosen)
        commands_list = self.categories.get(cog_name, [])

        embed = discord.Embed(
            title=f"{chosen} Commands",
            description=f"Here are the commands available in the **{chosen}** category.",
            color=discord.Color.blue()
        )

        if not commands_list:
            embed.description = "No commands found in this category."
        else:
            command_text = ""
            for cmd in commands_list:
                command_text += f"**`/{cmd['name']}`**\n└ {cmd['description']}\n\n"
            embed.description = command_text

        embed.set_footer(text="The Urbex Factory | Modern Urbex Community", icon_url=self.bot.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self.view)

def create_main_help_embed(bot):
    embed = discord.Embed(
        title="UrbexBot Help Center",
        description=(
            "Welcome to the **Urbex Factory** official bot. Use the dropdown below to explore our features!\n\n"
            "**Earnings**: Hoe je coins kunt verdienen in de community. 🪙\n"
            "**Economy**: Earn coins and compete on the leaderboard.\n"
            "**Submissions**: High-fidelity reviews and updates with native image grids.\n"
            "**Shop**: Open a manual claim ticket with staff.\n"
            "**Admin**: Tools for server staff to manage the bot.\n\n"
            "*Select a category from the menu below to see specific commands.*"
        ),
        color=discord.Color.blue()
    )
    embed.set_author(name="Urbex Factory | Support System", icon_url=bot.user.display_avatar.url)
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="Developed for The Urbex Factory • Modern Urbex Community")
    return embed

class HelpView(ui.View):
    def __init__(self, bot, categories):
        super().__init__(timeout=180)
        self.add_item(HelpDropdown(bot, categories))

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Get help with bot commands and features")
    async def help_command(self, interaction: discord.Interaction):
        chan_id = await get_setting('commands_channel')
        if chan_id and interaction.channel_id != int(chan_id) and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(f"Gebruik dit commando in <#{chan_id}>.", ephemeral=True)

        categories = {}

        # Scan all commands and group them by binding (Cog)
        tree_commands = []
        if interaction.guild:
            tree_commands = list(self.bot.tree.walk_commands(guild=interaction.guild))
        
        # Fallback to global if guild commands return empty
        if not tree_commands:
            tree_commands = list(self.bot.tree.walk_commands())
            
        for command in tree_commands:
            if isinstance(command, app_commands.Command):
                cog_name = "General"
                if command.binding:
                    cog_name = command.binding.__class__.__name__
                
                if cog_name not in categories:
                    categories[cog_name] = []
                
                if cog_name == "Admin" and not interaction.user.guild_permissions.administrator:
                    continue
                categories[cog_name].append({"name": command.name, "description": command.description.split('\n')[0]})

        view = HelpView(self.bot, categories)
        await interaction.response.send_message(embed=create_main_help_embed(self.bot), view=view)

    @app_commands.command(name="stats", description="View global server economy and submission statistics")
    async def stats(self, interaction: discord.Interaction):
        chan_id = await get_setting('commands_channel')
        if chan_id and interaction.channel_id != int(chan_id) and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(f"Gebruik dit commando in <#{chan_id}>.", ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT SUM(balance) FROM users") as cursor:
                row = await cursor.fetchone()
                total_coins = row[0] if row and row[0] else 0
            
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                row = await cursor.fetchone()
                total_users = row[0] if row and row[0] else 0
                
            async with db.execute("SELECT COUNT(*) FROM submissions WHERE status = 'approved'") as cursor:
                row = await cursor.fetchone()
                total_subs = row[0] if row and row[0] else 0
        
        embed = discord.Embed(title="Urbex Factory Global Stats", color=discord.Color.blue())
        embed.add_field(name="Total Economy", value=f"**`{total_coins:,}`** Coins", inline=True)
        embed.add_field(name="Active Explorers", value=f"**`{total_users:,}`** Members", inline=True)
        embed.add_field(name="Verified Submissions", value=f"**`{total_subs:,}`** Approved", inline=False)
        
        embed.set_author(name="Urbex Factory Statistics", icon_url=self.bot.user.display_avatar.url)
        embed.set_footer(text="The Urbex Factory | Modern Urbex Community")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(General(bot))
