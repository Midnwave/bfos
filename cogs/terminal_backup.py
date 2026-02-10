"""
BlockForge OS Backup Panel
Terminal interface for the comprehensive backup system
"""

import discord
import asyncio
from datetime import datetime
from utils.colors import ANSIColors, format_error
from utils.config import Config


class BackupPanel:
    """Backup system terminal panel"""
    
    def __init__(self, terminal_session):
        self.session = terminal_session
        self.bot = terminal_session.bot
        self.ctx = terminal_session.ctx
        self.db = terminal_session.db
        self.guild = terminal_session.guild
        
        # Import the comprehensive backup system
        try:
            from cogs.backup_system import ComprehensiveBackupSystem
            self.backup_system = ComprehensiveBackupSystem(self.bot, self.db)
        except Exception as e:
            print(f"[BACKUP PANEL] Failed to load backup system: {e}")
            self.backup_system = None
    
    async def handle_command(self, command_lower, user_input):
        """Handle backup panel commands"""
        output = ""
        should_exit = False
        
        # Handle navigation first (no prefix needed)
        if command_lower == "exit":
            output = await self.session.handle_exit()
            should_exit = True
        elif command_lower == "back":
            self.session.current_panel = "management"
            self.session.current_path = "Management"
            output = f"{ANSIColors.GREEN}Returned to management panel.{ANSIColors.RESET}"
        elif command_lower == "clr" or command_lower == "clear":
            self.session.command_history = []
            output = ""
        elif command_lower == "help":
            output = self.show_help()
        # Backup commands require "backup" prefix
        elif command_lower.startswith("backup "):
            # Get the sub-command after "backup "
            sub_command = command_lower[7:]
            sub_input = user_input[7:].strip() if len(user_input) > 7 else ""
            
            if sub_command.startswith("create "):
                backup_name = sub_input[7:].strip()
                if backup_name:
                    output = await self.handle_backup_create(backup_name)
                else:
                    output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} backup create <backup_name>"
            elif sub_command == "create":
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} backup create <backup_name>\n{ANSIColors.BRIGHT_BLACK}Example: backup create Daily Backup{ANSIColors.RESET}"
            elif sub_command == "list":
                output = await self.handle_backup_list()
            elif sub_command.startswith("info "):
                backup_id = sub_input[5:].strip()
                output = await self.handle_backup_info(backup_id)
            elif sub_command.startswith("restore "):
                # Parse backup ID and flags
                restore_args = sub_input[8:].strip()
                parts = restore_args.split()
                backup_id = parts[0] if parts else ""
                
                # Parse flags
                keep_channels = "--keepcurrentchannels" in restore_args.lower() or "--keepchannels" in restore_args.lower()
                keep_roles = "--keepcurrentroles" in restore_args.lower() or "--keeproles" in restore_args.lower()
                
                if backup_id and not backup_id.startswith("--"):
                    output = await self.handle_backup_restore_confirm(backup_id, keep_channels, keep_roles)
                else:
                    output = f"""{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} backup restore <backup_id> [flags]

{ANSIColors.BRIGHT_CYAN}Flags:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}--keepcurrentchannels{ANSIColors.RESET}  Don't delete channels created after backup
  {ANSIColors.BRIGHT_WHITE}--keepcurrentroles{ANSIColors.RESET}     Don't delete roles created after backup

{ANSIColors.BRIGHT_BLACK}Example: backup restore abc123 --keepcurrentchannels{ANSIColors.RESET}"""
            elif sub_command.startswith("delete "):
                backup_id = sub_input[7:].strip()
                output = await self.handle_backup_delete_confirm(backup_id)
            elif sub_command.startswith("lock "):
                backup_id = sub_input[5:].strip()
                output = await self.handle_backup_lock(backup_id, True)
            elif sub_command.startswith("unlock "):
                backup_id = sub_input[7:].strip()
                output = await self.handle_backup_lock(backup_id, False)
            elif sub_command.startswith("import "):
                backup_id = sub_input[7:].strip()
                output = await self.handle_backup_import(backup_id)
            else:
                output = format_error(
                    f"Unknown backup command. Type 'help' for commands.",
                    Config.ERROR_CODES['INVALID_COMMAND']
                )
        else:
            output = format_error(
                f"Unknown command '{user_input}'. Commands start with 'backup'. Type 'help' for commands.",
                Config.ERROR_CODES['INVALID_COMMAND']
            )
        
        return output, should_exit
    
    def show_help(self):
        """Show backup panel help"""
        return f"""
{ANSIColors.BRIGHT_YELLOW}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.BRIGHT_YELLOW}║{ANSIColors.RESET}      Comprehensive Backup System
{ANSIColors.BRIGHT_YELLOW}{'═' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Backup Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}backup create <n>{ANSIColors.RESET}     Create full server backup
  {ANSIColors.BRIGHT_WHITE}backup list{ANSIColors.RESET}              List all backups
  {ANSIColors.BRIGHT_WHITE}backup info <id>{ANSIColors.RESET}         View backup details
  {ANSIColors.BRIGHT_WHITE}backup restore <id>{ANSIColors.RESET}      Restore a backup
  {ANSIColors.BRIGHT_WHITE}backup delete <id>{ANSIColors.RESET}       Delete a backup
  {ANSIColors.BRIGHT_WHITE}backup lock <id>{ANSIColors.RESET}         Lock (prevent delete)
  {ANSIColors.BRIGHT_WHITE}backup unlock <id>{ANSIColors.RESET}       Unlock backup
  {ANSIColors.BRIGHT_WHITE}backup import <id>{ANSIColors.RESET}       Import from another server

{ANSIColors.BRIGHT_CYAN}Restore Flags:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}--keepcurrentchannels{ANSIColors.RESET}    Keep new channels made after backup
  {ANSIColors.BRIGHT_WHITE}--keepcurrentroles{ANSIColors.RESET}       Keep new roles made after backup
  
  {ANSIColors.BRIGHT_BLACK}Example: backup restore abc123 --keepcurrentchannels{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}What Gets Backed Up:{ANSIColors.RESET}
  {ANSIColors.GREEN}✓{ANSIColors.RESET} Server settings (icon, banner, name)
  {ANSIColors.GREEN}✓{ANSIColors.RESET} All roles with permissions & icons
  {ANSIColors.GREEN}✓{ANSIColors.RESET} All channels with permissions
  {ANSIColors.GREEN}✓{ANSIColors.RESET} Categories and channel order
  {ANSIColors.GREEN}✓{ANSIColors.RESET} Custom emojis (with images)
  {ANSIColors.GREEN}✓{ANSIColors.RESET} Stickers (with images)
  {ANSIColors.GREEN}✓{ANSIColors.RESET} Verification & content filter settings

{ANSIColors.BRIGHT_CYAN}Navigation:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                     Return to management
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}                     Exit terminal

{ANSIColors.BRIGHT_BLACK}Rate limiting is handled automatically.{ANSIColors.RESET}
"""
    
    def _format_size(self, size_bytes):
        """Format bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    async def handle_backup_create(self, backup_name):
        """Create a comprehensive backup"""
        if not self.backup_system:
            return f"{ANSIColors.RED}❌ Backup system not available.{ANSIColors.RESET}"
        
        # Block other commands during backup
        self.session.operation_in_progress = True
        
        # Progress callback to update terminal
        async def progress_callback(message):
            await self.session.send_progress_update(message, delay=0.8)
        
        try:
            success, message, backup_id = await self.backup_system.create_backup(
                self.guild,
                backup_name,
                progress_callback
            )
            
            if success:
                # Log to logging module
                logging_cog = self.session.bot.get_cog('LoggingModule')
                if logging_cog:
                    await logging_cog.log_bfos_action(
                        self.guild, 'backup', self.session.ctx.author,
                        f"Backup **{backup_name}** was created",
                        {'Backup ID': backup_id, 'Backup Name': backup_name, 'Action': 'Created'}
                    )
                
                return f"""
{ANSIColors.GREEN}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.GREEN}✓{ANSIColors.RESET} Backup Created Successfully!
{ANSIColors.GREEN}{'═' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Backup ID:{ANSIColors.RESET}    {ANSIColors.BRIGHT_WHITE}{backup_id}{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}Name:{ANSIColors.RESET}         {backup_name}
{ANSIColors.BRIGHT_CYAN}Server:{ANSIColors.RESET}       {self.guild.name}
{ANSIColors.BRIGHT_CYAN}Created:{ANSIColors.RESET}      {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

{ANSIColors.BRIGHT_BLACK}Use 'backup info {backup_id}' for details or 'backup list' to see all.{ANSIColors.RESET}
"""
            else:
                return f"{ANSIColors.RED}❌ {message}{ANSIColors.RESET}"
        finally:
            # Always unblock commands when done
            self.session.operation_in_progress = False
    
    async def handle_backup_list(self):
        """List all backups"""
        backups = self.db.list_comprehensive_backups(self.guild.id)
        
        if not backups:
            return f"""
{ANSIColors.BRIGHT_YELLOW}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.BRIGHT_YELLOW}║{ANSIColors.RESET}              No Backups Found
{ANSIColors.BRIGHT_YELLOW}{'═' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Create your first backup with:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}backup create <n>{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Example: backup create Daily Backup{ANSIColors.RESET}
"""
        
        output = f"""
{ANSIColors.BRIGHT_YELLOW}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.BRIGHT_YELLOW}║{ANSIColors.RESET}              Server Backups ({len(backups)})
{ANSIColors.BRIGHT_YELLOW}{'═' * 50}{ANSIColors.RESET}

"""
        
        for backup in backups:
            lock_icon = "🔒" if backup['locked'] else ""
            import_tag = f" {ANSIColors.BRIGHT_BLACK}[Imported]{ANSIColors.RESET}" if backup['imported_from'] else ""
            size = self._format_size(backup['file_size_bytes'])
            
            # Format date
            created = backup['created_at']
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except:
                    pass
            date_str = created.strftime('%Y-%m-%d %H:%M') if isinstance(created, datetime) else str(created)
            
            output += f"""  {ANSIColors.BRIGHT_WHITE}{backup['backup_id']}{ANSIColors.RESET} {lock_icon}{import_tag}
    {ANSIColors.BRIGHT_CYAN}Name:{ANSIColors.RESET} {backup['name']}
    {ANSIColors.BRIGHT_CYAN}Size:{ANSIColors.RESET} {size} | {ANSIColors.BRIGHT_CYAN}Roles:{ANSIColors.RESET} {backup['roles_count']} | {ANSIColors.BRIGHT_CYAN}Channels:{ANSIColors.RESET} {backup['channels_count']}
    {ANSIColors.BRIGHT_BLACK}{date_str}{ANSIColors.RESET}

"""
        
        output += f"{ANSIColors.BRIGHT_BLACK}Use 'backup info <id>' for details or 'backup restore <id>' to restore.{ANSIColors.RESET}"
        
        return output
    
    async def handle_backup_info(self, backup_id):
        """Show detailed backup info"""
        backup_data = self.db.get_comprehensive_backup(self.guild.id, backup_id)
        
        if not backup_data:
            return f"{ANSIColors.RED}❌ Backup not found: {backup_id}{ANSIColors.RESET}"
        
        size = self._format_size(backup_data.get('file_size_bytes', 0))
        roles = len(backup_data.get('roles', []))
        categories = len(backup_data.get('categories', []))
        channels = len(backup_data.get('channels', []))
        emojis = len(backup_data.get('emojis', []))
        stickers = len(backup_data.get('stickers', []))
        
        return f"""
{ANSIColors.BRIGHT_CYAN}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}              Backup Details
{ANSIColors.BRIGHT_CYAN}{'═' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_WHITE}Backup ID:{ANSIColors.RESET}        {backup_id}
{ANSIColors.BRIGHT_WHITE}Server Name:{ANSIColors.RESET}      {backup_data.get('guild_name', 'Unknown')}
{ANSIColors.BRIGHT_WHITE}Created:{ANSIColors.RESET}          {backup_data.get('created_at', 'Unknown')}
{ANSIColors.BRIGHT_WHITE}Total Size:{ANSIColors.RESET}       {size}

