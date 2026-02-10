"""
BlockForge OS AI Terminal Panel
Handles AI management through the BFOS terminal
"""

from utils.colors import ANSIColors, format_error, format_success, format_warning
from utils.config import Config
import re
from datetime import datetime


class AIPanel:
    """AI Management Panel for BFOS Terminal"""
    
    # Map commands to BFOS permission IDs
    PERMISSION_MAP = {
        'status': 'ai_manage',
        'enable': 'ai_manage',
        'disable': 'ai_manage',
        'model': 'ai_manage',
        'clearcontext': 'ai_clear',
        'blacklist': 'ai_blacklist',
        'unblacklist': 'ai_blacklist',
        'autorespond': 'ai_autorespond',
        'bypass': 'ai_bypass',
        'limits': 'ai_limits',
        'maintenance': None,  # Bot owner only, no BFOS permission
    }
    
    def __init__(self, session):
        self.session = session
        self.bot = session.bot
        self.db = session.db
        self.guild = session.guild
    
    def _get_ai_cog(self):
        """Get the AI system cog"""
        return self.bot.get_cog('AISystem')
    
    def _check_permission(self, command: str) -> bool:
        """Check if user has BFOS permission for command"""
        perm_id = self.PERMISSION_MAP.get(command.lower())
        if not perm_id:
            return False
        
        # Bot owner always has access
        if self.session.user.id == Config.BOT_OWNER_ID:
            return True
        
        # Check BFOS permission
        return self.session.has_permission(perm_id)
    
    def show_help(self):
        """Show AI panel help"""
        return f"""
{ANSIColors.BRIGHT_CYAN}╔═══════════════════════════════════════════╗
║           AI MANAGEMENT                   ║
╚═══════════════════════════════════════════╝{ANSIColors.RESET}

{ANSIColors.BRIGHT_WHITE}Status:{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}(ai_manage){ANSIColors.RESET}
  {ANSIColors.CYAN}status{ANSIColors.RESET}              Show AI configuration
  {ANSIColors.CYAN}enable / disable{ANSIColors.RESET}    Toggle AI for this server

{ANSIColors.BRIGHT_WHITE}Model:{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}(ai_manage){ANSIColors.RESET}
  {ANSIColors.CYAN}model set <name>{ANSIColors.RESET}    Set default (echo/sage/scorcher)
  {ANSIColors.CYAN}model lock/unlock{ANSIColors.RESET}   Lock model selection

{ANSIColors.BRIGHT_WHITE}Autorespond:{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}(ai_autorespond){ANSIColors.RESET}
  {ANSIColors.CYAN}autorespond add/remove <id>{ANSIColors.RESET}  Manage channels
  {ANSIColors.CYAN}autorespond list{ANSIColors.RESET}             List channels

{ANSIColors.BRIGHT_WHITE}Users:{ANSIColors.RESET}
  {ANSIColors.CYAN}clearcontext <id/all>{ANSIColors.RESET}  Clear memory {ANSIColors.BRIGHT_BLACK}(ai_clear){ANSIColors.RESET}
  {ANSIColors.CYAN}blacklist <id>{ANSIColors.RESET}         Block user {ANSIColors.BRIGHT_BLACK}(ai_blacklist){ANSIColors.RESET}
  {ANSIColors.CYAN}unblacklist <id>{ANSIColors.RESET}       Unblock user

{ANSIColors.BRIGHT_WHITE}Maintenance:{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}(bot owner only){ANSIColors.RESET}
  {ANSIColors.CYAN}maintenance{ANSIColors.RESET}              Toggle AI maintenance mode
  {ANSIColors.CYAN}maintenance msg <text>{ANSIColors.RESET}   Set maintenance message

{ANSIColors.BRIGHT_BLACK}back = return | help = this menu{ANSIColors.RESET}
"""
    
    async def handle_command(self, command: str, full_input: str):
        """Handle AI panel commands"""
        parts = full_input.split()
        first_word = parts[0].lower() if parts else ''
        
        if first_word == 'help':
            return self.show_help()
        
        elif first_word == 'back':
            self.session.current_panel = 'main'
            self.session.current_path = "System > Root"
            return f"{ANSIColors.GREEN}Returned to main menu.{ANSIColors.RESET}"
        
        elif first_word == 'status':
            if not self._check_permission('status'):
                return format_error("Permission denied - requires ai_manage", "0xFA01")
            return await self._show_status()
        
        elif first_word == 'enable':
            if not self._check_permission('enable'):
                return format_error("Permission denied - requires ai_manage", "0xFA02")
            return await self._set_enabled(True)
        
        elif first_word == 'disable':
            if not self._check_permission('disable'):
                return format_error("Permission denied - requires ai_manage", "0xFA03")
            return await self._set_enabled(False)
        
        elif first_word == 'model':
            if len(parts) < 2:
                return format_error("Usage: model <set/lock/unlock> [model_name]", "0xFA04")
            
            subcommand = parts[1].lower() if len(parts) > 1 else ''
            
            if subcommand == 'set':
                if not self._check_permission('model'):
                    return format_error("Permission denied - requires ai_manage", "0xFA05")
                if len(parts) < 3:
                    return format_error("Usage: model set <echo/sage/scorcher>", "0xFA06")
                return await self._set_model(parts[2].lower())
            
            elif subcommand == 'lock':
                if not self._check_permission('model'):
                    return format_error("Permission denied - requires ai_manage", "0xFA07")
                return await self._set_model_lock(True)
            
            elif subcommand == 'unlock':
                if not self._check_permission('model'):
                    return format_error("Permission denied - requires ai_manage", "0xFA08")
                return await self._set_model_lock(False)
            
            else:
                return format_error("Usage: model <set/lock/unlock>", "0xFA09")
        
        elif first_word == 'autorespond':
            if not self._check_permission('autorespond'):
                return format_error("Permission denied - requires ai_autorespond", "0xFA40")
            
            if len(parts) < 2:
                return format_error("Usage: autorespond <add/remove/list> [channel_id]", "0xFA41")
            
            subcommand = parts[1].lower()
            
            if subcommand == 'add':
                if len(parts) < 3:
                    return format_error("Usage: autorespond add <channel_id>", "0xFA42")
                return await self._autorespond_add(parts[2])
            
            elif subcommand == 'remove':
                if len(parts) < 3:
                    return format_error("Usage: autorespond remove <channel_id>", "0xFA43")
                return await self._autorespond_remove(parts[2])
            
            elif subcommand == 'list':
                return await self._autorespond_list()
            
            else:
                return format_error("Usage: autorespond <add/remove/list>", "0xFA44")
        
        elif first_word == 'clearcontext':
            if not self._check_permission('clearcontext'):
                return format_error("Permission denied - requires ai_clear", "0xFA10")
            if len(parts) < 2:
                return format_error("Usage: clearcontext <user_id/all>", "0xFA11")
            return await self._clear_context(parts[1])
        
        elif first_word == 'blacklist':
            if not self._check_permission('blacklist'):
                return format_error("Permission denied - requires ai_blacklist", "0xFA12")
            if len(parts) < 2:
                return format_error("Usage: blacklist <user_id>", "0xFA13")
            return await self._blacklist_user(parts[1])
        
        elif first_word == 'unblacklist':
            if not self._check_permission('unblacklist'):
                return format_error("Permission denied - requires ai_blacklist", "0xFA14")
            if len(parts) < 2:
                return format_error("Usage: unblacklist <user_id>", "0xFA15")
            return await self._unblacklist_user(parts[1])

        elif first_word == 'maintenance':
            # Bot owner only
            if self.session.user.id != Config.BOT_OWNER_ID:
                return format_error("Permission denied - bot owner only", "0xFA60")

            if len(parts) >= 2 and parts[1].lower() == 'msg':
                # Set maintenance message
                if len(parts) < 3:
                    return format_error("Usage: maintenance msg <message>", "0xFA61")
                msg_text = ' '.join(parts[2:])
                return await self._set_maintenance_message(msg_text)
            else:
                return await self._toggle_maintenance()

        else:
            return format_error(f"Unknown command: {full_input}. Type 'help' for available commands.", "0xFA00")
    
    async def _show_status(self):
        """Show AI status"""
        ai_cog = self._get_ai_cog()
        
        if not ai_cog:
            return format_error("AI System not loaded", "0xFA20")
        
        try:
            status = ai_cog.terminal_get_status(self.guild.id)
        except Exception as e:
            return format_error(f"Failed to get status: {e}", "0xFA21")
        
        enabled_str = f"{ANSIColors.GREEN}ENABLED{ANSIColors.RESET}" if status['enabled'] else f"{ANSIColors.RED}DISABLED{ANSIColors.RESET}"
        locked_str = f"{ANSIColors.YELLOW}LOCKED{ANSIColors.RESET}" if status['model_locked'] else f"{ANSIColors.GREEN}UNLOCKED{ANSIColors.RESET}"
        
        # Get autoresponder channels
        try:
            channels = ai_cog.terminal_list_autorespond(self.guild.id)
            if channels:
                channel_list = []
                for ch_id in channels.keys():
                    channel = self.guild.get_channel(ch_id)
                    if channel:
                        channel_list.append(f"#{channel.name} ({ch_id})")
                    else:
                        channel_list.append(f"#{ch_id} (deleted?)")
                autorespond_str = "\n    ".join(channel_list) if channel_list else "None"
            else:
                autorespond_str = "None"
        except:
            autorespond_str = "Error loading"
        
        return f"""
{ANSIColors.BRIGHT_CYAN}╔══════════════════════════════════════════════════════════════╗
║                    AI STATUS                                 ║
╚══════════════════════════════════════════════════════════════╝{ANSIColors.RESET}

  {ANSIColors.BRIGHT_WHITE}Status:{ANSIColors.RESET}        {enabled_str}
  {ANSIColors.BRIGHT_WHITE}Model:{ANSIColors.RESET}         {status['model_display']}
  {ANSIColors.BRIGHT_WHITE}Model Lock:{ANSIColors.RESET}    {locked_str}
  
  {ANSIColors.BRIGHT_WHITE}Autoresponder Channels:{ANSIColors.RESET}
    {autorespond_str}

{ANSIColors.BRIGHT_BLACK}Available models: echo (gen-z), sage (thinking), scorcher (roasts){ANSIColors.RESET}
"""
    
    async def _set_enabled(self, enabled: bool):
        """Enable or disable AI"""
        ai_cog = self._get_ai_cog()
        
        if not ai_cog:
            return format_error("AI System not loaded", "0xFA21")
        
        try:
            ai_cog.terminal_set_enabled(self.guild.id, enabled)
        except Exception as e:
            return format_error(f"Failed: {e}", "0xFA22")
        
        if enabled:
            return format_success("AI enabled for this server")
        else:
            return format_success("AI disabled for this server")
    
    async def _set_model(self, model: str):
        """Set default model"""
        ai_cog = self._get_ai_cog()
        
        if not ai_cog:
            return format_error("AI System not loaded", "0xFA22")
        
        model = model.lower()
        valid_models = ['echo', 'sage', 'scorcher']
        
        if model not in valid_models:
            return format_error(f"Invalid model. Available: {', '.join(valid_models)}", "0xFA23")
        
        try:
            success = ai_cog.terminal_set_model(self.guild.id, model)
        except Exception as e:
            return format_error(f"Failed: {e}", "0xFA24")
        
        if success:
            return format_success(f"Default model set to {model}")
        else:
            return format_error(f"Failed to set model to {model}", "0xFA24")
    
    async def _set_model_lock(self, locked: bool):
        """Lock or unlock model selection"""
        ai_cog = self._get_ai_cog()
        
        if not ai_cog:
            return format_error("AI System not loaded", "0xFA25")
        
        try:
            ai_cog.terminal_set_model_lock(self.guild.id, locked)
        except Exception as e:
            return format_error(f"Failed: {e}", "0xFA26")
        
        if locked:
            return format_success("Model selection locked - users cannot change their model")
        else:
            return format_success("Model selection unlocked - users can choose their model")
    
    async def _clear_context(self, target: str):
        """Clear conversation context"""
        ai_cog = self._get_ai_cog()
        
        if not ai_cog:
            return format_error("AI System not loaded", "0xFA26")
        
        if target.lower() == 'all':
            try:
                ai_cog.terminal_clear_context(self.guild.id, None)
            except Exception as e:
                return format_error(f"Failed: {e}", "0xFA27")
            return format_success("Cleared all AI conversation history for this server")
        else:
            try:
                user_id = int(target.strip('<@!>'))
                ai_cog.terminal_clear_context(self.guild.id, user_id)
                return format_success(f"Cleared AI conversation history for user {user_id}")
            except ValueError:
                return format_error("Invalid user ID", "0xFA27")
            except Exception as e:
                return format_error(f"Failed: {e}", "0xFA28")
    
    async def _autorespond_add(self, channel_id_str: str):
        """Add autoresponder channel"""
        ai_cog = self._get_ai_cog()
        
        if not ai_cog:
            return format_error("AI System not loaded", "0xFA45")
        
        try:
            # Parse channel ID (handles #channel mentions and raw IDs)
            channel_id = int(channel_id_str.strip('<#>'))
            
            # Verify channel exists
            channel = self.guild.get_channel(channel_id)
            if not channel:
                return format_error(f"Channel {channel_id} not found in this server", "0xFA46")
            
            success = ai_cog.terminal_add_autorespond(self.guild.id, channel_id)
            
            if success:
                return format_success(f"Added #{channel.name} as AI autoresponder channel")
            else:
                return format_error("Failed to add autoresponder channel", "0xFA47")
        except ValueError:
            return format_error("Invalid channel ID", "0xFA48")
        except Exception as e:
            return format_error(f"Failed: {e}", "0xFA49")
    
    async def _autorespond_remove(self, channel_id_str: str):
        """Remove autoresponder channel"""
        ai_cog = self._get_ai_cog()
        
        if not ai_cog:
            return format_error("AI System not loaded", "0xFA50")
        
        try:
            channel_id = int(channel_id_str.strip('<#>'))
            
            success = ai_cog.terminal_remove_autorespond(self.guild.id, channel_id)
            
            if success:
                channel = self.guild.get_channel(channel_id)
                channel_name = f"#{channel.name}" if channel else f"#{channel_id}"
                return format_success(f"Removed {channel_name} from autoresponder channels")
            else:
                return format_error("Failed to remove autoresponder channel", "0xFA51")
        except ValueError:
            return format_error("Invalid channel ID", "0xFA52")
        except Exception as e:
            return format_error(f"Failed: {e}", "0xFA53")
    
    async def _autorespond_list(self):
        """List autoresponder channels"""
        ai_cog = self._get_ai_cog()
        
        if not ai_cog:
            return format_error("AI System not loaded", "0xFA54")
        
        try:
            channels = ai_cog.terminal_list_autorespond(self.guild.id)
            
            if not channels:
                return f"""
{ANSIColors.BRIGHT_CYAN}╔══════════════════════════════════════════════════════════════╗
║                AUTORESPONDER CHANNELS                        ║
╚══════════════════════════════════════════════════════════════╝{ANSIColors.RESET}

  {ANSIColors.YELLOW}No autoresponder channels set.{ANSIColors.RESET}
  
  Use {ANSIColors.BRIGHT_CYAN}autorespond add <channel_id>{ANSIColors.RESET} to add one.
"""
            
            lines = []
            for ch_id in channels.keys():
                channel = self.guild.get_channel(ch_id)
                if channel:
                    lines.append(f"  {ANSIColors.GREEN}•{ANSIColors.RESET} #{channel.name} ({ch_id})")
                else:
                    lines.append(f"  {ANSIColors.RED}•{ANSIColors.RESET} #{ch_id} (deleted?)")
            
            return f"""
{ANSIColors.BRIGHT_CYAN}╔══════════════════════════════════════════════════════════════╗
║                AUTORESPONDER CHANNELS                        ║
╚══════════════════════════════════════════════════════════════╝{ANSIColors.RESET}

{chr(10).join(lines)}

{ANSIColors.BRIGHT_BLACK}Bot responds to ALL messages in these channels using user's model preference{ANSIColors.RESET}
"""
        except Exception as e:
            return format_error(f"Failed to list channels: {e}", "0xFA55")
    
    async def _blacklist_user(self, user_id_str: str):
        """Blacklist user from AI"""
        if not self.db:
            return format_error("Database not available", "0xFA28")
        
        try:
            user_id = int(user_id_str.strip('<@!>'))
            
            conn = self.db._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO ai_blacklist (guild_id, user_id, reason) VALUES (?, ?, ?)',
                (self.guild.id, user_id, 'Blacklisted via terminal')
            )
            conn.commit()
            conn.close()
            
            return format_success(f"User {user_id} blacklisted from AI")
        except ValueError:
            return format_error("Invalid user ID", "0xFA29")
        except Exception as e:
            return format_error(f"Failed: {e}", "0xFA30")
    
    async def _unblacklist_user(self, user_id_str: str):
        """Remove user from AI blacklist"""
        if not self.db:
            return format_error("Database not available", "0xFA30")
        
        try:
            user_id = int(user_id_str.strip('<@!>'))
            
            conn = self.db._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM ai_blacklist WHERE guild_id = ? AND user_id = ?',
                (self.guild.id, user_id)
            )
            conn.commit()
            conn.close()
            
            return format_success(f"User {user_id} removed from AI blacklist")
        except ValueError:
            return format_error("Invalid user ID", "0xFA31")
        except Exception as e:
            return format_error(f"Failed: {e}", "0xFA32")

    # ==================== MAINTENANCE MODE ====================

    async def _toggle_maintenance(self):
        """Toggle AI maintenance mode"""
        ai_cog = self._get_ai_cog()
        if not ai_cog:
            return format_error("AI System not loaded", "0xFA62")

        current = ai_cog.terminal_get_maintenance()
        new_state = not current['enabled']
        ai_cog.terminal_set_maintenance(new_state)

        if new_state:
            return format_success(f"AI maintenance mode ENABLED globally\nMessage: {current['message']}")
        else:
            return format_success("AI maintenance mode DISABLED globally")

    async def _set_maintenance_message(self, message: str):
        """Set the maintenance mode message"""
        ai_cog = self._get_ai_cog()
        if not ai_cog:
            return format_error("AI System not loaded", "0xFA63")

        ai_cog.terminal_set_maintenance(ai_cog.maintenance_mode, message)
        return format_success(f"Maintenance message set to: {message}")