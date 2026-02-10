"""
BlockForge OS Terminal Logging Panel
Configuration interface for the logging module
"""

import discord
import asyncio
from datetime import datetime
from utils.colors import ANSIColors, format_ansi, format_error, format_success, format_warning
from utils.config import Config


class LoggingPanel:
    """Terminal panel for logging configuration"""
    
    def __init__(self, session):
        self.session = session
        self.guild = session.guild
        self.ctx = session.ctx
        self.db = session.db
        
        # Get logging cog
        self.logging_cog = None
        try:
            self.logging_cog = session.bot.get_cog('LoggingModule')
        except:
            pass
    
    async def handle_command(self, command_lower, user_input):
        """Handle logging panel commands"""
        output = ""
        should_exit = False
        
        if command_lower == "exit":
            output = await self.session.handle_exit()
            should_exit = True
        elif command_lower == "back":
            self.session.current_panel = "config"
            self.session.current_path = "System > Config"
            output = f"{ANSIColors.GREEN}Returned to config panel.{ANSIColors.RESET}"
        elif command_lower == "clr" or command_lower == "clear":
            self.session.command_history = []
            output = ""
        elif command_lower == "help":
            output = self.show_help()
        elif command_lower == "list":
            output = await self.show_logging_list_animated()
        elif command_lower.startswith("enable "):
            log_type = command_lower[7:].strip()
            output = await self.handle_enable(log_type, True)
        elif command_lower.startswith("disable "):
            log_type = command_lower[8:].strip()
            output = await self.handle_enable(log_type, False)
        elif command_lower.startswith("setchannel "):
            parts = user_input[11:].strip().split()
            if len(parts) >= 2:
                log_type = parts[0].lower()
                channel_id = parts[1]
                output = await self.handle_set_channel(log_type, channel_id)
            else:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} setchannel <log_type|category> <channel_id>\n{ANSIColors.BRIGHT_BLACK}Categories: messages, members, roles, channels, server, voice, moderation, bfos{ANSIColors.RESET}"
        elif command_lower.startswith("enableall"):
            output = await self.handle_enable_all(True)
        elif command_lower.startswith("disableall"):
            output = await self.handle_enable_all(False)
        elif command_lower.startswith("setchannelall "):
            channel_id = user_input[14:].strip()
            output = await self.handle_set_channel_all(channel_id)
        else:
            output = format_error(
                f"Unknown command '{user_input}'. Type 'help' for commands.",
                Config.ERROR_CODES['INVALID_COMMAND']
            )
        
        return output, should_exit
    
    def show_help(self):
        """Show logging panel help"""
        return f"""
{ANSIColors.BRIGHT_YELLOW}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.BRIGHT_YELLOW}║{ANSIColors.RESET}      Logging Configuration
{ANSIColors.BRIGHT_YELLOW}{'═' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}list{ANSIColors.RESET}                      List all log types
  {ANSIColors.BRIGHT_WHITE}enable <type>{ANSIColors.RESET}             Enable a log type
  {ANSIColors.BRIGHT_WHITE}disable <type>{ANSIColors.RESET}            Disable a log type
  {ANSIColors.BRIGHT_WHITE}setchannel <type> <id>{ANSIColors.RESET}    Set log channel
  {ANSIColors.BRIGHT_WHITE}enableall{ANSIColors.RESET}                 Enable all log types
  {ANSIColors.BRIGHT_WHITE}disableall{ANSIColors.RESET}                Disable all log types
  {ANSIColors.BRIGHT_WHITE}setchannelall <id>{ANSIColors.RESET}        Set channel for all types

{ANSIColors.BRIGHT_CYAN}Log Categories:{ANSIColors.RESET}
  {ANSIColors.GREEN}►{ANSIColors.RESET} messages     - Message edits, deletes, bulk deletes
  {ANSIColors.GREEN}►{ANSIColors.RESET} members      - Joins, leaves, bans, kicks, updates
  {ANSIColors.GREEN}►{ANSIColors.RESET} roles        - Role creates, deletes, updates
  {ANSIColors.GREEN}►{ANSIColors.RESET} channels     - Channel creates, deletes, updates
  {ANSIColors.GREEN}►{ANSIColors.RESET} server       - Server settings, emojis, stickers
  {ANSIColors.GREEN}►{ANSIColors.RESET} voice        - Voice joins, leaves, mutes
  {ANSIColors.GREEN}►{ANSIColors.RESET} moderation   - Warns, bans, kicks, purges
  {ANSIColors.GREEN}►{ANSIColors.RESET} bfos         - BFOS actions, backups, settings

{ANSIColors.BRIGHT_BLACK}Tip: Use category name with setchannel to set all types in that category{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Example: setchannel messages 123456789{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Navigation:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                      Return to config
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}                      Exit terminal
"""
    
    async def show_logging_list_animated(self):
        """Show all logging types with animation"""
        if not self.logging_cog:
            return f"{ANSIColors.RED}❌ Logging module not loaded.{ANSIColors.RESET}"
        
        # Check if module is enabled
        if not self.db.is_module_enabled(self.guild.id, 'logging'):
            return f"""
{ANSIColors.RED}❌ Logging Module Disabled{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Enable it first:{ANSIColors.RESET}
  1. Type 'back' to return to config
  2. Type 'back' again to return to main
  3. Type 'modules'
  4. Type 'module enable logging'
"""
        
        config = self.logging_cog.get_all_config(self.guild.id)
        
        # Build categories list for animation
        categories = []
        for category, types in self.logging_cog.LOGGING_TYPES.items():
            cat_lines = [f"{ANSIColors.BRIGHT_CYAN}━━━ {category.upper()} ━━━{ANSIColors.RESET}"]
            
            for log_type, display_name in types.items():
                type_config = config.get(log_type, {'enabled': False, 'channel_id': None})
                status = f"{ANSIColors.GREEN}●{ANSIColors.RESET}" if type_config['enabled'] else f"{ANSIColors.RED}○{ANSIColors.RESET}"
                
                channel_text = ""
                if type_config['channel_id']:
                    channel = self.guild.get_channel(type_config['channel_id'])
                    if channel:
                        channel_text = f" → #{channel.name}"
                    else:
                        channel_text = f" → (invalid)"
                else:
                    channel_text = f" → {ANSIColors.BRIGHT_BLACK}not set{ANSIColors.RESET}"
                
                cat_lines.append(f"  {status} {ANSIColors.BRIGHT_WHITE}{log_type:<20}{ANSIColors.RESET}{channel_text}")
            
            categories.append("\n".join(cat_lines))
        
        # Use session's animated list display
        header = f"""
{ANSIColors.BRIGHT_YELLOW}{'═' * 55}{ANSIColors.RESET}
{ANSIColors.BRIGHT_YELLOW}║{ANSIColors.RESET}           Logging Configuration
{ANSIColors.BRIGHT_YELLOW}{'═' * 55}{ANSIColors.RESET}
"""
        
        footer = f"""
{ANSIColors.BRIGHT_BLACK}Use 'enable <type>' or 'disable <type>' to toggle{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Use 'setchannel <type|category> <channel_id>' to set channel{ANSIColors.RESET}
"""
        
        await self.session.show_animated_list(categories, header, footer)
        return None  # Animation handles display
    
    async def handle_enable(self, log_type: str, enabled: bool):
        """Enable or disable a specific log type or category"""
        if not self.logging_cog:
            return f"{ANSIColors.RED}❌ Logging module not loaded.{ANSIColors.RESET}"
        
        # Check if module is enabled
        if not self.db.is_module_enabled(self.guild.id, 'logging'):
            return f"{ANSIColors.RED}❌ Logging module is not enabled. Enable it first in modules panel.{ANSIColors.RESET}"
        
        # Build valid types list and check for category
        valid_types = []
        category_types = {}
        for category, types in self.logging_cog.LOGGING_TYPES.items():
            category_types[category] = list(types.keys())
            valid_types.extend(types.keys())
        
        # Check if it's a category
        if log_type in category_types:
            count = 0
            for t in category_types[log_type]:
                self.logging_cog.enable_log_type(self.guild.id, t, enabled)
                count += 1
            action = "enabled" if enabled else "disabled"
            color = ANSIColors.GREEN if enabled else ANSIColors.RED
            return f"{color}✓{ANSIColors.RESET} {action.title()} {count} log types in category `{log_type}`."
        
        if log_type not in valid_types:
            return f"""
{ANSIColors.RED}❌ Invalid log type: {log_type}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Valid types:{ANSIColors.RESET}
{', '.join(valid_types[:10])}...

{ANSIColors.BRIGHT_BLACK}Or use a category: messages, members, roles, channels, server, voice, moderation, bfos{ANSIColors.RESET}
"""
        
        self.logging_cog.enable_log_type(self.guild.id, log_type, enabled)
        
        action = "enabled" if enabled else "disabled"
        color = ANSIColors.GREEN if enabled else ANSIColors.RED
        
        return f"{color}✓{ANSIColors.RESET} Log type `{log_type}` has been {action}."
    
    async def handle_set_channel(self, log_type: str, channel_id: str):
        """Set the channel for a log type or entire category"""
        if not self.logging_cog:
            return f"{ANSIColors.RED}❌ Logging module not loaded.{ANSIColors.RESET}"
        
        # Check if module is enabled
        if not self.db.is_module_enabled(self.guild.id, 'logging'):
            return f"{ANSIColors.RED}❌ Logging module is not enabled.{ANSIColors.RESET}"
        
        # Parse channel ID first
        try:
            if channel_id.startswith('<#') and channel_id.endswith('>'):
                channel_id = channel_id[2:-1]
            
            channel_id_int = int(channel_id)
            channel = self.guild.get_channel(channel_id_int)
            
            if not channel:
                return f"{ANSIColors.RED}❌ Channel not found: {channel_id}{ANSIColors.RESET}"
            
            if not isinstance(channel, discord.TextChannel):
                return f"{ANSIColors.RED}❌ Must be a text channel{ANSIColors.RESET}"
            
        except ValueError:
            return f"{ANSIColors.RED}❌ Invalid channel ID: {channel_id}{ANSIColors.RESET}"
        
        # Build valid types list and check for category
        valid_types = []
        category_types = {}
        for category, types in self.logging_cog.LOGGING_TYPES.items():
            category_types[category] = list(types.keys())
            valid_types.extend(types.keys())
        
        # Check if it's a category
        if log_type in category_types:
            count = 0
            for t in category_types[log_type]:
                self.logging_cog.set_log_channel(self.guild.id, t, channel_id_int)
                count += 1
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Set #{channel.name} as log channel for {count} types in category `{log_type}`."
        
        if log_type not in valid_types:
            return f"""
{ANSIColors.RED}❌ Invalid log type: {log_type}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Valid types:{ANSIColors.RESET}
{', '.join(valid_types[:10])}...

{ANSIColors.BRIGHT_BLACK}Or use a category: messages, members, roles, channels, server, voice, moderation, bfos{ANSIColors.RESET}
"""
        
        self.logging_cog.set_log_channel(self.guild.id, log_type, channel_id_int)
        
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Log type `{log_type}` will now log to #{channel.name}"
    
    async def handle_enable_all(self, enabled: bool):
        """Enable or disable all log types"""
        if not self.logging_cog:
            return f"{ANSIColors.RED}❌ Logging module not loaded.{ANSIColors.RESET}"
        
        if not self.db.is_module_enabled(self.guild.id, 'logging'):
            return f"{ANSIColors.RED}❌ Logging module is not enabled.{ANSIColors.RESET}"
        
        count = 0
        for category, types in self.logging_cog.LOGGING_TYPES.items():
            for log_type in types.keys():
                self.logging_cog.enable_log_type(self.guild.id, log_type, enabled)
                count += 1
        
        action = "enabled" if enabled else "disabled"
        color = ANSIColors.GREEN if enabled else ANSIColors.RED
        
        return f"{color}✓{ANSIColors.RESET} {action.title()} {count} log types."
    
    async def handle_set_channel_all(self, channel_id: str):
        """Set the same channel for all log types"""
        if not self.logging_cog:
            return f"{ANSIColors.RED}❌ Logging module not loaded.{ANSIColors.RESET}"
        
        if not self.db.is_module_enabled(self.guild.id, 'logging'):
            return f"{ANSIColors.RED}❌ Logging module is not enabled.{ANSIColors.RESET}"
        
        # Parse channel ID
        try:
            if channel_id.startswith('<#') and channel_id.endswith('>'):
                channel_id = channel_id[2:-1]
            
            channel_id_int = int(channel_id)
            channel = self.guild.get_channel(channel_id_int)
            
            if not channel:
                return f"{ANSIColors.RED}❌ Channel not found: {channel_id}{ANSIColors.RESET}"
            
            if not isinstance(channel, discord.TextChannel):
                return f"{ANSIColors.RED}❌ Must be a text channel{ANSIColors.RESET}"
            
        except ValueError:
            return f"{ANSIColors.RED}❌ Invalid channel ID: {channel_id}{ANSIColors.RESET}"
        
        count = 0
        for category, types in self.logging_cog.LOGGING_TYPES.items():
            for log_type in types.keys():
                self.logging_cog.set_log_channel(self.guild.id, log_type, channel_id_int)
                count += 1
        
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Set #{channel.name} as log channel for {count} log types."
