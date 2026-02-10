"""
BlockForge OS - Ticket System v2.2.0
Handles support tickets with persistent views, categories, claiming, and transcripts
"""

import discord
from discord.ext import commands
from datetime import datetime
import asyncio
import json
import io
from utils.database import Database
from utils.config import Config


# ==================== PERSISTENT VIEWS ====================

class TicketControlView(discord.ui.View):
    """Buttons inside each ticket channel (Close, Claim)"""

    def __init__(self, cog, ticket_id: int):
        super().__init__(timeout=None)
        self.cog = cog

        close_btn = discord.ui.Button(
            label="Close Ticket",
            style=discord.ButtonStyle.danger,
            emoji="\U0001f512",
            custom_id=f"bfos_ticket_close_{ticket_id}",
        )
        close_btn.callback = self.close_callback
        self.add_item(close_btn)

        claim_btn = discord.ui.Button(
            label="Claim",
            style=discord.ButtonStyle.secondary,
            emoji="\U0001f4cb",
            custom_id=f"bfos_ticket_claim_{ticket_id}",
        )
        claim_btn.callback = self.claim_callback
        self.add_item(claim_btn)

    async def close_callback(self, interaction: discord.Interaction):
        await self.cog._handle_ticket_close(interaction, interaction.channel)

    async def claim_callback(self, interaction: discord.Interaction):
        await self.cog._handle_ticket_claim(interaction, interaction.channel)


class TicketCloseConfirmView(discord.ui.View):
    """Confirmation buttons before closing a ticket"""

    def __init__(self, cog, ticket, closer: discord.Member, reason: str = None):
        super().__init__(timeout=30)
        self.cog = cog
        self.ticket = ticket
        self.closer = closer
        self.reason = reason

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, emoji="\u2705")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.closer.id:
            await interaction.response.send_message("Only the person who initiated the close can confirm.", ephemeral=True)
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await self.cog._execute_ticket_close(interaction.channel, self.closer, self.reason)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="\u274c")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.closer.id:
            await interaction.response.send_message("Only the person who initiated the close can cancel.", ephemeral=True)
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            embed=discord.Embed(title="Close Cancelled", description="Ticket close has been cancelled.", color=0x95A5A6),
            view=self
        )
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class TicketPanelView(discord.ui.View):
    """Button-based ticket panel (one button per category)"""

    def __init__(self, cog, categories: list):
        super().__init__(timeout=None)
        for cat in categories[:25]:  # Discord max 25 components
            btn = discord.ui.Button(
                label=cat['name'],
                style=discord.ButtonStyle.primary,
                emoji=cat.get('emoji') or None,
                custom_id=f"bfos_ticket_cat_{cat['id']}",
            )
            btn.callback = self._make_callback(cog, cat['id'])
            self.add_item(btn)

    @staticmethod
    def _make_callback(cog, category_id):
        async def callback(interaction: discord.Interaction):
            await cog._handle_ticket_create(interaction, category_id)
        return callback


class TicketDropdownView(discord.ui.View):
    """Dropdown-based ticket panel"""

    def __init__(self, cog, categories: list):
        super().__init__(timeout=None)
        self.cog = cog
        self.categories = categories
        options = []
        for cat in categories[:25]:
            options.append(discord.SelectOption(
                label=cat['name'],
                value=str(cat['id']),
                description=(cat.get('description') or '')[:100],
                emoji=cat.get('emoji') or None,
            ))
        select = discord.ui.Select(
            placeholder="Select a ticket category...",
            options=options,
            min_values=0,
            max_values=1,
            custom_id="bfos_ticket_dropdown",
        )
        select.callback = self._make_callback(cog, self)
        self.add_item(select)

    @staticmethod
    def _make_callback(cog, view_instance):
        async def callback(interaction: discord.Interaction):
            if not interaction.data.get('values'):
                await interaction.response.defer()
                return
            category_id = int(interaction.data['values'][0])
            # Reset dropdown by replacing with fresh view
            try:
                fresh_view = TicketDropdownView(cog, view_instance.categories)
                await interaction.message.edit(view=fresh_view)
            except discord.HTTPException:
                pass
            await cog._handle_ticket_create(interaction, category_id)
        return callback


