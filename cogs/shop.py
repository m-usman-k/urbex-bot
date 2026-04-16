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
    embed = discord.Embed(
        title="Urbex Shop",
        description=(
            "Klik op de knop hieronder om je claim-ticket te openen.\n"
            "Staff helpt je daar handmatig met je claim."
        ),
        color=discord.Color.green(),
    )
    embed.set_footer(text="The Urbex Factory")
    return embed


async def send_shop_panel(channel: discord.abc.Messageable):
    await channel.send(embed=build_shop_panel_embed(), view=ShopPanelView())


async def create_or_get_shop_ticket(interaction: discord.Interaction) -> tuple[discord.TextChannel | None, bool]:
    panel_channel_id = await get_setting("shop_panel_channel")
    panel_channel = interaction.guild.get_channel(int(panel_channel_id)) if panel_channel_id else None
    if not isinstance(panel_channel, discord.TextChannel):
        return None, False

    category = panel_channel.category
    if not category:
        return None, False

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


class ShopPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Open Shop", style=discord.ButtonStyle.primary, custom_id="panel_open_shop")
    async def open_shop(self, interaction: discord.Interaction, button: ui.Button):
        ticket_channel, created = await create_or_get_shop_ticket(interaction)
        if not ticket_channel:
            return await interaction.response.send_message(
                "Shop panel kanaal is niet goed ingesteld. Run `/setup_shop_panel` opnieuw in het juiste kanaal.",
                ephemeral=True,
            )
        if created:
            opener_embed = discord.Embed(
                title="Shop Ticket",
                description=(
                    "Je ticket is geopend.\n"
                    "Beschrijf hier wat je wilt claimen, staff helpt je handmatig verder."
                ),
                color=discord.Color.green(),
            )
            await ticket_channel.send(
                content=f"{interaction.user.mention}",
                embed=opener_embed,
                view=ShopTicketControlView(),
            )
            await log_event(
                interaction.client,
                'shop',
                "Shop Ticket Created",
                f"**User**: {interaction.user.mention}\n**Channel**: {ticket_channel.mention}",
                color=discord.Color.blue(),
            )
            return await interaction.response.send_message(f"Je shop ticket is aangemaakt: {ticket_channel.mention}", ephemeral=True)

        await interaction.response.send_message(f"Je hebt al een open shop ticket: {ticket_channel.mention}", ephemeral=True)


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
        description: str,
        stock: int = -1,
        is_physical: bool = False,
    ):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO shop_items (name, price, description, stock, is_physical) VALUES (?, ?, ?, ?, ?)",
                (name, price, description, stock, is_physical),
            )
            await db.commit()
        embed = discord.Embed(title="Shop Item Added", color=discord.Color.green())
        embed.description = f"Successfully added **`{name}`** to the shop for **`{price}`** coins."
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await log_event(
            interaction.client,
            'admin',
            "New Shop Item Added",
            f"**Admin**: {interaction.user.mention}\n**Item**: {name}\n**Price**: {price}\n**Stock**: {stock}",
            color=discord.Color.blue(),
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
