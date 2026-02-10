# ==================== WORKING EMBED EDITOR FOR terminal.py ====================

# Add this to TerminalSession class in terminal.py

# ==================== EMBED EDITOR STATE ====================
# Add to __init__ method:
def __init__(self, bot, ctx, db):
    # ... existing init code ...
    
    # Embed editor state
    self.editing_embed = None  # Current embed being edited
    self.embed_data = {}  # Temporary embed data

# ==================== EMBED EDITOR PANEL ====================

async def handle_embed_panel(self, command_lower, user_input):
    """Handle commands in embed panel"""
    output = ""
    should_exit = False
    
    # Check if we're in edit mode
    if self.editing_embed:
        return await self.handle_embed_edit_commands(command_lower, user_input)
    
    # Regular embed panel commands
    if command_lower == "exit":
        output = await self.handle_exit()
        should_exit = True
    elif command_lower == "back":
        self.current_panel = "config"
        self.current_path = "Configuration"
        output = f"{ANSIColors.GREEN}Returned to configuration.{ANSIColors.RESET}"
    elif command_lower == "help":
        output = self.show_embed_help()
    elif command_lower == "list":
        output = await self.handle_embed_list()
    elif command_lower.startswith("edit "):
        embed_id = user_input[5:].strip()
        output = await self.handle_embed_edit_start(embed_id)
    elif command_lower == "edit":
        output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}edit <id>{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Example: edit warnings_response{ANSIColors.RESET}"
    elif command_lower.startswith("preview "):
        parts = user_input[8:].strip().split()
        if len(parts) >= 2 and parts[-1] == "-real":
            embed_id = " ".join(parts[:-1])
            await self.handle_embed_preview_real(embed_id)
            output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Real embed sent below!"
        else:
            embed_id = user_input[8:].strip()
            output = await self.handle_embed_preview_text(embed_id)
    elif command_lower == "preview":
        output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}preview <id> [-real]{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Example: preview warnings_dm -real{ANSIColors.RESET}"
    elif command_lower.startswith("reset "):
        embed_id = user_input[6:].strip()
        output = await self.handle_embed_reset(embed_id)
    elif command_lower == "reset":
        output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}reset <id>{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Example: reset warnings_response{ANSIColors.RESET}"
    else:
        output = format_error(
            f"Invalid command '{user_input}'. Type 'help' for embed commands.",
            Config.ERROR_CODES['INVALID_COMMAND']
        )
    
    return output, should_exit

# ==================== EMBED EDIT MODE ====================

async def handle_embed_edit_start(self, embed_id):
    """Start editing an embed"""
    valid_ids = ['warnings_response', 'warnings_dm', 'ban_response', 'kick_response', 
                 'mute_response', 'mute_dm', 'unmute_response', 'kick_dm']
    
    if embed_id not in valid_ids:
        return format_error(
            f"Invalid embed ID. Valid IDs: {', '.join(valid_ids[:4])}...",
            Config.ERROR_CODES['INVALID_INPUT']
        )
    
    # Load existing config or use defaults
    config = self.db.get_embed_config(self.guild.id, embed_id)
    
    if config:
        self.embed_data = {
            'title': config['title'],
            'description': config['description'],
            'color': config['color'],
            'fields': config['fields'] or []
        }
    else:
        # Default values based on embed type
        defaults = {
            'warnings_response': {
                'title': '⚠️ Warning Issued',
                'description': 'A user has been warned.',
                'color': 'FFAA00',
                'fields': []
            },
            'warnings_dm': {
                'title': '⚠️ You Have Been Warned',
                'description': 'You received a warning in {server}.',
                'color': 'FF0000',
                'fields': []
            },
            'mute_response': {
                'title': '🔇 User Muted',
                'description': '{user} has been muted.',
                'color': 'FF9900',
                'fields': []
            },
            'mute_dm': {
                'title': '🔇 You Have Been Muted',
                'description': 'You have been muted in {server}.',
                'color': 'FF0000',
                'fields': []
            }
        }
        
        self.embed_data = defaults.get(embed_id, {
            'title': 'Embed Title',
            'description': 'Embed description',
            'color': '00FF00',
            'fields': []
        })
    
    self.editing_embed = embed_id
    
    return f"""
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}   {ANSIColors.BOLD}Editing: {embed_id}{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Current Configuration:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}Title:{ANSIColors.RESET} {self.embed_data.get('title', 'Not set')}
  {ANSIColors.BRIGHT_BLACK}Description:{ANSIColors.RESET} {self.embed_data.get('description', 'Not set')}
  {ANSIColors.BRIGHT_BLACK}Color:{ANSIColors.RESET} #{self.embed_data.get('color', 'Not set')}
  {ANSIColors.BRIGHT_BLACK}Fields:{ANSIColors.RESET} {len(self.embed_data.get('fields', []))}

{ANSIColors.BRIGHT_CYAN}Edit Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}title <text>{ANSIColors.RESET}         Set title
  {ANSIColors.BRIGHT_WHITE}desc <text>{ANSIColors.RESET}          Set description
  {ANSIColors.BRIGHT_WHITE}color <hex>{ANSIColors.RESET}         Set color (e.g., FF0000)
  {ANSIColors.BRIGHT_WHITE}field add <n> <v>{ANSIColors.RESET}   Add field
  {ANSIColors.BRIGHT_WHITE}field list{ANSIColors.RESET}          List fields
  {ANSIColors.BRIGHT_WHITE}field remove <n>{ANSIColors.RESET}    Remove field
  {ANSIColors.BRIGHT_WHITE}preview{ANSIColors.RESET}             Preview current
  {ANSIColors.BRIGHT_WHITE}save{ANSIColors.RESET}                Save changes
  {ANSIColors.BRIGHT_WHITE}cancel{ANSIColors.RESET}              Cancel editing

{ANSIColors.BRIGHT_BLACK}Type a command to continue...{ANSIColors.RESET}
"""

async def handle_embed_edit_commands(self, command_lower, user_input):
    """Handle commands while in edit mode"""
    output = ""
    should_exit = False
    
    if command_lower.startswith("title "):
        title = user_input[6:].strip()
        self.embed_data['title'] = title
        output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Title set to: {ANSIColors.BRIGHT_WHITE}{title}{ANSIColors.RESET}"
    
    elif command_lower.startswith("desc "):
        desc = user_input[5:].strip()
        self.embed_data['description'] = desc
        output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Description set"
    
    elif command_lower.startswith("color "):
        color = user_input[6:].strip().replace('#', '')
        if len(color) == 6 and all(c in '0123456789ABCDEFabcdef' for c in color):
            self.embed_data['color'] = color.upper()
            output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Color set to: #{color.upper()}"
        else:
            output = format_error("Invalid hex color (use format: FF0000)", Config.ERROR_CODES['INVALID_INPUT'])
    
    elif command_lower.startswith("field add "):
        parts = user_input[10:].strip().split(None, 1)
        if len(parts) >= 2:
            field_name = parts[0]
            field_value = parts[1]
            if 'fields' not in self.embed_data:
                self.embed_data['fields'] = []
            self.embed_data['fields'].append({'name': field_name, 'value': field_value, 'inline': False})
            output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Added field: {ANSIColors.BRIGHT_WHITE}{field_name}{ANSIColors.RESET}"
        else:
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} field add <name> <value>"
    
    elif command_lower == "field list":
        if not self.embed_data.get('fields'):
            output = f"{ANSIColors.YELLOW}No fields added yet.{ANSIColors.RESET}"
        else:
            fields_text = ""
            for i, field in enumerate(self.embed_data['fields'], 1):
                fields_text += f"  {ANSIColors.BRIGHT_BLACK}{i}.{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}{field['name']}{ANSIColors.RESET}: {field['value']}\n"
            output = f"{ANSIColors.BRIGHT_CYAN}Fields:{ANSIColors.RESET}\n{fields_text}"
    
    elif command_lower.startswith("field remove "):
        try:
            index = int(user_input[13:].strip()) - 1
            if 0 <= index < len(self.embed_data.get('fields', [])):
                removed = self.embed_data['fields'].pop(index)
                output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Removed field: {removed['name']}"
            else:
                output = format_error(f"Field index out of range (1-{len(self.embed_data.get('fields', []))})", Config.ERROR_CODES['INVALID_INPUT'])
        except ValueError:
            output = format_error("Invalid field number", Config.ERROR_CODES['INVALID_INPUT'])
    
    elif command_lower == "preview":
        output = await self.show_embed_preview()
    
    elif command_lower == "save":
        # Save to database
        success = self.db.save_embed_config(
            self.guild.id,
            self.editing_embed,
            self.embed_data.get('title'),
            self.embed_data.get('description'),
            self.embed_data.get('color'),
            self.embed_data.get('fields')
        )
        
        if success:
            output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Embed configuration saved!\n{ANSIColors.BRIGHT_BLACK}ID: {self.editing_embed}{ANSIColors.RESET}"
            self.editing_embed = None
            self.embed_data = {}
        else:
            output = format_error("Failed to save configuration", Config.ERROR_CODES['DATABASE_ERROR'])
    
    elif command_lower == "cancel":
        output = f"{ANSIColors.YELLOW}Editing cancelled.{ANSIColors.RESET}"
        self.editing_embed = None
        self.embed_data = {}
    
    elif command_lower == "exit":
        output = f"{ANSIColors.YELLOW}Please 'save' or 'cancel' first.{ANSIColors.RESET}"
    
    elif command_lower == "back":
        output = f"{ANSIColors.YELLOW}Please 'save' or 'cancel' first.{ANSIColors.RESET}"
    
    else:
        output = format_error(f"Invalid edit command. Type the command name only.", Config.ERROR_CODES['INVALID_COMMAND'])
    
    return output, should_exit