# ==================== MAIN COG ====================

class TicketSystem(commands.Cog):
    """Ticket system with persistent views"""

    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self._init_tables()

    def _init_tables(self):
        """Create ticket tables"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute('''CREATE TABLE IF NOT EXISTS ticket_config (
            guild_id INTEGER PRIMARY KEY,
            panel_channel_id INTEGER,
            panel_message_id INTEGER,
            panel_style TEXT DEFAULT 'buttons',
            close_behavior TEXT DEFAULT 'wait_delete',
            max_tickets_per_user INTEGER DEFAULT 3,
            transcript_channel_id INTEGER,
            claim_enabled INTEGER DEFAULT 1,
            delete_delay_seconds INTEGER DEFAULT 300
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS ticket_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            name TEXT,
            emoji TEXT,
            description TEXT,
            welcome_message TEXT,
            channel_category_id INTEGER,
            ping_roles TEXT DEFAULT '[]',
            color INTEGER DEFAULT 5793266,
            position INTEGER DEFAULT 0
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS ticket_panels (
            guild_id INTEGER PRIMARY KEY,
            panel_data TEXT DEFAULT '{}'
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            channel_id INTEGER,
            user_id INTEGER,
            category_id INTEGER,
            claimed_by INTEGER,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            close_reason TEXT,
            ticket_number INTEGER
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS ticket_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            user_id INTEGER,
            content TEXT,
            attachments TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        conn.commit()
        conn.close()

    # ==================== DB HELPERS ====================

    def get_ticket_config(self, guild_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ticket_config WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'guild_id': row[0], 'panel_channel_id': row[1], 'panel_message_id': row[2],
            'panel_style': row[3], 'close_behavior': row[4], 'max_tickets_per_user': row[5],
            'transcript_channel_id': row[6], 'claim_enabled': bool(row[7]),
            'delete_delay_seconds': row[8]
        }

    def set_ticket_config(self, guild_id, **kwargs):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        # Ensure row exists
        cursor.execute('INSERT OR IGNORE INTO ticket_config (guild_id) VALUES (?)', (guild_id,))
        for key, value in kwargs.items():
            cursor.execute(f'UPDATE ticket_config SET {key} = ? WHERE guild_id = ?', (value, guild_id))
        conn.commit()
        conn.close()

    def add_ticket_category(self, guild_id, name, emoji=None, description=None,
                            welcome_message=None, channel_category_id=None,
                            ping_roles=None, color=0x5865F2, position=0):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO ticket_categories
               (guild_id, name, emoji, description, welcome_message, channel_category_id, ping_roles, color, position)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (guild_id, name, emoji, description, welcome_message, channel_category_id,
             json.dumps(ping_roles or []), color, position)
        )
        cat_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return cat_id

    def get_ticket_categories(self, guild_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ticket_categories WHERE guild_id = ? ORDER BY position', (guild_id,))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_category(r) for r in rows]

    def get_ticket_category(self, category_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ticket_categories WHERE id = ?', (category_id,))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_category(row) if row else None

    def _row_to_category(self, row):
        return {
            'id': row[0], 'guild_id': row[1], 'name': row[2], 'emoji': row[3],
            'description': row[4], 'welcome_message': row[5],
            'channel_category_id': row[6],
            'ping_roles': json.loads(row[7]) if row[7] else [],
            'color': row[8], 'position': row[9]
        }

    def update_ticket_category(self, category_id, **kwargs):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        for key, value in kwargs.items():
            if key == 'ping_roles':
                value = json.dumps(value)
            cursor.execute(f'UPDATE ticket_categories SET {key} = ? WHERE id = ?', (value, category_id))
        conn.commit()
        conn.close()

    def delete_ticket_category(self, category_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM ticket_categories WHERE id = ?', (category_id,))
        conn.commit()
        conn.close()

    def get_ticket_panel_data(self, guild_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT panel_data FROM ticket_panels WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
        return {'title': 'Support Tickets', 'description': 'Click a button below to open a ticket.', 'color': 0x5865F2}

    def set_ticket_panel_data(self, guild_id, data):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO ticket_panels (guild_id, panel_data) VALUES (?, ?)',
                       (guild_id, json.dumps(data)))
        conn.commit()
        conn.close()

    def create_ticket(self, guild_id, channel_id, user_id, category_id, ticket_number):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO tickets (guild_id, channel_id, user_id, category_id, ticket_number)
               VALUES (?, ?, ?, ?, ?)''',
            (guild_id, channel_id, user_id, category_id, ticket_number)
        )
        ticket_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return ticket_id

    def get_ticket(self, ticket_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_ticket(row) if row else None

    def get_ticket_by_channel(self, channel_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tickets WHERE channel_id = ? AND status = ?', (channel_id, 'open'))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_ticket(row) if row else None

    def _row_to_ticket(self, row):
        return {
            'id': row[0], 'guild_id': row[1], 'channel_id': row[2], 'user_id': row[3],
            'category_id': row[4], 'claimed_by': row[5], 'status': row[6],
            'created_at': row[7], 'closed_at': row[8], 'close_reason': row[9],
            'ticket_number': row[10]
        }

    def get_open_tickets_count(self, guild_id, user_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM tickets WHERE guild_id = ? AND user_id = ? AND status = ?',
                       (guild_id, user_id, 'open'))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_next_ticket_number(self, guild_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(ticket_number) FROM tickets WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        conn.close()
        return (row[0] or 0) + 1

    def close_ticket(self, ticket_id, reason=None):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE tickets SET status = ?, closed_at = ?, close_reason = ? WHERE id = ?',
            ('closed', datetime.utcnow().isoformat(), reason, ticket_id)
        )
        conn.commit()
        conn.close()

    def set_ticket_claimed(self, ticket_id, user_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE tickets SET claimed_by = ? WHERE id = ?', (user_id, ticket_id))
        conn.commit()
        conn.close()

    def add_ticket_message(self, ticket_id, user_id, content, attachments=None):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO ticket_messages (ticket_id, user_id, content, attachments)
               VALUES (?, ?, ?, ?)''',
            (ticket_id, user_id, content, json.dumps(attachments or []))
        )
        conn.commit()
        conn.close()

    def get_ticket_messages(self, ticket_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY created_at', (ticket_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{
            'id': r[0], 'ticket_id': r[1], 'user_id': r[2], 'content': r[3],
            'attachments': json.loads(r[4]) if r[4] else [], 'created_at': r[5]
        } for r in rows]

    def get_all_open_tickets(self, guild_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tickets WHERE guild_id = ? AND status = ?', (guild_id, 'open'))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_ticket(r) for r in rows]

    # ==================== PERMISSION HELPERS ====================

    def _has_ticket_permission(self, member, permission_id):
        """Check if member has a ticket permission"""
        if member.id == Config.BOT_OWNER_ID:
            return True
        if member.id == member.guild.owner_id:
            return True
        if member.guild_permissions.administrator:
            return True
        db = Database()
        if db.has_permission(member.guild.id, member.id, permission_id):
            return True
        for role in member.roles:
            if db.role_has_permission(member.guild.id, role.id, permission_id):
                return True
        return False

    # ==================== TICKET CREATION ====================

    async def _handle_ticket_create(self, interaction: discord.Interaction, category_id: int):
        """Handle ticket creation from panel button/dropdown"""
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        # Check module enabled
        if not self.db.get_module_state(guild.id, 'tickets'):
            await interaction.followup.send("Ticket system is not enabled.", ephemeral=True)
            return

        config = self.get_ticket_config(guild.id)
        if not config:
            await interaction.followup.send("Ticket system is not configured.", ephemeral=True)
            return

        # Check max tickets
        open_count = self.get_open_tickets_count(guild.id, user.id)
        max_tickets = config.get('max_tickets_per_user', 3)
        if open_count >= max_tickets:
            await interaction.followup.send(
                f"You already have {open_count}/{max_tickets} open tickets. Please close one first.",
                ephemeral=True
            )
            return

        category = self.get_ticket_category(category_id)
        if not category:
            await interaction.followup.send("This ticket category no longer exists.", ephemeral=True)
            return

        ticket_number = self.get_next_ticket_number(guild.id)

        # Create channel
        discord_category = guild.get_channel(category['channel_category_id']) if category['channel_category_id'] else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, manage_channels=True,
                manage_messages=True, embed_links=True, attach_files=True
            ),
            user: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, embed_links=True, attach_files=True
            ),
        }

        # Add ping roles
        for role_id in category.get('ping_roles', []):
            role = guild.get_role(int(role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # Build channel name: ticket-username-category
        safe_username = ''.join(c if c.isalnum() or c == '-' else '-' for c in user.display_name.lower()).strip('-')[:20] or str(ticket_number)
        safe_category = ''.join(c if c.isalnum() or c == '-' else '-' for c in category['name'].lower()).strip('-')[:20] or 'general'

        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{safe_username}-{safe_category}",
                category=discord_category,
                overwrites=overwrites,
                topic=f"Ticket #{ticket_number} | {category['name']} | {user.display_name}"
            )
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to create channels.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"Failed to create ticket channel: {e}", ephemeral=True)
            return

        # Store ticket in DB
        ticket_id = self.create_ticket(guild.id, channel.id, user.id, category_id, ticket_number)

        # Build welcome embed
        welcome_msg = category.get('welcome_message') or f"Welcome to your ticket! A staff member will be with you shortly."
        guild_prefix = self.db.get_command_prefix(guild.id) or ';'
        embed = discord.Embed(
            title=f"Ticket #{ticket_number} — {category['name']}",
            description=f"{welcome_msg}\n\nCreated by: {user.mention}",
            color=category.get('color', 0x5865F2),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{guild_prefix}close [reason]` — Close this ticket\n"
                f"`{guild_prefix}add @user` — Add a user\n"
                f"`{guild_prefix}remove @user` — Remove a user\n"
                f"`{guild_prefix}rename <name>` — Rename channel\n"
                f"`{guild_prefix}claim` — Claim ticket (staff)\n"
                f"`{guild_prefix}transcript` — Get transcript (staff)"
            ),
            inline=False
        )
        embed.set_footer(text=f"BlockForge OS v{Config.VERSION} | Ticket ID: {ticket_id}")

        # Send welcome message with control buttons
        control_view = TicketControlView(self, ticket_id)
        await channel.send(embed=embed, view=control_view)

        # Ping roles (keep visible for staff)
        ping_roles = category.get('ping_roles', [])
        if ping_roles:
            mentions = " ".join(f"<@&{r}>" for r in ping_roles)
            await channel.send(mentions)

        # Ghost-ping ticket creator (notification only, then delete)
        try:
            user_ping = await channel.send(user.mention)
            await user_ping.delete()
        except:
            pass

        await interaction.followup.send(f"Ticket created: {channel.mention}", ephemeral=True)

    # ==================== TICKET CLOSE ====================

    async def _handle_ticket_close(self, interaction: discord.Interaction, channel: discord.TextChannel, reason=None):
        """Show close confirmation before closing a ticket"""
        ticket = self.get_ticket_by_channel(channel.id)
        if not ticket:
            if interaction:
                await interaction.response.send_message("This is not an active ticket.", ephemeral=True)
            return

        user = interaction.user if interaction else None

        # Permission check: ticket creator or ticket_close permission
        if user and user.id != ticket['user_id'] and not self._has_ticket_permission(user, 'ticket_close'):
            await interaction.response.send_message("You don't have permission to close this ticket.", ephemeral=True)
            return

        confirm_embed = discord.Embed(
            title="\U0001f512 Close Ticket?",
            description=(
                "Are you sure you want to close this ticket?"
                + (f"\n**Reason:** {reason}" if reason else "")
                + "\n\nThis action cannot be undone."
            ),
            color=0xE74C3C,
            timestamp=datetime.utcnow()
        )
        confirm_view = TicketCloseConfirmView(self, ticket, user, reason)

        if not interaction.response.is_done():
            await interaction.response.send_message(embed=confirm_embed, view=confirm_view)
        else:
            await interaction.followup.send(embed=confirm_embed, view=confirm_view)

    async def _execute_ticket_close(self, channel: discord.TextChannel, closer: discord.Member, reason=None):
        """Execute the actual ticket close (called after confirmation)"""
        ticket = self.get_ticket_by_channel(channel.id)
        if not ticket:
            return

        config = self.get_ticket_config(ticket['guild_id'])
        close_behavior = config.get('close_behavior', 'wait_delete') if config else 'wait_delete'

        # Close ticket in DB
        self.close_ticket(ticket['id'], reason=reason)

        # Generate transcript
        await self._send_transcript(ticket, channel.guild)

        if close_behavior == 'wait_delete':
            delay = config.get('delete_delay_seconds', 300) if config else 300
            try:
                await channel.set_permissions(channel.guild.default_role, send_messages=False)
                member = channel.guild.get_member(ticket['user_id'])
                if member:
                    await channel.set_permissions(member, send_messages=False, read_messages=True)
            except:
                pass

            embed = discord.Embed(
                title="\U0001f512 Ticket Closed",
                description=f"This ticket has been closed{f' by {closer.mention}' if closer else ''}."
                            f"\n{'**Reason:** ' + reason if reason else ''}"
                            f"\n\nThis channel will be deleted in {delay // 60} minute(s).",
                color=0xE74C3C,
                timestamp=datetime.utcnow()
            )
            await channel.send(embed=embed)
            await asyncio.sleep(delay)
            try:
                await channel.delete(reason=f"Ticket #{ticket['ticket_number']} closed")
            except:
                pass

        elif close_behavior == 'archive':
            try:
                member = channel.guild.get_member(ticket['user_id'])
                if member:
                    await channel.set_permissions(member, read_messages=False)
            except:
                pass
            embed = discord.Embed(
                title="\U0001f4e6 Ticket Archived",
                description=f"This ticket has been archived{f' by {closer.mention}' if closer else ''}."
                            f"\n{'**Reason:** ' + reason if reason else ''}",
                color=0x95A5A6,
                timestamp=datetime.utcnow()
            )
            await channel.send(embed=embed)

        elif close_behavior == 'instant_delete':
            try:
                await channel.delete(reason=f"Ticket #{ticket['ticket_number']} closed")
            except:
                pass

    # ==================== TICKET CLAIM ====================

    async def _handle_ticket_claim(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Handle ticket claim from button or command"""
        ticket = self.get_ticket_by_channel(channel.id)
        if not ticket:
            await interaction.response.send_message("This is not an active ticket.", ephemeral=True)
            return

        if not self._has_ticket_permission(interaction.user, 'ticket_claim'):
            await interaction.response.send_message("You don't have permission to claim tickets.", ephemeral=True)
            return

        if ticket['claimed_by']:
            claimer = channel.guild.get_member(ticket['claimed_by'])
            name = claimer.display_name if claimer else str(ticket['claimed_by'])
            await interaction.response.send_message(f"This ticket is already claimed by {name}.", ephemeral=True)
            return

        self.set_ticket_claimed(ticket['id'], interaction.user.id)

        embed = discord.Embed(
            title="\U0001f4cb Ticket Claimed",
            description=f"{interaction.user.mention} has claimed this ticket and will be assisting you.",
            color=0x2ECC71,
            timestamp=datetime.utcnow()
        )
        await interaction.response.send_message(embed=embed)

    # ==================== TRANSCRIPT ====================

    async def _send_transcript(self, ticket, guild):
        """Generate and send transcript to log channel"""
        config = self.get_ticket_config(guild.id)
        if not config or not config.get('transcript_channel_id'):
            return

        log_channel = guild.get_channel(config['transcript_channel_id'])
        if not log_channel:
            return

        messages = self.get_ticket_messages(ticket['id'])
        if not messages:
            return

        # Build transcript text
        lines = [f"=== Transcript: Ticket #{ticket['ticket_number']} ==="]
        lines.append(f"Created: {ticket['created_at']}")
        lines.append(f"Closed: {ticket.get('closed_at', 'N/A')}")
        lines.append(f"Close Reason: {ticket.get('close_reason', 'None')}")
        creator = guild.get_member(ticket['user_id'])
        lines.append(f"Creator: {creator.display_name if creator else ticket['user_id']}")
        if ticket.get('claimed_by'):
            claimer = guild.get_member(ticket['claimed_by'])
            lines.append(f"Claimed by: {claimer.display_name if claimer else ticket['claimed_by']}")
        lines.append(f"{'=' * 50}\n")

        for msg in messages:
            user = guild.get_member(msg['user_id'])
            username = user.display_name if user else str(msg['user_id'])
            lines.append(f"[{msg['created_at']}] {username}: {msg['content']}")
            if msg.get('attachments'):
                for att in msg['attachments']:
                    lines.append(f"  [Attachment: {att}]")

        transcript_text = "\n".join(lines)
        file = discord.File(io.BytesIO(transcript_text.encode('utf-8')),
                            filename=f"transcript-{ticket['ticket_number']:04d}.txt")

        category = self.get_ticket_category(ticket['category_id'])
        cat_name = category['name'] if category else 'Unknown'

        embed = discord.Embed(
            title=f"Ticket #{ticket['ticket_number']} Transcript",
            description=f"**Category:** {cat_name}\n**Messages:** {len(messages)}",
            color=0x3498DB,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"BlockForge OS v{Config.VERSION}")

        try:
            await log_channel.send(embed=embed, file=file)
        except:
            pass

    # ==================== MESSAGE TRACKING ====================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        ticket = self.get_ticket_by_channel(message.channel.id)
        if ticket:
            attachments = [a.url for a in message.attachments]
            self.add_ticket_message(ticket['id'], message.author.id, message.content, attachments)

    # ==================== COMMANDS ====================

    @commands.command(name='close')
    async def close_command(self, ctx, *, reason: str = None):
        """Close the current ticket"""
        if not self.db.get_module_state(ctx.guild.id, 'tickets'):
            return

        ticket = self.get_ticket_by_channel(ctx.channel.id)
        if not ticket:
            return

        # Permission check
        if ctx.author.id != ticket['user_id'] and not self._has_ticket_permission(ctx.author, 'ticket_close'):
            return

        confirm_embed = discord.Embed(
            title="\U0001f512 Close Ticket?",
            description=(
                "Are you sure you want to close this ticket?"
                + (f"\n**Reason:** {reason}" if reason else "")
                + "\n\nThis action cannot be undone."
            ),
            color=0xE74C3C,
            timestamp=datetime.utcnow()
        )
        confirm_view = TicketCloseConfirmView(self, ticket, ctx.author, reason)
        await ctx.send(embed=confirm_embed, view=confirm_view)

    @commands.command(name='add')
    async def add_user_command(self, ctx, user: discord.Member):
        """Add a user to the current ticket"""
        if not self.db.get_module_state(ctx.guild.id, 'tickets'):
            return
        ticket = self.get_ticket_by_channel(ctx.channel.id)
        if not ticket:
            return
        if not self._has_ticket_permission(ctx.author, 'ticket_add_user'):
            return
        await ctx.channel.set_permissions(user, read_messages=True, send_messages=True)
        await ctx.send(f"\u2705 {user.mention} has been added to the ticket.")

    @commands.command(name='remove')
    async def remove_user_command(self, ctx, user: discord.Member):
        """Remove a user from the current ticket"""
        if not self.db.get_module_state(ctx.guild.id, 'tickets'):
            return
        ticket = self.get_ticket_by_channel(ctx.channel.id)
        if not ticket:
            return
        if not self._has_ticket_permission(ctx.author, 'ticket_remove_user'):
            return
        if user.id == ticket['user_id']:
            await ctx.send("\u274c Cannot remove the ticket creator.")
            return
        await ctx.channel.set_permissions(user, overwrite=None)
        await ctx.send(f"\u2705 {user.mention} has been removed from the ticket.")

    @commands.command(name='rename')
    async def rename_command(self, ctx, *, name: str):
        """Rename the current ticket channel"""
        if not self.db.get_module_state(ctx.guild.id, 'tickets'):
            return
        ticket = self.get_ticket_by_channel(ctx.channel.id)
        if not ticket:
            return
        try:
            await ctx.channel.edit(name=name)
            await ctx.send(f"\u2705 Ticket renamed to **{name}**.")
        except discord.Forbidden:
            await ctx.send("\u274c Missing permissions to rename channel.")

    @commands.command(name='claim')
    async def claim_command(self, ctx):
        """Claim the current ticket"""
        if not self.db.get_module_state(ctx.guild.id, 'tickets'):
            return
        ticket = self.get_ticket_by_channel(ctx.channel.id)
        if not ticket:
            return
        if not self._has_ticket_permission(ctx.author, 'ticket_claim'):
            return
        if ticket['claimed_by']:
            claimer = ctx.guild.get_member(ticket['claimed_by'])
            name = claimer.display_name if claimer else str(ticket['claimed_by'])
            await ctx.send(f"This ticket is already claimed by **{name}**.")
            return
        self.set_ticket_claimed(ticket['id'], ctx.author.id)
        embed = discord.Embed(
            title="\U0001f4cb Ticket Claimed",
            description=f"{ctx.author.mention} has claimed this ticket.",
            color=0x2ECC71, timestamp=datetime.utcnow()
        )
        await ctx.send(embed=embed)

    @commands.command(name='transcript')
    async def transcript_command(self, ctx):
        """Generate transcript for current ticket"""
        if not self.db.get_module_state(ctx.guild.id, 'tickets'):
            return
        ticket = self.get_ticket_by_channel(ctx.channel.id)
        if not ticket:
            return
        if not self._has_ticket_permission(ctx.author, 'ticket_close'):
            return
        await self._send_transcript(ticket, ctx.guild)
        await ctx.send("\u2705 Transcript sent to the log channel.")

    # ==================== PERSISTENT VIEW REGISTRATION ====================

    async def cog_load(self):
        """Register persistent views on bot startup"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Register control views for all open tickets
        cursor.execute('SELECT id FROM tickets WHERE status = ?', ('open',))
        for row in cursor.fetchall():
            self.bot.add_view(TicketControlView(self, row[0]))

        # Register panel views for all guilds with ticket config
        cursor.execute('SELECT guild_id FROM ticket_config')
        for row in cursor.fetchall():
            guild_id = row[0]
            categories = self.get_ticket_categories(guild_id)
            if categories:
                config = self.get_ticket_config(guild_id)
                style = config.get('panel_style', 'buttons') if config else 'buttons'
                if style == 'dropdown':
                    self.bot.add_view(TicketDropdownView(self, categories))
                else:
                    self.bot.add_view(TicketPanelView(self, categories))

        conn.close()

    async def deploy_panel(self, guild):
        """Deploy or update the ticket panel in the configured channel"""
        config = self.get_ticket_config(guild.id)
        if not config or not config.get('panel_channel_id'):
            return None

        channel = guild.get_channel(config['panel_channel_id'])
        if not channel:
            return None

        categories = self.get_ticket_categories(guild.id)
        if not categories:
            return None

        panel_data = self.get_ticket_panel_data(guild.id)

        embed = discord.Embed(
            title=panel_data.get('title', 'Support Tickets'),
            description=panel_data.get('description', 'Click a button below to open a ticket.'),
            color=panel_data.get('color', 0x5865F2),
            timestamp=datetime.utcnow()
        )

        # Add category info
        for cat in categories:
            emoji = cat.get('emoji', '') or ''
            embed.add_field(
                name=f"{emoji} {cat['name']}",
                value=cat.get('description', 'No description') or 'No description',
                inline=False
            )

        embed.set_footer(text=f"BlockForge OS v{Config.VERSION}")

        if panel_data.get('thumbnail'):
            embed.set_thumbnail(url=panel_data['thumbnail'])

        # Create view
        style = config.get('panel_style', 'buttons')
        if style == 'dropdown':
            view = TicketDropdownView(self, categories)
        else:
            view = TicketPanelView(self, categories)

        # Delete old panel message
        if config.get('panel_message_id'):
            try:
                old_msg = await channel.fetch_message(config['panel_message_id'])
                await old_msg.delete()
            except:
                pass

        # Send new panel
        msg = await channel.send(embed=embed, view=view)
        self.set_ticket_config(guild.id, panel_message_id=msg.id, panel_channel_id=channel.id)

        return msg


async def setup(bot):
    await bot.add_cog(TicketSystem(bot))
