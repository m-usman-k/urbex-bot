import discord
from discord import ui, app_commands
from discord.ext import commands
import aiosqlite
from utils.database import DB_PATH, get_setting, update_user_balance, get_submission, set_setting
from utils.logger import log_event

async def prepare_grid(attachments):
    """
    Returns a list of discord.MediaGalleryItem for use in a MediaGallery.
    Uses native MediaGallery support in discord.py 2.7.1+.
    """
    items = []
    files_to_send = []
    image_count = 0
    
    print(f"DEBUG: Preparing native MediaGallery for {len(attachments)} attachments.")
    
    for a in attachments:
        name = getattr(a, 'filename', 'image.png')
        ext = name.split('.')[-1] if '.' in name else 'png'
        if ext.lower() in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
            clean_name = f"image_{image_count}.{ext.lower()}"
            f = await a.to_file(filename=clean_name)
            files_to_send.append(f)
            # Wrap file in MediaGalleryItem
            items.append(
                discord.MediaGalleryItem(f)
            )
            image_count += 1
            
    return items, files_to_send

# -------------------- Approval Logic --------------------

class SubmissionApprovalView(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        
        btn_app = ui.Button(label="Approve", style=discord.ButtonStyle.success, custom_id="approve_sub")
        btn_app.callback = self.approve_callback
        
        btn_rej = ui.Button(label="Reject", style=discord.ButtonStyle.danger, custom_id="reject_sub")
        btn_rej.callback = self.reject_callback
        
        self.action_row = ui.ActionRow(btn_app, btn_rej)
        self.add_item(self.action_row)

    async def get_context(self, interaction: discord.Interaction):
        """Helper to get submission context from the text display."""
        try:
            # The sub ID is in the TextDisplay content
            content = ""
            for item in interaction.message.components:
                # Traverse LayoutView components
                if item.type == discord.ComponentType.container:
                    for child in item.children:
                        if child.type == discord.ComponentType.text_display:
                            content = child.content
                            break
            
            # Use regex or simple split to find ID
            import re
            match = re.search(r"Submission ID:\*\* (\d+)", content)
            if not match:
                raise ValueError("ID not found")
            sub_id = int(match.group(1))
        except Exception as e:
            print(f"DEBUG: Context error: {e}")
            await interaction.response.send_message("❌ Kan context niet vinden. Dit bericht is waarschijnlijk te oud.", ephemeral=True)
            return None
        
        from utils.database import get_submission
        sub = await get_submission(sub_id)
        if not sub:
            await interaction.response.send_message("❌ Inzending niet gevonden in de database.", ephemeral=True)
            return None
        return sub

    async def approve_callback(self, interaction: discord.Interaction):
        sub = await self.get_context(interaction)
        if not sub:
            return
            
        await interaction.response.defer()

        user_id = sub['user_id']
        sub_type = sub['type']
        location_id = sub['location_id']

        import os
        # Get the right reward amount based on current settings
        if sub_type == 'review':
            reward_amt = int(os.getenv('COINS_REVIEW', 25))
        else:
            reward_amt = int(os.getenv('COINS_UPDATE', 5))

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE submissions SET status = 'approved' WHERE submission_id = ?",
                (sub['submission_id'],)
            )
            await db.commit()

        new_balance = await update_user_balance(
            user_id, reward_amt,
            f"Approved {sub_type} for {location_id}"
        )

        user = interaction.guild.get_member(user_id)

        # Post approved review publicly
        if sub_type == 'review':
            review_channel_id = await get_setting('review_panel_channel')
            review_channel = interaction.guild.get_channel(int(review_channel_id)) if review_channel_id else None
            if isinstance(review_channel, discord.TextChannel):
                mention = user.mention if user else f"<@{user_id}>"
                
                # Reconstruct values directly from database record to avoid duplicate labels
                loc_val = sub['location_id']
                # Re-format accessibility and quality with stars
                acc_val = '⭐' * int(sub['accessibility'] or 5) + f" ({sub['accessibility']}/5)"
                qual_val = '⭐' * int(sub['quality'] or 5) + f" ({sub['quality']}/5)"
                detail_val = sub['content'] or "Geen details."

                # Vertical Stacked Text
                pub_content = (
                    f"👤 **Ingediend door:** {mention}\n\n"
                    f"**Vul hier de locatie nummer of naam in**\n{loc_val}\n\n"
                    f"**Toegankelijkheid**\n{acc_val}\n\n"
                    f"**Kwaliteit van de locatie**\n{qual_val}\n\n"
                    f"**Datum van bezoek + Toelichting**\n{detail_val}\n\n"
                    f"**Upload hieronder je foto('s)**"
                )

                grid_url = "https://theurbexfactory.com"

                # Safely extract the existing MediaGallery directly from the Admin layout view
                # Natively bypasses having to re-upload files or read attachments
                gallery_cmp = None
                admin_view = ui.LayoutView.from_message(interaction.message)
                for item in admin_view.children:
                    if item.type == discord.ComponentType.container:
                        for child in getattr(item, 'children', []):
                            if child.type == discord.ComponentType.media_gallery:
                                gallery_cmp = child
                                break
                
                # Public Unified UI Construction
                pub_view = ui.LayoutView(timeout=None)
                text_disp = ui.TextDisplay(content=pub_content)
                
                if gallery_cmp:
                    container = ui.Container(text_disp, gallery_cmp, accent_colour=discord.Color.blue())
                else:
                    container = ui.Container(text_disp, accent_colour=discord.Color.blue())
                    
                pub_view.add_item(container)

                print(f"DEBUG: Approving review. Sending unified Ui Container.")
                posted = await review_channel.send(view=pub_view)
                
                await refresh_review_sticky(interaction.guild)

                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "UPDATE submissions SET submission_message_link = ? WHERE submission_id = ?",
                        (posted.jump_url, sub['submission_id']),
                    )
                    await db.commit()
        
        # Post approved update publicly
        elif sub_type == 'update':
            update_channel_id = await get_setting('update_panel_channel')
            update_channel = interaction.guild.get_channel(int(update_channel_id)) if update_channel_id else None
            
            if isinstance(update_channel, discord.TextChannel):
                mention = user.mention if user else f"<@{user_id}>"
                
                # Format update content
                extra_info = sub['coordinates'] or "Geen"
                map_val = sub['map_category'] or "Niet opgegeven"
                update_type = sub['content'] or "Onbekend"
                
                pub_content = (
                    f"👤 **Update door:** {mention}\n\n"
                    f"**Locatie:** {location_id}\n"
                    f"**Map:** {map_val}\n\n"
                    f"**{update_type}**\n"
                    f"**Extra info:** {extra_info}\n\n"
                    f"**Foto's hieronder**"
                )

                # Extracts the existing MediaGallery directly from the Admin layout view
                gallery_cmp = None
                admin_view = ui.LayoutView.from_message(interaction.message)
                for item in admin_view.children:
                    if item.type == discord.ComponentType.container:
                        for child in getattr(item, 'children', []):
                            if child.type == discord.ComponentType.media_gallery:
                                gallery_cmp = child
                                break
                
                pub_view = ui.LayoutView(timeout=None)
                text_disp = ui.TextDisplay(content=pub_content)
                
                if gallery_cmp:
                    container = ui.Container(text_disp, gallery_cmp, accent_colour=discord.Color.orange())
                else:
                    container = ui.Container(text_disp, accent_colour=discord.Color.orange())
                    
                pub_view.add_item(container)

                posted = await update_channel.send(view=pub_view)
                await refresh_update_sticky(interaction.guild)

                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "UPDATE submissions SET submission_message_link = ? WHERE submission_id = ?",
                        (posted.jump_url, sub['submission_id']),
                    )
                    await db.commit()

        # Update the button message in-place natively
        # Use from_message to perfectly preserve dynamically added containers
        view = ui.LayoutView.from_message(interaction.message)
        for item in view.children:
            if item.type == discord.ComponentType.action_row:
                for child in getattr(item, 'children', []):
                    if hasattr(child, 'disabled'):
                        child.disabled = True
            elif hasattr(item, 'disabled'):
                item.disabled = True
        
        status_disp = ui.TextDisplay(content=f"\n✅ **Goedgekeurd door:** {interaction.user.mention}")
        view.add_item(status_disp)
        
        await interaction.followup.edit_message(interaction.message.id, view=view)

        # Notify User
        if user:
            try:
                msg = (
                    f"✅ Je {sub_type} voor **{location_id}** is goedgekeurd!\n"
                    f"Je hebt **{reward_amt} coins** ontvangen.\n"
                    f"Nieuw saldo: **{new_balance}** coins."
                )
                await user.send(msg)
            except:
                pass

    async def reject_callback(self, interaction: discord.Interaction):
        sub = await self.get_context(interaction)
        if not sub:
            return
        
        # Open the modal to get a reason
        await interaction.response.send_modal(RejectionModal(sub))

