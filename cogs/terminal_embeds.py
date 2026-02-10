"""
BlockForge OS Embed Editor Panel
Handles embed editing with proper state management
"""

import discord
from datetime import datetime
from utils.colors import ANSIColors
from utils.config import Config

class EmbedEditorPanel:
    """Embed editor panel with state management"""
    
    def __init__(self, terminal_session):
        self.session = terminal_session
        self.bot = terminal_session.bot
        self.ctx = terminal_session.ctx
        self.db = terminal_session.db
        self.guild = terminal_session.guild
        
        # Editor state
        self.current_embed_id = None
        self.embed_data = {}
    
    async def start_editing(self, embed_id):
        """Start editing an embed"""
        valid_ids = ['warnings_response', 'warnings_dm', 'ban_response', 'ban_dm', 
                     'kick_response', 'kick_dm', 'mute_response', 'mute_dm', 'unmute_response',
                     'unban_response', 'unban_dm', 'verify_dm']
        
        if embed_id not in valid_ids:
            return f"{ANSIColors.RED}❌ Invalid embed ID: {embed_id}{ANSIColors.RESET}"
        
        # Set editing state
        self.current_embed_id = embed_id
        self.session.current_panel = f"embed_edit_{embed_id}"
        self.session.current_path = f"Configuration > Embeds > {embed_id}"
        
        # Load existing embed config or use defaults
        config = self.db.get_embed_config(self.guild.id, embed_id)
        if config:
            self.embed_data = config
        else:
            self.embed_data = self.get_default_embed_data(embed_id)
        
        return self.show_editor()
    
    def get_default_embed_data(self, embed_id):
        """Get default embed configuration from database defaults"""
        return self.db.get_default_embed_config(embed_id)
    
    def show_editor(self):
        """Show embed editor interface"""
        return f"""
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}    {ANSIColors.BOLD}Editing: {self.current_embed_id}{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Current Configuration:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} Title: {ANSIColors.BRIGHT_WHITE}{self.embed_data.get('title', 'Not set')}{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} Description: {ANSIColors.BRIGHT_WHITE}{self.embed_data.get('description', 'Not set')}{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} Color: {ANSIColors.BRIGHT_WHITE}#{self.embed_data.get('color', 'Not set')}{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} Fields: {ANSIColors.BRIGHT_WHITE}{len(self.embed_data.get('fields', []))}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Edit Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}title <text>{ANSIColors.RESET}         Set embed title
  {ANSIColors.BRIGHT_WHITE}desc <text>{ANSIColors.RESET}          Set description
  {ANSIColors.BRIGHT_WHITE}color <hex>{ANSIColors.RESET}          Set color (e.g., FF0000)
  {ANSIColors.BRIGHT_WHITE}field add <n> <v>{ANSIColors.RESET}    Add field
  {ANSIColors.BRIGHT_WHITE}field remove <n>{ANSIColors.RESET}     Remove field number
  {ANSIColors.BRIGHT_WHITE}fields{ANSIColors.RESET}               List all fields
  {ANSIColors.BRIGHT_WHITE}preview{ANSIColors.RESET}              Preview embed
  {ANSIColors.BRIGHT_WHITE}save{ANSIColors.RESET}                 Save changes
  {ANSIColors.BRIGHT_WHITE}cancel{ANSIColors.RESET}               Cancel (no save)

{ANSIColors.BRIGHT_CYAN}Placeholders:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}{{user}} {{user_id}} {{moderator}} {{reason}}{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}{{duration}} {{expires}} {{server}} {{timestamp}}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Type a command to edit...{ANSIColors.RESET}
"""
    
    async def handle_command(self, command_lower, user_input):
        """Handle embed editor commands"""
        output = ""
        should_exit = False
        
        if command_lower == "exit":
            output = await self.session.handle_exit()
            should_exit = True
        elif command_lower == "back" or command_lower == "cancel":
            self.session.current_panel = "embeds"
            self.session.current_path = "Configuration > Embeds"
            self.current_embed_id = None
            self.embed_data = {}
            output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Editing cancelled. Returned to embeds panel."
        elif command_lower == "clr":
            output = ""
        elif command_lower.startswith("title "):
            new_title = user_input[6:].strip()
            self.embed_data['title'] = new_title
            output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Title updated: {ANSIColors.BRIGHT_WHITE}{new_title}{ANSIColors.RESET}"
        elif command_lower.startswith("desc ") or command_lower.startswith("description "):
            new_desc = user_input[5:].strip() if command_lower.startswith("desc ") else user_input[12:].strip()
            self.embed_data['description'] = new_desc
            output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Description updated"
        elif command_lower.startswith("color "):
            color = user_input[6:].strip().replace('#', '').upper()
            if len(color) == 6:
                self.embed_data['color'] = color
                output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Color set to: {ANSIColors.BRIGHT_WHITE}#{color}{ANSIColors.RESET}"
            else:
                output = f"{ANSIColors.RED}❌ Invalid color hex. Use 6 characters (e.g., FF0000){ANSIColors.RESET}"
        elif command_lower.startswith("field add "):
            parts = user_input[10:].strip().split(None, 1)
            if len(parts) >= 2:
                if 'fields' not in self.embed_data:
                    self.embed_data['fields'] = []
                self.embed_data['fields'].append({'name': parts[0], 'value': parts[1]})
                output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Field added: {ANSIColors.BRIGHT_WHITE}{parts[0]}{ANSIColors.RESET}"
            else:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} field add <name> <value>"
        elif command_lower.startswith("field remove "):
            try:
                index = int(user_input[13:].strip()) - 1
                if 'fields' in self.embed_data and 0 <= index < len(self.embed_data['fields']):
                    removed = self.embed_data['fields'].pop(index)
                    output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Field removed: {ANSIColors.BRIGHT_WHITE}{removed['name']}{ANSIColors.RESET}"
                else:
                    output = f"{ANSIColors.RED}❌ Invalid field number{ANSIColors.RESET}"
            except ValueError:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} field remove <number>"
        elif command_lower == "fields":
            output = self.list_fields()
        elif command_lower == "preview":
            output = await self.preview_embed()
        elif command_lower == "save":
            output = await self.save_embed()
        else:
            output = f"{ANSIColors.RED}❌ Unknown command. Type 'back' to return or use edit commands.{ANSIColors.RESET}"
        
        return output, should_exit
    
    def list_fields(self):
        """List all current fields"""
        fields = self.embed_data.get('fields', [])
        
        if not fields:
            return f"{ANSIColors.YELLOW}No fields configured yet.{ANSIColors.RESET}"
        
        output = f"""
{ANSIColors.BRIGHT_CYAN}Current Fields:{ANSIColors.RESET}
"""
        for i, field in enumerate(fields, 1):
            output += f"  {ANSIColors.BRIGHT_WHITE}{i}.{ANSIColors.RESET} {ANSIColors.BRIGHT_CYAN}{field['name']}{ANSIColors.RESET}\n"
            output += f"     {ANSIColors.BRIGHT_BLACK}{field['value']}{ANSIColors.RESET}\n"
        
        return output
    
    async def preview_embed(self):
        """Preview the embed in chat"""
        try:
            # Create embed
            color_hex = self.embed_data.get('color', '00FF00')
            color_int = int(color_hex, 16)
            
            embed = discord.Embed(
                title=self.embed_data.get('title', 'No Title'),
                description=self.embed_data.get('description', 'No Description'),
                color=color_int,
                timestamp=datetime.utcnow()
            )
            
            # Add fields
            for field in self.embed_data.get('fields', []):
                embed.add_field(
                    name=field['name'],
                    value=field['value'],
                    inline=False
                )
            
            embed.set_footer(text=f"Preview of {self.current_embed_id}")
            
            # Send preview
            await self.ctx.channel.send(embed=embed)
            
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Preview sent! Check above for embed."
        except Exception as e:
            return f"{ANSIColors.RED}❌ Preview failed: {str(e)}{ANSIColors.RESET}"
    
    async def save_embed(self):
        """Save embed configuration"""
        try:
            # Unpack embed_data dict for database method
            success = self.db.save_embed_config(
                self.guild.id,
                self.current_embed_id,
                title=self.embed_data.get('title'),
                description=self.embed_data.get('description'),
                color=self.embed_data.get('color'),
                fields=self.embed_data.get('fields')
            )
            
            if success:
                # Return to embeds panel
                self.session.current_panel = "embeds"
                self.session.current_path = "Configuration > Embeds"
                self.current_embed_id = None
                self.embed_data = {}
                
                return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Embed saved successfully! Returned to embeds panel."
            else:
                return f"{ANSIColors.RED}❌ Failed to save embed configuration{ANSIColors.RESET}"
        except Exception as e:
            return f"{ANSIColors.RED}❌ Save failed: {str(e)}{ANSIColors.RESET}"
