import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import pandas as pd
import io
import sqlite3
import sqlite3
from utils.database import DB_PATH, update_user_balance, set_setting, get_setting
from utils.logger import log_event

def create_setup_home_embed() -> discord.Embed:
    embed = discord.Embed(
        title="UrbexBot Setup Guide",
        description=(
            "Use the dropdown to open a setup topic.\n\n"
            "This guide is intended for administrators and covers full configuration of channels, "
            "submission workflows, shop workflows, rewards, and validation."
        ),
        color=discord.Color.blue(),
    )
    embed.set_footer(text="UrbexBot Administration")
    return embed

class SetupGuideDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Home", description="Back to the setup landing page", emoji="🏠"),
            discord.SelectOption(label="Logging & Automation", description="Setup automated admin categories and log channels", emoji="📠"),
            discord.SelectOption(label="Core Channels", description="Configure all required channels", emoji="🧭"),
            discord.SelectOption(label="Reviews System", description="Configure native review form flow", emoji="📝"),
            discord.SelectOption(label="Updates System", description="Configure location update flow", emoji="📍"),
            discord.SelectOption(label="Shop System", description="Configure shop panel, items, and claim threads", emoji="🛒"),
            discord.SelectOption(label="Rewards and Economy", description="Configure coin rewards and economy controls", emoji="💰"),
            discord.SelectOption(label="Validation Checklist", description="End-to-end test checklist after setup", emoji="✅"),
        ]
        super().__init__(placeholder="Choose a setup topic...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        if selected == "Home":
            return await interaction.response.edit_message(embed=create_setup_home_embed(), view=self.view)

        if selected == "Logging & Automation":
            embed = discord.Embed(title="Setup: Logging & Automation", color=discord.Color.brand_red())
            embed.description = "The bot can automatically generate an Admin Category and wire up logging routing for you."
            embed.add_field(
                name="Automated Setup",
                value=(
                    "Usage: `/setup_logs`\n"
                    "This command will automatically create an `Urbex Admin` category hidden from members.\n"
                    "It parses and generates specific text channels (`submissions-log`, `shop-log`, `economy-log`, etc.).\n"
                    "It instantly bounds those channels into the bot's system variables securely."
                ),
                inline=False
            )
            embed.add_field(
                name="Manual Setup",
                value="If you prefer manual setup, you can use `/set_log_channel` and bind variables one-by-one.",
                inline=False
            )
            return await interaction.response.edit_message(embed=embed, view=self.view)

        if selected == "Core Channels":
            embed = discord.Embed(title="Setup: Core Channels", color=discord.Color.blue())
            embed.description = (
                "Configure channels first. The full system depends on these settings."
            )
            embed.add_field(
                name="Required Channel Keys",
                value=(
                    "`commands_channel`: Where users run economy/general commands.\n"
                    "`approval_channel`: Where staff approves/rejects submissions.\n"
                    "`reviews_channel`: Where approved reviews are posted.\n"
                    "`updates_channel`: Where approved location updates are posted.\n"
                    "`review_panel_channel`: Native form intake for reviews.\n"
                    "`update_panel_channel`: Native form intake for updates.\n"
                    "`shop_panel_channel`: Defines where the shop panel lives and which category tickets use."
                ),
                inline=False,
            )
            embed.add_field(
                name="How to Configure",
                value=(
                    "Use `/set_commands_channel` for command usage channel.\n"
                    "Use `/set_approval_channel` for staff review queue.\n"
                    "Use `/set_log_channel` for custom logging routing.\n"
                    "Use `/setup_review_public` and `/setup_update_public` for the high-fidelity panels.\n"
                    "Use `/setup_shop_panel` in the channel whose category should receive shop tickets."
                ),
                inline=False,
            )
            return await interaction.response.edit_message(embed=embed, view=self.view)

        if selected == "Reviews System":
            embed = discord.Embed(title="Setup: Reviews System", color=discord.Color.blue())
            embed.description = "The review system uses a high-fidelity native wizard for data collection."
            embed.add_field(
                name="Premium Review Wizard",
                value=(
                    "1. Go to your public reviews channel.\n"
                    "2. Run `/setup_review_public channel:#channel-name`.\n"
                    "**Result**: The bot locks the channel (read-only), posts a sticky button, and opens the high-fidelity Review Modal."
                ),
                inline=False,
            )
            embed.add_field(
                name="Approvals",
                value=(
                    "3. Run `/setup_review_admin channel:#admin-channel` to set where staff review the queue."
                ),
                inline=False,
            )
            return await interaction.response.edit_message(embed=embed, view=self.view)

        if selected == "Updates System":
            embed = discord.Embed(title="Setup: Updates System", color=discord.Color.orange())
            embed.description = "Location updates are now handled via a high-fidelity native wizard matching the premium review flow."
            embed.add_field(
                name="Premium Update Wizard",
                value=(
                    "1. Go to your public updates channel.\n"
                    "2. Run `/setup_update_public channel:#channel-name`.\n"
                    "**Result**: The bot locks the channel (read-only), posts a sticky panel, and opens the high-fidelity Update Modal."
                ),
                inline=False,
                )
            embed.add_field(
                name="Approvals",
                value=(
                    "3. Run `/setup_update_admin channel:#admin-channel` to set where staff review the queue."
                ),
                inline=False,
            )
            return await interaction.response.edit_message(embed=embed, view=self.view)

        if selected == "Shop System":
            embed = discord.Embed(title="Setup: Shop System", color=discord.Color.blue())
            embed.description = "This sets up shop-window usage and ticket-style claim handling."
            embed.add_field(
                name="Step 1: Post Shop Panel",
                value="Run `/setup_shop_panel channel:#shop-window`.",
                inline=False,
            )
            embed.add_field(
                name="Step 2: Add Items",
                value=(
                    "Use `/add_shop_item` to add rewards.\n"
                    "Example: `/add_shop_item name:\"Reward\" price:100 description:\"Details\" stock:5 is_physical:false`."
                ),
                inline=False,
            )
            embed.add_field(
                name="Step 3: User Claim Flow",
                value=(
                    "User clicks `Open Shop` button in panel.\n"
                    "Bot creates/reuses a private claim ticket channel.\n"
                    "User and staff handle the claim manually in that ticket."
                ),
                inline=False,
            )
            embed.add_field(
                name="Step 4: Staff Handling",
                value=(
                    "Claim ticket channels are created in the category of the configured `shop_panel_channel`.\n"
                    "Staff and user handle claim manually inside the ticket channel.\n"
                    "No automatic fulfillment is performed.\n"
                    "New items appear automatically when users re-open the shop panel."
                ),
                inline=False,
            )
            return await interaction.response.edit_message(embed=embed, view=self.view)

        if selected == "Rewards and Economy":
            embed = discord.Embed(title="Setup: Rewards and Economy", color=discord.Color.blue())
            embed.description = "Configure all reward amounts and manual admin controls."
            embed.add_field(
                name="Reward Configuration",
                value=(
                    "Use `/set_reward` to set:\n"
                    "`reward_daily`, `reward_review`, `reward_update`, `reward_boost_initial`, `reward_boost_monthly`."
                ),
                inline=False,
            )
            embed.add_field(
                name="Booster Rewards",
                value=(
                    "Initial booster reward is granted when boost starts.\n"
                    "Monthly booster reward is granted on recurring schedule."
                ),
                inline=False,
            )
            embed.add_field(
                name="Admin Economy Controls",
                value="Use `/add_coins`, `/remove_coins`, `/set_coins`, `/user_info`, `/export_data`.",
                inline=False,
            )
            return await interaction.response.edit_message(embed=embed, view=self.view)

        embed = discord.Embed(title="Setup: Validation Checklist", color=discord.Color.blue())
        embed.description = (
            "Run this checklist after setup is complete."
        )
        embed.add_field(
            name="Checklist",
            value=(
                "1. `/help` shows admin tools only to admins.\n"
                "2. Review and update panel buttons open in their own channels.\n"
                "3. Review and update posts appear in configured separate channels.\n"
                "4. Approval buttons in `approval_channel` grant coins correctly.\n"
                "5. Shop panel opens and displays latest items.\n"
                "6. Shop claim creates ticket channel in configured category.\n"
                "7. `/daily` cooldown and `/history member:@user` work as expected."
            ),
            inline=False,
        )
        await interaction.response.edit_message(embed=embed, view=self.view)

class SetupGuideView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(SetupGuideDropdown())

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="add_coins", description="Add coins to a user's balance")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def add_coins(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Manual addition"):
        if amount <= 0:
            return await interaction.response.send_message(embed=discord.Embed(description="Amount must be greater than 0.", color=discord.Color.red()), ephemeral=True)
        
        new_balance = await update_user_balance(member.id, amount, reason)
        embed = discord.Embed(title="Coins Added", color=discord.Color.green())
        embed.description = f"Successfully added **`{amount}`** coins to {member.mention}.\nNew balance: **`{new_balance}`**"
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Log the action
        await log_event(self.bot, 'economy', "Coins Added", 
                        f"**Admin**: {interaction.user.mention}\n**Recipient**: {member.mention}\n**Amount**: {amount}\n**Reason**: {reason}",
                        color=discord.Color.green())

    @app_commands.command(name="remove_coins", description="Remove coins from a user's balance")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_coins(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Manual removal"):
        if amount <= 0:
            return await interaction.response.send_message(embed=discord.Embed(description="Amount must be greater than 0.", color=discord.Color.red()), ephemeral=True)
        
        new_balance = await update_user_balance(member.id, -amount, reason)
        embed = discord.Embed(title="Coins Removed", color=discord.Color.red())
        embed.description = f"Successfully removed **`{amount}`** coins from {member.mention}.\nNew balance: **`{new_balance}`**"
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Log the action
        await log_event(self.bot, 'economy', "Coins Removed", 
                        f"**Admin**: {interaction.user.mention}\n**User**: {member.mention}\n**Amount**: {amount}\n**Reason**: {reason}",
                        color=discord.Color.red())

    @app_commands.command(name="set_coins", description="Set a user's balance to a specific amount")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_coins(self, interaction: discord.Interaction, member: discord.Member, balance: int):
        if balance < 0:
             return await interaction.response.send_message(embed=discord.Embed(description="Balance cannot be negative.", color=discord.Color.red()), ephemeral=True)
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance, member.id))
            await db.execute("INSERT INTO transactions (user_id, amount, type, reason) VALUES (?, ?, ?, ?)", (member.id, balance, 'admin', "Manual set"))
            await db.commit()
            
        embed = discord.Embed(title="Balance Override", color=discord.Color.orange())
        embed.description = f"Set {member.mention}'s balance to **`{balance}`** coins."
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Log the action
        await log_event(self.bot, 'economy', "Balance Override", 
                        f"**Admin**: {interaction.user.mention}\n**User**: {member.mention}\n**New Balance**: {balance}",
                        color=discord.Color.orange())

    @app_commands.command(name="user_info", description="View a user's economy details")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def user_info(self, interaction: discord.Interaction, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT balance, level, xp, total_earned FROM users WHERE user_id = ?", (member.id,)) as cursor:
                row = await cursor.fetchone()
        
        if not row:
            return await interaction.response.send_message("User not found in database.", ephemeral=True)

        balance, level, xp, total_earned = row
        embed = discord.Embed(title=f"User Info: {member.display_name}", color=discord.Color.blue())
        embed.add_field(name="Balance", value=f"{balance} coins", inline=True)
        embed.add_field(name="Level", value=f"{level}", inline=True)
        embed.add_field(name="XP", value=f"{xp}", inline=True)
        embed.add_field(name="Total Earned", value=f"{total_earned}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="export_data", description="Export all user data to an Excel file")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def export_data(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # We use a synchronous connection for pandas as it's easier to handle for a bulk export
            # and we are running inside a defered interaction
            conn = sqlite3.connect(DB_PATH)
            
            # Create a buffer for the Excel file
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Local helper to add usernames and fix ID formatting
                def format_ids_and_names(df):
                    if 'user_id' in df.columns:
                        # Convert IDs to string first to prevent scientific notation
                        df['user_id'] = df['user_id'].apply(lambda x: str(x))
                        
                        # Add Username column if possible
                        usernames = []
                        for uid_str in df['user_id']:
                            try:
                                uid = int(uid_str)
                                member = interaction.guild.get_member(uid)
                                if member:
                                    usernames.append(str(member))
                                else:
                                    user = self.bot.get_user(uid)
                                    usernames.append(str(user) if user else "Unknown User")
                            except:
                                usernames.append("Unknown User")
                        
                        df.insert(df.columns.get_loc('user_id') + 1, 'Username', usernames)
                    return df

                # 1. Users Sheet
                df_users = pd.read_sql_query("SELECT * FROM users", conn)
                df_users = format_ids_and_names(df_users)
                df_users.to_excel(writer, sheet_name='User Economy', index=False)
                
                # 2. Submissions Sheet (Structured)
                df_subs = pd.read_sql_query("SELECT * FROM submissions", conn)
                df_subs = format_ids_and_names(df_subs)
                # Cleanup headers for Excel
                df_subs.columns = [c.replace('_', ' ').capitalize() for c in df_subs.columns]
                df_subs.to_excel(writer, sheet_name='All Submissions', index=False)
                
                # 3. Shop & Inventory
                df_items = pd.read_sql_query("SELECT * FROM shop_items", conn)
                df_items.to_excel(writer, sheet_name='Shop Items', index=False)
                
                df_inventory = pd.read_sql_query("SELECT * FROM inventory", conn)
                df_inventory = format_ids_and_names(df_inventory)
                df_inventory.to_excel(writer, sheet_name='User Inventory', index=False)
                
                # 4. Transactions
                df_tx = pd.read_sql_query("SELECT * FROM transactions", conn)
                df_tx = format_ids_and_names(df_tx)
                df_tx.to_excel(writer, sheet_name='Transaction History', index=False)
            
            conn.close()
            output.seek(0)
            
            # Create the discord file
            file = discord.File(fp=output, filename="urbex_factory_full_export.xlsx")
            
            embed = discord.Embed(title="Data Export Complete", color=discord.Color.blue())
            embed.description = "The requested database snapshot has been generated and is ready for download."
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(embed=discord.Embed(description=f"An error occurred while exporting data: {str(e)}", color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="setup_logs", description="Automatically setup admin category and log channels")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_logs(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        
        try:
            # 1. Create Category
            category = discord.utils.get(guild.categories, name="🛡️ Urbex Admin")
            if not category:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
                }
                category = await guild.create_category("🛡️ Urbex Admin", overwrites=overwrites)
            
            # 2. Create Channels and Map them to settings
            channels_to_create = {
                "log_submissions": "📝-submissions-log",
                "log_economy": "💰-economy-log",
                "log_shop": "🛒-shop-log",
                "log_admin": "🤖-bot-logs"
            }
            
            created_channels = []
            for setting_key, channel_name in channels_to_create.items():
                channel = discord.utils.get(category.text_channels, name=channel_name)
                if not channel:
                    channel = await guild.create_text_channel(channel_name, category=category)
                
                await set_setting(setting_key, channel.id)
                created_channels.append(channel.mention)
            
            embed = discord.Embed(title="Logging Setup Complete", color=discord.Color.green())
            embed.description = f"Channels created/configured in {category.mention}:\n" + "\n".join(created_channels)
            
            # Use 'log_admin' as a default for approvals if not set
            if not await get_setting("approval_channel"):
                await set_setting("approval_channel", category.text_channels[3].id) # robot logs channel
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            await log_event(self.bot, 'admin', "Manual Setup Triggered", f"Admin logging setup was initialized by {interaction.user.mention}.")
            
        except Exception as e:
            await interaction.followup.send(embed=discord.Embed(description=f"Failed to setup logs: {str(e)}", color=discord.Color.red()), ephemeral=True)

    @app_commands.command(name="set_log_channel", description="Manually set a logging channel for a specific type")
    @app_commands.describe(log_type="The type of logs for this channel", channel="The channel to send logs to")
    @app_commands.choices(log_type=[
        app_commands.Choice(name="Submissions", value="log_submissions"),
        app_commands.Choice(name="Economy", value="log_economy"),
        app_commands.Choice(name="Shop", value="log_shop"),
        app_commands.Choice(name="Admin", value="log_admin"),
        app_commands.Choice(name="Approvals", value="approval_channel"),
        app_commands.Choice(name="Commands Channel", value="commands_channel"),
        app_commands.Choice(name="Reviews Channel", value="reviews_channel"),
        app_commands.Choice(name="Updates Channel", value="updates_channel")
    ])
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, log_type: str, channel: discord.TextChannel):
        await set_setting(log_type, channel.id)
        embed = discord.Embed(title="Log Channel Updated", color=discord.Color.blue())
        embed.description = f"Set **`{log_type.replace('_', ' ').capitalize()}`** logs to {channel.mention}."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await log_event(self.bot, 'admin', "Log Channel Updated", f"{interaction.user.mention} updated the {log_type} channel to {channel.mention}.")

    @app_commands.command(name="set_approval_channel", description="Set the channel where submission approval requests are sent")
    @app_commands.describe(channel="The channel for staff to review submissions")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_approval_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await set_setting("approval_channel", channel.id)
        embed = discord.Embed(title="Approval Channel Updated", color=discord.Color.blue())
        embed.description = f"Set submission approvals to {channel.mention}."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await log_event(self.bot, 'admin', "Approval Channel Updated", f"{interaction.user.mention} updated the approval channel to {channel.mention}.")

    @app_commands.command(name="set_reward", description="Configure coin rewards for various actions")
    @app_commands.choices(action=[
        app_commands.Choice(name="Daily Login", value="reward_daily"),
        app_commands.Choice(name="Review Submission", value="reward_review"),
        app_commands.Choice(name="Update Submission", value="reward_update"),
        app_commands.Choice(name="Initial Boost", value="reward_boost_initial"),
        app_commands.Choice(name="Monthly Boost", value="reward_boost_monthly")
    ])
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_reward(self, interaction: discord.Interaction, action: str, amount: int):
        if amount < 0:
            return await interaction.response.send_message("Amount cannot be negative.", ephemeral=True)
            
        await set_setting(action, amount)
        embed = discord.Embed(title="Reward Configuration Updated", color=discord.Color.green())
        embed.description = f"Set **{action.replace('reward_', '').replace('_', ' ').title()}** reward to **`{amount}`** coins."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await log_event(self.bot, 'admin', "Reward Config Updated", f"{interaction.user.mention} updated the {action} reward to {amount}.")

    @app_commands.command(name="setup_review_public", description="Automated setup of a read-only public review channel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_review_public(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Sets channel permissions to read-only for users and posts sticky panel."""
        await interaction.response.defer(ephemeral=True)
        
        # 1. Update Permissions
        overwrites = channel.overwrites
        overwrites[interaction.guild.default_role] = discord.PermissionOverwrite(send_messages=False, read_messages=True, add_reactions=True)
        overwrites[interaction.guild.me] = discord.PermissionOverwrite(send_messages=True, manage_messages=True, read_messages=True, embed_links=True, attach_files=True)
        
        try:
            await channel.edit(overwrites=overwrites)
            
            # 2. Configure Settings: panel channel (where sticky lives) and
            # the reviews_channel (where approved reviews are posted) are THE SAME
            # for reviews — users submit via button and approved posts appear here.
            await set_setting("review_panel_channel", channel.id)
            await set_setting("reviews_channel", channel.id)
            
            # 3. Send Initial Sticky
            from cogs.forms import refresh_review_sticky
            await refresh_review_sticky(interaction.guild)
            
            await interaction.followup.send(f"✅ {channel.mention} has been configured as your **Public Reviews** channel.\n- Permissions locked (read-only for users).\n- Sticky submit panel posted.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to configure channel: {str(e)}", ephemeral=True)

    @app_commands.command(name="setup_review_admin", description="Set the private admin channel where review submissions are queued for approval")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_review_admin(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await set_setting("review_approval_channel", channel.id)
        embed = discord.Embed(title="Review Admin Channel Set", color=discord.Color.blue())
        embed.description = f"New **review** submissions will now be queued for approval in {channel.mention}."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await log_event(self.bot, 'admin', "Review Admin Channel Set", f"{interaction.user.mention} set the review approval channel to {channel.mention}.")

    @app_commands.command(name="setup_update_public", description="Automated setup of a read-only public updates channel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_update_public(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Sets channel permissions to read-only for users and posts sticky panel."""
        await interaction.response.defer(ephemeral=True)
        
        # 1. Update Permissions
        overwrites = channel.overwrites
        overwrites[interaction.guild.default_role] = discord.PermissionOverwrite(send_messages=False, read_messages=True, add_reactions=True)
        overwrites[interaction.guild.me] = discord.PermissionOverwrite(send_messages=True, manage_messages=True, read_messages=True, embed_links=True, attach_files=True)
        
        try:
            await channel.edit(overwrites=overwrites)
            
            # 2. Configure Settings: update panel (where sticky is) and
            # updates_channel (where approved updates are posted) are the same channel.
            await set_setting("update_panel_channel", channel.id)
            await set_setting("updates_channel", channel.id)
            
            # 3. Send Initial Sticky
            from cogs.forms import refresh_update_sticky
            await refresh_update_sticky(interaction.guild)
            
            await interaction.followup.send(f"✅ {channel.mention} has been configured as your **Public Updates** channel.\n- Permissions locked (read-only for users).\n- Sticky submit panel posted.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to configure channel: {str(e)}", ephemeral=True)

    @app_commands.command(name="setup_update_admin", description="Set the private admin channel where location update submissions are queued for approval")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_update_admin(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await set_setting("update_approval_channel", channel.id)
        embed = discord.Embed(title="Update Admin Channel Set", color=discord.Color.orange())
        embed.description = f"New **location update** submissions will now be queued for approval in {channel.mention}."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await log_event(self.bot, 'admin', "Update Admin Channel Set", f"{interaction.user.mention} set the update approval channel to {channel.mention}.")

    @app_commands.command(name="set_commands_channel", description="Set the channel where users are allowed to use economy/general commands")
    @app_commands.describe(channel="The channel for user commands")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_commands_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await set_setting("commands_channel", channel.id)
        embed = discord.Embed(title="Commands Channel Updated", color=discord.Color.blue())
        embed.description = f"Users must now use commands in {channel.mention}."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await log_event(self.bot, 'admin', "Commands Channel Updated", f"{interaction.user.mention} updated the commands channel to {channel.mention}.")

    @app_commands.command(name="setup_shop_panel", description="Send a persistent shop interface to a channel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_shop_panel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=True)
        target_channel = channel or interaction.channel
        await set_setting("shop_panel_channel", target_channel.id)
        from cogs.shop import send_shop_panel
        await send_shop_panel(target_channel)
        await interaction.followup.send(f"Shop panel sent to {target_channel.mention}!", ephemeral=True)

    @app_commands.command(name="bot_setup_guide", description="Show complete admin setup and operation guide")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_guide(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=create_setup_home_embed(),
            view=SetupGuideView(),
            ephemeral=True,
        )

async def setup(bot):
    await bot.add_cog(Admin(bot))