# -------------------- Rejection Reason Modal --------------------

class RejectionModal(ui.Modal, title="Reden van afwijzing"):
    reason = ui.TextInput(
        label="Geef een reden op",
        style=discord.TextStyle.paragraph,
        placeholder="Bijv. Foto's zijn onduidelijk, locatie bestaat al, etc.",
        required=True,
        max_length=500
    )

    def __init__(self, sub):
        super().__init__()
        self.sub = sub

    async def on_submit(self, interaction: discord.Interaction):
        # We don't defer here, we edit_message cleanly at the end to fulfill the modal natively.
        
        sub_id = self.sub['submission_id']
        sub_type = self.sub['type']
        user_id = self.sub['user_id']
        loc_id = self.sub['location_id']
        reason_text = self.reason.value

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE submissions SET status = 'rejected' WHERE submission_id = ?",
                (sub_id,)
            )
            await db.commit()

        # Update the button message natively using from_message and native edit_message
        view = ui.LayoutView.from_message(interaction.message)
        for item in view.children:
            if item.type == discord.ComponentType.action_row:
                for child in getattr(item, 'children', []):
                    if hasattr(child, 'disabled'):
                        child.disabled = True
            elif hasattr(item, 'disabled'):
                item.disabled = True
        
        status_disp = ui.TextDisplay(content=f"\n❌ **Afgewezen door:** {interaction.user.mention}\n**Reden:** {reason_text}")
        view.add_item(status_disp)
        
        await interaction.response.edit_message(view=view)

        # Notify User
        user = interaction.guild.get_member(user_id)
        if user:
            try:
                msg = (
                    f"❌ Je {sub_type} voor **{loc_id}** is afgewezen.\n"
                    f"**Reden**: {reason_text}\n"
                    f"Je kunt een nieuwe inzending doen als je de bovenstaande punten hebt aangepast!"
                )
                await user.send(msg)
            except:
                pass

        # Log
        await log_event(
            interaction.client, 'submissions', "Submission Rejected",
            f"**Admin**: {interaction.user.mention}\n**Type**: {sub_type}\n**Locatie**: {loc_id}\n**Reden**: {reason_text}",
            color=discord.Color.red()
        )

