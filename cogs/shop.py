import discord
from discord.ext import commands
from discord import app_commands, ui
import aiosqlite
from utils.database import DB_PATH, get_setting
from utils.logger import log_event

TICKET_TOPIC_PREFIX = "shop_ticket_owner:"

def get_ticket_owner_id(channel: discord.TextChannel) -> int | None:
    if not channel.topic or not channel.topic.startswith(TICKET_TOPIC_PREFIX):
        return None
    raw = channel.topic.replace(TICKET_TOPIC_PREFIX, "", 1).strip()
    return int(raw) if raw.isdigit() else None

def is_shop_ticket_channel(channel: discord.abc.GuildChannel) -> bool:
    return isinstance(channel, discord.TextChannel) and channel.name.startswith("shop-claim-")


def build_shop_panel_embed() -> discord.Embed:
    import json
    import os
    rewards = []
    if os.path.exists("rewards.json"):
        with open("rewards.json", "r", encoding="utf-8") as f:
            try:
                rewards = json.load(f)
            except:
                pass
    
    embed = discord.Embed(
        title="🏪 Urbex Shop",
        description="Welkom in de officiële community shop! Gebruik je verdiende coins om exclusieve rewards te claimen.",
        color=discord.Color.from_rgb(43, 45, 49)
    )

    if rewards:
        # Sort rewards by price
        rewards.sort(key=lambda x: x.get('price', 0))
        rewards_list = ""
        for item in rewards:
            name = item.get("name", "Unknown")
            price = item.get("price", 0)
            rewards_list += f"**{name}**\n└ 💰 `{price} coins`\n\n"
        
        embed.add_field(name="🎁 Beschikbare Rewards", value=rewards_list if rewards_list else "Geen items gevonden.", inline=False)
    else:
        embed.add_field(name="🎁 Beschikbare Rewards", value="Er zijn momenteel geen items beschikbaar.", inline=False)

    embed.add_field(name="❓ Hoe te claimen?", value="Kies **'Claim reward'** in het menu hieronder en selecteer het item dat je wilt hebben. De bot controleert automatisch of je genoeg coins hebt!", inline=False)
    
    embed.set_footer(text="The Urbex Factory | Gebruik /help voor meer informatie")
    return embed


async def send_shop_panel(channel: discord.abc.Messageable):
    await channel.send(embed=build_shop_panel_embed(), view=ShopPanelView())


async def create_or_get_shop_ticket(interaction: discord.Interaction) -> tuple[discord.TextChannel | None, bool]:
    panel_channel_id = await get_setting("shop_panel_channel")
    panel_channel = interaction.guild.get_channel(int(panel_channel_id)) if panel_channel_id else None
    if not isinstance(panel_channel, discord.TextChannel):
        return None, False

    category = panel_channel.category

    existing_ticket = discord.utils.get(
        interaction.guild.text_channels,
        name=f"shop-claim-{interaction.user.id}",
    )
    if existing_ticket:
        return existing_ticket, False

    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        ),
        interaction.guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True,
        ),
    }
    channel = await interaction.guild.create_text_channel(
        name=f"shop-claim-{interaction.user.id}",
        category=category,
        topic=f"{TICKET_TOPIC_PREFIX}{interaction.user.id}",
        overwrites=overwrites,
        reason=f"Shop claim ticket for {interaction.user}",
    )
    return channel, True

class ConfirmDeleteView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: ui.Button):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not is_shop_ticket_channel(channel):
            return await interaction.response.send_message("Dit commando werkt alleen in een shop ticket.", ephemeral=True)
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("Je hebt geen toegang tot deze commando.", ephemeral=True)
        await interaction.response.send_message("Ticket wordt verwijderd...", ephemeral=True)
        await channel.delete(reason=f"Deleted by {interaction.user}")

