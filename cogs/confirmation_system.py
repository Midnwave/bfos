"""
BlockForge OS Confirmation System
Handles confirmation dialogs for destructive actions
"""

import discord
from discord.ui import Button, View
import asyncio
from datetime import datetime
from utils.colors import ANSIColors

class ConfirmationView(View):
    """Confirmation button view"""
    
    def __init__(self, author_id, timeout=60):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.confirmed = None
        self.message = None
    
    @discord.ui.button(label="✓ Confirm", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        """Confirm action"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can confirm.", ephemeral=True)
            return
        
        self.confirmed = True
        self.stop()
        await interaction.response.edit_message(content="✓ **Confirmed!** Processing...", view=None)
    
    @discord.ui.button(label="✗ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        """Cancel action"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can cancel.", ephemeral=True)
            return
        
        self.confirmed = False
        self.stop()
        await interaction.response.edit_message(content="✗ **Cancelled.** No changes made.", view=None)
    
    async def on_timeout(self):
        """Handle timeout"""
        self.confirmed = False
        if self.message:
            try:
                await self.message.edit(content="⏱️ **Confirmation timed out.** No changes made.", view=None)
            except:
                pass

class ConfirmationSystem:
    """Handles all confirmation dialogs"""
    
    @staticmethod
    async def confirm_action(ctx, title, description, warning=None, timeout=60):
        """
        Show confirmation dialog and wait for response
        
        Returns: True if confirmed, False if cancelled/timeout
        """
        embed = discord.Embed(
            title=f"⚠️ {title}",
            description=description,
            color=0xFF0000,
            timestamp=datetime.utcnow()
        )
        
        if warning:
            embed.add_field(
                name="⚠️ Warning",
                value=warning,
                inline=False
            )
        
        embed.add_field(
            name="Confirmation Required",
            value="Click **✓ Confirm** to proceed or **✗ Cancel** to abort.",
            inline=False
        )
        
        embed.set_footer(text=f"Timeout: {timeout}s")
        
        # Create view
        view = ConfirmationView(ctx.author.id, timeout=timeout)
        
        # Send message
        message = await ctx.send(embed=embed, view=view)
        view.message = message
        
        # Wait for response
        await view.wait()
        
        return view.confirmed == True
    
    @staticmethod
    async def confirm_terminal_action(session, action_name, details, warning=None):
        """
        Show confirmation in terminal format
        
        Returns: True if confirmed, False if cancelled
        """
        # Store confirmation request
        session.pending_confirmation = {
            'action': action_name,
            'details': details,
            'warning': warning
        }
        
        output = f"""
{ANSIColors.RED}{'━' * 46}{ANSIColors.RESET}
{ANSIColors.RED}║{ANSIColors.RESET}            {ANSIColors.BOLD}CONFIRMATION REQUIRED{ANSIColors.RESET}           {ANSIColors.RED}║{ANSIColors.RESET}
{ANSIColors.RED}{'━' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_RED}Action:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}{action_name}{ANSIColors.RESET}
"""
        
        if details:
            output += f"\n{ANSIColors.BRIGHT_CYAN}Details:{ANSIColors.RESET}\n"
            for key, value in details.items():
                output += f"  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {key}: {ANSIColors.BRIGHT_WHITE}{value}{ANSIColors.RESET}\n"
        
        if warning:
            output += f"""
{ANSIColors.YELLOW}⚠️  Warning:{ANSIColors.RESET}
{warning}
"""
        
        output += f"""
{ANSIColors.BRIGHT_WHITE}Type 'confirm' to proceed or 'cancel' to abort{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}This confirmation will timeout in 60 seconds{ANSIColors.RESET}
"""
        
        return output
    
    @staticmethod
    def handle_terminal_confirmation(session, user_input):
        """
        Handle confirmation response in terminal
        
        Returns: (confirmed, action_data) or (None, None) if no pending
        """
        if not session.pending_confirmation:
            return None, None
        
        command_lower = user_input.lower().strip()
        
        if command_lower == "confirm":
            action_data = session.pending_confirmation
            session.pending_confirmation = None
            return True, action_data
        elif command_lower == "cancel":
            session.pending_confirmation = None
            return False, None
        else:
            # Still waiting for confirmation
            return None, session.pending_confirmation