{ANSIColors.BRIGHT_CYAN}Contents:{ANSIColors.RESET}
  {ANSIColors.GREEN}►{ANSIColors.RESET} Roles:        {roles}
  {ANSIColors.GREEN}►{ANSIColors.RESET} Categories:   {categories}
  {ANSIColors.GREEN}►{ANSIColors.RESET} Channels:     {channels}
  {ANSIColors.GREEN}►{ANSIColors.RESET} Emojis:       {emojis}
  {ANSIColors.GREEN}►{ANSIColors.RESET} Stickers:     {stickers}

{ANSIColors.BRIGHT_CYAN}Server Settings:{ANSIColors.RESET}
  {ANSIColors.GREEN}►{ANSIColors.RESET} Icon:         {'✓' if backup_data.get('icon_path') else '✗'}
  {ANSIColors.GREEN}►{ANSIColors.RESET} Banner:       {'✓' if backup_data.get('banner_path') else '✗'}
  {ANSIColors.GREEN}►{ANSIColors.RESET} Description:  {'✓' if backup_data.get('description') else '✗'}

{ANSIColors.BRIGHT_BLACK}Use 'backup restore {backup_id}' to restore this backup.{ANSIColors.RESET}
"""
    
    async def handle_backup_restore_confirm(self, backup_id, keep_channels=False, keep_roles=False):
        """Show confirmation before restore"""
        backup_data = self.db.get_comprehensive_backup(self.guild.id, backup_id)
        
        if not backup_data:
            return f"{ANSIColors.RED}❌ Backup not found: {backup_id}{ANSIColors.RESET}"
        
        from cogs.confirmation_system import ConfirmationSystem
        
        details = {
            'backup_id': backup_id,
            'backup_name': backup_data.get('guild_name', 'Unknown'),
            'created_at': backup_data.get('created_at', 'Unknown'),
            'keep_channels': keep_channels,
            'keep_roles': keep_roles
        }
        
        # Build flags info
        flags_info = ""
        if keep_channels or keep_roles:
            flags_info = f"\n  {ANSIColors.BRIGHT_CYAN}Active Flags:{ANSIColors.RESET}"
            if keep_channels:
                flags_info += f"\n  {ANSIColors.GREEN}✓ --keepcurrentchannels{ANSIColors.RESET} (new channels preserved)"
            if keep_roles:
                flags_info += f"\n  {ANSIColors.GREEN}✓ --keepcurrentroles{ANSIColors.RESET} (new roles preserved)"
            flags_info += "\n"
        
        warning = f"""  {ANSIColors.BRIGHT_RED}⚠️ This restore will:{ANSIColors.RESET}
  {ANSIColors.YELLOW}• Restore channels from backup (non-matching {'kept' if keep_channels else 'deleted'}){ANSIColors.RESET}
  {ANSIColors.YELLOW}• Restore roles from backup (non-matching {'kept' if keep_roles else 'deleted'}){ANSIColors.RESET}
  {ANSIColors.YELLOW}• Restore server settings from backup time{ANSIColors.RESET}
  {flags_info}
  {ANSIColors.GREEN}✓ This terminal channel will be preserved{ANSIColors.RESET}
  {ANSIColors.GREEN}✓ Items matching by ID or name will be updated{ANSIColors.RESET}
  {ANSIColors.GREEN}✓ Bot roles are never touched{ANSIColors.RESET}
  
  {ANSIColors.BRIGHT_YELLOW}⚠️ TIP: Move bot's role to TOP of role list for best results{ANSIColors.RESET}
  
  {ANSIColors.BRIGHT_BLACK}Create a safety backup first: 'backup create Pre-Restore'{ANSIColors.RESET}"""
        
        return await ConfirmationSystem.confirm_terminal_action(
            self.session,
            'backup_restore',
            details,
            warning
        )
    
    async def execute_backup_restore(self, backup_id, keep_channels=False, keep_roles=False):
        """Execute the backup restore"""
        if not self.backup_system:
            return f"{ANSIColors.RED}❌ Backup system not available.{ANSIColors.RESET}"
        
        # Block other commands during restore
        self.session.operation_in_progress = True
        
        async def progress_callback(message):
            await self.session.send_progress_update(message, delay=0.8)
        
        try:
            # Get the terminal channel ID to exclude from deletion
            terminal_channel_id = self.session.channel.id if self.session.channel else None
            
            success, message = await self.backup_system.restore_backup(
                self.guild,
                backup_id,
                progress_callback,
                exclude_channel_id=terminal_channel_id,
                keep_current_channels=keep_channels,
                keep_current_roles=keep_roles
            )
            
            if success:
                # Log to logging module
                logging_cog = self.session.bot.get_cog('LoggingModule')
                if logging_cog:
                    await logging_cog.log_bfos_action(
                        self.guild, 'backup', self.session.ctx.author,
                        f"Backup **{backup_id}** was restored",
                        {'Backup ID': backup_id, 'Action': 'Restored', 'Keep Channels': str(keep_channels), 'Keep Roles': str(keep_roles)}
                    )
                
                return f"""
{ANSIColors.GREEN}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.GREEN}✓{ANSIColors.RESET} Backup Restored Successfully!
{ANSIColors.GREEN}{'═' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}All roles, channels, and settings have been restored.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Note: Terminal channel was preserved during restore.{ANSIColors.RESET}
"""
            else:
                return f"{ANSIColors.RED}❌ Restore failed: {message}{ANSIColors.RESET}"
        finally:
            # Always unblock commands when done
            self.session.operation_in_progress = False
    
    async def handle_backup_delete_confirm(self, backup_id):
        """Show confirmation before delete"""
        backup_data = self.db.get_comprehensive_backup(self.guild.id, backup_id)
        
        if not backup_data:
            return f"{ANSIColors.RED}❌ Backup not found: {backup_id}{ANSIColors.RESET}"
        
        # Check if locked
        backups = self.db.list_comprehensive_backups(self.guild.id)
        backup_info = next((b for b in backups if b['backup_id'] == backup_id), None)
        if backup_info and backup_info.get('locked'):
            return f"{ANSIColors.RED}❌ Cannot delete locked backup. Use 'backup unlock {backup_id}' first.{ANSIColors.RESET}"
        
        from cogs.confirmation_system import ConfirmationSystem
        
        details = {
            'backup_id': backup_id,
            'backup_name': backup_data.get('guild_name', 'Unknown'),
            'created_at': backup_data.get('created_at', 'Unknown')
        }
        
        return await ConfirmationSystem.confirm_terminal_action(
            self.session,
            'backup_delete',
            details,
            f"{ANSIColors.YELLOW}This backup will be permanently deleted.{ANSIColors.RESET}"
        )
    
    async def execute_backup_delete(self, backup_id):
        """Execute backup deletion"""
        if not self.backup_system:
            return f"{ANSIColors.RED}❌ Backup system not available.{ANSIColors.RESET}"
        
        success = self.backup_system.delete_backup(self.guild.id, backup_id)
        
        if success:
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Backup {ANSIColors.BRIGHT_WHITE}{backup_id}{ANSIColors.RESET} deleted successfully."
        else:
            return f"{ANSIColors.RED}❌ Failed to delete backup.{ANSIColors.RESET}"
    
    async def handle_backup_lock(self, backup_id, lock=True):
        """Lock or unlock a backup"""
        success = self.db.lock_comprehensive_backup(self.guild.id, backup_id, lock)
        
        if success:
            status = "locked 🔒" if lock else "unlocked 🔓"
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Backup {ANSIColors.BRIGHT_WHITE}{backup_id}{ANSIColors.RESET} {status}."
        else:
            return f"{ANSIColors.RED}❌ Backup not found: {backup_id}{ANSIColors.RESET}"
    
    async def handle_backup_import(self, backup_id):
        """Import a backup from another server"""
        if not self.backup_system:
            return f"{ANSIColors.RED}❌ Backup system not available.{ANSIColors.RESET}"
        
        success, message = await self.backup_system.import_backup(self.guild.id, backup_id)
        
        if success:
            return f"""
{ANSIColors.GREEN}✓{ANSIColors.RESET} Backup Imported Successfully!

{ANSIColors.BRIGHT_BLACK}{message}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Use 'backup list' to see the imported backup.{ANSIColors.RESET}
"""
        else:
            return f"{ANSIColors.RED}❌ {message}{ANSIColors.RESET}"
