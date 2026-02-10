"""
BlockForge OS - Terminal XP Panel
Configuration panel for the XP & Leveling system in BFOS terminal
"""

from utils.colors import ANSIColors
from utils.config import Config


class XPPanel:
    """Handles XP system configuration in BFOS terminal"""

    def __init__(self, session):
        self.session = session
        self.db = session.db
        self.guild = session.guild

    def format_error(self, message, code):
        return f"{ANSIColors.RED}\u274c Error: {message}{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Code: {code}{ANSIColors.RESET}"

    def _get_xp_cog(self):
        return self.session.bot.get_cog('XPSystem')

    async def handle_command(self, command_lower, user_input):
        output = ""
        should_exit = False

        if command_lower == "exit":
            output = await self.session.handle_exit()
            should_exit = True
        elif command_lower == "back":
            self.session.current_panel = "main"
            self.session.current_path = "System > Root"
            output = f"{ANSIColors.GREEN}Returned to main menu.{ANSIColors.RESET}"
        elif command_lower == "help":
            output = self.show_help()
        elif command_lower == "status":
            output = await self.show_status()
        elif command_lower.startswith("config "):
            output = await self.handle_config(user_input[7:].strip())
        elif command_lower == "config":
            output = self._config_help()
        elif command_lower.startswith("voice "):
            output = await self.handle_voice(user_input[6:].strip())
        elif command_lower == "voice":
            output = self._voice_help()
        elif command_lower.startswith("roles "):
            output = await self.handle_roles(user_input[6:].strip())
        elif command_lower == "roles":
            output = self._roles_help()
        elif command_lower.startswith("multiplier "):
            output = await self.handle_multiplier(user_input[11:].strip())
        elif command_lower == "multiplier":
            output = self._multiplier_help()
        elif command_lower.startswith("exclude "):
            output = await self.handle_exclude(user_input[8:].strip())
        elif command_lower == "exclude":
            output = self._exclude_help()
        else:
            output = self.format_error(f"Unknown command: {user_input}", Config.ERROR_CODES['INVALID_COMMAND'])

        return output, should_exit

    def show_help(self):
        return f"""
{ANSIColors.CYAN}{'=' * 50}{ANSIColors.RESET}
{ANSIColors.CYAN}|{ANSIColors.RESET}         {ANSIColors.BOLD}XP & Leveling Panel{ANSIColors.RESET}              {ANSIColors.CYAN}|{ANSIColors.RESET}
{ANSIColors.CYAN}{'=' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}General:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}status{ANSIColors.RESET}                     Show XP system overview

{ANSIColors.BRIGHT_CYAN}XP Config:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}config xpmessage <n>{ANSIColors.RESET}       XP per message
  {ANSIColors.BRIGHT_WHITE}config xpimage <n>{ANSIColors.RESET}         XP per image
  {ANSIColors.BRIGHT_WHITE}config xplink <n>{ANSIColors.RESET}          XP per link
  {ANSIColors.BRIGHT_WHITE}config xpvoice <n>{ANSIColors.RESET}         XP per voice minute
  {ANSIColors.BRIGHT_WHITE}config cooldown <sec>{ANSIColors.RESET}      Spam cooldown
  {ANSIColors.BRIGHT_WHITE}config curve <type>{ANSIColors.RESET}        linear | scaled | exponential
  {ANSIColors.BRIGHT_WHITE}config rolemode <type>{ANSIColors.RESET}     stack | replace
  {ANSIColors.BRIGHT_WHITE}config levelupchannel <id>{ANSIColors.RESET} Level-up announcement channel
  {ANSIColors.BRIGHT_WHITE}config levelupmessage <t>{ANSIColors.RESET}  Custom message ({{user}}, {{level}})
  {ANSIColors.BRIGHT_WHITE}config periods <list>{ANSIColors.RESET}      all_time,weekly,monthly

{ANSIColors.BRIGHT_CYAN}Voice XP:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}voice unmuted <on|off>{ANSIColors.RESET}     Require unmuted
  {ANSIColors.BRIGHT_WHITE}voice undeafened <on|off>{ANSIColors.RESET}  Require undeafened
  {ANSIColors.BRIGHT_WHITE}voice notalone <on|off>{ANSIColors.RESET}    Require not alone
  {ANSIColors.BRIGHT_WHITE}voice afk <on|off>{ANSIColors.RESET}         Exclude AFK channel

{ANSIColors.BRIGHT_CYAN}Level Roles:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}roles list{ANSIColors.RESET}                 List level roles
  {ANSIColors.BRIGHT_WHITE}roles add <level> <role_id>{ANSIColors.RESET} Add level role
  {ANSIColors.BRIGHT_WHITE}roles remove <level>{ANSIColors.RESET}       Remove level role

{ANSIColors.BRIGHT_CYAN}Multipliers:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}multiplier list{ANSIColors.RESET}            List multipliers
  {ANSIColors.BRIGHT_WHITE}multiplier add <type> <id> <x>{ANSIColors.RESET} Add multiplier
  {ANSIColors.BRIGHT_WHITE}multiplier remove <id>{ANSIColors.RESET}     Remove multiplier

{ANSIColors.BRIGHT_CYAN}Exclusions:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}exclude list{ANSIColors.RESET}               List exclusions
  {ANSIColors.BRIGHT_WHITE}exclude add <type> <id>{ANSIColors.RESET}    Add exclusion
  {ANSIColors.BRIGHT_WHITE}exclude remove <type> <id>{ANSIColors.RESET} Remove exclusion

{ANSIColors.BRIGHT_CYAN}Navigation:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                       Return to main menu
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}                       Exit terminal
"""

    async def show_status(self):
        cog = self._get_xp_cog()
        if not cog:
            return self.format_error("XP system cog not loaded", Config.ERROR_CODES['MODULE_DISABLED'])

        config = cog.get_xp_config(self.guild.id)
        enabled = self.db.get_module_state(self.guild.id, 'xp')
        level_roles = cog.get_xp_level_roles(self.guild.id) if cog else []
        multipliers = cog.get_xp_multipliers(self.guild.id) if cog else []

        output = f"""
{ANSIColors.CYAN}{'=' * 50}{ANSIColors.RESET}
{ANSIColors.CYAN}|{ANSIColors.RESET}         {ANSIColors.BOLD}XP System Status{ANSIColors.RESET}                 {ANSIColors.CYAN}|{ANSIColors.RESET}
{ANSIColors.CYAN}{'=' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Module Enabled:      {ANSIColors.GREEN if enabled else ANSIColors.RED}{'Yes' if enabled else 'No'}{ANSIColors.RESET}
"""
        if config:
            lu_ch = self.guild.get_channel(config['levelup_channel_id']) if config.get('levelup_channel_id') else None
            output += f"""{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}XP/Message:          {ANSIColors.BRIGHT_WHITE}{config.get('xp_per_message', 15)}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}XP/Image:            {ANSIColors.BRIGHT_WHITE}{config.get('xp_per_image', 20)}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}XP/Link:             {ANSIColors.BRIGHT_WHITE}{config.get('xp_per_link', 10)}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}XP/Voice Min:        {ANSIColors.BRIGHT_WHITE}{config.get('xp_per_voice_minute', 5)}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Spam Cooldown:       {ANSIColors.BRIGHT_WHITE}{config.get('spam_cooldown_seconds', 60)}s{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Level Curve:         {ANSIColors.BRIGHT_WHITE}{config.get('level_curve', 'scaled')}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Role Mode:           {ANSIColors.BRIGHT_WHITE}{config.get('level_role_mode', 'stack')}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Level-Up Channel:    {ANSIColors.BRIGHT_WHITE}{lu_ch.name if lu_ch else 'Current channel'}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Level Roles:         {ANSIColors.BRIGHT_WHITE}{len(level_roles)}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Multipliers:         {ANSIColors.BRIGHT_WHITE}{len(multipliers)}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Voice Unmuted:       {ANSIColors.GREEN if config.get('voice_require_unmuted') else ANSIColors.RED}{'On' if config.get('voice_require_unmuted') else 'Off'}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Voice Undeafened:    {ANSIColors.GREEN if config.get('voice_require_undeafened') else ANSIColors.RED}{'On' if config.get('voice_require_undeafened') else 'Off'}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Voice Not Alone:     {ANSIColors.GREEN if config.get('voice_require_not_alone') else ANSIColors.RED}{'On' if config.get('voice_require_not_alone') else 'Off'}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Exclude AFK:         {ANSIColors.GREEN if config.get('voice_exclude_afk') else ANSIColors.RED}{'On' if config.get('voice_exclude_afk') else 'Off'}{ANSIColors.RESET}
"""
        else:
            output += f"\n{ANSIColors.YELLOW}No configuration found. Enable the module and it will auto-configure.{ANSIColors.RESET}\n"

        return output

    # ==================== CONFIG ====================

    def _config_help(self):
        return f"""
{ANSIColors.BRIGHT_CYAN}Config Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}config xpmessage <n>{ANSIColors.RESET}        XP per message (default: 15)
  {ANSIColors.BRIGHT_WHITE}config xpimage <n>{ANSIColors.RESET}          XP per image (default: 20)
  {ANSIColors.BRIGHT_WHITE}config xplink <n>{ANSIColors.RESET}           XP per link (default: 10)
  {ANSIColors.BRIGHT_WHITE}config xpvoice <n>{ANSIColors.RESET}          XP per voice minute (default: 5)
  {ANSIColors.BRIGHT_WHITE}config cooldown <sec>{ANSIColors.RESET}       Spam cooldown (default: 60)
  {ANSIColors.BRIGHT_WHITE}config curve <type>{ANSIColors.RESET}         linear | scaled | exponential
  {ANSIColors.BRIGHT_WHITE}config rolemode <type>{ANSIColors.RESET}      stack | replace
  {ANSIColors.BRIGHT_WHITE}config levelupchannel <id>{ANSIColors.RESET}  Level-up channel ID
  {ANSIColors.BRIGHT_WHITE}config levelupmessage <t>{ANSIColors.RESET}   Use {{user}} and {{level}} placeholders
  {ANSIColors.BRIGHT_WHITE}config periods <list>{ANSIColors.RESET}       Comma-separated: all_time,weekly,monthly
"""

    async def handle_config(self, args):
        cog = self._get_xp_cog()
        if not cog:
            return self.format_error("XP system cog not loaded", Config.ERROR_CODES['MODULE_DISABLED'])

        parts = args.split(maxsplit=1)
        key = parts[0].lower() if parts else ""
        value = parts[1].strip() if len(parts) > 1 else ""

        if not key or not value:
            return self._config_help()

        int_fields = {
            'xpmessage': ('xp_per_message', 1, 1000),
            'xpimage': ('xp_per_image', 1, 1000),
            'xplink': ('xp_per_link', 1, 1000),
            'xpvoice': ('xp_per_voice_minute', 1, 100),
            'cooldown': ('spam_cooldown_seconds', 0, 3600),
        }

        if key in int_fields:
            db_key, min_val, max_val = int_fields[key]
            try:
                n = int(value)
                if n < min_val or n > max_val:
                    raise ValueError
            except ValueError:
                return self.format_error(f"Must be a number between {min_val}-{max_val}", Config.ERROR_CODES['INVALID_INPUT'])
            cog.set_xp_config(self.guild.id, **{db_key: n})
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} {key} set to {n}."

        elif key == 'curve':
            if value not in ('linear', 'scaled', 'exponential'):
                return self.format_error("Options: linear, scaled, exponential", Config.ERROR_CODES['INVALID_INPUT'])
            cog.set_xp_config(self.guild.id, level_curve=value)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Level curve set to '{value}'."

        elif key == 'rolemode':
            if value not in ('stack', 'replace'):
                return self.format_error("Options: stack, replace", Config.ERROR_CODES['INVALID_INPUT'])
            cog.set_xp_config(self.guild.id, level_role_mode=value)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Role mode set to '{value}'."

        elif key == 'levelupchannel':
            try:
                ch_id = int(value)
            except ValueError:
                return self.format_error("Invalid channel ID", Config.ERROR_CODES['INVALID_INPUT'])
            ch = self.guild.get_channel(ch_id)
            if not ch:
                return self.format_error("Channel not found", Config.ERROR_CODES['CHANNEL_NOT_FOUND'])
            cog.set_xp_config(self.guild.id, levelup_channel_id=ch_id)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Level-up channel set to #{ch.name}."

        elif key == 'levelupmessage':
            cog.set_xp_config(self.guild.id, levelup_message=value)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Level-up message set."

        elif key == 'periods':
            valid = {'all_time', 'weekly', 'monthly'}
            periods = [p.strip() for p in value.split(',')]
            invalid = [p for p in periods if p not in valid]
            if invalid:
                return self.format_error(f"Invalid period(s): {', '.join(invalid)}. Options: all_time, weekly, monthly", Config.ERROR_CODES['INVALID_INPUT'])
            cog.set_xp_config(self.guild.id, leaderboard_periods=periods)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Leaderboard periods set to: {', '.join(periods)}."

        return self._config_help()

    # ==================== VOICE CONFIG ====================

    def _voice_help(self):
        return f"""
{ANSIColors.BRIGHT_CYAN}Voice XP Conditions:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}voice unmuted <on|off>{ANSIColors.RESET}     Must not be self-muted
  {ANSIColors.BRIGHT_WHITE}voice undeafened <on|off>{ANSIColors.RESET}  Must not be self-deafened
  {ANSIColors.BRIGHT_WHITE}voice notalone <on|off>{ANSIColors.RESET}    Must not be alone in VC
  {ANSIColors.BRIGHT_WHITE}voice afk <on|off>{ANSIColors.RESET}         Exclude AFK channel
"""

    async def handle_voice(self, args):
        cog = self._get_xp_cog()
        if not cog:
            return self.format_error("XP system cog not loaded", Config.ERROR_CODES['MODULE_DISABLED'])

        parts = args.split(maxsplit=1)
        key = parts[0].lower() if parts else ""
        value = parts[1].strip().lower() if len(parts) > 1 else ""

        field_map = {
            'unmuted': 'voice_require_unmuted',
            'undeafened': 'voice_require_undeafened',
            'notalone': 'voice_require_not_alone',
            'afk': 'voice_exclude_afk',
        }

        if key not in field_map or value not in ('on', 'off'):
            return self._voice_help()

        enabled = 1 if value == 'on' else 0
        cog.set_xp_config(self.guild.id, **{field_map[key]: enabled})
        return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Voice '{key}' set to {value}."

    # ==================== LEVEL ROLES ====================

    def _roles_help(self):
        return f"""
{ANSIColors.BRIGHT_CYAN}Level Role Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}roles list{ANSIColors.RESET}                  List all level roles
  {ANSIColors.BRIGHT_WHITE}roles add <level> <role_id>{ANSIColors.RESET} Assign role to level (max 30)
  {ANSIColors.BRIGHT_WHITE}roles remove <level>{ANSIColors.RESET}        Remove role from level
"""

    async def handle_roles(self, args):
        cog = self._get_xp_cog()
        if not cog:
            return self.format_error("XP system cog not loaded", Config.ERROR_CODES['MODULE_DISABLED'])

        parts = args.split(maxsplit=2)
        subcmd = parts[0].lower() if parts else ""

        if subcmd == 'list':
            roles = cog.get_xp_level_roles(self.guild.id)
            if not roles:
                return f"{ANSIColors.BRIGHT_BLACK}No level roles configured.{ANSIColors.RESET}"
            output = f"{ANSIColors.BRIGHT_CYAN}Level Roles:{ANSIColors.RESET}\n"
            for lr in roles:
                role = self.guild.get_role(lr['role_id'])
                name = role.name if role else str(lr['role_id'])
                output += f"  Level {ANSIColors.BRIGHT_WHITE}{lr['level']}{ANSIColors.RESET} -> {name}\n"
            return output

        elif subcmd == 'add' and len(parts) >= 3:
            try:
                level = int(parts[1])
                role_id = int(parts[2])
            except ValueError:
                return self.format_error("Invalid level or role ID", Config.ERROR_CODES['INVALID_INPUT'])

            existing = cog.get_xp_level_roles(self.guild.id)
            if len(existing) >= 30:
                return self.format_error("Maximum 30 level roles reached", Config.ERROR_CODES['INVALID_INPUT'])

            role = self.guild.get_role(role_id)
            if not role:
                return self.format_error("Role not found", Config.ERROR_CODES['ROLE_NOT_FOUND'])

            cog.set_xp_level_role(self.guild.id, level, role_id)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Level {level} -> @{role.name}"

        elif subcmd == 'remove' and len(parts) >= 2:
            try:
                level = int(parts[1])
            except ValueError:
                return self.format_error("Invalid level", Config.ERROR_CODES['INVALID_INPUT'])
            cog.remove_xp_level_role(self.guild.id, level)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Level role for level {level} removed."

        return self._roles_help()

    # ==================== MULTIPLIERS ====================

    def _multiplier_help(self):
        return f"""
{ANSIColors.BRIGHT_CYAN}Multiplier Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}multiplier list{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}multiplier add <type> <target_id> <multiplier>{ANSIColors.RESET}
    Types: global, channel, role
    Example: multiplier add channel 123456 2.0
  {ANSIColors.BRIGHT_WHITE}multiplier remove <id>{ANSIColors.RESET}
"""

    async def handle_multiplier(self, args):
        cog = self._get_xp_cog()
        if not cog:
            return self.format_error("XP system cog not loaded", Config.ERROR_CODES['MODULE_DISABLED'])

        parts = args.split(maxsplit=3)
        subcmd = parts[0].lower() if parts else ""

        if subcmd == 'list':
            mults = cog.get_xp_multipliers(self.guild.id)
            if not mults:
                return f"{ANSIColors.BRIGHT_BLACK}No multipliers configured.{ANSIColors.RESET}"
            output = f"{ANSIColors.BRIGHT_CYAN}XP Multipliers:{ANSIColors.RESET}\n"
            for m in mults:
                target = ""
                if m['type'] == 'channel':
                    ch = self.guild.get_channel(m['target_id'])
                    target = f" #{ch.name}" if ch else f" {m['target_id']}"
                elif m['type'] == 'role':
                    role = self.guild.get_role(m['target_id'])
                    target = f" @{role.name}" if role else f" {m['target_id']}"
                elif m['type'] == 'global':
                    target = " (all)"

                expires = f" (expires: {m['expires_at']})" if m.get('expires_at') else ""
                output += f"  [{m['id']}] {m['type']}{target}: {ANSIColors.BRIGHT_WHITE}{m['multiplier']}x{ANSIColors.RESET}{expires}\n"
            return output

        elif subcmd == 'add' and len(parts) >= 4:
            mult_type = parts[1].lower()
            if mult_type not in ('global', 'channel', 'role'):
                return self.format_error("Type must be: global, channel, or role", Config.ERROR_CODES['INVALID_INPUT'])
            try:
                target_id = int(parts[2])
                multiplier = float(parts[3])
            except ValueError:
                return self.format_error("Invalid target ID or multiplier", Config.ERROR_CODES['INVALID_INPUT'])
            if multiplier <= 0 or multiplier > 10:
                return self.format_error("Multiplier must be between 0.1 and 10", Config.ERROR_CODES['INVALID_INPUT'])

            mid = cog.add_xp_multiplier(self.guild.id, mult_type, target_id, multiplier)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Multiplier added (ID: {mid}): {mult_type} {target_id} = {multiplier}x"

        elif subcmd == 'remove' and len(parts) >= 2:
            try:
                mid = int(parts[1])
            except ValueError:
                return self.format_error("Invalid multiplier ID", Config.ERROR_CODES['INVALID_INPUT'])
            cog.remove_xp_multiplier(mid)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Multiplier {mid} removed."

        return self._multiplier_help()

    # ==================== EXCLUSIONS ====================

    def _exclude_help(self):
        return f"""
{ANSIColors.BRIGHT_CYAN}Exclusion Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}exclude list{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}exclude add <type> <target_id>{ANSIColors.RESET}
    Types: channel, role, user
  {ANSIColors.BRIGHT_WHITE}exclude remove <type> <target_id>{ANSIColors.RESET}
"""

    async def handle_exclude(self, args):
        cog = self._get_xp_cog()
        if not cog:
            return self.format_error("XP system cog not loaded", Config.ERROR_CODES['MODULE_DISABLED'])

        parts = args.split(maxsplit=2)
        subcmd = parts[0].lower() if parts else ""

        if subcmd == 'list':
            conn = self.db._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type, target_id FROM xp_excluded WHERE guild_id = ?', (self.guild.id,))
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return f"{ANSIColors.BRIGHT_BLACK}No exclusions configured.{ANSIColors.RESET}"

            output = f"{ANSIColors.BRIGHT_CYAN}XP Exclusions:{ANSIColors.RESET}\n"
            for exc_type, target_id in rows:
                name = str(target_id)
                if exc_type == 'channel':
                    ch = self.guild.get_channel(target_id)
                    name = f"#{ch.name}" if ch else name
                elif exc_type == 'role':
                    role = self.guild.get_role(target_id)
                    name = f"@{role.name}" if role else name
                elif exc_type == 'user':
                    member = self.guild.get_member(target_id)
                    name = member.display_name if member else name
                output += f"  {exc_type}: {ANSIColors.BRIGHT_WHITE}{name}{ANSIColors.RESET}\n"
            return output

        elif subcmd == 'add' and len(parts) >= 3:
            exc_type = parts[1].lower()
            if exc_type not in ('channel', 'role', 'user'):
                return self.format_error("Type must be: channel, role, or user", Config.ERROR_CODES['INVALID_INPUT'])
            try:
                target_id = int(parts[2])
            except ValueError:
                return self.format_error("Invalid target ID", Config.ERROR_CODES['INVALID_INPUT'])
            cog.add_xp_exclusion(self.guild.id, exc_type, target_id)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Exclusion added: {exc_type} {target_id}"

        elif subcmd == 'remove' and len(parts) >= 3:
            exc_type = parts[1].lower()
            try:
                target_id = int(parts[2])
            except ValueError:
                return self.format_error("Invalid target ID", Config.ERROR_CODES['INVALID_INPUT'])
            cog.remove_xp_exclusion(self.guild.id, exc_type, target_id)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Exclusion removed: {exc_type} {target_id}"

        return self._exclude_help()
