"""
BlockForge OS - Terminal Permissions Panel
Handles permission management in BFOS terminal
"""

from utils.colors import ANSIColors
from utils.config import Config

# All available permission IDs
PERMISSION_IDS = {
    # Moderation
    'mod_warn': 'Warn users',
    'mod_ban': 'Ban users',
    'mod_kick': 'Kick users',
    'mod_mute': 'Mute users',
    'mod_unmute': 'Unmute users',
    'mod_unban': 'Unban users',
    # Voice
    'vc_mute': 'Voice mute users',
    'vc_unmute': 'Voice unmute users',
    'vc_deafen': 'Deafen users',
    'vc_undeafen': 'Undeafen users',
    'vc_disconnect': 'Disconnect users from VC',
    'vc_move': 'Move users between VCs',
    # Channel
    'channel_lock': 'Lock channels',
    'channel_unlock': 'Unlock channels',
    'channel_hardlock': 'Hardlock channels',
    'channel_slowmode': 'Set slowmode',
    # User management
    'user_nick': 'Change nicknames',
    'role_add': 'Add roles to users',
    'role_remove': 'Remove roles from users',
    # Case/logs
    'case_view': 'View punishment cases',
    'modlog_view': 'View moderation logs',
    'modnote_set': 'Set mod notes',
    'modnote_view': 'View mod notes',
    'modnote_delete': 'Delete mod notes',
    # Server
    'backup_create': 'Create backups',
    'backup_restore': 'Restore backups',
    'backup_delete': 'Delete backups',
    # Permissions
    'perm_assign': 'Assign permissions',
    'perm_remove': 'Remove permissions',
    'perm_view': 'View permissions',
    # Embeds
    'embed_edit': 'Edit embeds',
    'embed_preview': 'Preview embeds',
    # BFOS
    'bfos_access': 'Access BFOS terminal',
    'bfos_modules': 'Manage BFOS modules',
    'bfos_config': 'Configure BFOS settings',
    # AI Management
    'ai_manage': 'Manage AI settings (enable/disable, model, etc)',
    'ai_blacklist': 'Blacklist users from AI',
    'ai_bypass': 'Grant AI limit bypass',
    'ai_autorespond': 'Manage AI autorespond channels',
    'ai_limits': 'Configure AI limits',
    'ai_clear': 'Clear AI conversation history',
    # Tickets
    'ticket_manage': 'Configure ticket system',
    'ticket_close': 'Close tickets',
    'ticket_delete': 'Delete tickets',
    'ticket_add_user': 'Add users to tickets',
    'ticket_remove_user': 'Remove users from tickets',
    'ticket_claim': 'Claim tickets',
    # XP System
    'xp_manage': 'Configure XP system',
    'xp_admin': 'Add/remove/set user XP',
}

# Permission categories
PERMISSION_CATEGORIES = {
    'Moderation': ['mod_warn', 'mod_ban', 'mod_kick', 'mod_mute', 'mod_unmute', 'mod_unban'],
    'Voice Channel': ['vc_mute', 'vc_unmute', 'vc_deafen', 'vc_undeafen', 'vc_disconnect', 'vc_move'],
    'Channel Management': ['channel_lock', 'channel_unlock', 'channel_hardlock', 'channel_slowmode'],
    'User Management': ['user_nick', 'role_add', 'role_remove'],
    'Case Management': ['case_view', 'modlog_view', 'modnote_set', 'modnote_view', 'modnote_delete'],
    'Server Management': ['backup_create', 'backup_restore', 'backup_delete'],
    'Permissions': ['perm_assign', 'perm_remove', 'perm_view'],
    'Embeds': ['embed_edit', 'embed_preview'],
    'BFOS': ['bfos_access', 'bfos_modules', 'bfos_config'],
    'AI Management': ['ai_manage', 'ai_blacklist', 'ai_bypass', 'ai_autorespond', 'ai_limits', 'ai_clear'],
    'Tickets': ['ticket_manage', 'ticket_close', 'ticket_delete', 'ticket_add_user', 'ticket_remove_user', 'ticket_claim'],
    'XP System': ['xp_manage', 'xp_admin'],
}