class ConfirmCloseView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="Confirm Close", style=discord.ButtonStyle.primary)
    async def confirm_close(self, interaction: discord.Interaction, button: ui.Button):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not is_shop_ticket_channel(channel):
            return await interaction.response.send_message("Dit commando werkt alleen in een shop ticket.", ephemeral=True)

        owner_id = get_ticket_owner_id(channel)
        if owner_id is None:
            return await interaction.response.send_message("Ticket eigenaar niet gevonden.", ephemeral=True)

        is_owner = interaction.user.id == owner_id
        is_staff = interaction.user.guild_permissions.manage_channels
        if not is_owner and not is_staff:
            return await interaction.response.send_message("Je hebt geen toegang tot deze commando.", ephemeral=True)

        owner_member = interaction.guild.get_member(owner_id)
        if owner_member:
            await channel.set_permissions(owner_member, view_channel=False, send_messages=False, read_message_history=False)
        await interaction.response.send_message("Ticket gesloten. De opener heeft geen toegang meer.", ephemeral=False)

class ShopTicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Close", style=discord.ButtonStyle.secondary, custom_id="shop_ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not is_shop_ticket_channel(channel):
            return await interaction.response.send_message("Dit commando werkt alleen in een shop ticket.", ephemeral=True)

        owner_id = get_ticket_owner_id(channel)
        if owner_id is None:
            return await interaction.response.send_message("Ticket eigenaar niet gevonden.", ephemeral=True)

        is_owner = interaction.user.id == owner_id
        is_staff = interaction.user.guild_permissions.manage_channels
        if not is_owner and not is_staff:
            return await interaction.response.send_message("Je hebt geen toegang tot deze commando.", ephemeral=True)

        embed = discord.Embed(
            title="Bevestig sluiten",
            description="Weet je zeker dat je dit ticket wilt sluiten? De opener verliest toegang.",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed, view=ConfirmCloseView(), ephemeral=True)

    @ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="shop_ticket_delete")
    async def delete_ticket(self, interaction: discord.Interaction, button: ui.Button):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not is_shop_ticket_channel(channel):
            return await interaction.response.send_message("Dit commando werkt alleen in een shop ticket.", ephemeral=True)
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("Je hebt geen toegang tot deze commando.", ephemeral=True)
        embed = discord.Embed(
            title="Bevestig verwijderen",
            description="Weet je zeker dat je dit ticket volledig wilt verwijderen? Dit kan niet ongedaan gemaakt worden.",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, view=ConfirmDeleteView(), ephemeral=True)

# -------------------- Shop UI Components --------------------