# -------------------- Native Review Modal (discord.py 2.7+) --------------------

class ReviewModal(ui.Modal, title="Laat een review achter"):
    def __init__(self):
        super().__init__()
        
        # Wrapped in Label (Type 18) for native UI with Dots/Stars
        self.loc_input = ui.TextInput(placeholder="Bijv. \"#00001\" en/of \"Ancient Disco [BEL]\"", min_length=2, required=True)
        self.add_item(ui.Label(
            text="Vul hier de locatie nummer of naam in", 
            description="Zorg ervoor dat je het juiste van de kaart gebruikt, zodat mede urbexers deze ook kunnen vinden!",
            component=self.loc_input
        ))

        self.acc_radio = ui.RadioGroup(
            options=[
                discord.RadioGroupOption(label="⭐★★★★", value="1"),
                discord.RadioGroupOption(label="⭐⭐★★★", value="2"),
                discord.RadioGroupOption(label="⭐⭐⭐★★", value="3"),
                discord.RadioGroupOption(label="⭐⭐⭐⭐★", value="4"),
                discord.RadioGroupOption(label="⭐⭐⭐⭐⭐", value="5"),
            ],
            required=True
        )
        self.add_item(ui.Label(
            text="Toegankelijkheid", 
            description="Geef aan hoe toegankelijk de locatie is (1⭐ = slecht toegankelijk, 5⭐ = goed toegankelijk)",
            component=self.acc_radio
        ))

        self.qual_radio = ui.RadioGroup(
            options=[
                discord.RadioGroupOption(label="⭐★★★★", value="1"),
                discord.RadioGroupOption(label="⭐⭐★★★", value="2"),
                discord.RadioGroupOption(label="⭐⭐⭐★★", value="3"),
                discord.RadioGroupOption(label="⭐⭐⭐⭐★", value="4"),
                discord.RadioGroupOption(label="⭐⭐⭐⭐⭐", value="5"),
            ],
            required=True
        )
        self.add_item(ui.Label(
            text="Kwaliteit van de locatie", 
            description="Laat weten hoe goed je de locatie vond (1⭐ = slecht, 5⭐ = goed)",
            component=self.qual_radio
        ))

        self.details_input = ui.TextInput(style=discord.TextStyle.paragraph, placeholder="Dag-Maand-Jaar + toelichting", required=False)
        self.add_item(ui.Label(
            text="Datum van bezoek + Toelichting", 
            description="Vertel wat meer over je review en laat de mede urbexers weten wanneer je deze locatie hebt bezocht.",
            component=self.details_input
        ))

        self.photo_upload = ui.FileUpload(min_values=1, max_values=10, required=True)
        self.add_item(ui.Label(
            text="Upload hieronder je foto('s)", 
            description="Laat zien hoe de locatie eruit ziet, zodat mede urbexers weten wat ze te wachten staat!",
            component=self.photo_upload
        ))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        loc      = self.loc_input.value
        acc_val  = int(self.acc_radio.value)
        qual_val = int(self.qual_radio.value)
        detail   = self.details_input.value or "Geen toelichting."
        files    = self.photo_upload.values  # list of discord.Attachment

        # Save to DB
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                '''INSERT INTO submissions (user_id, type, status, location_id, location_name, accessibility, quality, content)
                   VALUES (?, 'review', 'pending', ?, ?, ?, ?, ?)''',
                (interaction.user.id, loc, loc, acc_val, qual_val, detail)
            )
            sub_id = cursor.lastrowid
            await db.commit()

        # Admin channel (reviews use their own dedicated key)
        admin_ch_id = await get_setting("review_approval_channel")
        admin_ch = interaction.guild.get_channel(int(admin_ch_id)) if admin_ch_id else None

        if admin_ch:
            desc = (
                f"**Vul hier de locatie nummer of naam in**\n{loc}\n\n"
                f"**Toegankelijkheid**\n{'⭐' * acc_val} ({acc_val}/5)\n\n"
                f"**Kwaliteit van de locatie**\n{'⭐' * qual_val} ({qual_val}/5)\n\n"
                f"**Datum van bezoek + Toelichting**\n{detail}\n\n"
                f"**Upload hieronder je foto('s)**"
            )

            # The single LayoutView correctly manages persistent customIDs
            view = SubmissionApprovalView()
            
            text_disp = ui.TextDisplay(
                content=f"📋 **Submission ID:** {sub_id}\n👤 **Ingediend door:** {interaction.user.mention}\n📎 **Type:** Review\n\n{desc}"
            )
            
            gallery_items, discord_files = await prepare_grid(files or [])
            if gallery_items:
                gallery = ui.MediaGallery(*gallery_items)
                container = ui.Container(text_disp, gallery, accent_colour=discord.Color.blue())
            else:
                container = ui.Container(text_disp, accent_colour=discord.Color.blue())
                
            # Pop the action row that was added in __init__, add the container, then re-add the row
            view.remove_item(view.action_row)
            view.add_item(container)
            view.add_item(view.action_row)
            
            # MUST explicitly pass files=discord_files so Discord can upload them
            btn_msg = await admin_ch.send(view=view, files=discord_files)

        await interaction.followup.send(
            "✅ Bedankt! Je review is verstuurd naar de admins ter beoordeling.", ephemeral=True
        )

