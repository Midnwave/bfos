"""
BlockForge OS Terminal Security Panel v2.0.8
Handles Security menu: Verification, Lockdown, Raid Protection
"""

import discord
from datetime import datetime
from utils.database import Database
from utils.config import Config


# ANSI color codes for terminal styling
class ANSIColors:
    RESET = "\u001b[0m"
    RED = "\u001b[31m"
    GREEN = "\u001b[32m"
    YELLOW = "\u001b[33m"
    BLUE = "\u001b[34m"
    MAGENTA = "\u001b[35m"
    CYAN = "\u001b[36m"
    WHITE = "\u001b[37m"
    BRIGHT_BLACK = "\u001b[30;1m"
    BRIGHT_RED = "\u001b[31;1m"
    BRIGHT_GREEN = "\u001b[32;1m"
    BRIGHT_YELLOW = "\u001b[33;1m"
    BRIGHT_BLUE = "\u001b[34;1m"
    BRIGHT_MAGENTA = "\u001b[35;1m"
    BRIGHT_CYAN = "\u001b[36;1m"
    BRIGHT_WHITE = "\u001b[37;1m"


def format_error(message, error_code=None):
    """Format error message with optional error code"""
    error = f"{ANSIColors.RED}✖ {message}{ANSIColors.RESET}"
    if error_code:
        error += f"\n{ANSIColors.BRIGHT_BLACK}Error Code: {error_code}{ANSIColors.RESET}"
    return error