async def show_embed_preview(self):
    """Show text preview of current embed being edited"""
    return f"""
{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}          {ANSIColors.BOLD}Embed Preview{ANSIColors.RESET}                  {ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_WHITE}{self.embed_data.get('title', 'No title')}{ANSIColors.RESET}
{self.embed_data.get('description', 'No description')}

{ANSIColors.BRIGHT_BLACK}Color:{ANSIColors.RESET} #{self.embed_data.get('color', 'Not set')}

{self._format_fields_preview()}

{ANSIColors.BRIGHT_BLACK}Type 'save' to apply or 'cancel' to discard.{ANSIColors.RESET}
"""

def _format_fields_preview(self):
    """Format fields for preview"""
    if not self.embed_data.get('fields'):
        return f"{ANSIColors.BRIGHT_BLACK}No fields{ANSIColors.RESET}"
    
    text = f"{ANSIColors.BRIGHT_CYAN}Fields:{ANSIColors.RESET}\n"
    for field in self.embed_data['fields']:
        text += f"{ANSIColors.BRIGHT_BLACK}• {field['name']}:{ANSIColors.RESET} {field['value']}\n"
    return text

async def handle_embed_preview_real(self, embed_id):
    """Send actual Discord embed"""
    import discord
    from datetime import datetime
    
    valid_ids = ['warnings_response', 'warnings_dm', 'mute_response', 'mute_dm']
    
    if embed_id not in valid_ids:
        return
    
    # Get config or use defaults
    config = self.db.get_embed_config(self.guild.id, embed_id) or self.embed_data
    
    # Create embed with placeholders replaced
    title = config.get('title', 'Embed Title')
    description = config.get('description', 'Embed description')
    color_hex = config.get('color', 'FFAA00')
    
    # Replace placeholders with examples
    title = title.replace('{user}', 'TestUser').replace('{server}', self.guild.name)
    description = description.replace('{user}', 'TestUser').replace('{server}', self.guild.name)
    description = description.replace('{moderator}', 'ModeratorName').replace('{reason}', 'Test reason')
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=int(color_hex, 16),
        timestamp=datetime.utcnow()
    )
    
    # Add fields
    for field in config.get('fields', []):
        value = field['value'].replace('{user}', 'TestUser').replace('{moderator}', 'ModeratorName')
        value = value.replace('{reason}', 'Test reason').replace('{duration}', '1d')
        embed.add_field(name=field['name'], value=value, inline=field.get('inline', False))
    
    if self.guild.icon:
        embed.set_thumbnail(url=self.guild.icon.url)
    
    embed.set_footer(text=f"Preview of {embed_id}")
    
    await self.channel.send(embed=embed)

# ==================== INTEGRATION NOTES ====================
"""
1. Add these methods to the TerminalSession class in cogs/terminal.py
2. Update handle_embed_panel() to use the new implementation
3. The edit mode maintains state across commands
4. Users can save or cancel their changes
5. Real-time preview with -real flag shows actual Discord embed
6. All configs saved to database via utils/database.py methods

Test flow:
1. BFOS > Configuration > embeds
2. embeds > edit warnings_response
3. title ⚠️ Custom Warning
4. desc Custom warning description
5. color FF0000
6. field add Moderator {moderator}
7. field add Reason {reason}
8. preview
9. save
10. preview warnings_response -real  (to see actual embed)
"""
