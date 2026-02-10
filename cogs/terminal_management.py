"""
BlockForge OS Management Panel
Handles server management operations including channels and backups
"""

import discord
from datetime import datetime
from utils.colors import ANSIColors, format_error
from utils.config import Config

class ManagementPanel:
    """Management panel for server administration"""
    
    def __init__(self, terminal_session):
        self.session = terminal_session
        self.bot = terminal_session.bot
        self.ctx = terminal_session.ctx
        self.db = terminal_session.db
        self.guild = terminal_session.guild
    
    async def handle_command(self, command_lower, user_input):
        """Handle management panel commands"""
        output = ""
        should_exit = False
        
        if command_lower == "exit":
            output = await self.session.handle_exit()
            should_exit = True
        elif command_lower == "back":
            self.session.current_panel = "main"
            self.session.current_path = "System > Root"
            output = f"{ANSIColors.GREEN}Returned to main menu.{ANSIColors.RESET}"
        elif command_lower == "clr":
            output = ""  # Clear handled by caller
        elif command_lower == "help":
            output = self.show_help()
        elif command_lower == "channels":
            self.session.current_panel = "channels"
            self.session.current_path = "Management > Channels"
            output = await self.show_channels_panel()
        elif command_lower == "backup":
            self.session.current_panel = "backup"
            self.session.current_path = "Management > Backup"
            output = await self.show_backup_panel()
        else:
            output = format_error(
                f"Invalid command '{user_input}'. Type 'help' for management commands.",
                Config.ERROR_CODES['INVALID_COMMAND']
            )
        
        return output, should_exit
    
    def show_help(self):
        """Show management panel help"""
        return f"""
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}        {ANSIColors.BOLD}Management Panel Commands{ANSIColors.RESET}        {ANSIColors.CYAN}║{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Sub-Panels:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}channels{ANSIColors.RESET}              Manage server channels
  {ANSIColors.BRIGHT_WHITE}backup{ANSIColors.RESET}                Server backup & restore

{ANSIColors.BRIGHT_CYAN}Navigation:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                  Return to main menu
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}                  Close terminal
  {ANSIColors.BRIGHT_WHITE}clr{ANSIColors.RESET}                   Clear terminal

{ANSIColors.BRIGHT_BLACK}Type a sub-panel name to continue...{ANSIColors.RESET}
"""
    
    async def show_channels_panel(self):
        """Show channels panel introduction"""
        return f"""
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}          {ANSIColors.BOLD}Channel Management{ANSIColors.RESET}             {ANSIColors.CYAN}║{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Available Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}list{ANSIColors.RESET}                  List all channels
  {ANSIColors.BRIGHT_WHITE}delete <id>{ANSIColors.RESET}           Delete a channel
  {ANSIColors.BRIGHT_WHITE}duplicate <id>{ANSIColors.RESET}        Duplicate channel with permissions
  {ANSIColors.BRIGHT_WHITE}rename <id> <name>{ANSIColors.RESET}    Rename a channel
  {ANSIColors.BRIGHT_WHITE}viewperms <id>{ANSIColors.RESET}        View channel permissions
  {ANSIColors.BRIGHT_WHITE}changeperms <id>{ANSIColors.RESET}      Change channel permissions
  
{ANSIColors.BRIGHT_CYAN}Permission Presets:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}preset create <n> <id>{ANSIColors.RESET}   Save permissions as preset
  {ANSIColors.BRIGHT_WHITE}preset set <id> <n>{ANSIColors.RESET}       Apply preset to channel
  {ANSIColors.BRIGHT_WHITE}preset delete <n>{ANSIColors.RESET}         Delete a preset

{ANSIColors.BRIGHT_CYAN}Navigation:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                  Return to management
  {ANSIColors.BRIGHT_WHITE}help{ANSIColors.RESET}                  Show this help

{ANSIColors.BRIGHT_BLACK}Type 'list' to see all channels...{ANSIColors.RESET}
"""
    
    async def show_backup_panel(self):
        """Show backup panel introduction"""
        return f"""
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}            {ANSIColors.BOLD}Backup System{ANSIColors.RESET}               {ANSIColors.CYAN}║{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Backup Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}backup create <name>{ANSIColors.RESET}     Create new backup
  {ANSIColors.BRIGHT_WHITE}backup list{ANSIColors.RESET}             List all backups
  {ANSIColors.BRIGHT_WHITE}backup restore <id>{ANSIColors.RESET}     Restore from backup
  {ANSIColors.BRIGHT_WHITE}backup delete <id>{ANSIColors.RESET}      Delete a backup
  
{ANSIColors.BRIGHT_CYAN}Backup Protection:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}backup lock <id>{ANSIColors.RESET}        Lock backup (prevent delete)
  {ANSIColors.BRIGHT_WHITE}backup unlock <id>{ANSIColors.RESET}      Unlock backup

{ANSIColors.BRIGHT_CYAN}Auto-Backup:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}backup auto <true/false>{ANSIColors.RESET}      Daily auto-backup
  {ANSIColors.BRIGHT_WHITE}backup autooverwrite <t/f>{ANSIColors.RESET}    Overwrite oldest

{ANSIColors.BRIGHT_CYAN}Navigation:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                  Return to management
  {ANSIColors.BRIGHT_WHITE}help{ANSIColors.RESET}                  Show this help

{ANSIColors.YELLOW}⚠️  Maximum 10 backups per server{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Type 'backup list' to see existing backups...{ANSIColors.RESET}
"""