# -------------------- Native Update Modal (discord.py 2.7+) --------------------

class UpdateModal(ui.Modal, title="Geef een update door!"):
    def __init__(self):
        super().__init__()
        
        # Wrapped RadioGroup for selection
        self.type_selection = ui.RadioGroup(
            options=[
                discord.RadioGroupOption(label="Verwijderen", value="Verwijderen"),
                discord.RadioGroupOption(label="Toevoegen", value="Toevoegen"),
                discord.RadioGroupOption(label="Naams Wijziging", value="Naams Wijziging"),
            ],
            required=True
        )
        self.add_item(ui.Label(
            text="Wil je een locatie verwijderen of toevoegen?",
            component=self.type_selection
        ))
        
        self.loc_input = ui.TextInput(placeholder="Naam of nummer van de locatie", required=True)
        self.add_item(ui.Label(text="Locatie naam of nummer", component=self.loc_input))

        self.extra_info_input = ui.TextInput(placeholder="Vul hier de coördinaten of de gewenste naamswijziging in", required=False, style=discord.TextStyle.paragraph)
        self.add_item(ui.Label(text="Extra info (Coördinaten / Naamswijziging)", component=self.extra_info_input))

        self.map_input = ui.TextInput(placeholder="Map naam (Bijv. België)", required=True)
        self.add_item(ui.Label(text="Welke map?", component=self.map_input))

        self.photo_upload = ui.FileUpload(min_values=0, max_values=10, required=False)
        self.add_item(ui.Label(text="Upload hieronder je foto('s)", component=self.photo_upload))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        type_val = self.type_selection.value
        loc = self.loc_input.value
        extra_info = self.extra_info_input.value
        map_val = self.map_input.value
        files = self.photo_upload.values or []

        # Store in database
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                '''INSERT INTO submissions (user_id, type, status, location_id, location_name, coordinates, map_category, content)
                   VALUES (?, 'update', 'pending', ?, ?, ?, ?, ?)''',
                (interaction.user.id, loc, loc, extra_info, map_val, f"Type update: {type_val}")
            )
            sub_id = cursor.lastrowid
            await db.commit()

        # Admin channel (updates use their own dedicated key)
        approval_channel_id = await get_setting('update_approval_channel')
        admin_channel = interaction.guild.get_channel(int(approval_channel_id)) if approval_channel_id else None

        if admin_channel:
            desc = (
                f"**Wil je een locatie verwijderen of toevoegen?**\n{type_val}\n\n"
                f"**Locatie naam of nummer**\n{loc}\n\n"
                f"**Extra info (Coördinaten / Naamswijziging)**\n{extra_info or 'Geen'}\n\n"
                f"**Welke map?**\n{map_val}\n\n"
                f"**Upload hieronder je foto('s)**"
            )

            # Unified Native UI Container
            view = SubmissionApprovalView()
            
            text_disp = ui.TextDisplay(
                content=f"📋 **Submission ID:** {sub_id}\n👤 **Ingediend door:** {interaction.user.mention}\n📎 **Type:** Update\n\n{desc}"
            )
            
            gallery_items, discord_files = await prepare_grid(files or [])
            if gallery_items:
                gallery = ui.MediaGallery(*gallery_items)
                container = ui.Container(text_disp, gallery, accent_colour=discord.Color.orange())
            else:
                container = ui.Container(text_disp, accent_colour=discord.Color.orange())
                
            # Reorder container above persistent buttons
            view.remove_item(view.action_row)
            view.add_item(container)
            view.add_item(view.action_row)

            # MUST explicitly pass files=discord_files so Discord can upload them
            btn_msg = await admin_channel.send(view=view, files=discord_files)

        await interaction.followup.send(
            "✅ Bedankt! Je update is verstuurd naar de admins.", ephemeral=True
        )

