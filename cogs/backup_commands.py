"""
BlockForge OS Backup Chat Commands
Provides Discord chat commands for backup management
"""

import discord
from discord.ext import commands
from discord.ui import Select, View, Button
from utils.colors import Colors
from utils.config import Config
from datetime import datetime
import asyncio

def is_server_owner():
    """Decorator to check if user is server owner"""
    async def predicate(ctx):
        return ctx.author.id == ctx.guild.owner_id
    return commands.check(predicate)

class BackupSelectView(View):
    """Dropdown for selecting backups"""
    
    def __init__(self, backups, author_id, action='restore'):
        super().__init__(timeout=300)  # 5 minute timeout
        self.backups = backups
        self.author_id = author_id
        self.action = action
        self.selected_backup = None
        
        # Create dropdown options
        options = []
        for backup in backups[:25]:  # Discord max 25 options
            lock_emoji = "🔒" if backup.get('locked') else "🔓"
            options.append(discord.SelectOption(
                label=f"{lock_emoji} {backup['name']}",
                description=f"Created: {backup.get('created_at', 'Unknown')[:10]}",
                value=backup['id']
            ))
        
        select = Select(
            placeholder=f"Select backup to {action}...",
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)
    
    async def select_callback(self, interaction: discord.Interaction):
        """Handle backup selection"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can select.", ephemeral=True)
            return
        
        self.selected_backup = interaction.values[0]
        await interaction.response.edit_message(content=f"✓ Selected backup: **{self.selected_backup}**", view=None)
        self.stop()

class BackupChatCommands(commands.Cog):
    """Chat commands for backup management"""
    
    def __init__(self, bot):
        self.bot = bot
        from utils.database import Database
        self.db = Database()
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{Colors.GREEN}[✓] Backup chat commands loaded{Colors.RESET}")
    
    @commands.command(name='backup')
    @is_server_owner()
    async def backup_main(self, ctx, action: str = None, *, args: str = None):
        """
        Backup management commands
        
        Usage:
          ;backup create <name> - Create a new backup
          ;backup list - List all backups
          ;backup restore - Interactive restore
          ;backup lock <id> - Lock a backup
          ;backup unlock <id> - Unlock a backup
        """
        if not action:
            await ctx.send(embed=self.show_backup_help())
            return
        
        action = action.lower()
        
        if action == 'create':
            if not args:
                await ctx.send("❌ **Usage:** `;backup create <name>`")
                return
            await self.handle_backup_create(ctx, args)
        
        elif action == 'list':
            await self.handle_backup_list(ctx)
        
        elif action == 'restore':
            await self.handle_backup_restore(ctx)
        
        elif action == 'lock':
            if not args:
                await ctx.send("❌ **Usage:** `;backup lock <id>`")
                return
            await self.handle_backup_lock(ctx, args)
        
        elif action == 'unlock':
            if not args:
                await ctx.send("❌ **Usage:** `;backup unlock <id>`")
                return
            await self.handle_backup_unlock(ctx, args)
        
        else:
            await ctx.send(f"❌ Unknown action: **{action}**\n\nUse `;backup` to see available commands.")
    
    def show_backup_help(self):
        """Show backup help embed"""
        embed = discord.Embed(
            title="📦 Backup System",
            description="Manage server backups with these commands:",
            color=0x00AAFF,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name=";backup create <name>",
            value="Create a new backup of the server",
            inline=False
        )
        
        embed.add_field(
            name=";backup list",
            value="List all server backups",
            inline=False
        )
        
        embed.add_field(
            name=";backup restore",
            value="Restore server from a backup (interactive)",
            inline=False
        )
        
        embed.add_field(
            name=";backup lock <id>",
            value="Lock a backup to prevent deletion",
            inline=False
        )
        
        embed.add_field(
            name=";backup unlock <id>",
            value="Unlock a backup",
            inline=False
        )
        
        embed.set_footer(text="Maximum 10 backups per server")
        
        return embed
    
    async def handle_backup_create(self, ctx, backup_name):
        """Create a new backup"""
        # Check backup count
        backups = self.db.get_server_backups(ctx.guild.id)
        if len(backups) >= 10:
            await ctx.send("❌ **Maximum 10 backups reached.** Delete an old backup first.")
            return
        
        # Send initial message
        embed = discord.Embed(
            title="⏳ Creating Backup...",
            description=f"**Name:** {backup_name}",
            color=0xFFAA00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Status", value="► Initializing...", inline=False)
        
        message = await ctx.send(embed=embed)
        
        # Import backup panel for backup logic
        from cogs.terminal_backup import BackupPanel
        
        # Create temporary terminal session object
        class TempSession:
            def __init__(self, bot, ctx, db):
                self.bot = bot
                self.ctx = ctx
                self.db = db
                self.guild = ctx.guild
                self.message = message
            
            async def send_progress_update(self, text, delay=0.5):
                embed.set_field_at(0, name="Status", value=f"► {text}", inline=False)
                await self.message.edit(embed=embed)
                await asyncio.sleep(delay)
        
        temp_session = TempSession(self.bot, ctx, self.db)
        panel = BackupPanel(temp_session)
        
        # Create backup
        try:
            # Collect data
            await temp_session.send_progress_update("Backing up channels...")
            channels_data = await panel.backup_channels()
            
            await temp_session.send_progress_update("Backing up roles...")
            roles_data = await panel.backup_roles()
            
            await temp_session.send_progress_update("Backing up settings...")
            settings_data = await panel.backup_settings()
            
            # Create backup object
            backup_data = {
                'name': backup_name,
                'created_at': datetime.utcnow().isoformat(),
                'channels': channels_data,
                'roles': roles_data,
                'settings': settings_data,
                'locked': False
            }
            
            # Save to database
            backup_id = self.db.create_backup(ctx.guild.id, backup_name, backup_data)
            
            # Success message
            embed = discord.Embed(
                title="✅ Backup Created Successfully!",
                description=f"**Name:** {backup_name}\n**ID:** `{backup_id}`",
                color=0x00FF00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Channels", value=str(len(channels_data)), inline=True)
            embed.add_field(name="Roles", value=str(len(roles_data)), inline=True)
            embed.set_footer(text=f"Backup ID: {backup_id}")
            
            await message.edit(embed=embed)
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ Backup Failed",
                description=f"Error: {str(e)}",
                color=0xFF0000
            )
            await message.edit(embed=embed)
    
    async def handle_backup_list(self, ctx):
        """List all backups"""
        backups = self.db.get_server_backups(ctx.guild.id)
        
        if not backups:
            await ctx.send("❌ **No backups found.** Create one with `;backup create <name>`")
            return
        
        embed = discord.Embed(
            title="📦 Server Backups",
            description=f"**Total:** {len(backups)}/10 backups",
            color=0x00AAFF,
            timestamp=datetime.utcnow()
        )
        
        for i, backup in enumerate(backups, 1):
            lock_emoji = "🔒" if backup.get('locked') else "🔓"
            status = "Locked" if backup.get('locked') else "Unlocked"
            
            embed.add_field(
                name=f"{lock_emoji} {i}. {backup['name']}",
                value=f"**ID:** `{backup['id']}`\n**Created:** {backup.get('created_at', 'Unknown')[:10]}\n**Status:** {status}",
                inline=False
            )
        
        embed.set_footer(text="Use ;backup restore to restore a backup")
        
        await ctx.send(embed=embed)
    
    async def handle_backup_restore(self, ctx):
        """Interactive backup restore"""
        backups = self.db.get_server_backups(ctx.guild.id)
        
        if not backups:
            await ctx.send("❌ **No backups found.** Create one first with `;backup create <name>`")
            return
        
        # Show selection
        embed = discord.Embed(
            title="📦 Select Backup to Restore",
            description="⚠️ **Warning:** Restoring will delete all current channels and roles!",
            color=0xFF0000,
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="⚠️ This Action Will:",
            value="• Delete ALL current channels\n• Delete ALL current roles\n• Reset server settings\n• **Cannot be undone**",
            inline=False
        )
        
        view = BackupSelectView(backups, ctx.author.id, 'restore')
        message = await ctx.send(embed=embed, view=view)
        
        # Wait for selection
        await view.wait()
        
        if not view.selected_backup:
            await message.edit(content="❌ **Selection timed out.** No changes made.", embed=None, view=None)
            return
        
        # Get backup
        backup = self.db.get_backup(ctx.guild.id, view.selected_backup)
        if not backup:
            await message.edit(content="❌ **Backup not found.**", embed=None, view=None)
            return
        
        # Show confirmation
        from cogs.confirmation_system import ConfirmationView
        
        confirm_embed = discord.Embed(
            title="⚠️ Final Confirmation Required",
            description=f"**Restoring:** {backup['name']}\n**Created:** {backup.get('created_at', 'Unknown')[:10]}",
            color=0xFF0000
        )
        confirm_embed.add_field(
            name="⚠️ This Will DELETE:",
            value="• All current channels\n• All current roles\n• Current server settings",
            inline=False
        )
        confirm_embed.add_field(
            name="Confirmation Required",
            value="Click **✓ Confirm** to proceed or **✗ Cancel** to abort.",
            inline=False
        )
        
        confirm_view = ConfirmationView(ctx.author.id, timeout=60)
        await message.edit(embed=confirm_embed, view=confirm_view)
        confirm_view.message = message
        
        await confirm_view.wait()
        
        if not confirm_view.confirmed:
            return  # Already handled by ConfirmationView
        
        # Execute restore
        from cogs.confirmation_system import BackupRestoreSystem
        restore_system = BackupRestoreSystem(self.bot, self.db)
        
        # Progress callback
        async def update_progress(text):
            progress_embed = discord.Embed(
                title="⏳ Restoring Backup...",
                description=f"**{backup['name']}**",
                color=0xFFAA00
            )
            progress_embed.add_field(name="Status", value=f"► {text}", inline=False)
            await message.edit(embed=progress_embed, view=None)
        
        success, result_message = await restore_system.restore_backup(
            ctx.guild,
            backup['data'],
            progress_callback=update_progress
        )
        
        if success:
            final_embed = discord.Embed(
                title="✅ Backup Restored Successfully!",
                description=f"**{backup['name']}** has been restored.",
                color=0x00FF00
            )
            final_embed.add_field(name="Status", value="All channels, roles, and settings have been restored.", inline=False)
            await message.edit(embed=final_embed)
        else:
            error_embed = discord.Embed(
                title="❌ Restore Failed",
                description=result_message,
                color=0xFF0000
            )
            await message.edit(embed=error_embed)
    
    async def handle_backup_lock(self, ctx, backup_id):
        """Lock a backup"""
        success = self.db.set_backup_lock(ctx.guild.id, backup_id, True)
        
        if success:
            await ctx.send(f"✅ **Backup locked:** `{backup_id}`\nThis backup cannot be deleted or overwritten.")
        else:
            await ctx.send(f"❌ **Backup not found:** `{backup_id}`")
    
    async def handle_backup_unlock(self, ctx, backup_id):
        """Unlock a backup"""
        success = self.db.set_backup_lock(ctx.guild.id, backup_id, False)
        
        if success:
            await ctx.send(f"✅ **Backup unlocked:** `{backup_id}`")
        else:
            await ctx.send(f"❌ **Backup not found:** `{backup_id}`")

async def setup(bot):
    await bot.add_cog(BackupChatCommands(bot))
