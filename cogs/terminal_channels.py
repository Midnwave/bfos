"""
BlockForge OS Channels Panel
Handles channel management operations
"""

import discord
import asyncio
from datetime import datetime
from utils.colors import ANSIColors, format_error
from utils.config import Config

class ChannelsPanel:
    """Channel management panel"""
    
    def __init__(self, terminal_session):
        self.session = terminal_session
        self.bot = terminal_session.bot
        self.ctx = terminal_session.ctx
        self.db = terminal_session.db
        self.guild = terminal_session.guild
    
    async def handle_command(self, command_lower, user_input):
        """Handle channels panel commands"""
        output = ""
        should_exit = False
        
        # Check for pending confirmation
        if self.session.pending_confirmation:
            confirmed = command_lower == "confirm"
            cancelled = command_lower == "cancel"
            
            if confirmed or cancelled:
                action_data = self.session.pending_confirmation
                self.session.pending_confirmation = None
                
                if confirmed:
                    action = action_data['action']
                    if action == 'preset_set':
                        output = await self.execute_preset_set(
                            action_data['details']['channel_id'],
                            action_data['details']['preset_name']
                        )
                    elif action == 'preset_delete':
                        output = await self.execute_preset_delete(
                            action_data['details']['preset_name']
                        )
                else:
                    output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Action cancelled."
                
                return output, False
        
        if command_lower == "exit":
            output = await self.session.handle_exit()
            should_exit = True
        elif command_lower == "back":
            self.session.current_panel = "management"
            self.session.current_path = "Management"
            output = f"{ANSIColors.GREEN}Returned to management panel.{ANSIColors.RESET}"
        elif command_lower == "clr":
            output = ""  # Clear handled by caller
        elif command_lower == "help":
            output = self.show_help()
        elif command_lower == "list":
            output = await self.handle_list_channels()
        elif command_lower.startswith("delete "):
            channel_id = user_input[7:].strip()
            output = await self.handle_delete_channel(channel_id)
        elif command_lower.startswith("duplicate "):
            channel_id = user_input[10:].strip()
            output = await self.handle_duplicate_channel(channel_id)
        elif command_lower.startswith("rename "):
            parts = user_input[7:].strip().split(None, 1)
            if len(parts) >= 2:
                output = await self.handle_rename_channel(parts[0], parts[1])
            else:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} rename <channel_id> <new_name>"
        elif command_lower.startswith("viewperms "):
            channel_id = user_input[10:].strip()
            output = await self.handle_view_permissions(channel_id)
        elif command_lower == "changeperms":
            # No channel ID - open the picker
            output = await self.handle_change_permissions_picker()
        elif command_lower.startswith("changeperms "):
            channel_id = user_input[12:].strip()
            output = await self.handle_change_permissions_direct(channel_id)
        elif command_lower.startswith("preset create "):
            parts = user_input[14:].strip().split(None, 1)
            if len(parts) >= 2:
                output = await self.handle_preset_create(parts[0], parts[1])
            else:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} preset create <name> <channel_id>"
        elif command_lower.startswith("preset set "):
            parts = user_input[11:].strip().split(None, 1)
            if len(parts) >= 2:
                output = await self.handle_preset_set(parts[0], parts[1])
            else:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} preset set <channel_id> <preset_name>"
        elif command_lower.startswith("preset delete "):
            preset_name = user_input[14:].strip()
            output = await self.handle_preset_delete(preset_name)
        elif command_lower.isdigit():
            # Bare channel ID - treat as changeperms
            output = await self.handle_change_permissions_direct(command_lower)
        else:
            output = format_error(
                f"Invalid command '{user_input}'. Type 'help' for channel commands.",
                Config.ERROR_CODES['INVALID_COMMAND']
            )
        
        return output, should_exit
    
    def show_help(self):
        """Show channels panel help"""
        return f"""
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}         Channel Management Commands          {ANSIColors.CYAN}║{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Channel Operations:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}list{ANSIColors.RESET}                  List all channels with IDs
  {ANSIColors.BRIGHT_WHITE}delete <id>{ANSIColors.RESET}           Delete a channel
  {ANSIColors.BRIGHT_WHITE}duplicate <id>{ANSIColors.RESET}        Duplicate with permissions
  {ANSIColors.BRIGHT_WHITE}rename <id> <name>{ANSIColors.RESET}    Rename a channel
  {ANSIColors.BRIGHT_WHITE}viewperms <id>{ANSIColors.RESET}        View permissions
  {ANSIColors.BRIGHT_WHITE}changeperms{ANSIColors.RESET}           Open permission editor
  {ANSIColors.BRIGHT_WHITE}changeperms <id>{ANSIColors.RESET}      Edit channel directly

{ANSIColors.BRIGHT_CYAN}Permission Presets:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}preset create <n> <id>{ANSIColors.RESET}   Save as preset
  {ANSIColors.BRIGHT_WHITE}preset set <id> <n>{ANSIColors.RESET}       Apply preset
  {ANSIColors.BRIGHT_WHITE}preset delete <n>{ANSIColors.RESET}         Delete preset

{ANSIColors.BRIGHT_BLACK}Examples:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}list{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}delete 123456789{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}rename 123456789 new-channel-name{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}preset create VIP 123456789{ANSIColors.RESET}
"""
    
    async def handle_list_channels(self):
        """List all channels with animated output"""
        # Build items list
        items = []
        categories = {}
        no_category = []
        
        # Organize channels by category
        for channel in self.guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                categories[channel.id] = {
                    'name': channel.name,
                    'id': channel.id,
                    'position': channel.position,
                    'channels': []
                }
            elif isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel, discord.StageChannel)):
                if channel.category:
                    if channel.category.id not in categories:
                        categories[channel.category.id] = {
                            'name': channel.category.name,
                            'id': channel.category.id,
                            'position': channel.category.position,
                            'channels': []
                        }
                    categories[channel.category.id]['channels'].append(channel)
                else:
                    no_category.append(channel)
        
        # Build items
        if no_category:
            items.append(f"{ANSIColors.BRIGHT_YELLOW}📁 No Category{ANSIColors.RESET}")
            for channel in sorted(no_category, key=lambda c: c.position):
                icon = self._get_channel_icon(channel)
                items.append(f"  {ANSIColors.BRIGHT_BLACK}├─{ANSIColors.RESET} {icon} {ANSIColors.WHITE}{channel.name}{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}({channel.id}){ANSIColors.RESET}")
        
        for cat_id, cat_data in sorted(categories.items(), key=lambda x: x[1]['position']):
            items.append(f"{ANSIColors.BRIGHT_YELLOW}📁 {cat_data['name']}{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}({cat_data['id']}){ANSIColors.RESET}")
            for channel in sorted(cat_data['channels'], key=lambda c: c.position):
                icon = self._get_channel_icon(channel)
                items.append(f"  {ANSIColors.BRIGHT_BLACK}├─{ANSIColors.RESET} {icon} {ANSIColors.WHITE}{channel.name}{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}({channel.id}){ANSIColors.RESET}")
        
        # Use animated list
        header = f"""{ANSIColors.BRIGHT_CYAN}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}               Server Channels                   {ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}{'═' * 50}{ANSIColors.RESET}"""
        
        footer = f"{ANSIColors.BRIGHT_BLACK}Total: {len(self.guild.channels)} channels | Use 'delete <id>' to manage{ANSIColors.RESET}"
        
        # Call animated list on session
        await self.session.animated_list(header, items, footer, delay=0.3)
        return ""  # Already displayed
    
    def _get_channel_icon(self, channel):
        """Get icon for channel type"""
        if isinstance(channel, discord.TextChannel):
            return "💬"
        elif isinstance(channel, discord.VoiceChannel):
            return "🔊"
        elif isinstance(channel, discord.ForumChannel):
            return "💭"
        elif isinstance(channel, discord.StageChannel):
            return "🎙️"
        return "📝"
    
    async def handle_delete_channel(self, channel_id):
        """Delete a channel"""
        try:
            channel_id = int(channel_id)
            channel = self.guild.get_channel(channel_id)
            
            if not channel:
                return f"{ANSIColors.RED}❌ Channel not found: {channel_id}{ANSIColors.RESET}"
            
            channel_name = channel.name
            await channel.delete(reason=f"Deleted by {self.ctx.author} via BFOS")
            
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Channel deleted: {ANSIColors.BRIGHT_WHITE}{channel_name}{ANSIColors.RESET}"
        
        except ValueError:
            return f"{ANSIColors.RED}❌ Invalid channel ID{ANSIColors.RESET}"
        except discord.Forbidden:
            return f"{ANSIColors.RED}❌ Missing permissions to delete channel{ANSIColors.RESET}"
        except Exception as e:
            return f"{ANSIColors.RED}❌ Error: {str(e)}{ANSIColors.RESET}"
    
    async def handle_duplicate_channel(self, channel_id):
        """Duplicate a channel with permissions"""
        try:
            channel_id = int(channel_id)
            channel = self.guild.get_channel(channel_id)
            
            if not channel:
                return f"{ANSIColors.RED}❌ Channel not found: {channel_id}{ANSIColors.RESET}"
            
            # Create duplicate
            overwrites = {target: overwrite for target, overwrite in channel.overwrites.items()}
            
            if isinstance(channel, discord.TextChannel):
                new_channel = await channel.category.create_text_channel(
                    name=f"{channel.name}-copy",
                    overwrites=overwrites,
                    position=channel.position + 1,
                    topic=channel.topic,
                    slowmode_delay=channel.slowmode_delay,
                    nsfw=channel.nsfw,
                    reason=f"Duplicated by {self.ctx.author} via BFOS"
                )
            elif isinstance(channel, discord.VoiceChannel):
                new_channel = await channel.category.create_voice_channel(
                    name=f"{channel.name}-copy",
                    overwrites=overwrites,
                    position=channel.position + 1,
                    bitrate=channel.bitrate,
                    user_limit=channel.user_limit,
                    reason=f"Duplicated by {self.ctx.author} via BFOS"
                )
            else:
                return f"{ANSIColors.YELLOW}⚠️  Channel type not supported for duplication{ANSIColors.RESET}"
            
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Channel duplicated: {ANSIColors.BRIGHT_WHITE}{new_channel.name}{ANSIColors.RESET}\n   {ANSIColors.BRIGHT_BLACK}New ID: {new_channel.id}{ANSIColors.RESET}"
        
        except ValueError:
            return f"{ANSIColors.RED}❌ Invalid channel ID{ANSIColors.RESET}"
        except discord.Forbidden:
            return f"{ANSIColors.RED}❌ Missing permissions to create channel{ANSIColors.RESET}"
        except Exception as e:
            return f"{ANSIColors.RED}❌ Error: {str(e)}{ANSIColors.RESET}"
    
    async def handle_rename_channel(self, channel_id, new_name):
        """Rename a channel"""
        try:
            channel_id = int(channel_id)
            channel = self.guild.get_channel(channel_id)
            
            if not channel:
                return f"{ANSIColors.RED}❌ Channel not found: {channel_id}{ANSIColors.RESET}"
            
            old_name = channel.name
            await channel.edit(name=new_name, reason=f"Renamed by {self.ctx.author} via BFOS")
            
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Channel renamed:\n   {ANSIColors.BRIGHT_BLACK}{old_name}{ANSIColors.RESET} → {ANSIColors.BRIGHT_WHITE}{new_name}{ANSIColors.RESET}"
        
        except ValueError:
            return f"{ANSIColors.RED}❌ Invalid channel ID{ANSIColors.RESET}"
        except discord.Forbidden:
            return f"{ANSIColors.RED}❌ Missing permissions to edit channel{ANSIColors.RESET}"
        except Exception as e:
            return f"{ANSIColors.RED}❌ Error: {str(e)}{ANSIColors.RESET}"
    
    async def handle_view_permissions(self, channel_id):
        """View channel permissions"""
        try:
            channel_id = int(channel_id)
            channel = self.guild.get_channel(channel_id)
            
            if not channel:
                return f"{ANSIColors.RED}❌ Channel not found: {channel_id}{ANSIColors.RESET}"
            
            output = f"""
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}   Permissions: {channel.name}
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}

"""
            
            if not channel.overwrites:
                output += f"{ANSIColors.YELLOW}No custom permissions set{ANSIColors.RESET}\n"
            else:
                for target, overwrite in channel.overwrites.items():
                    target_name = target.name if hasattr(target, 'name') else str(target)
                    target_type = "👤 User" if isinstance(target, discord.Member) else "👥 Role"
                    
                    output += f"{ANSIColors.BRIGHT_CYAN}{target_type}: {target_name}{ANSIColors.RESET}\n"
                    output += f"  {ANSIColors.BRIGHT_BLACK}ID: {target.id}{ANSIColors.RESET}\n"
                    
                    # Show allowed permissions
                    allowed = [perm for perm, value in overwrite if value == True]
                    if allowed:
                        output += f"  {ANSIColors.GREEN}✓ Allowed:{ANSIColors.RESET} {', '.join(allowed[:5])}\n"
                        if len(allowed) > 5:
                            output += f"    {ANSIColors.BRIGHT_BLACK}...and {len(allowed)-5} more{ANSIColors.RESET}\n"
                    
                    # Show denied permissions
                    denied = [perm for perm, value in overwrite if value == False]
                    if denied:
                        output += f"  {ANSIColors.RED}✗ Denied:{ANSIColors.RESET} {', '.join(denied[:5])}\n"
                        if len(denied) > 5:
                            output += f"    {ANSIColors.BRIGHT_BLACK}...and {len(denied)-5} more{ANSIColors.RESET}\n"
                    
                    output += "\n"
            
            return output
        
        except ValueError:
            return f"{ANSIColors.RED}❌ Invalid channel ID{ANSIColors.RESET}"
        except Exception as e:
            return f"{ANSIColors.RED}❌ Error: {str(e)}{ANSIColors.RESET}"
    
    async def handle_change_permissions_picker(self):
        """Launch interactive permission editor with channel picker"""
        try:
            from cogs.permission_editor import launch_permission_editor
            await launch_permission_editor(self.ctx, self.db)
            
            return f"""{ANSIColors.BRIGHT_MAGENTA}🚀 Permission Editor Launched{ANSIColors.RESET}

{ANSIColors.GREEN}✓{ANSIColors.RESET} Select a channel from the dropdown to manage permissions."""
        
        except Exception as e:
            return f"{ANSIColors.RED}❌ Error launching editor: {str(e)}{ANSIColors.RESET}"
    
    async def handle_change_permissions_direct(self, channel_id):
        """Launch permission editor directly for a specific channel"""
        try:
            channel_id_int = int(channel_id)
            channel = self.guild.get_channel(channel_id_int)
            
            if not channel:
                return f"{ANSIColors.RED}❌ Channel not found: {channel_id}{ANSIColors.RESET}"
            
            # Launch editor directly with the channel
            from cogs.permission_editor import launch_permission_editor
            await launch_permission_editor(self.ctx, self.db, channel=channel)
            
            return f"""{ANSIColors.BRIGHT_MAGENTA}🚀 Permission Editor Launched{ANSIColors.RESET}

{ANSIColors.GREEN}✓{ANSIColors.RESET} Now editing: {ANSIColors.BRIGHT_WHITE}{channel.name}{ANSIColors.RESET}"""
        
        except ValueError:
            return f"{ANSIColors.RED}❌ Invalid channel ID{ANSIColors.RESET}"
        except Exception as e:
            return f"{ANSIColors.RED}❌ Error launching editor: {str(e)}{ANSIColors.RESET}"
    
    async def handle_preset_create(self, preset_name, channel_id):
        """Create permission preset from channel"""
        try:
            channel_id = int(channel_id)
            channel = self.guild.get_channel(channel_id)
            
            if not channel:
                return f"{ANSIColors.RED}❌ Channel not found: {channel_id}{ANSIColors.RESET}"
            
            # Extract permissions
            preset_data = {
                'overwrites': {}
            }
            
            for target, overwrite in channel.overwrites.items():
                target_id = str(target.id)
                target_type = 'role' if isinstance(target, discord.Role) else 'member'
                target_name = target.name if hasattr(target, 'name') else str(target)
                
                allow, deny = overwrite.pair()
                preset_data['overwrites'][target_id] = {
                    'type': target_type,
                    'name': target_name,
                    'allow': allow.value,
                    'deny': deny.value
                }
            
            # Save to database
            self.db.save_channel_preset(self.guild.id, preset_name, preset_data)
            
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Preset created: {ANSIColors.BRIGHT_WHITE}{preset_name}{ANSIColors.RESET}\n   {ANSIColors.BRIGHT_BLACK}From channel: {channel.name}{ANSIColors.RESET}\n   {ANSIColors.BRIGHT_BLACK}Overwrites: {len(preset_data['overwrites'])}{ANSIColors.RESET}"
        
        except ValueError:
            return f"{ANSIColors.RED}❌ Invalid channel ID{ANSIColors.RESET}"
        except Exception as e:
            return f"{ANSIColors.RED}❌ Error: {str(e)}{ANSIColors.RESET}"
    
    async def handle_preset_set(self, channel_id, preset_name):
        """Apply preset to channel"""
        try:
            channel_id = int(channel_id)
            channel = self.guild.get_channel(channel_id)
            
            if not channel:
                return f"{ANSIColors.RED}❌ Channel not found: {channel_id}{ANSIColors.RESET}"
            
            # Get preset
            preset = self.db.get_channel_preset(self.guild.id, preset_name)
            if not preset:
                return f"{ANSIColors.RED}❌ Preset not found: {preset_name}{ANSIColors.RESET}"
            
            # Show confirmation
            self.session.pending_confirmation = {
                'action': 'preset_set',
                'details': {
                    'channel_id': channel_id,
                    'channel_name': channel.name,
                    'preset_name': preset_name,
                    'overwrites': len(preset['data']['overwrites'])
                }
            }
            
            return f"""
{ANSIColors.YELLOW}⚠️  Confirmation Required{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Apply Preset:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} Preset: {ANSIColors.BRIGHT_WHITE}{preset_name}{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} Channel: {ANSIColors.BRIGHT_WHITE}{channel.name}{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} Overwrites: {ANSIColors.BRIGHT_WHITE}{len(preset['data']['overwrites'])}{ANSIColors.RESET}

{ANSIColors.YELLOW}This will replace all current permissions!{ANSIColors.RESET}

{ANSIColors.BRIGHT_WHITE}Type 'confirm' to proceed or 'cancel' to abort{ANSIColors.RESET}
"""
        
        except ValueError:
            return f"{ANSIColors.RED}❌ Invalid channel ID{ANSIColors.RESET}"
        except Exception as e:
            return f"{ANSIColors.RED}❌ Error: {str(e)}{ANSIColors.RESET}"
    
    async def execute_preset_set(self, channel_id, preset_name):
        """Execute preset application"""
        try:
            channel = self.guild.get_channel(channel_id)
            if not channel:
                return f"{ANSIColors.RED}❌ Channel not found{ANSIColors.RESET}"
            
            preset = self.db.get_channel_preset(self.guild.id, preset_name)
            if not preset:
                return f"{ANSIColors.RED}❌ Preset not found{ANSIColors.RESET}"
            
            # Clear existing overwrites
            for target in list(channel.overwrites.keys()):
                await channel.set_permissions(target, overwrite=None)
            
            # Apply preset overwrites
            applied = 0
            for target_id, overwrite_data in preset['data']['overwrites'].items():
                if overwrite_data['type'] == 'role':
                    target = self.guild.get_role(int(target_id))
                    if target:
                        allow = discord.Permissions(overwrite_data['allow'])
                        deny = discord.Permissions(overwrite_data['deny'])
                        overwrite = discord.PermissionOverwrite.from_pair(allow, deny)
                        await channel.set_permissions(target, overwrite=overwrite)
                        applied += 1
                        await asyncio.sleep(0.2)  # Rate limit protection
            
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Preset applied: {ANSIColors.BRIGHT_WHITE}{preset_name}{ANSIColors.RESET}\n   {ANSIColors.BRIGHT_BLACK}Applied {applied} overwrites to {channel.name}{ANSIColors.RESET}"
        
        except Exception as e:
            return f"{ANSIColors.RED}❌ Error applying preset: {str(e)}{ANSIColors.RESET}"
    
    async def handle_preset_delete(self, preset_name):
        """Delete a preset"""
        # Check if exists
        preset = self.db.get_channel_preset(self.guild.id, preset_name)
        if not preset:
            return f"{ANSIColors.RED}❌ Preset not found: {preset_name}{ANSIColors.RESET}"
        
        # Show confirmation
        self.session.pending_confirmation = {
            'action': 'preset_delete',
            'details': {
                'preset_name': preset_name,
                'created': preset.get('created_at', 'Unknown')
            }
        }
        
        return f"""
{ANSIColors.YELLOW}⚠️  Confirmation Required{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Delete Preset:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} Name: {ANSIColors.BRIGHT_WHITE}{preset_name}{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} Created: {ANSIColors.BRIGHT_WHITE}{preset.get('created_at', 'Unknown')[:10]}{ANSIColors.RESET}

{ANSIColors.BRIGHT_WHITE}Type 'confirm' to delete or 'cancel' to abort{ANSIColors.RESET}
"""
    
    async def execute_preset_delete(self, preset_name):
        """Execute preset deletion"""
        success = self.db.delete_channel_preset(self.guild.id, preset_name)
        
        if success:
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Preset deleted: {ANSIColors.BRIGHT_WHITE}{preset_name}{ANSIColors.RESET}"
        else:
            return f"{ANSIColors.RED}❌ Failed to delete preset{ANSIColors.RESET}"
