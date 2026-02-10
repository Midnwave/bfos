"""
BlockForge OS Help System
Provides comprehensive command documentation with pagination
"""

import discord
from discord.ext import commands
from discord.ui import Button, View
from utils.colors import Colors


class CommandsView(View):
    """Paginated command view with buttons"""
    
    def __init__(self, pages, author_id):
        super().__init__(timeout=None)  # No timeout per user request
        self.pages = pages
        self.current_page = 0
        self.author_id = author_id
        self.message = None
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button enabled/disabled states"""
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page >= len(self.pages) - 1
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        """Go to previous page"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can use these buttons.", ephemeral=True)
            return
        
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        """Go to next page"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can use these buttons.", ephemeral=True)
            return
        
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)


class HelpCommands(commands.Cog):
    """Help and documentation commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{Colors.GREEN}[✓] Help cog loaded{Colors.RESET}")
    
    def get_all_commands(self):
        """Get all module commands organized by module"""
        commands_data = {
            'warns': [
                {
                    'cmd_name': ';warn',
                    'usage': ';warn <user> <duration> <reason>',
                    'description': 'Issue a warning to a user',
                    'permission': 'mod_warn',
                    'examples': [';warn @User 7d Spamming in chat'],
                    'module': 'warns'
                },
                {
                    'cmd_name': ';masswarn',
                    'usage': ';masswarn <users> <duration> <reason>',
                    'description': 'Warn multiple users at once. Separate users with commas.',
                    'permission': 'mod_warn',
                    'examples': [';masswarn @U1,@U2 7d Mass spam'],
                    'module': 'warns'
                },
                {
                    'cmd_name': ';clearwarning',
                    'usage': ';clearwarning <user> <case_id>',
                    'description': 'Clear a specific warning from a user by case ID',
                    'permission': 'mod_warn',
                    'examples': [';clearwarning @User 1734567890'],
                    'module': 'warns'
                },
                {
                    'cmd_name': ';listwarnings',
                    'usage': ';listwarnings <user>',
                    'description': 'View all active warnings for a user',
                    'permission': 'case_view',
                    'examples': [';listwarnings @User'],
                    'module': 'warns'
                }
            ],
            'mutes': [
                {
                    'cmd_name': ';mute',
                    'usage': ';mute <user> <duration> <reason>',
                    'description': 'Timeout/mute a user for a specified duration',
                    'permission': 'mod_mute',
                    'examples': [';mute @User 1d Spamming'],
                    'module': 'mutes'
                },
                {
                    'cmd_name': ';unmute',
                    'usage': ';unmute <user> [reason]',
                    'description': 'Remove timeout from a user early',
                    'permission': 'mod_unmute',
                    'examples': [';unmute @User Appeal accepted'],
                    'module': 'mutes'
                },
                {
                    'cmd_name': ';bulkmute',
                    'usage': ';bulkmute <users> <duration> <reason>',
                    'description': 'Mute multiple users simultaneously',
                    'permission': 'mod_mute',
                    'examples': [';bulkmute @U1,@U2 1d Raid'],
                    'module': 'mutes'
                },
                {
                    'cmd_name': ';unbulkmute',
                    'usage': ';unbulkmute <users> [reason]',
                    'description': 'Unmute multiple users at once',
                    'permission': 'mod_unmute',
                    'examples': [';unbulkmute @U1,@U2 Appeals'],
                    'module': 'mutes'
                }
            ],
            'kicks': [
                {
                    'cmd_name': ';kick',
                    'usage': ';kick <user> <reason>',
                    'description': 'Kick a user from the server',
                    'permission': 'mod_kick',
                    'examples': [';kick @User Breaking rules'],
                    'module': 'kicks'
                },
                {
                    'cmd_name': ';masskick',
                    'usage': ';masskick <users> <reason>',
                    'description': 'Kick multiple users simultaneously',
                    'permission': 'mod_kick',
                    'examples': [';masskick @U1,@U2 Raid attempt'],
                    'module': 'kicks'
                }
            ],
            'bans': [
                {
                    'cmd_name': ';ban',
                    'usage': ';ban <user> <duration|perm> <reason>',
                    'description': 'Ban a user temporarily or permanently. Use "perm" for permanent bans.',
                    'permission': 'mod_ban',
                    'examples': [';ban @User 7d Repeated violations'],
                    'module': 'bans'
                },
                {
                    'cmd_name': ';unban',
                    'usage': ';unban <user_id> <reason>',
                    'description': 'Unban a user from the server by their ID',
                    'permission': 'mod_unban',
                    'examples': [';unban 123456789 Appeal accepted'],
                    'module': 'bans'
                },
                {
                    'cmd_name': ';massban',
                    'usage': ';massban <ids...> <duration|perm> <reason>',
                    'description': 'Ban multiple users at once by their IDs',
                    'permission': 'mod_ban',
                    'examples': [';massban 111 222 perm Raid attempt'],
                    'module': 'bans'
                }
            ],
            'cases': [
                {
                    'cmd_name': ';viewcase',
                    'usage': ';viewcase <case_id>',
                    'description': 'View detailed information about a punishment case',
                    'permission': 'case_view',
                    'examples': [';viewcase 1734567890'],
                    'module': 'cases'
                },
                {
                    'cmd_name': ';punishments',
                    'usage': ';punishments <user>',
                    'description': 'Show all punishments for a user (even if not in server)',
                    'permission': 'case_view',
                    'examples': [';punishments @User', ';punishments 123456789'],
                    'module': 'cases'
                },
                {
                    'cmd_name': ';modlog',
                    'usage': ';modlog [user] [duration]',
                    'description': 'View moderation logs. Duration: 24h, 7d, 1w, 1m',
                    'permission': 'modlog_view',
                    'examples': [';modlog', ';modlog @User 7d'],
                    'module': 'cases'
                }
            ],
            'modnotes': [
                {
                    'cmd_name': ';modnote set',
                    'usage': ';modnote set <user> <note>',
                    'description': 'Add a moderator note for a user (deletes command)',
                    'permission': 'modnote_set',
                    'examples': [';modnote set @User Watch for spam'],
                    'module': 'modnotes'
                },
                {
                    'cmd_name': ';modnote view',
                    'usage': ';modnote view <user>',
                    'description': 'View all moderator notes for a user',
                    'permission': 'modnote_view',
                    'examples': [';modnote view @User'],
                    'module': 'modnotes'
                },
                {
                    'cmd_name': ';modnote delete',
                    'usage': ';modnote delete <user>',
                    'description': 'Delete all moderator notes for a user',
                    'permission': 'modnote_delete',
                    'examples': [';modnote delete @User'],
                    'module': 'modnotes'
                }
            ],
            'voice': [
                {
                    'cmd_name': ';vcmute',
                    'usage': ';vcmute <user> [duration] [reason]',
                    'description': 'Mute user in voice channel. Auto-applies when they join VC.',
                    'permission': 'vc_mute',
                    'examples': [';vcmute @User 1h Mic spam'],
                    'module': 'voice'
                },
                {
                    'cmd_name': ';vcunmute',
                    'usage': ';vcunmute <user> [reason]',
                    'description': 'Unmute user in voice channel',
                    'permission': 'vc_unmute',
                    'examples': [';vcunmute @User'],
                    'module': 'voice'
                },
                {
                    'cmd_name': ';vcdeafen',
                    'usage': ';vcdeafen <user> [duration] [reason]',
                    'description': 'Deafen user in voice channel',
                    'permission': 'vc_deafen',
                    'examples': [';vcdeafen @User 30m'],
                    'module': 'voice'
                },
                {
                    'cmd_name': ';vcundeafen',
                    'usage': ';vcundeafen <user> [reason]',
                    'description': 'Undeafen user in voice channel',
                    'permission': 'vc_undeafen',
                    'examples': [';vcundeafen @User'],
                    'module': 'voice'
                },
                {
                    'cmd_name': ';vcdisconnect',
                    'usage': ';vcdisconnect <user>',
                    'description': 'Disconnect user from voice channel',
                    'permission': 'vc_disconnect',
                    'examples': [';vcdisconnect @User'],
                    'module': 'voice'
                },
                {
                    'cmd_name': ';vcmove',
                    'usage': ';vcmove <user> <channel_id>',
                    'description': 'Move user to different voice channel',
                    'permission': 'vc_move',
                    'examples': [';vcmove @User 123456789'],
                    'module': 'voice'
                }
            ],
            'channels': [
                {
                    'cmd_name': ';lock',
                    'usage': ';lock [channel_id]',
                    'description': 'Lock channel (read-only, no sending). Saves permissions.',
                    'permission': 'channel_lock',
                    'examples': [';lock', ';lock 123456789'],
                    'module': 'channels'
                },
                {
                    'cmd_name': ';unlock',
                    'usage': ';unlock [channel_id]',
                    'description': 'Unlock channel and restore permissions',
                    'permission': 'channel_unlock',
                    'examples': [';unlock', ';unlock 123456789'],
                    'module': 'channels'
                },
                {
                    'cmd_name': ';hardlock',
                    'usage': ';hardlock [channel_id]',
                    'description': 'Hardlock channel (staff-only access). Saves permissions.',
                    'permission': 'channel_hardlock',
                    'examples': [';hardlock', ';hardlock 123456789'],
                    'module': 'channels'
                },
                {
                    'cmd_name': ';unhardlock',
                    'usage': ';unhardlock [channel_id]',
                    'description': 'Remove hardlock and restore permissions',
                    'permission': 'channel_hardlock',
                    'examples': [';unhardlock', ';unhardlock 123456789'],
                    'module': 'channels'
                },
                {
                    'cmd_name': ';slowmode',
                    'usage': ';slowmode [channel_id] <duration>',
                    'description': 'Set channel slowmode. Use 0 to disable.',
                    'permission': 'channel_slowmode',
                    'examples': [';slowmode 5s', ';slowmode 123456789 1m'],
                    'module': 'channels'
                }
            ],
            'users': [
                {
                    'cmd_name': ';nick',
                    'usage': ';nick <user> <new_nick>',
                    'description': 'Change a user\'s nickname',
                    'permission': 'user_nick',
                    'examples': [';nick @User NewName'],
                    'module': 'users'
                },
                {
                    'cmd_name': ';nick reset',
                    'usage': ';nick reset <user>',
                    'description': 'Reset a user\'s nickname to their username',
                    'permission': 'user_nick',
                    'examples': [';nick reset @User'],
                    'module': 'users'
                },
                {
                    'cmd_name': ';role add',
                    'usage': ';role add <user|all> <role_id>',
                    'description': 'Add role(s) to user(s). Separate multiple roles with comma.',
                    'permission': 'role_add',
                    'examples': [';role add @User 123456789', ';role add all 123,456'],
                    'module': 'users'
                },
                {
                    'cmd_name': ';role remove',
                    'usage': ';role remove <user|all> <role_id>',
                    'description': 'Remove role(s) from user(s). Separate multiple with comma.',
                    'permission': 'role_remove',
                    'examples': [';role remove @User 123456789'],
                    'module': 'users'
                }
            ],
            'purges': [
                {
                    'cmd_name': ';purge',
                    'usage': ';purge <user|all> <type|all> <amount>',
                    'description': 'Purge messages with advanced filters. Types: all, bots, files, images, links, embeds, or custom text to match.',
                    'permission': 'Manage Messages',
                    'examples': [';purge all all 100', ';purge @User bots 50', ';purge all spam 200'],
                    'module': 'purges'
                }
            ],
            'logging': [
                {
                    'cmd_name': 'BFOS Logging',
                    'usage': 'BFOS > Config > Logging',
                    'description': 'Configure server logging via BFOS terminal. Logs messages, members, roles, channels, voice, moderation, and more.',
                    'permission': 'Server Owner',
                    'examples': ['.bfos() → config → logging'],
                    'module': 'logging'
                }
            ],
            'system': [
                {
                    'cmd_name': ';cmds',
                    'usage': ';cmds',
                    'description': 'Display this paginated command list',
                    'permission': 'Server Owner',
                    'examples': [';cmds'],
                    'module': 'system'
                },
                {
                    'cmd_name': '.bfos()',
                    'usage': '.bfos()',
                    'description': 'Open the BFOS terminal for configuration',
                    'permission': 'Server Owner',
                    'examples': ['.bfos()'],
                    'module': 'system'
                }
            ]
        }
        
        return commands_data
    
    def create_command_pages(self, commands_data, max_per_page=15):
        """Create paginated embeds for commands"""
        all_commands = []
        
        # Flatten all commands into a single list
        for module, cmds in commands_data.items():
            for cmd in cmds:
                all_commands.append(cmd)
        
        # Create pages
        pages = []
        total_pages = max(1, (len(all_commands) + max_per_page - 1) // max_per_page)
        
        for page_num in range(total_pages):
            start_idx = page_num * max_per_page
            end_idx = min(start_idx + max_per_page, len(all_commands))
            page_commands = all_commands[start_idx:end_idx]
            
            embed = discord.Embed(
                title="📖 BlockForge OS Commands",
                description=f"Comprehensive command documentation\n**Page {page_num + 1} of {total_pages}**",
                color=0x00AAFF,
                timestamp=discord.utils.utcnow()
            )
            
            for cmd in page_commands:
                # Format command field - use cmd_name instead of name
                field_value = f"**Usage:** `{cmd.get('usage', 'N/A')}`\n"
                field_value += f"**Description:** {cmd.get('description', 'No description')}\n"
                field_value += f"**Permission:** {cmd.get('permission', 'Unknown')}\n"
                field_value += f"**Module:** `{cmd.get('module', 'system')}`"
                
                examples = cmd.get('examples', [])
                if examples:
                    field_value += f"\n**Example:** `{examples[0]}`"
                
                embed.add_field(
                    name=f"{cmd.get('cmd_name', 'Unknown')}",
                    value=field_value,
                    inline=False
                )
            
            embed.set_footer(text=f"Use .bfos() to enable modules • Page {page_num + 1}/{total_pages}")
            pages.append(embed)
        
        return pages
    
    @commands.command(name='cmds')
    async def show_commands(self, ctx):
        """
        Display all available commands with pagination
        
        Usage: ;cmds
        """
        try:
            # Check if user is server owner
            if ctx.author.id != ctx.guild.owner_id:
                # Silent failure per requirements
                return
            
            # Get all commands
            commands_data = self.get_all_commands()
            
            # Create pages (15 commands per page)
            pages = self.create_command_pages(commands_data, max_per_page=15)
            
            if not pages:
                await ctx.send("❌ No commands available.")
                return
            
            # Create view with buttons
            view = CommandsView(pages, ctx.author.id)
            
            # Send first page
            message = await ctx.send(embed=pages[0], view=view)
            view.message = message
            
        except Exception as e:
            print(f"{Colors.RED}[ERROR] cmds command failed: {type(e).__name__}: {e}{Colors.RESET}")
            import traceback
            traceback.print_exc()
            await ctx.send(f"❌ **An Error Occurred**\n\n`{type(e).__name__}`: {str(e)}\n\n*Error Code: 0xCMDS*")


async def setup(bot):
    await bot.add_cog(HelpCommands(bot))