class TerminalPermissions:
    """Handles permissions panel in BFOS terminal"""
    
    def __init__(self, session):
        self.session = session
        self.db = session.db
        self.guild = session.guild
    
    def format_error(self, message, code):
        """Format an error message"""
        return f"{ANSIColors.RED}❌ Error: {message}{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Code: {code}{ANSIColors.RESET}"
    
    async def handle_command(self, command_lower, user_input):
        """Handle permissions panel commands"""
        output = ""
        should_exit = False
        
        if command_lower == "exit":
            output = await self.session.handle_exit()
            should_exit = True
        elif command_lower == "back":
            self.session.current_panel = "staff"
            self.session.current_path = "Staff"
            output = f"{ANSIColors.GREEN}Returned to staff panel.{ANSIColors.RESET}"
        elif command_lower == "help":
            output = self.show_help()
        elif command_lower == "list":
            output = self.show_permission_list()
        elif command_lower.startswith("assign "):
            parts = user_input[7:].strip().split(maxsplit=1)
            if len(parts) >= 2:
                output = await self.assign_permission(parts[0], parts[1])
            else:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} assign <user_or_role_id> <permission_id>\n{ANSIColors.BRIGHT_BLACK}Example: assign 123456789 mod_warn{ANSIColors.RESET}"
        elif command_lower == "assign":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} assign <user_or_role_id> <permission_id>\n{ANSIColors.BRIGHT_BLACK}Example: assign 123456789 mod_warn,mod_ban{ANSIColors.RESET}"
        elif command_lower.startswith("remove "):
            parts = user_input[7:].strip().split(maxsplit=1)
            if len(parts) >= 2:
                output = await self.remove_permission(parts[0], parts[1])
            else:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} remove <user_or_role_id> <permission_id>"
        elif command_lower == "remove":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} remove <user_or_role_id> <permission_id>"
        elif command_lower.startswith("view "):
            target_id = user_input[5:].strip()
            output = await self.view_permissions(target_id)
        elif command_lower == "view":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} view <user_or_role_id>"
        elif command_lower.startswith("group "):
            output = await self.handle_group_command(user_input[6:].strip())
        elif command_lower == "group":
            output = self.show_group_help()
        elif command_lower == "all":
            output = await self.view_all_permissions()
        else:
            output = self.format_error(f"Unknown command: {user_input}", Config.ERROR_CODES['INVALID_COMMAND'])
        
        return output, should_exit
    
    def show_help(self):
        """Show permissions panel help"""
        return f"""
{ANSIColors.CYAN}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}        {ANSIColors.BOLD}Permissions Management{ANSIColors.RESET}           {ANSIColors.CYAN}║{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}list{ANSIColors.RESET}                     Show all permission IDs
  {ANSIColors.BRIGHT_WHITE}assign <id> <perm>{ANSIColors.RESET}       Assign permission to user/role
  {ANSIColors.BRIGHT_WHITE}remove <id> <perm>{ANSIColors.RESET}       Remove permission from user/role
  {ANSIColors.BRIGHT_WHITE}view <id>{ANSIColors.RESET}                View permissions for user/role
  {ANSIColors.BRIGHT_WHITE}all{ANSIColors.RESET}                      View all permission assignments

{ANSIColors.BRIGHT_CYAN}Group Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}group create <name>{ANSIColors.RESET}      Create a permission group
  {ANSIColors.BRIGHT_WHITE}group add <name> <perm>{ANSIColors.RESET}  Add permission to group
  {ANSIColors.BRIGHT_WHITE}group assign <id> <name>{ANSIColors.RESET} Assign group to user/role
  {ANSIColors.BRIGHT_WHITE}group list{ANSIColors.RESET}               List all groups

{ANSIColors.BRIGHT_CYAN}Multiple Permissions:{ANSIColors.RESET}
  Separate with comma: {ANSIColors.BRIGHT_WHITE}assign 123 mod_warn,mod_ban,mod_kick{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Navigation:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                     Return to staff panel
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}                     Exit terminal

{ANSIColors.BRIGHT_BLACK}Type 'list' to see all available permissions.{ANSIColors.RESET}
"""
    
    def show_permission_list(self):
        """Show all permission IDs organized by category"""
        output = f"""
{ANSIColors.CYAN}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}          {ANSIColors.BOLD}Available Permissions{ANSIColors.RESET}           {ANSIColors.CYAN}║{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 50}{ANSIColors.RESET}
"""
        
        for category, perms in PERMISSION_CATEGORIES.items():
            output += f"\n{ANSIColors.BRIGHT_CYAN}{category}:{ANSIColors.RESET}\n"
            for perm_id in perms:
                desc = PERMISSION_IDS.get(perm_id, 'Unknown')
                output += f"  {ANSIColors.BRIGHT_WHITE}{perm_id:25}{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}{desc}{ANSIColors.RESET}\n"
        
        output += f"\n{ANSIColors.BRIGHT_BLACK}Use 'assign <user/role id> <perm_id>' to assign a permission.{ANSIColors.RESET}"
        return output
    
    async def assign_permission(self, target_id: str, perm_ids: str):
        """Assign permission(s) to a user or role"""
        try:
            target_id_int = int(target_id)
        except:
            return self.format_error("Invalid user/role ID", Config.ERROR_CODES['INVALID_INPUT'])
        
        # Parse permission IDs (comma-separated)
        perm_list = [p.strip() for p in perm_ids.split(',')]
        
        # Validate all permissions
        invalid_perms = [p for p in perm_list if p not in PERMISSION_IDS]
        if invalid_perms:
            return self.format_error(f"Invalid permission(s): {', '.join(invalid_perms)}", Config.ERROR_CODES['INVALID_INPUT'])
        
        # Determine if it's a user or role
        user = self.guild.get_member(target_id_int)
        role = self.guild.get_role(target_id_int)
        
        if not user and not role:
            return self.format_error("User or role not found", Config.ERROR_CODES['INVALID_INPUT'])
        
        # Assign permissions
        assigned = []
        already_has = []
        
        for perm_id in perm_list:
            if user:
                if self.db.has_permission(self.guild.id, user.id, perm_id):
                    already_has.append(perm_id)
                else:
                    self.db.assign_permission(self.guild.id, perm_id, user_id=user.id, assigned_by=self.session.author.id)
                    assigned.append(perm_id)
            else:
                if self.db.role_has_permission(self.guild.id, role.id, perm_id):
                    already_has.append(perm_id)
                else:
                    self.db.assign_permission(self.guild.id, perm_id, role_id=role.id, assigned_by=self.session.author.id)
                    assigned.append(perm_id)
        
        target_name = user.display_name if user else role.name
        target_type = "User" if user else "Role"
        
        output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Permissions assigned to {target_type}: {ANSIColors.BRIGHT_WHITE}{target_name}{ANSIColors.RESET}\n\n"
        
        if assigned:
            output += f"{ANSIColors.BRIGHT_CYAN}Assigned:{ANSIColors.RESET}\n"
            for p in assigned:
                output += f"  {ANSIColors.GREEN}✓{ANSIColors.RESET} {p}\n"
        
        if already_has:
            output += f"\n{ANSIColors.BRIGHT_BLACK}Already had:{ANSIColors.RESET}\n"
            for p in already_has:
                output += f"  {ANSIColors.BRIGHT_BLACK}• {p}{ANSIColors.RESET}\n"
        
        return output
    
    async def remove_permission(self, target_id: str, perm_ids: str):
        """Remove permission(s) from a user or role"""
        try:
            target_id_int = int(target_id)
        except:
            return self.format_error("Invalid user/role ID", Config.ERROR_CODES['INVALID_INPUT'])
        
        perm_list = [p.strip() for p in perm_ids.split(',')]
        
        user = self.guild.get_member(target_id_int)
        role = self.guild.get_role(target_id_int)
        
        if not user and not role:
            return self.format_error("User or role not found", Config.ERROR_CODES['INVALID_INPUT'])
        
        removed = []
        not_had = []
        
        for perm_id in perm_list:
            if user:
                if self.db.has_permission(self.guild.id, user.id, perm_id):
                    self.db.remove_permission(self.guild.id, perm_id, user_id=user.id)
                    removed.append(perm_id)
                else:
                    not_had.append(perm_id)
            else:
                if self.db.role_has_permission(self.guild.id, role.id, perm_id):
                    self.db.remove_permission(self.guild.id, perm_id, role_id=role.id)
                    removed.append(perm_id)
                else:
                    not_had.append(perm_id)
        
        target_name = user.display_name if user else role.name
        target_type = "User" if user else "Role"
        
        output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Permissions removed from {target_type}: {ANSIColors.BRIGHT_WHITE}{target_name}{ANSIColors.RESET}\n\n"
        
        if removed:
            output += f"{ANSIColors.BRIGHT_CYAN}Removed:{ANSIColors.RESET}\n"
            for p in removed:
                output += f"  {ANSIColors.RED}✗{ANSIColors.RESET} {p}\n"
        
        if not_had:
            output += f"\n{ANSIColors.BRIGHT_BLACK}Didn't have:{ANSIColors.RESET}\n"
            for p in not_had:
                output += f"  {ANSIColors.BRIGHT_BLACK}• {p}{ANSIColors.RESET}\n"
        
        return output
    
    async def view_permissions(self, target_id: str):
        """View permissions for a user or role"""
        try:
            target_id_int = int(target_id)
        except:
            return self.format_error("Invalid user/role ID", Config.ERROR_CODES['INVALID_INPUT'])
        
        user = self.guild.get_member(target_id_int)
        role = self.guild.get_role(target_id_int)
        
        if not user and not role:
            return self.format_error("User or role not found", Config.ERROR_CODES['INVALID_INPUT'])
        
        if user:
            perms = self.db.get_user_permissions(self.guild.id, user.id)
            target_name = user.display_name
            target_type = "User"
        else:
            perms = self.db.get_role_permissions(self.guild.id, role.id)
            target_name = role.name
            target_type = "Role"
        
        output = f"""
{ANSIColors.CYAN}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET} Permissions for {target_type}: {ANSIColors.BRIGHT_WHITE}{target_name}{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 50}{ANSIColors.RESET}
"""
        
        if not perms:
            output += f"\n{ANSIColors.BRIGHT_BLACK}No permissions assigned.{ANSIColors.RESET}\n"
        else:
            # Group by category
            for category, cat_perms in PERMISSION_CATEGORIES.items():
                has_any = any(p in perms for p in cat_perms)
                if has_any:
                    output += f"\n{ANSIColors.BRIGHT_CYAN}{category}:{ANSIColors.RESET}\n"
                    for perm_id in cat_perms:
                        if perm_id in perms:
                            output += f"  {ANSIColors.GREEN}✓{ANSIColors.RESET} {perm_id}\n"
                        else:
                            output += f"  {ANSIColors.RED}✗{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}{perm_id}{ANSIColors.RESET}\n"
        
        return output
    
    async def view_all_permissions(self):
        """View all permission assignments in the guild"""
        all_perms = self.db.get_all_permissions(self.guild.id)
        
        output = f"""
{ANSIColors.CYAN}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}       {ANSIColors.BOLD}All Permission Assignments{ANSIColors.RESET}         {ANSIColors.CYAN}║{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 50}{ANSIColors.RESET}
"""
        
        if not all_perms:
            output += f"\n{ANSIColors.BRIGHT_BLACK}No permissions assigned yet.{ANSIColors.RESET}\n"
            return output
        
        # Group by user/role
        user_perms = {}
        role_perms = {}
        
        for perm in all_perms:
            if perm['user_id']:
                if perm['user_id'] not in user_perms:
                    user_perms[perm['user_id']] = []
                user_perms[perm['user_id']].append(perm['permission_id'])
            elif perm['role_id']:
                if perm['role_id'] not in role_perms:
                    role_perms[perm['role_id']] = []
                role_perms[perm['role_id']].append(perm['permission_id'])
        
        if user_perms:
            output += f"\n{ANSIColors.BRIGHT_CYAN}Users:{ANSIColors.RESET}\n"
            for user_id, perms in user_perms.items():
                user = self.guild.get_member(user_id)
                name = user.display_name if user else str(user_id)
                output += f"  {ANSIColors.BRIGHT_WHITE}{name}{ANSIColors.RESET}: {', '.join(perms[:5])}"
                if len(perms) > 5:
                    output += f" +{len(perms) - 5} more"
                output += "\n"
        
        if role_perms:
            output += f"\n{ANSIColors.BRIGHT_CYAN}Roles:{ANSIColors.RESET}\n"
            for role_id, perms in role_perms.items():
                role = self.guild.get_role(role_id)
                name = role.name if role else str(role_id)
                output += f"  {ANSIColors.BRIGHT_WHITE}{name}{ANSIColors.RESET}: {', '.join(perms[:5])}"
                if len(perms) > 5:
                    output += f" +{len(perms) - 5} more"
                output += "\n"
        
        return output
    
    def show_group_help(self):
        """Show group commands help"""
        return f"""
{ANSIColors.BRIGHT_CYAN}Permission Group Commands:{ANSIColors.RESET}

  {ANSIColors.BRIGHT_WHITE}group create <name>{ANSIColors.RESET}
    Create a new permission group
    Example: group create Moderators

  {ANSIColors.BRIGHT_WHITE}group add <name> <perm_id>{ANSIColors.RESET}
    Add permission(s) to a group
    Example: group add Moderators mod_warn,mod_ban

  {ANSIColors.BRIGHT_WHITE}group assign <user/role_id> <name>{ANSIColors.RESET}
    Give all permissions in a group to user/role
    Example: group assign 123456789 Moderators

  {ANSIColors.BRIGHT_WHITE}group list{ANSIColors.RESET}
    List all permission groups
"""
    
    async def handle_group_command(self, args: str):
        """Handle group subcommands"""
        parts = args.split(maxsplit=2)
        if not parts:
            return self.show_group_help()
        
        subcmd = parts[0].lower()
        
        if subcmd == "create" and len(parts) >= 2:
            group_name = parts[1]
            group_id = self.db.create_permission_group(self.guild.id, group_name)
            if group_id:
                return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Permission group '{ANSIColors.BRIGHT_WHITE}{group_name}{ANSIColors.RESET}' created!"
            else:
                return self.format_error(f"Group '{group_name}' already exists", Config.ERROR_CODES['INVALID_INPUT'])
        
        elif subcmd == "add" and len(parts) >= 3:
            group_name = parts[1]
            perm_ids = parts[2]
            
            group_id = self.db.get_permission_group_id(self.guild.id, group_name)
            if not group_id:
                return self.format_error(f"Group '{group_name}' not found", Config.ERROR_CODES['INVALID_INPUT'])
            
            perm_list = [p.strip() for p in perm_ids.split(',')]
            added = []
            for perm in perm_list:
                if perm in PERMISSION_IDS:
                    self.db.add_permission_to_group(group_id, perm)
                    added.append(perm)
            
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Added {len(added)} permission(s) to group '{ANSIColors.BRIGHT_WHITE}{group_name}{ANSIColors.RESET}'"
        
        elif subcmd == "assign" and len(parts) >= 3:
            target_id = parts[1]
            group_name = parts[2]
            
            # Get group permissions
            group_perms = self.db.get_group_permissions(self.guild.id, group_name)
            if not group_perms:
                return self.format_error(f"Group '{group_name}' not found or empty", Config.ERROR_CODES['INVALID_INPUT'])
            
            # Assign all permissions
            return await self.assign_permission(target_id, ','.join(group_perms))
        
        elif subcmd == "list":
            groups = self.db.list_permission_groups(self.guild.id)
            if not groups:
                return f"{ANSIColors.BRIGHT_BLACK}No permission groups created yet.{ANSIColors.RESET}"
            
            output = f"{ANSIColors.BRIGHT_CYAN}Permission Groups:{ANSIColors.RESET}\n\n"
            for group in groups:
                perms = self.db.get_group_permissions(self.guild.id, group['name'])
                output += f"  {ANSIColors.BRIGHT_WHITE}{group['name']}{ANSIColors.RESET} ({len(perms)} permissions)\n"
            
            return output
        
        return self.show_group_help()