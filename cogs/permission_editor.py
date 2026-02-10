"""
BlockForge OS Interactive Permission Editor
Advanced permission management with Discord UI components
"""

import discord
from discord.ui import Select, View, Button, Modal, TextInput
from discord import SelectOption
import asyncio
from datetime import datetime

class PermissionEditorView(View):
    """Main permission editor view"""
    
    def __init__(self, ctx, db, channels_data, author_id, editor_type='channel'):
        super().__init__(timeout=None)  # No timeout per user request
        self.ctx = ctx
        self.db = db
        self.channels_data = channels_data
        self.author_id = author_id
        self.editor_type = editor_type
        self.selected_channel = None
        self.current_page = 0
        
        # Create initial view
        self.update_view()
    
    def update_view(self):
        """Update view components"""
        self.clear_items()
        
        if self.selected_channel is None:
            # Show channel selection
            self.add_channel_select()
        else:
            # Show permission management
            self.add_permission_buttons()
    
    def add_channel_select(self):
        """Add channel selection dropdown"""
        # Get channels for current page
        channels_per_page = 25
        start = self.current_page * channels_per_page
        end = start + channels_per_page
        page_channels = self.channels_data[start:end]
        
        if not page_channels:
            return
        
        options = []
        for channel in page_channels:
            emoji = "💬" if channel['type'] == 'text' else "🔊"
            options.append(SelectOption(
                label=f"{emoji} {channel['name']}",
                description=f"ID: {channel['id']}",
                value=str(channel['id'])
            ))
        
        select = Select(
            placeholder="Select a channel to manage permissions...",
            options=options,
            custom_id="channel_select"
        )
        select.callback = self.channel_selected
        self.add_item(select)
        
        # Add pagination if needed
        if len(self.channels_data) > channels_per_page:
            if self.current_page > 0:
                prev_btn = Button(label="◀️ Previous", style=discord.ButtonStyle.secondary, custom_id="prev")
                prev_btn.callback = self.previous_page
                self.add_item(prev_btn)
            
            if end < len(self.channels_data):
                next_btn = Button(label="Next ▶️", style=discord.ButtonStyle.secondary, custom_id="next")
                next_btn.callback = self.next_page
                self.add_item(next_btn)
        
        # Back button
        back_btn = Button(label="🔙 Back", style=discord.ButtonStyle.danger, custom_id="back")
        back_btn.callback = self.go_back
        self.add_item(back_btn)
    
    def add_permission_buttons(self):
        """Add permission management buttons"""
        # View permissions button
        view_btn = Button(label="👁️ View Permissions", style=discord.ButtonStyle.primary, custom_id="view")
        view_btn.callback = self.view_permissions
        self.add_item(view_btn)
        
        # Change permissions button
        change_btn = Button(label="✏️ Change Permissions", style=discord.ButtonStyle.primary, custom_id="change")
        change_btn.callback = self.change_permissions
        self.add_item(change_btn)
        
        # Sync with category button (if channel has category)
        channel = self.ctx.guild.get_channel(int(self.selected_channel))
        if channel and channel.category:
            sync_btn = Button(label="🔄 Sync with Category", style=discord.ButtonStyle.secondary, custom_id="sync")
            sync_btn.callback = self.sync_category
            self.add_item(sync_btn)
        
        # Back button
        back_btn = Button(label="🔙 Change Channel", style=discord.ButtonStyle.secondary, custom_id="back_channel")
        back_btn.callback = self.back_to_selection
        self.add_item(back_btn)
        
        # Exit button - saves and returns to terminal
        exit_btn = Button(label="🚪 Exit to Terminal", style=discord.ButtonStyle.danger, custom_id="done")
        exit_btn.callback = self.finish_editing
        self.add_item(exit_btn)
    
    async def channel_selected(self, interaction: discord.Interaction):
        """Handle channel selection"""
        try:
            if interaction.user.id != self.author_id:
                await interaction.response.send_message("❌ Only the command author can interact.", ephemeral=True)
                return
            
            # discord.py v2: Access values from interaction.data
            self.selected_channel = interaction.data['values'][0]
            channel = self.ctx.guild.get_channel(int(self.selected_channel))
            
            if not channel:
                await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🔐 Permission Editor",
                description=f"**Channel:** {channel.name}\n**ID:** `{channel.id}`",
                color=0x00AAFF,
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="What would you like to do?",
                value="• **View Permissions** - See current permissions\n• **Change Permissions** - Add/edit role or user permissions\n• **Sync with Category** - Copy category permissions",
                inline=False
            )
            
            self.update_view()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            print(f"[PERM EDITOR] channel_selected error: {e}")
            try:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            except:
                pass
    
    async def view_permissions(self, interaction: discord.Interaction):
        """View channel permissions"""
        try:
            if interaction.user.id != self.author_id:
                await interaction.response.send_message("❌ Only the command author can interact.", ephemeral=True)
                return
            
            channel = self.ctx.guild.get_channel(int(self.selected_channel))
            
            if not channel:
                await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title=f"🔐 Permissions: {channel.name}",
                color=0x00AAFF,
                timestamp=datetime.utcnow()
            )
            
            if not channel.overwrites:
                embed.add_field(name="No Custom Permissions", value="This channel has no permission overwrites.", inline=False)
            else:
                for target, overwrite in list(channel.overwrites.items())[:10]:  # Limit to 10
                    target_name = target.name if hasattr(target, 'name') else str(target)
                    target_type = "👥 Role" if isinstance(target, discord.Role) else "👤 User"
                    
                    allow, deny = overwrite.pair()
                    allowed = [perm for perm, value in allow if value]
                    denied = [perm for perm, value in deny if value]
                    
                    value = ""
                    if allowed:
                        value += f"✅ **Allow:** {', '.join(allowed[:3])}"
                        if len(allowed) > 3:
                            value += f" (+{len(allowed)-3} more)"
                        value += "\n"
                    if denied:
                        value += f"❌ **Deny:** {', '.join(denied[:3])}"
                        if len(denied) > 3:
                            value += f" (+{len(denied)-3} more)"
                    
                    embed.add_field(
                        name=f"{target_type} {target_name}",
                        value=value or "No specific permissions",
                        inline=False
                    )
            
            embed.set_footer(text=f"Total overwrites: {len(channel.overwrites)}")
            
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            print(f"[PERM EDITOR] view_permissions error: {e}")
            try:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            except:
                pass
    
    async def change_permissions(self, interaction: discord.Interaction):
        """Start permission change flow"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can interact.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="✏️ Change Permissions",
            description="**Mention a role or user** in chat to modify their permissions.\n\nOr enter a **Role ID** or **User ID**.",
            color=0xFFAA00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Examples:",
            value="• Mention: `@Moderators`\n• Role ID: `123456789`\n• User ID: `987654321`",
            inline=False
        )
        embed.add_field(
            name="📝 Note:",
            value="Send your message in chat, then I'll show the permission editor.",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Wait for user input
        def check(m):
            return m.author.id == self.author_id and m.channel.id == self.ctx.channel.id
        
        try:
            msg = await self.ctx.bot.wait_for('message', timeout=60.0, check=check)
            
            # Try to delete user message
            try:
                await msg.delete()
            except:
                pass
            
            # Parse target (role/user)
            target = await self.parse_target(msg.content)
            
            if target:
                await self.show_permission_editor(interaction, target)
            else:
                embed.description = "❌ **Could not find that role or user.**\n\nTry again with a valid mention or ID."
                await interaction.message.edit(embed=embed, view=self)
        
        except asyncio.TimeoutError:
            embed.description = "⏱️ **Timed out.** No changes made."
            await interaction.message.edit(embed=embed, view=self)
    
    async def parse_target(self, content):
        """Parse target from user input"""
        # Try role mention
        if content.startswith('<@&') and content.endswith('>'):
            role_id = int(content[3:-1])
            return self.ctx.guild.get_role(role_id)
        
        # Try user mention
        if content.startswith('<@') and content.endswith('>'):
            user_id = int(content[2:-1].replace('!', ''))
            return self.ctx.guild.get_member(user_id)
        
        # Try ID
        if content.isdigit():
            target_id = int(content)
            target = self.ctx.guild.get_role(target_id)
            if target:
                return target
            return self.ctx.guild.get_member(target_id)
        
        return None
    
    async def show_permission_editor(self, interaction, target):
        """Show permission document editor"""
        channel = self.ctx.guild.get_channel(int(self.selected_channel))
        
        # Get current permissions
        overwrite = channel.overwrites_for(target)
        allow, deny = overwrite.pair()
        
        # Create permission document
        doc_lines = ["# Permission Configuration"]
        doc_lines.append(f"# Target: {target.name}")
        doc_lines.append(f"# Channel: {channel.name}")
        doc_lines.append("")
        doc_lines.append("# Format: permission=true/false/neutral")
        doc_lines.append("# true = allow, false = deny, neutral = inherit")
        doc_lines.append("")
        
        # ALL Discord permissions - comprehensive list
        all_perms = [
            # General Channel Permissions
            'view_channel',
            'manage_channels',
            'manage_permissions',
            'manage_webhooks',
            'create_instant_invite',
            
            # Text Channel Permissions
            'send_messages',
            'send_messages_in_threads',
            'create_public_threads',
            'create_private_threads',
            'embed_links',
            'attach_files',
            'add_reactions',
            'use_external_emojis',
            'use_external_stickers',
            'mention_everyone',
            'manage_messages',
            'manage_threads',
            'read_message_history',
            'send_tts_messages',
            'use_application_commands',
            
            # Voice Channel Permissions
            'connect',
            'speak',
            'stream',
            'use_embedded_activities',
            'use_soundboard',
            'use_external_sounds',
            'use_voice_activation',
            'priority_speaker',
            'mute_members',
            'deafen_members',
            'move_members',
            
            # Stage Channel Permissions
            'request_to_speak',
            
            # Events Permissions
            'manage_events',
            
            # Advanced Permissions
            'administrator',
            'view_audit_log',
            'view_guild_insights',
            'manage_guild',
            'manage_roles',
            'manage_nicknames',
            'change_nickname',
            'kick_members',
            'ban_members',
            'moderate_members',  # Timeout
        ]
        
        for perm in all_perms:
            perm_value = getattr(allow, perm, None)
            deny_value = getattr(deny, perm, None)
            if perm_value:
                doc_lines.append(f"{perm}=true")
            elif deny_value:
                doc_lines.append(f"{perm}=false")
            else:
                doc_lines.append(f"{perm}=neutral")
        
        document = "\n".join(doc_lines)
        
        embed = discord.Embed(
            title="📝 Permission Document",
            description=f"**Target:** {target.mention}\n**Channel:** {channel.mention}",
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Instructions:",
            value="1. Copy the document below\n2. Edit the permissions\n3. Send it back in chat",
            inline=False
        )
        embed.add_field(
            name="Format:",
            value="`permission=true` (allow)\n`permission=false` (deny)\n`permission=neutral` (inherit)",
            inline=False
        )
        
        # Send document in code block
        await interaction.message.edit(embed=embed, view=self)
        await self.ctx.send(f"```ini\n{document}\n```")
        
        # Wait for response
        def check(m):
            return m.author.id == self.author_id and m.channel.id == self.ctx.channel.id
        
        try:
            response = await self.ctx.bot.wait_for('message', timeout=300.0, check=check)
            
            # Parse permissions
            success = await self.apply_permissions(channel, target, response.content)
            
            try:
                await response.delete()
            except:
                pass
            
            if success:
                embed = discord.Embed(
                    title="✅ Permissions Updated",
                    description=f"**Target:** {target.mention}\n**Channel:** {channel.mention}",
                    color=0x00FF00
                )
                embed.add_field(name="Status", value="Permissions have been applied successfully!", inline=False)
            else:
                embed = discord.Embed(
                    title="❌ Update Failed",
                    description="Could not parse or apply permissions.",
                    color=0xFF0000
                )
            
            self.update_view()
            await interaction.message.edit(embed=embed, view=self)
        
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="⏱️ Timed Out",
                description="Permission edit timed out. No changes made.",
                color=0xFF0000
            )
            self.update_view()
            await interaction.message.edit(embed=embed, view=self)
    
    async def apply_permissions(self, channel, target, content):
        """Apply permissions from document"""
        try:
            # Parse document
            lines = content.replace('```', '').replace('ini', '').strip().split('\n')
            
            perms_dict = {}
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    perm, value = line.split('=', 1)
                    perm = perm.strip()
                    value = value.strip().lower()
                    
                    if value == 'true':
                        perms_dict[perm] = True
                    elif value == 'false':
                        perms_dict[perm] = False
                    # neutral = None (inherit)
            
            # Build overwrite
            overwrite = discord.PermissionOverwrite(**perms_dict)
            
            # Apply
            await channel.set_permissions(target, overwrite=overwrite, reason=f"Edited by {self.ctx.author}")
            
            return True
        
        except Exception as e:
            print(f"Permission apply error: {e}")
            return False
    
    async def sync_category(self, interaction: discord.Interaction):
        """Sync permissions with category"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can interact.", ephemeral=True)
            return
        
        channel = self.ctx.guild.get_channel(int(self.selected_channel))
        
        if not channel.category:
            await interaction.response.send_message("❌ This channel has no category.", ephemeral=True)
            return
        
        try:
            await channel.edit(sync_permissions=True, reason=f"Synced by {self.ctx.author}")
            
            embed = discord.Embed(
                title="✅ Permissions Synced",
                description=f"**Channel:** {channel.mention}\n**Category:** {channel.category.name}",
                color=0x00FF00
            )
            embed.add_field(name="Status", value="Permissions have been synced with category.", inline=False)
            
            await interaction.response.edit_message(embed=embed, view=self)
        
        except Exception as e:
            await interaction.response.send_message(f"❌ Sync failed: {str(e)}", ephemeral=True)
    
    async def back_to_selection(self, interaction: discord.Interaction):
        """Go back to channel selection"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can interact.", ephemeral=True)
            return
        
        self.selected_channel = None
        self.update_view()
        
        embed = discord.Embed(
            title="🔐 Permission Editor",
            description="Select a channel to manage permissions",
            color=0x00AAFF
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can interact.", ephemeral=True)
            return
        
        self.current_page -= 1
        self.update_view()
        await interaction.response.edit_message(view=self)
    
    async def next_page(self, interaction: discord.Interaction):
        """Go to next page"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can interact.", ephemeral=True)
            return
        
        self.current_page += 1
        self.update_view()
        await interaction.response.edit_message(view=self)
    
    async def go_back(self, interaction: discord.Interaction):
        """Exit editor"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can interact.", ephemeral=True)
            return
        
        # Remove from active editors
        if hasattr(self.ctx.bot, '_perm_editor_active'):
            self.ctx.bot._perm_editor_active.discard(self.author_id)
        
        await interaction.response.edit_message(content="✅ **Permission editor closed.**", embed=None, view=None)
        self.stop()
    
    async def finish_editing(self, interaction: discord.Interaction):
        """Finish editing and return to terminal"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can interact.", ephemeral=True)
            return
        
        # Remove from active editors
        if hasattr(self.ctx.bot, '_perm_editor_active'):
            self.ctx.bot._perm_editor_active.discard(self.author_id)
        
        embed = discord.Embed(
            title="✅ Permission Editor Closed",
            description="All changes have been saved automatically.\n\n**Return to the terminal to continue.**",
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Changes are applied immediately - no manual save needed")
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

async def launch_permission_editor(ctx, db, channel=None):
    """Launch the interactive permission editor
    
    Args:
        ctx: Command context
        db: Database instance
        channel: Optional channel to edit directly (skips channel selection)
    """
    # Get all channels
    channels_data = []
    for ch in ctx.guild.channels:
        if isinstance(ch, (discord.TextChannel, discord.VoiceChannel)):
            channels_data.append({
                'id': ch.id,
                'name': ch.name,
                'type': 'text' if isinstance(ch, discord.TextChannel) else 'voice'
            })
    
    # Create view
    view = PermissionEditorView(ctx, db, channels_data, ctx.author.id)
    
    # Store view reference in bot to prevent garbage collection
    if not hasattr(ctx.bot, '_permission_editor_views'):
        ctx.bot._permission_editor_views = {}
    ctx.bot._permission_editor_views[ctx.author.id] = view
    
    # If channel is provided, pre-select it
    if channel:
        view.selected_channel = str(channel.id)
        view.update_view()
        
        embed = discord.Embed(
            title="🔐 Permission Editor",
            description=f"**Channel:** {channel.name}\n**ID:** `{channel.id}`",
            color=0x00AAFF,
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="What would you like to do?",
            value="• **View Permissions** - See current permissions\n• **Change Permissions** - Add/edit role or user permissions\n• **Sync with Category** - Copy category permissions",
            inline=False
        )
        embed.set_footer(text="This editor will not timeout")
    else:
        # No channel - show channel selection
        embed = discord.Embed(
            title="🔐 Interactive Permission Editor",
            description="Select a channel to begin managing permissions",
            color=0x00AAFF,
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Features:",
            value="• View current permissions\n• Edit role/user permissions\n• Sync with category\n• Visual interface",
            inline=False
        )
        embed.set_footer(text="This editor will not timeout")
    
    msg = await ctx.send(embed=embed, view=view)
    view.message = msg  # Store message reference
    
    # Add view to bot's view registry for persistence
    ctx.bot.add_view(view)
    
    # Mark that permission editor is active for this user
    if not hasattr(ctx.bot, '_perm_editor_active'):
        ctx.bot._perm_editor_active = set()
    ctx.bot._perm_editor_active.add(ctx.author.id)