class RewardSelectDropdown(ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Welk reward wil je claimen?", min_values=1, max_values=1, options=options, custom_id="reward_select_dropdown")

    async def callback(self, interaction: discord.Interaction):
        reward_selected = self.values[0]
        
        # 1. Fetch price from rewards.json
        import json
        import os
        price = None
        if os.path.exists("rewards.json"):
            with open("rewards.json", "r", encoding="utf-8") as f:
                try:
                    for item in json.load(f):
                        if item.get("name") == reward_selected:
                            price = item.get("price")
                            break
                except:
                    pass
        
        if price is None:
            return await interaction.response.send_message("❌ Fout bij het laden van item data. Probeer het later opnieuw.", ephemeral=True)

        # 2. Check balance
        from utils.database import get_user_balance
        user_balance = await get_user_balance(interaction.user.id)
        
        if user_balance < price:
            embed = discord.Embed(
                title="❌ Onvoldoende Saldo",
                description=(
                    f"Je hebt niet genoeg coins voor **{reward_selected}**.\n\n"
                    f"**Prijs**: `{price} coins`\n"
                    f"**Jouw saldo**: `{user_balance} coins`\n\n"
                    f"Je hebt nog **`{price - user_balance}`** coins nodig!"
                ),
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 3. Create or get ticket
        ticket_channel, created = await create_or_get_shop_ticket(interaction)
        if not ticket_channel:
            return await interaction.response.send_message(
                "❌ Shop panel kanaal is niet goed ingesteld. Ticket kon niet gemaakt worden.",
                ephemeral=True
            )
            
        if created:
            opener_embed = discord.Embed(
                title="🎟️ Reward Claim Ticket",
                description=(
                    f"Je ticket is geopend voor het claimen van: **{reward_selected}**\n\n"
                    "Staff zal zo snel mogelijk contact met je opnemen om je verificatie en aankoop af te ronden."
                ),
                color=discord.Color.green(),
            )
            await ticket_channel.send(
                content=f"{interaction.user.mention}",
                embed=opener_embed,
                view=ShopTicketControlView(),
            )
            await interaction.response.edit_message(content=f"✅ Je shop ticket is aangemaakt: {ticket_channel.mention}", view=None, embed=None)
            
            await log_event(
                interaction.client,
                'shop',
                "Shop Claim Ticket Created",
                f"**User**: {interaction.user.mention}\n**Channel**: {ticket_channel.mention}\n**Reward**: {reward_selected}",
                color=discord.Color.blue(),
            )
        else:
            await ticket_channel.send(f"{interaction.user.mention} wil nog een reward eraan toevoegen: **{reward_selected}**")
            await interaction.response.edit_message(content=f"✅ Je hebt al een open shop ticket: {ticket_channel.mention}. Je verzoek is daaraan toegevoegd.", view=None, embed=None)

class RewardSelectView(ui.View):
    def __init__(self, options):
        super().__init__(timeout=None)
        self.add_item(RewardSelectDropdown(options))

class RewardsNavView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @ui.button(label="Claim Reward", emoji="🎟️", style=discord.ButtonStyle.success)
    async def btn_claim(self, interaction: discord.Interaction, button: ui.Button):
        import json
        import os
        options = []
        if os.path.exists("rewards.json"):
            with open("rewards.json", "r", encoding="utf-8") as f:
                try:
                    for item in json.load(f):
                        name = item.get("name", "Unknown")
                        price = item.get("price", 0)
                        if len(options) < 25:
                            options.append(discord.SelectOption(label=name[:100], value=name[:100], description=f"{price} coins"))
                except Exception:
                    pass
        if not options:
            return await interaction.response.send_message("Er zijn nog geen rewards om te claimen.", ephemeral=True)
        await interaction.response.send_message("Kies hieronder welk reward je wilt claimen:", view=RewardSelectView(options), ephemeral=True)
        
    @ui.button(label="Check je saldo", emoji="💰", style=discord.ButtonStyle.secondary)
    async def btn_balance(self, interaction: discord.Interaction, button: ui.Button):
        from utils.database import get_user_balance
        coins = await get_user_balance(interaction.user.id)
        embed = discord.Embed(
            title="💰 Saldo Check",
            description=f"Je hebt momenteel **`{coins}`** coins beschikbaar om te besteden.",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ShopDropdown(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Check je saldo", emoji="💰", value="balance", description="Bekijk je huidige hoeveelheid coins."),
            discord.SelectOption(label="Claim reward", emoji="🎟️", value="claim", description="Selecteer een item om te claimen.")
        ]
        super().__init__(placeholder="Kies een actie...", min_values=1, max_values=1, options=options, custom_id="shop_panel_dropdown")

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        
        if choice == "claim":
            import json
            import os
            options = []
            if os.path.exists("rewards.json"):
                with open("rewards.json", "r", encoding="utf-8") as f:
                    try:
                        for item in json.load(f):
                            name = item.get("name", "Unknown")
                            price = item.get("price", 0)
                            if len(options) < 25:
                                options.append(discord.SelectOption(label=name[:100], value=name[:100], description=f"{price} coins"))
                    except Exception:
                        pass
            if not options:
                return await interaction.response.send_message("Er zijn nog geen rewards om te claimen.", ephemeral=True)
            await interaction.response.send_message("Kies hieronder welk reward je wilt claimen:", view=RewardSelectView(options), ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)

        if choice == "balance":
            from utils.database import get_user_balance
            coins = await get_user_balance(interaction.user.id)
            embed = discord.Embed(
                title="💰 Saldo Check",
                description=f"Je hebt momenteel **`{coins}`** coins beschikbaar om te besteden.",
                color=discord.Color.gold()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

class ShopPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ShopDropdown())



class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="add_shop_item", description="Add an item to the shop")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def add_shop_item(
        self,
        interaction: discord.Interaction,
        name: str,
        price: int,
    ):
        import json
        import os
        from utils.logger import log_event
        
        rewards_file = "rewards.json"
        rewards = []
        if os.path.exists(rewards_file):
            with open(rewards_file, "r", encoding="utf-8") as f:
                try:
                    rewards = json.load(f)
                except Exception:
                    pass
                    
        rewards.append({"price": price, "name": name})
        rewards.sort(key=lambda x: x.get('price', 0))
        
        with open(rewards_file, "w", encoding="utf-8") as f:
            json.dump(rewards, f, indent=4)
            
        embed = discord.Embed(title="Shop Item Added", color=discord.Color.green())
        embed.description = f"Successfully added **`{name}`** to the shop for **`{price}`** coins."
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await log_event(
            interaction.client,
            'admin',
            "New Shop Item Added",
            f"**Admin**: {interaction.user.mention}\n**Item**: {name}\n**Price**: {price}",
            color=discord.Color.blue(),
        )

    @app_commands.command(name="remove_shop_item", description="Remove an item from the shop by name")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_shop_item(
        self,
        interaction: discord.Interaction,
        name: str,
    ):
        import json
        import os
        from utils.logger import log_event
        
        rewards_file = "rewards.json"
        rewards = []
        if os.path.exists(rewards_file):
            with open(rewards_file, "r", encoding="utf-8") as f:
                try:
                    rewards = json.load(f)
                except Exception:
                    pass
                    
        new_rewards = [r for r in rewards if r.get('name', '').lower() != name.lower()]
        
        if len(new_rewards) == len(rewards):
            return await interaction.response.send_message(f"Item **{name}** niet gevonden in de shop.", ephemeral=True)
            
        with open(rewards_file, "w", encoding="utf-8") as f:
            json.dump(new_rewards, f, indent=4)
            
        embed = discord.Embed(title="Shop Item Removed", color=discord.Color.red())
        embed.description = f"Successfully removed **`{name}`** from the shop."
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await log_event(
            interaction.client,
            'admin',
            "Shop Item Removed",
            f"**Admin**: {interaction.user.mention}\n**Item**: {name}",
            color=discord.Color.red(),
        )

    @app_commands.command(name="close_shop_ticket", description="Close current shop ticket")
    async def close_shop_ticket(self, interaction: discord.Interaction):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not is_shop_ticket_channel(channel):
            return await interaction.response.send_message("Gebruik dit in een shop ticketkanaal.", ephemeral=True)

        owner_id = get_ticket_owner_id(channel)
        if owner_id is None:
            return await interaction.response.send_message("Ticket eigenaar niet gevonden.", ephemeral=True)

        is_owner = interaction.user.id == owner_id
        is_staff = interaction.user.guild_permissions.manage_channels
        if not is_owner and not is_staff:
            return await interaction.response.send_message("Je hebt geen toegang tot deze commando.", ephemeral=True)

        embed = discord.Embed(
            title="Bevestig sluiten",
            description="Weet je zeker dat je dit ticket wilt sluiten? De opener verliest toegang.",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed, view=ConfirmCloseView(), ephemeral=True)

    @app_commands.command(name="delete_shop_ticket", description="Delete current shop ticket with confirmation")
    @app_commands.default_permissions(manage_channels=True)
    async def delete_shop_ticket(self, interaction: discord.Interaction):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not is_shop_ticket_channel(channel):
            return await interaction.response.send_message("Gebruik dit in een shop ticketkanaal.", ephemeral=True)
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("Je hebt geen toegang tot deze commando.", ephemeral=True)
        embed = discord.Embed(
            title="Bevestig verwijderen",
            description="Weet je zeker dat je dit ticket volledig wilt verwijderen? Dit kan niet ongedaan gemaakt worden.",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, view=ConfirmDeleteView(), ephemeral=True)


async def setup(bot):
    bot.add_view(ShopPanelView())
    bot.add_view(ShopTicketControlView())
    await bot.add_cog(Shop(bot))