class BackupRestoreSystem:
    """Handles backup restore operations"""
    
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
    
    async def restore_backup(self, guild, backup_data, progress_callback=None):
        """
        Restore a backup
        
        Args:
            guild: Discord Guild object
            backup_data: Backup data dictionary
            progress_callback: async function to call for progress updates
        
        Returns: (success, message)
        """
        try:
            if progress_callback:
                await progress_callback("🗑️ Deleting existing channels...")
            
            # Delete all existing channels
            for channel in guild.channels:
                try:
                    await channel.delete(reason="Backup restore")
                    await asyncio.sleep(0.5)  # Rate limit protection
                except:
                    pass
            
            if progress_callback:
                await progress_callback("🗑️ Deleting existing roles...")
            
            # Delete all existing roles (except @everyone)
            for role in guild.roles:
                if not role.is_default():
                    try:
                        await role.delete(reason="Backup restore")
                        await asyncio.sleep(0.3)  # Rate limit protection
                    except:
                        pass
            
            if progress_callback:
                await progress_callback("🎭 Restoring roles...")
            
            # Restore roles
            role_map = {}  # Map old IDs to new roles
            for role_data in backup_data.get('roles', []):
                try:
                    permissions = discord.Permissions(role_data['permissions'])
                    color = discord.Color(role_data['color'])
                    
                    new_role = await guild.create_role(
                        name=role_data['name'],
                        permissions=permissions,
                        color=color,
                        hoist=role_data['hoist'],
                        mentionable=role_data['mentionable'],
                        reason="Backup restore"
                    )
                    
                    role_map[role_data['id']] = new_role
                    await asyncio.sleep(0.3)
                except Exception as e:
                    print(f"Failed to restore role {role_data['name']}: {e}")
            
            if progress_callback:
                await progress_callback("📁 Restoring categories...")
            
            # Restore categories first
            category_map = {}
            channels_data = backup_data.get('channels', [])
            
            for channel_data in channels_data:
                if channel_data.get('is_category'):
                    try:
                        new_category = await guild.create_category(
                            name=channel_data['name'],
                            position=channel_data['position'],
                            reason="Backup restore"
                        )
                        category_map[channel_data['id']] = new_category
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        print(f"Failed to restore category {channel_data['name']}: {e}")
            
            if progress_callback:
                await progress_callback("💬 Restoring channels...")
            
            # Restore channels
            for channel_data in channels_data:
                if channel_data.get('is_category'):
                    continue  # Already created
                
                try:
                    # Get category if exists
                    category = None
                    if channel_data.get('category_id'):
                        category = category_map.get(channel_data['category_id'])
                    
                    # Build overwrites
                    overwrites = {}
                    for target_id, overwrite_data in channel_data.get('overwrites', {}).items():
                        if overwrite_data['type'] == 'role':
                            target = role_map.get(target_id) or guild.default_role
                        else:
                            continue  # Skip member overwrites
                        
                        allow = discord.Permissions(overwrite_data['allow'])
                        deny = discord.Permissions(overwrite_data['deny'])
                        overwrites[target] = discord.PermissionOverwrite.from_pair(allow, deny)
                    
                    # Create channel based on type
                    if channel_data['type'] == 'text':
                        await guild.create_text_channel(
                            name=channel_data['name'],
                            category=category,
                            overwrites=overwrites,
                            position=channel_data['position'],
                            topic=channel_data.get('topic'),
                            slowmode_delay=channel_data.get('slowmode_delay', 0),
                            nsfw=channel_data.get('nsfw', False),
                            reason="Backup restore"
                        )
                    elif channel_data['type'] == 'voice':
                        await guild.create_voice_channel(
                            name=channel_data['name'],
                            category=category,
                            overwrites=overwrites,
                            position=channel_data['position'],
                            bitrate=channel_data.get('bitrate', 64000),
                            user_limit=channel_data.get('user_limit', 0),
                            reason="Backup restore"
                        )
                    
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Failed to restore channel {channel_data['name']}: {e}")
            
            if progress_callback:
                await progress_callback("⚙️ Restoring settings...")
            
            # Restore server settings
            settings = backup_data.get('settings', {})
            try:
                if settings.get('name'):
                    await guild.edit(name=settings['name'])
            except:
                pass
            
            if progress_callback:
                await progress_callback("✅ Restore complete!")
            
            return True, "Backup restored successfully"
        
        except Exception as e:
            return False, f"Restore failed: {str(e)}"