class TerminalSecurityHandler:
    """Handles all Security panel operations for BFOS terminal"""
    
    def __init__(self, session):
        self.session = session
        self.bot = session.bot
        self.guild = session.guild
        self.db = Database()
        self.security_cog = self.bot.get_cog('SecurityModule')
    
    async def handle_command(self, command: str) -> str:
        """Route security panel commands"""
        cmd = command.lower().strip()
        parts = command.split()
        
        # Global commands available in all security panels
        if cmd == 'exit':
            return "EXIT_TERMINAL"  # Signal to terminal to handle exit
        
        # Main security panel
        if self.session.current_panel == "security":
            if cmd in ['help', '?']:
                return self.show_security_help()
            elif cmd == 'verification':
                self.session.current_panel = "verification"
                self.session.current_path = "Security > Verification"
                return self.show_verification_panel()
            elif cmd == 'lockdown':
                return await self.handle_lockdown()
            elif cmd == 'unlockdown' or cmd.startswith('unlockdown '):
                return await self.handle_unlockdown(command)
            elif cmd == 'raidprotection' or cmd == 'raid':
                return self.show_raid_protection()
            elif cmd == 'back':
                self.session.current_panel = "main"
                self.session.current_path = "Main"
                return f"{ANSIColors.BRIGHT_GREEN}Returning to main menu...{ANSIColors.RESET}"
            else:
                return format_error(f"Unknown command: {cmd}", "0xCNTF")
        
        # Verification panel
        elif self.session.current_panel == "verification":
            return await self.handle_verification_command(command)
        
        # Autoroles panel
        elif self.session.current_panel == "autoroles":
            return await self.handle_autoroles_command(command)
        
        return format_error("Invalid panel state", "0xPNL")
    
    def show_security_help(self) -> str:
        """Show security panel help"""
        return f"""
{ANSIColors.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}
{ANSIColors.BRIGHT_WHITE}                  🛡️ SECURITY PANEL{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}

{ANSIColors.BRIGHT_WHITE}Available Commands:{ANSIColors.RESET}

  {ANSIColors.BRIGHT_CYAN}verification{ANSIColors.RESET}      Open verification settings
  {ANSIColors.BRIGHT_CYAN}lockdown{ANSIColors.RESET}          Activate server lockdown
  {ANSIColors.BRIGHT_CYAN}unlockdown{ANSIColors.RESET}        Deactivate server lockdown
  {ANSIColors.BRIGHT_CYAN}raidprotection{ANSIColors.RESET}    View raid protection (coming soon)

{ANSIColors.BRIGHT_WHITE}Navigation:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}              Return to main menu
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}              Exit terminal
"""
    
    # ==================== LOCKDOWN ====================
    
    async def handle_lockdown(self) -> str:
        """Activate server lockdown"""
        if not self.security_cog:
            return format_error("Security module not loaded.", "0xMODL")
        
        state = self.security_cog.get_lockdown_state(self.guild.id)
        
        if state['active']:
            return f"""
{ANSIColors.YELLOW}⚠️ Server is already in lockdown!{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Started: {state.get('started_at', 'Unknown')}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Lockdown Role ID: {state.get('lockdown_role_id', 'Unknown')}{ANSIColors.RESET}

{ANSIColors.BRIGHT_WHITE}Use 'unlockdown' to deactivate.{ANSIColors.RESET}
"""
        
        # Show confirmation
        self.session.pending_confirmation = {
            'action': 'lockdown',
            'type': 'lockdown'
        }
        
        return f"""
{ANSIColors.BRIGHT_RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}
{ANSIColors.BRIGHT_WHITE}              ⚠️ LOCKDOWN CONFIRMATION{ANSIColors.RESET}
{ANSIColors.BRIGHT_RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}

{ANSIColors.YELLOW}This will:{ANSIColors.RESET}
  • Create a lockdown role below the bot's highest role
  • Apply restrictions to ALL channels:
    - No sending messages
    - No adding reactions
    - No creating threads
    - No joining voice channels
  • Pause server invites for 24 hours (auto-renews)
  • Add the lockdown role to ALL non-bot members

{ANSIColors.BRIGHT_RED}Are you sure you want to activate lockdown?{ANSIColors.RESET}

{ANSIColors.BRIGHT_WHITE}Type 'confirm' to proceed or 'cancel' to abort.{ANSIColors.RESET}
"""
    
    async def execute_lockdown(self) -> str:
        """Execute the lockdown"""
        await self.session.send_progress_update("Creating lockdown role...")
        await self.session.send_progress_update("Applying channel restrictions...")
        await self.session.send_progress_update("Adding role to members...")
        await self.session.send_progress_update("Pausing invites...")
        
        success, message = await self.security_cog.activate_lockdown(self.guild, self.session.ctx.author)
        
        if success:
            return f"""
{ANSIColors.GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}
{ANSIColors.GREEN}✓{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}LOCKDOWN ACTIVATED{ANSIColors.RESET}
{ANSIColors.GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}{message}{ANSIColors.RESET}

{ANSIColors.YELLOW}The server is now in lockdown mode.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Use 'unlockdown' to deactivate when ready.{ANSIColors.RESET}
"""
        else:
            return format_error(message, "0xLOCK")
    
    async def handle_unlockdown(self, command: str) -> str:
        """Deactivate server lockdown"""
        if not self.security_cog:
            return format_error("Security module not loaded.", "0xMODL")
        
        state = self.security_cog.get_lockdown_state(self.guild.id)
        
        if not state['active']:
            return f"{ANSIColors.YELLOW}Server is not currently in lockdown.{ANSIColors.RESET}"
        
        # Check for hidden flag
        remove_user_perms = '--remove-members' in command.lower()
        
        await self.session.send_progress_update("Removing lockdown role...")
        await self.session.send_progress_update("Re-enabling invites...")
        
        if remove_user_perms:
            await self.session.send_progress_update("Removing user permissions from channels...")
        
        success, message = await self.security_cog.deactivate_lockdown(self.guild, remove_user_perms)
        
        if success:
            extra = ""
            if remove_user_perms:
                extra = f"\n{ANSIColors.YELLOW}User permissions have been removed from all channels.{ANSIColors.RESET}"
            
            return f"""
{ANSIColors.GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}
{ANSIColors.GREEN}✓{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}LOCKDOWN DEACTIVATED{ANSIColors.RESET}
{ANSIColors.GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Server lockdown has been lifted.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}All restrictions have been removed.{ANSIColors.RESET}{extra}
"""
        else:
            return format_error(message, "0xUNLK")
    
    # ==================== RAID PROTECTION ====================
    
    def show_raid_protection(self) -> str:
        """Show raid protection panel"""
        return f"""
{ANSIColors.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}
{ANSIColors.BRIGHT_WHITE}            🛡️ RAID PROTECTION{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}

{ANSIColors.YELLOW}⏳ Coming Soon!{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Raid Protection will include:{ANSIColors.RESET}
  • Auto-detection of join raids
  • Configurable join rate limits
  • Auto-lockdown on raid detection
  • Suspicious account flagging
  • Anti-spam measures

{ANSIColors.BRIGHT_BLACK}Stay tuned for updates!{ANSIColors.RESET}
"""
    
    # ==================== VERIFICATION ====================
    
    def show_verification_panel(self) -> str:
        """Show verification configuration panel"""
        if not self.security_cog:
            return format_error("Security module not loaded.", "0xMODL")
        
        config = self.security_cog.get_verification_config(self.guild.id)
        
        status = f"{ANSIColors.GREEN}ENABLED{ANSIColors.RESET}" if config['enabled'] else f"{ANSIColors.RED}DISABLED{ANSIColors.RESET}"
        
        channel = "Not Set"
        if config['channel_id']:
            ch = self.guild.get_channel(config['channel_id'])
            channel = f"#{ch.name}" if ch else f"ID: {config['channel_id']}"
        
        verified_role = "Not Set"
        if config['verified_role_id']:
            r = self.guild.get_role(config['verified_role_id'])
            verified_role = r.name if r else f"ID: {config['verified_role_id']}"
        
        unverified_role = "Not Set"
        if config['unverified_role_id']:
            r = self.guild.get_role(config['unverified_role_id'])
            unverified_role = r.name if r else f"ID: {config['unverified_role_id']}"
        
        # Questions status
        questions = ""
        for i in range(1, 6):
            enabled = config.get(f'q{i}_enabled', False)
            question = config.get(f'q{i}_question', '')[:40]
            status_icon = f"{ANSIColors.GREEN}●{ANSIColors.RESET}" if enabled else f"{ANSIColors.RED}○{ANSIColors.RESET}"
            questions += f"  {status_icon} Q{i}: {question}{'...' if len(config.get(f'q{i}_question', '')) > 40 else ''}\n"
        
        return f"""
{ANSIColors.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}
{ANSIColors.BRIGHT_WHITE}            🔐 VERIFICATION SYSTEM{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}

{ANSIColors.BRIGHT_WHITE}Status:{ANSIColors.RESET} {status}
{ANSIColors.BRIGHT_WHITE}Channel:{ANSIColors.RESET} {channel}
{ANSIColors.BRIGHT_WHITE}Verified Role:{ANSIColors.RESET} {verified_role}
{ANSIColors.BRIGHT_WHITE}Unverified Role:{ANSIColors.RESET} {unverified_role}

{ANSIColors.BRIGHT_WHITE}Questions:{ANSIColors.RESET}
{questions}
{ANSIColors.BRIGHT_CYAN}━━━ How Verification Works ━━━{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}1. Users see a verification embed with a green "Verify" button
2. Clicking shows a unique 6-digit code (expires in 5 minutes)
3. Users complete a form with your configured questions
4. They must enter the correct code to verify
5. On success, they receive the Verified role and a welcome DM
{ANSIColors.RESET}
{ANSIColors.BRIGHT_WHITE}Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_CYAN}enable{ANSIColors.RESET} / {ANSIColors.BRIGHT_CYAN}disable{ANSIColors.RESET}     Toggle verification
  {ANSIColors.BRIGHT_CYAN}setchannel <id>{ANSIColors.RESET}      Set verification channel
  {ANSIColors.BRIGHT_CYAN}setverified <id>{ANSIColors.RESET}     Set verified role
  {ANSIColors.BRIGHT_CYAN}setunverified <id>{ANSIColors.RESET}   Set unverified role
  {ANSIColors.BRIGHT_CYAN}createunverified{ANSIColors.RESET}     Create & setup unverified role
  {ANSIColors.BRIGHT_CYAN}q1 <question>{ANSIColors.RESET}        Set question 1 (max 45 chars)
  {ANSIColors.BRIGHT_CYAN}q2 <question>{ANSIColors.RESET}        Set question 2
  {ANSIColors.BRIGHT_CYAN}q3 <question>{ANSIColors.RESET}        Set question 3
  {ANSIColors.BRIGHT_CYAN}q4 <question>{ANSIColors.RESET}        Set question 4
  {ANSIColors.BRIGHT_CYAN}toggle q1{ANSIColors.RESET}            Enable/disable question 1
  {ANSIColors.BRIGHT_CYAN}deploy{ANSIColors.RESET}               Send verification embed to channel
  {ANSIColors.BRIGHT_CYAN}autoroles{ANSIColors.RESET}            Manage autoroles
  {ANSIColors.BRIGHT_CYAN}back{ANSIColors.RESET}                 Return to Security

{ANSIColors.BRIGHT_BLACK}Note: Q5 (verification code) cannot be disabled.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Use {{server}} placeholder in questions for server name.{ANSIColors.RESET}
"""
    
    async def handle_verification_command(self, command: str) -> str:
        """Handle verification panel commands"""
        cmd = command.lower().strip()
        parts = command.split(maxsplit=1)
        
        if cmd in ['help', '?']:
            return self.show_verification_panel()
        
        elif cmd == 'back':
            self.session.current_panel = "security"
            self.session.current_path = "Security"
            return self.show_security_help()
        
        elif cmd == 'enable':
            return await self.toggle_verification(True)
        
        elif cmd == 'disable':
            return await self.toggle_verification(False)
        
        elif cmd.startswith('setchannel '):
            channel_id = parts[1].strip() if len(parts) > 1 else None
            return await self.set_verification_channel(channel_id)
        
        elif cmd.startswith('setverified '):
            role_id = parts[1].strip() if len(parts) > 1 else None
            return await self.set_verified_role(role_id)
        
        elif cmd.startswith('setunverified '):
            role_id = parts[1].strip() if len(parts) > 1 else None
            return await self.set_unverified_role(role_id)
        
        elif cmd == 'createunverified':
            return await self.create_unverified_role()
        
        elif cmd.startswith('q') and len(cmd) > 1 and cmd[1].isdigit():
            q_num = int(cmd[1])
            if q_num == 5:
                return f"{ANSIColors.YELLOW}Q5 (verification code) cannot be modified.{ANSIColors.RESET}"
            question = parts[1][2:].strip() if len(parts) > 1 and len(parts[1]) > 2 else None
            if question:
                return await self.set_question(q_num, question)
            else:
                return f"{ANSIColors.YELLOW}Usage: q{q_num} <question text>{ANSIColors.RESET}"
        
        elif cmd.startswith('toggle q'):
            try:
                q_num = int(cmd.split('q')[1].strip())
                if q_num == 5:
                    return f"{ANSIColors.YELLOW}Q5 (verification code) cannot be disabled.{ANSIColors.RESET}"
                return await self.toggle_question(q_num)
            except:
                return f"{ANSIColors.YELLOW}Usage: toggle q1{ANSIColors.RESET}"
        
        elif cmd == 'deploy':
            return await self.deploy_verification()
        
        elif cmd == 'autoroles':
            self.session.current_panel = "autoroles"
            self.session.current_path = "Security > Verification > Autoroles"
            return self.show_autoroles_panel()
        
        return format_error(f"Unknown command: {cmd}", "0xCNTF")
    
    async def toggle_verification(self, enabled: bool) -> str:
        """Enable or disable verification"""
        config = self.security_cog.get_verification_config(self.guild.id)
        config['enabled'] = enabled
        self.security_cog.save_verification_config(self.guild.id, config)
        
        status = "enabled" if enabled else "disabled"
        color = ANSIColors.GREEN if enabled else ANSIColors.RED
        return f"{color}✓{ANSIColors.RESET} Verification has been {status}."
    
    async def set_verification_channel(self, channel_id: str) -> str:
        """Set the verification channel"""
        try:
            cid = int(channel_id.strip('<#>'))
            channel = self.guild.get_channel(cid)
            if not channel:
                return format_error(f"Channel not found: {channel_id}", "0xCHNL")
            
            config = self.security_cog.get_verification_config(self.guild.id)
            config['channel_id'] = cid
            self.security_cog.save_verification_config(self.guild.id, config)
            
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Verification channel set to #{channel.name}"
        except ValueError:
            return format_error("Invalid channel ID.", "0xBADA")
    
    async def set_verified_role(self, role_id: str) -> str:
        """Set the verified role"""
        try:
            rid = int(role_id.strip('<@&>'))
            role = self.guild.get_role(rid)
            if not role:
                return format_error(f"Role not found: {role_id}", "0xROLE")
            
            await self.security_cog.setup_verified_role(self.guild, role)
            
            return f"""{ANSIColors.GREEN}✓{ANSIColors.RESET} Verified role set to {role.name}

{ANSIColors.YELLOW}⚠️ Important:{ANSIColors.RESET}
Make sure this role is positioned ABOVE the Unverified role
in your server's role hierarchy!"""
        except ValueError:
            return format_error("Invalid role ID.", "0xBADA")
    
    async def set_unverified_role(self, role_id: str) -> str:
        """Set the unverified role (for existing roles)"""
        try:
            rid = int(role_id.strip('<@&>'))
            role = self.guild.get_role(rid)
            if not role:
                return format_error(f"Role not found: {role_id}", "0xROLE")
            
            # Save to config
            config = self.security_cog.get_verification_config(self.guild.id)
            config['unverified_role_id'] = role.id
            self.security_cog.save_verification_config(self.guild.id, config)
            
            return f"""{ANSIColors.GREEN}✓{ANSIColors.RESET} Unverified role set to {role.name}

{ANSIColors.BRIGHT_BLACK}This role will be:{ANSIColors.RESET}
  • Removed when users complete verification
  • Added to new members when they join

{ANSIColors.YELLOW}⚠️ Note:{ANSIColors.RESET}
You may want to manually configure this role's permissions,
or use 'createunverified' to auto-create a properly configured role."""
        except ValueError:
            return format_error("Invalid role ID.", "0xBADA")
    
    async def create_unverified_role(self) -> str:
        """Create the unverified role"""
        await self.session.send_progress_update("Creating unverified role...")
        await self.session.send_progress_update("Configuring channel permissions...")
        
        role = await self.security_cog.create_unverified_role(self.guild)
        
        return f"""{ANSIColors.GREEN}✓{ANSIColors.RESET} Unverified role created: {role.name}

{ANSIColors.BRIGHT_BLACK}The role has been configured to:{ANSIColors.RESET}
  • Hide all channels except verification channel
  • Allow viewing the verification channel
  • Deny sending messages in verification channel

{ANSIColors.YELLOW}⚠️ Note:{ANSIColors.RESET}
This role will automatically be updated when new channels are created."""
    
    async def set_question(self, q_num: int, question: str) -> str:
        """Set a verification question"""
        if len(question) > 45:
            return f"{ANSIColors.YELLOW}Warning: Discord limits question labels to 45 characters. Your question will be truncated.{ANSIColors.RESET}"
        
        config = self.security_cog.get_verification_config(self.guild.id)
        config[f'q{q_num}_question'] = question
        config[f'q{q_num}_enabled'] = True
        self.security_cog.save_verification_config(self.guild.id, config)
        
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Question {q_num} set: {question[:45]}"
    
    async def toggle_question(self, q_num: int) -> str:
        """Toggle a question on/off"""
        config = self.security_cog.get_verification_config(self.guild.id)
        current = config.get(f'q{q_num}_enabled', False)
        config[f'q{q_num}_enabled'] = not current
        self.security_cog.save_verification_config(self.guild.id, config)
        
        status = "enabled" if not current else "disabled"
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Question {q_num} is now {status}."
    
    async def deploy_verification(self) -> str:
        """Deploy verification embed to channel"""
        config = self.security_cog.get_verification_config(self.guild.id)
        
        if not config['channel_id']:
            return format_error("No verification channel set. Use 'setchannel <id>' first.", "0xCHNL")
        
        channel = self.guild.get_channel(config['channel_id'])
        if not channel:
            return format_error("Verification channel not found.", "0xCHNL")
        
        embed = await self.security_cog.create_verification_embed(self.guild)
        
        # Create view directly
        from cogs.security import VerifyButton
        view = VerifyButton(self.security_cog)
        
        await channel.send(embed=embed, view=view)
        
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Verification embed sent to #{channel.name}"
    
    # ==================== AUTOROLES ====================
    
    def show_autoroles_panel(self) -> str:
        """Show autoroles panel"""
        autoroles = self.security_cog.get_autoroles(self.guild.id)
        
        roles_list = ""
        if autoroles:
            for rid in autoroles:
                role = self.guild.get_role(rid)
                role_name = role.name if role else f"Unknown ({rid})"
                roles_list += f"  {ANSIColors.GREEN}●{ANSIColors.RESET} {role_name} ({rid})\n"
        else:
            roles_list = f"  {ANSIColors.BRIGHT_BLACK}No autoroles configured.{ANSIColors.RESET}\n"
        
        return f"""
{ANSIColors.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}
{ANSIColors.BRIGHT_WHITE}              📋 AUTOROLES{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Autoroles are assigned when a user completes verification.{ANSIColors.RESET}

{ANSIColors.BRIGHT_WHITE}Current Autoroles:{ANSIColors.RESET}
{roles_list}
{ANSIColors.BRIGHT_WHITE}Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_CYAN}autorole add <role_id>{ANSIColors.RESET}     Add an autorole
  {ANSIColors.BRIGHT_CYAN}autorole remove <role_id>{ANSIColors.RESET}  Remove an autorole
  {ANSIColors.BRIGHT_CYAN}back{ANSIColors.RESET}                       Return to Verification
"""
    
    async def handle_autoroles_command(self, command: str) -> str:
        """Handle autoroles commands"""
        cmd = command.lower().strip()
        
        if cmd == 'back':
            self.session.current_panel = "verification"
            self.session.current_path = "Security > Verification"
            return self.show_verification_panel()
        
        elif cmd.startswith('autorole add '):
            role_id = command.split('autorole add ')[1].strip()
            return await self.add_autorole(role_id)
        
        elif cmd.startswith('autorole remove '):
            role_id = command.split('autorole remove ')[1].strip()
            return await self.remove_autorole(role_id)
        
        return format_error(f"Unknown command: {cmd}", "0xCNTF")
    
    async def add_autorole(self, role_id: str) -> str:
        """Add an autorole"""
        try:
            rid = int(role_id.strip('<@&>'))
            role = self.guild.get_role(rid)
            if not role:
                return format_error(f"Role not found: {role_id}", "0xROLE")
            
            if self.security_cog.add_autorole(self.guild.id, rid):
                return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Added autorole: {role.name}"
            else:
                return f"{ANSIColors.YELLOW}Role is already an autorole.{ANSIColors.RESET}"
        except ValueError:
            return format_error("Invalid role ID.", "0xBADA")
    
    async def remove_autorole(self, role_id: str) -> str:
        """Remove an autorole"""
        try:
            rid = int(role_id.strip('<@&>'))
            
            if self.security_cog.remove_autorole(self.guild.id, rid):
                return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Removed autorole."
            else:
                return f"{ANSIColors.YELLOW}Role is not an autorole.{ANSIColors.RESET}"
        except ValueError:
            return format_error("Invalid role ID.", "0xBADA")