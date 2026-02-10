"""
BlockForge OS - Terminal Tickets Panel
Configuration panel for the ticket system in BFOS terminal
"""

from utils.colors import ANSIColors
from utils.config import Config


class TicketPanel:
    """Handles ticket configuration in BFOS terminal"""

    def __init__(self, session):
        self.session = session
        self.db = session.db
        self.guild = session.guild

    def format_error(self, message, code):
        return f"{ANSIColors.RED}\u274c Error: {message}{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Code: {code}{ANSIColors.RESET}"

    def _get_ticket_cog(self):
        return self.session.bot.get_cog('TicketSystem')

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
        elif command_lower.startswith("category "):
            output = await self.handle_category(user_input[9:].strip())
        elif command_lower == "category":
            output = self._category_help()
        elif command_lower.startswith("panel "):
            output = await self.handle_panel(user_input[6:].strip())
        elif command_lower == "panel":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} panel style <buttons|dropdown> | panel embed"
        elif command_lower == "deploy":
            output = await self.handle_deploy()
        elif command_lower.startswith("config "):
            output = await self.handle_config(user_input[7:].strip())
        elif command_lower == "config":
            output = self._config_help()
        else:
            output = self.format_error(f"Unknown command: {user_input}", Config.ERROR_CODES['INVALID_COMMAND'])

        return output, should_exit

    def show_help(self):
        return f"""
{ANSIColors.CYAN}{'=' * 50}{ANSIColors.RESET}
{ANSIColors.CYAN}|{ANSIColors.RESET}          {ANSIColors.BOLD}Ticket System Panel{ANSIColors.RESET}              {ANSIColors.CYAN}|{ANSIColors.RESET}
{ANSIColors.CYAN}{'=' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}General:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}status{ANSIColors.RESET}                    Show ticket system overview
  {ANSIColors.BRIGHT_WHITE}deploy{ANSIColors.RESET}                    Send/update ticket panel

{ANSIColors.BRIGHT_CYAN}Categories:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}category list{ANSIColors.RESET}              List all categories
  {ANSIColors.BRIGHT_WHITE}category add{ANSIColors.RESET}               Add a new category (guided)
  {ANSIColors.BRIGHT_WHITE}category edit <id>{ANSIColors.RESET}         Edit a category
  {ANSIColors.BRIGHT_WHITE}category delete <id>{ANSIColors.RESET}       Delete a category

{ANSIColors.BRIGHT_CYAN}Panel:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}panel style <type>{ANSIColors.RESET}         Set panel style (buttons/dropdown)
  {ANSIColors.BRIGHT_WHITE}panel embed{ANSIColors.RESET}                Customize panel embed

{ANSIColors.BRIGHT_CYAN}Configuration:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}config closebehavior <v>{ANSIColors.RESET}   wait_delete | archive | instant_delete
  {ANSIColors.BRIGHT_WHITE}config maxtickets <n>{ANSIColors.RESET}      Max tickets per user
  {ANSIColors.BRIGHT_WHITE}config transcriptchannel <id>{ANSIColors.RESET} Transcript log channel
  {ANSIColors.BRIGHT_WHITE}config claiming <on|off>{ANSIColors.RESET}   Enable/disable claiming
  {ANSIColors.BRIGHT_WHITE}config panelchannel <id>{ANSIColors.RESET}   Set panel channel
  {ANSIColors.BRIGHT_WHITE}config deletedelay <sec>{ANSIColors.RESET}   Delay before delete (seconds)

{ANSIColors.BRIGHT_CYAN}Navigation:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                       Return to main menu
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}                       Exit terminal
"""

    async def show_status(self):
        cog = self._get_ticket_cog()
        if not cog:
            return self.format_error("Ticket system cog not loaded", Config.ERROR_CODES['MODULE_DISABLED'])

        config = cog.get_ticket_config(self.guild.id)
        categories = cog.get_ticket_categories(self.guild.id)
        open_tickets = cog.get_all_open_tickets(self.guild.id)
        enabled = self.db.get_module_state(self.guild.id, 'tickets')

        output = f"""
{ANSIColors.CYAN}{'=' * 50}{ANSIColors.RESET}
{ANSIColors.CYAN}|{ANSIColors.RESET}         {ANSIColors.BOLD}Ticket System Status{ANSIColors.RESET}             {ANSIColors.CYAN}|{ANSIColors.RESET}
{ANSIColors.CYAN}{'=' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Module Enabled:     {ANSIColors.GREEN if enabled else ANSIColors.RED}{'Yes' if enabled else 'No'}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Categories:         {ANSIColors.BRIGHT_WHITE}{len(categories)}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Open Tickets:       {ANSIColors.BRIGHT_WHITE}{len(open_tickets)}{ANSIColors.RESET}
"""
        if config:
            panel_ch = self.guild.get_channel(config['panel_channel_id']) if config.get('panel_channel_id') else None
            transcript_ch = self.guild.get_channel(config['transcript_channel_id']) if config.get('transcript_channel_id') else None
            output += f"""{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Panel Channel:      {ANSIColors.BRIGHT_WHITE}{panel_ch.name if panel_ch else 'Not set'}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Panel Style:        {ANSIColors.BRIGHT_WHITE}{config.get('panel_style', 'buttons')}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Close Behavior:     {ANSIColors.BRIGHT_WHITE}{config.get('close_behavior', 'wait_delete')}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Max Tickets/User:   {ANSIColors.BRIGHT_WHITE}{config.get('max_tickets_per_user', 3)}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Transcript Channel: {ANSIColors.BRIGHT_WHITE}{transcript_ch.name if transcript_ch else 'Not set'}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Claiming:           {ANSIColors.GREEN if config.get('claim_enabled') else ANSIColors.RED}{'Enabled' if config.get('claim_enabled') else 'Disabled'}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}> {ANSIColors.RESET}Delete Delay:       {ANSIColors.BRIGHT_WHITE}{config.get('delete_delay_seconds', 300)}s{ANSIColors.RESET}
"""
        else:
            output += f"\n{ANSIColors.YELLOW}No configuration found. Use 'config' commands to set up.{ANSIColors.RESET}\n"

        return output

    # ==================== CATEGORY COMMANDS ====================

    def _category_help(self):
        return f"""
{ANSIColors.BRIGHT_CYAN}Category Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}category list{ANSIColors.RESET}          List all categories
  {ANSIColors.BRIGHT_WHITE}category add{ANSIColors.RESET}           Add new category
  {ANSIColors.BRIGHT_WHITE}category edit <id>{ANSIColors.RESET}     Edit a category field
  {ANSIColors.BRIGHT_WHITE}category delete <id>{ANSIColors.RESET}   Delete a category
"""

    async def handle_category(self, args):
        cog = self._get_ticket_cog()
        if not cog:
            return self.format_error("Ticket system cog not loaded", Config.ERROR_CODES['MODULE_DISABLED'])

        parts = args.split(maxsplit=1)
        subcmd = parts[0].lower() if parts else ""

        if subcmd == "list":
            categories = cog.get_ticket_categories(self.guild.id)
            if not categories:
                return f"{ANSIColors.BRIGHT_BLACK}No categories created yet. Use 'category add' to create one.{ANSIColors.RESET}"

            output = f"""
{ANSIColors.CYAN}{'=' * 50}{ANSIColors.RESET}
{ANSIColors.CYAN}|{ANSIColors.RESET}         {ANSIColors.BOLD}Ticket Categories{ANSIColors.RESET}                {ANSIColors.CYAN}|{ANSIColors.RESET}
{ANSIColors.CYAN}{'=' * 50}{ANSIColors.RESET}
"""
            for cat in categories:
                emoji = cat.get('emoji', '') or ''
                desc = cat.get('description', 'No description') or 'No description'
                dc_cat = self.guild.get_channel(cat['channel_category_id']) if cat.get('channel_category_id') else None
                ping_count = len(cat.get('ping_roles', []))
                output += f"""
{ANSIColors.BRIGHT_WHITE}[{cat['id']}]{ANSIColors.RESET} {emoji} {ANSIColors.BRIGHT_CYAN}{cat['name']}{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Description:{ANSIColors.RESET} {desc[:60]}
    {ANSIColors.BRIGHT_BLACK}Discord Category:{ANSIColors.RESET} {dc_cat.name if dc_cat else 'None'}
    {ANSIColors.BRIGHT_BLACK}Ping Roles:{ANSIColors.RESET} {ping_count}
"""
            return output

        elif subcmd == "add":
            # Quick add — parse: category add <name> [emoji]
            remaining = parts[1].strip() if len(parts) > 1 else ""
            if not remaining:
                return f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} category add <name> [emoji]\n{ANSIColors.BRIGHT_BLACK}Example: category add General Support \U0001f4e9{ANSIColors.RESET}"

            # Try to detect emoji at the end
            add_parts = remaining.rsplit(maxsplit=1)
            name = remaining
            emoji = None
            if len(add_parts) == 2 and len(add_parts[1]) <= 4:
                # Might be an emoji
                name = add_parts[0]
                emoji = add_parts[1]

            cat_id = cog.add_ticket_category(self.guild.id, name, emoji=emoji)
            output = f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Category created: {ANSIColors.BRIGHT_WHITE}{name}{ANSIColors.RESET} (ID: {cat_id})\n"
            output += f"\n{ANSIColors.BRIGHT_BLACK}Use 'category edit {cat_id}' to set description, welcome message, Discord category, and ping roles.{ANSIColors.RESET}"
            return output

        elif subcmd == "edit":
            remaining = parts[1].strip() if len(parts) > 1 else ""
            edit_parts = remaining.split(maxsplit=2)
            if len(edit_parts) < 3:
                return f"""{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} category edit <id> <field> <value>

{ANSIColors.BRIGHT_CYAN}Fields:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}name{ANSIColors.RESET}              Category name
  {ANSIColors.BRIGHT_WHITE}emoji{ANSIColors.RESET}             Category emoji
  {ANSIColors.BRIGHT_WHITE}description{ANSIColors.RESET}       Short description
  {ANSIColors.BRIGHT_WHITE}welcome{ANSIColors.RESET}           Welcome message in ticket
  {ANSIColors.BRIGHT_WHITE}discordcategory{ANSIColors.RESET}   Discord category ID for channels
  {ANSIColors.BRIGHT_WHITE}pingroles{ANSIColors.RESET}         Comma-separated role IDs
  {ANSIColors.BRIGHT_WHITE}color{ANSIColors.RESET}             Hex color (e.g. 5865F2)
"""
            try:
                cat_id = int(edit_parts[0])
            except ValueError:
                return self.format_error("Invalid category ID", Config.ERROR_CODES['INVALID_INPUT'])

            field = edit_parts[1].lower()
            value = edit_parts[2]

            cat = cog.get_ticket_category(cat_id)
            if not cat or cat['guild_id'] != self.guild.id:
                return self.format_error("Category not found", Config.ERROR_CODES['INVALID_INPUT'])

            field_map = {
                'name': 'name', 'emoji': 'emoji', 'description': 'description',
                'welcome': 'welcome_message', 'discordcategory': 'channel_category_id',
                'pingroles': 'ping_roles', 'color': 'color',
            }

            db_field = field_map.get(field)
            if not db_field:
                return self.format_error(f"Unknown field: {field}", Config.ERROR_CODES['INVALID_INPUT'])

            if field == 'discordcategory':
                try:
                    value = int(value)
                except ValueError:
                    return self.format_error("Invalid category ID", Config.ERROR_CODES['INVALID_INPUT'])
            elif field == 'pingroles':
                value = [r.strip() for r in value.split(',') if r.strip()]
            elif field == 'color':
                try:
                    value = int(value, 16)
                except ValueError:
                    return self.format_error("Invalid hex color", Config.ERROR_CODES['INVALID_INPUT'])

            cog.update_ticket_category(cat_id, **{db_field: value})
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Category {cat_id} field '{field}' updated."

        elif subcmd == "delete":
            remaining = parts[1].strip() if len(parts) > 1 else ""
            if not remaining:
                return f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} category delete <id>"
            try:
                cat_id = int(remaining)
            except ValueError:
                return self.format_error("Invalid category ID", Config.ERROR_CODES['INVALID_INPUT'])

            cat = cog.get_ticket_category(cat_id)
            if not cat or cat['guild_id'] != self.guild.id:
                return self.format_error("Category not found", Config.ERROR_CODES['INVALID_INPUT'])

            cog.delete_ticket_category(cat_id)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Category '{cat['name']}' deleted."

        return self._category_help()

    # ==================== PANEL COMMANDS ====================

    async def handle_panel(self, args):
        cog = self._get_ticket_cog()
        if not cog:
            return self.format_error("Ticket system cog not loaded", Config.ERROR_CODES['MODULE_DISABLED'])

        parts = args.split(maxsplit=1)
        subcmd = parts[0].lower() if parts else ""

        if subcmd == "style":
            value = parts[1].strip().lower() if len(parts) > 1 else ""
            if value not in ('buttons', 'dropdown'):
                return f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} panel style <buttons|dropdown>"
            cog.set_ticket_config(self.guild.id, panel_style=value)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Panel style set to '{value}'. Use 'deploy' to update the panel."

        elif subcmd == "embed":
            remaining = parts[1].strip() if len(parts) > 1 else ""
            if not remaining:
                panel_data = cog.get_ticket_panel_data(self.guild.id)
                return f"""{ANSIColors.BRIGHT_CYAN}Panel Embed Settings:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}Title:{ANSIColors.RESET}       {panel_data.get('title', 'Support Tickets')}
  {ANSIColors.BRIGHT_BLACK}Description:{ANSIColors.RESET} {panel_data.get('description', 'Click a button below...')}
  {ANSIColors.BRIGHT_BLACK}Color:{ANSIColors.RESET}       {hex(panel_data.get('color', 0x5865F2))}

{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} panel embed <field> <value>
  Fields: title, description, color, footer, thumbnail
"""
            embed_parts = remaining.split(maxsplit=1)
            if len(embed_parts) < 2:
                return f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} panel embed <field> <value>"

            field = embed_parts[0].lower()
            value = embed_parts[1]
            panel_data = cog.get_ticket_panel_data(self.guild.id)

            if field == 'color':
                try:
                    value = int(value, 16)
                except ValueError:
                    return self.format_error("Invalid hex color", Config.ERROR_CODES['INVALID_INPUT'])

            panel_data[field] = value
            cog.set_ticket_panel_data(self.guild.id, panel_data)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Panel embed '{field}' updated. Use 'deploy' to apply changes."

        return f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} panel style <buttons|dropdown> | panel embed [field] [value]"

    # ==================== DEPLOY ====================

    async def handle_deploy(self):
        cog = self._get_ticket_cog()
        if not cog:
            return self.format_error("Ticket system cog not loaded", Config.ERROR_CODES['MODULE_DISABLED'])

        config = cog.get_ticket_config(self.guild.id)
        if not config or not config.get('panel_channel_id'):
            return self.format_error("Set a panel channel first: config panelchannel <channel_id>", Config.ERROR_CODES['SETUP_INCOMPLETE'])

        categories = cog.get_ticket_categories(self.guild.id)
        if not categories:
            return self.format_error("Create at least one category first: category add <name>", Config.ERROR_CODES['SETUP_INCOMPLETE'])

        try:
            msg = await cog.deploy_panel(self.guild)
            if msg:
                return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Ticket panel deployed to #{self.guild.get_channel(config['panel_channel_id']).name}!"
            else:
                return self.format_error("Failed to deploy panel. Check channel and permissions.", Config.ERROR_CODES['COMMAND_FAILED'])
        except Exception as e:
            return self.format_error(f"Deploy failed: {e}", Config.ERROR_CODES['COMMAND_FAILED'])

    # ==================== CONFIG ====================

    def _config_help(self):
        return f"""
{ANSIColors.BRIGHT_CYAN}Config Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}config closebehavior <value>{ANSIColors.RESET}
    Options: wait_delete, archive, instant_delete

  {ANSIColors.BRIGHT_WHITE}config maxtickets <number>{ANSIColors.RESET}
    Max tickets per user (default: 3)

  {ANSIColors.BRIGHT_WHITE}config transcriptchannel <channel_id>{ANSIColors.RESET}
    Channel for ticket transcripts

  {ANSIColors.BRIGHT_WHITE}config claiming <on|off>{ANSIColors.RESET}
    Enable/disable ticket claiming

  {ANSIColors.BRIGHT_WHITE}config panelchannel <channel_id>{ANSIColors.RESET}
    Channel where the ticket panel is sent

  {ANSIColors.BRIGHT_WHITE}config deletedelay <seconds>{ANSIColors.RESET}
    Seconds before deleting closed ticket channel
"""

    async def handle_config(self, args):
        cog = self._get_ticket_cog()
        if not cog:
            return self.format_error("Ticket system cog not loaded", Config.ERROR_CODES['MODULE_DISABLED'])

        parts = args.split(maxsplit=1)
        key = parts[0].lower() if parts else ""
        value = parts[1].strip() if len(parts) > 1 else ""

        if not key or not value:
            return self._config_help()

        if key == "closebehavior":
            if value not in ('wait_delete', 'archive', 'instant_delete'):
                return self.format_error("Invalid value. Options: wait_delete, archive, instant_delete", Config.ERROR_CODES['INVALID_INPUT'])
            cog.set_ticket_config(self.guild.id, close_behavior=value)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Close behavior set to '{value}'."

        elif key == "maxtickets":
            try:
                n = int(value)
                if n < 1 or n > 25:
                    raise ValueError
            except ValueError:
                return self.format_error("Must be a number between 1-25", Config.ERROR_CODES['INVALID_INPUT'])
            cog.set_ticket_config(self.guild.id, max_tickets_per_user=n)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Max tickets per user set to {n}."

        elif key == "transcriptchannel":
            try:
                ch_id = int(value)
            except ValueError:
                return self.format_error("Invalid channel ID", Config.ERROR_CODES['INVALID_INPUT'])
            ch = self.guild.get_channel(ch_id)
            if not ch:
                return self.format_error("Channel not found", Config.ERROR_CODES['CHANNEL_NOT_FOUND'])
            cog.set_ticket_config(self.guild.id, transcript_channel_id=ch_id)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Transcript channel set to #{ch.name}."

        elif key == "claiming":
            enabled = value.lower() in ('on', 'true', 'yes', '1')
            cog.set_ticket_config(self.guild.id, claim_enabled=int(enabled))
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Claiming {'enabled' if enabled else 'disabled'}."

        elif key == "panelchannel":
            try:
                ch_id = int(value)
            except ValueError:
                return self.format_error("Invalid channel ID", Config.ERROR_CODES['INVALID_INPUT'])
            ch = self.guild.get_channel(ch_id)
            if not ch:
                return self.format_error("Channel not found", Config.ERROR_CODES['CHANNEL_NOT_FOUND'])
            cog.set_ticket_config(self.guild.id, panel_channel_id=ch_id)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Panel channel set to #{ch.name}."

        elif key == "deletedelay":
            try:
                seconds = int(value)
                if seconds < 10 or seconds > 86400:
                    raise ValueError
            except ValueError:
                return self.format_error("Must be a number between 10-86400 seconds", Config.ERROR_CODES['INVALID_INPUT'])
            cog.set_ticket_config(self.guild.id, delete_delay_seconds=seconds)
            return f"{ANSIColors.GREEN}\u2713{ANSIColors.RESET} Delete delay set to {seconds} seconds."

        return self._config_help()