# -------------------- Panel Views --------------------

class ReviewPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="⭐ Laat een review achter", style=discord.ButtonStyle.success, custom_id="panel_submit_review")
    async def submit_review(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReviewModal())

class UpdatePanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Updates Doorgeven", style=discord.ButtonStyle.primary, custom_id="panel_update_location")
    async def update_location(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(UpdateModal())

# -------------------- Sticky Panel Helpers --------------------

async def send_review_panel(channel: discord.TextChannel):
    content = (
        "Laat een review achter 👇\n"
        "Klik op de knop hieronder en deel jouw ervaring met deze locatie.\n\n"
        "Je review wordt automatisch in dit kanaal geplaatst.\n\n"
        "-# Toegankelijkheid: (1:star: = slecht toegankelijk, 5:star: = goed toegankelijk)\n"
        "-# Kwaliteit: (1:star: = slecht, 5:star: = goed)\n\n"
        "👇 Klik hier om je review te plaatsen"
    )
    view = ReviewPanelView()
    message = await channel.send(content=content, view=view)
    await set_setting("review_panel_sticky_id", str(message.id))
    await set_setting("review_panel_channel", str(channel.id))

async def refresh_review_sticky(guild: discord.Guild):
    channel_id = await get_setting("review_panel_channel")
    if not channel_id:
        return
    channel = guild.get_channel(int(channel_id))
    if not isinstance(channel, discord.TextChannel):
        return
    old_msg_id = await get_setting("review_panel_sticky_id")
    if old_msg_id:
        try:
            old_msg = await channel.fetch_message(int(old_msg_id))
            await old_msg.delete()
        except Exception:
            pass
    await send_review_panel(channel)

async def refresh_update_sticky(guild: discord.Guild):
    channel_id = await get_setting("update_panel_channel")
    if not channel_id:
        return
    channel = guild.get_channel(int(channel_id))
    if not isinstance(channel, discord.TextChannel):
        return
    old_msg_id = await get_setting("update_panel_sticky_id")
    if old_msg_id:
        try:
            old_msg = await channel.fetch_message(int(old_msg_id))
            await old_msg.delete()
        except Exception:
            pass
    await send_update_panel(channel)

async def send_update_panel(channel: discord.TextChannel):
    content = (
        "📍 **Locatie Update Doorgeven**\n\n"
        "Zie je een locatie die niet meer bestaat, wil je er een toevoegen of is de naam onjuist?\n"
        "Klik op de knop hieronder om een update door te geven aan het team!"
    )
    view = UpdatePanelView()
    message = await channel.send(content=content, view=view)
    await set_setting("update_panel_sticky_id", str(message.id))
    await set_setting("update_panel_channel", str(channel.id))
    await send_review_panel(channel)

async def send_update_panel(channel: discord.abc.Messageable):
    embed = discord.Embed(
        title="Geef een update door!",
        description="Alle updates die door jullie zijn geconstateerd kunnen hier worden doorgegeven.\nKlik op de knop hieronder om direct het update-formulier te openen.",
        color=discord.Color.orange(),
    )
    embed.set_footer(text="The Urbex Factory")
    await channel.send(embed=embed, view=UpdatePanelView())

# -------------------- Cog --------------------

class Forms(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Check for review panel sticky
        review_ch_id = await get_setting("review_panel_channel")
        if review_ch_id and message.channel.id == int(review_ch_id):
            await refresh_review_sticky(message.guild)

        # Check for update panel sticky
        update_ch_id = await get_setting("update_panel_channel")
        if update_ch_id and message.channel.id == int(update_ch_id):
            await refresh_update_sticky(message.guild)

async def setup(bot):
    bot.add_view(ReviewPanelView())
    bot.add_view(UpdatePanelView())
    bot.add_view(SubmissionApprovalView())
    await bot.add_cog(Forms(bot))
