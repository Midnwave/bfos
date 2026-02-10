"""
BlockForge OS Debug Module v2.1.0
Debug commands, error code explanations, permission tracing, and owner bypass
"""

import discord
from discord.ext import commands
import asyncio
from datetime import datetime
from utils.database import Database
from utils.config import Config


# Error code explanations
ERROR_CODES = {
    '0xCNTF': {
        'name': 'Command Not Found',
        'description': 'The command you entered was not recognized.',
        'solutions': [
            'Check the spelling of the command',
            'Type `help` to see available commands',
            'Make sure you are in the correct panel'
        ]
    },
    '0xINPT': {
        'name': 'Invalid Input',
        'description': 'The input provided was not in the correct format.',
        'solutions': [
            'Check the command syntax',
            'Make sure IDs are numeric',
            'Verify role/channel mentions are valid'
        ]
    },
    '0xARGS': {
        'name': 'Missing Arguments',
        'description': 'Required arguments were not provided.',
        'solutions': [
            'Check command usage with `help <command>`',
            'Provide all required parameters',
            'Arguments in <> are required, [] are optional'
        ]
    },
    '0xUSER': {
        'name': 'User Not Found',
        'description': 'Could not find the specified user.',
        'solutions': [
            'Use the user ID instead of name',
            'Make sure the user is in this server',
            'Try @mentioning the user'
        ]
    },
    '0xDURA': {
        'name': 'Invalid Duration',
        'description': 'Duration format was not recognized.',
        'solutions': [
            'Use format: 1d, 3h, 30m, 1d3h',
            'd = days, h = hours, m = minutes',
            'Example: 1d12h for 1 day 12 hours'
        ]
    },
    '0xMAXD': {
        'name': 'Duration Exceeded',
        'description': 'The specified duration exceeds the maximum allowed.',
        'solutions': [
            'Reduce the duration',
            'Maximum warn duration is typically 365 days',
            'Use `perm` for permanent bans'
        ]
    },
    '0xMODL': {
        'name': 'Module Disabled',
        'description': 'The required module is not enabled.',
        'solutions': [
            'Open BFOS terminal with `.bfos()`',
            'Go to `modules` panel',
            'Enable the required module'
        ]
    },
    '0xHIER': {
        'name': 'Role Hierarchy Error',
        'description': 'Cannot perform action due to role hierarchy.',
        'solutions': [
            'Target user has higher/equal role',
            'Move bot role higher in server settings',
            'You cannot moderate users with higher roles'
        ]
    },
    '0xPERM': {
        'name': 'Permission Denied',
        'description': 'Missing required permissions for this action.',
        'solutions': [
            'Grant the bot required permissions',
            'Check bot role permissions',
            'Make sure bot role is high enough'
        ]
    },
    '0xROLE': {
        'name': 'Role Not Found',
        'description': 'The specified role could not be found.',
        'solutions': [
            'Use the role ID',
            'Make sure the role exists',
            'Check role was not deleted'
        ]
    },
    '0xCHNL': {
        'name': 'Channel Not Found',
        'description': 'The specified channel could not be found.',
        'solutions': [
            'Use the channel ID',
            'Make sure the channel exists',
            'Check channel permissions'
        ]
    },
    '0xBADA': {
        'name': 'Invalid ID',
        'description': 'The ID provided is not valid.',
        'solutions': [
            'IDs must be numeric (numbers only)',
            'Copy ID from Discord (Enable Developer Mode)',
            'Right-click → Copy ID'
        ]
    },
    '0xPNL': {
        'name': 'Invalid Panel',
        'description': 'Could not navigate to the requested panel.',
        'solutions': [
            'Use `back` to return to previous panel',
            'Type `help` for available commands',
            'Restart terminal with `.bfos()`'
        ]
    },
    '0xLOCK': {
        'name': 'Lockdown Failed',
        'description': 'Could not activate server lockdown.',
        'solutions': [
            'Check bot permissions',
            'Make sure bot role is high enough',
            'Try again or check audit log'
        ]
    },
    '0xUNLK': {
        'name': 'Unlock Failed',
        'description': 'Could not deactivate server lockdown.',
        'solutions': [
            'Server may not be in lockdown',
            'Lockdown role may have been deleted',
            'Manually delete the lockdown role'
        ]
    },
    '0xBKUP': {
        'name': 'Backup Error',
        'description': 'Backup operation failed.',
        'solutions': [
            'Check backup exists',
            'Verify backup is not corrupted',
            'Try creating a new backup'
        ]
    },
    '0xCFAI': {
        'name': 'Command Failed',
        'description': 'The command failed to execute.',
        'solutions': [
            'Check bot permissions',
            'Try the command again',
            'Check Discord status for outages'
        ]
    }
}


class Debug(commands.Cog):
    """Debug commands for BlockForge OS"""

    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

        # Debug state (runtime only, not persisted)
        self.debug_enabled = False
        self.debug_permissions = False
        self.owner_bypass_guilds = set()  # guild_ids where server owner is demoted to regular user

    # ==================== DEBUG HELPER METHODS ====================

    def debug_log(self, category: str, message: str):
        """Print debug log to console if debug is enabled"""
        if self.debug_enabled:
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[DEBUG {timestamp}] [{category}] {message}")

    def perm_log(self, message: str):
        """Print permission trace to console if permission debugging is enabled"""
        if self.debug_permissions:
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[PERM-TRACE {timestamp}] {message}")

    def is_owner_demoted(self, guild_id: int) -> bool:
        """Check if server owner is demoted in this guild (for permission testing)"""
        return guild_id in self.owner_bypass_guilds

    # ==================== COMMANDS ====================

    @commands.command(name='debug')
    async def debug_command(self, ctx, *args):
        """
        Debug command for error codes and testing

        Admin commands:
          ;debug <error_code>     - Explain an error code
          ;debug codes            - List all error codes
          ;debug logging sendall  - Send all log embed examples

        Bot owner commands:
          ;debug true/false       - Toggle debug logging
          ;debug logs             - Show debug state
          ;debug permissions      - Toggle permission trace
          ;debug ownerbypass true/false - Demote server owner in this guild
        """
        if not args:
            # Show debug help
            embed = discord.Embed(
                title="Debug Menu",
                description="Debug tools for BlockForge OS.",
                color=0x3498DB
            )

            # Admin commands
            embed.add_field(
                name="Admin Commands",
                value=(
                    "`;debug <error_code>` - Explain an error code\n"
                    "`;debug codes` - List all error codes\n"
                    "`;debug logging sendall` - Send all log embed examples"
                ),
                inline=False
            )

            # Bot owner commands
            if ctx.author.id == Config.BOT_OWNER_ID:
                embed.add_field(
                    name="Bot Owner Commands",
                    value=(
                        "`;debug true/false` - Toggle debug logging (console)\n"
                        "`;debug logs` - Show current debug state\n"
                        "`;debug permissions` - Toggle permission trace (console)\n"
                        "`;debug ownerbypass true/false` - Demote server owner in this guild"
                    ),
                    inline=False
                )

            embed.add_field(
                name="Error Code Format",
                value="Error codes look like: `0xCNTF`, `0xMODL`, etc.",
                inline=False
            )
            embed.set_footer(text=f"BFOS Debug v{Config.VERSION}")
            await ctx.send(embed=embed)
            return

        first_arg = args[0].lower()

        # ==================== BOT OWNER COMMANDS ====================

        # Toggle debug mode
        if first_arg in ('true', 'false', 'on', 'off'):
            if ctx.author.id != Config.BOT_OWNER_ID:
                await ctx.send("Bot owner only.", delete_after=5)
                return
            self.debug_enabled = first_arg in ('true', 'on')
            status = "ENABLED" if self.debug_enabled else "DISABLED"
            await ctx.send(f"Debug logging: **{status}** (output to console)")
            if self.debug_enabled:
                self.debug_log("SYSTEM", "Debug logging enabled")
            return

        # Show debug state
        if first_arg == 'logs':
            if ctx.author.id != Config.BOT_OWNER_ID:
                await ctx.send("Bot owner only.", delete_after=5)
                return
            embed = discord.Embed(title="Debug State", color=0x3498DB)
            embed.add_field(
                name="Debug Logging",
                value="ENABLED" if self.debug_enabled else "DISABLED",
                inline=True
            )
            embed.add_field(
                name="Permission Trace",
                value="ENABLED" if self.debug_permissions else "DISABLED",
                inline=True
            )
            bypass_text = "None"
            if self.owner_bypass_guilds:
                bypass_text = "\n".join(str(gid) for gid in self.owner_bypass_guilds)
            embed.add_field(
                name="Owner Bypass Guilds",
                value=bypass_text,
                inline=False
            )
            embed.set_footer(text=f"BFOS Debug v{Config.VERSION}")
            await ctx.send(embed=embed)
            return

        # Toggle permission trace
        if first_arg == 'permissions':
            if ctx.author.id != Config.BOT_OWNER_ID:
                await ctx.send("Bot owner only.", delete_after=5)
                return
            self.debug_permissions = not self.debug_permissions
            status = "ENABLED" if self.debug_permissions else "DISABLED"
            await ctx.send(f"Permission trace: **{status}** (output to console)")
            return

        # Toggle owner bypass for current guild
        if first_arg == 'ownerbypass':
            if ctx.author.id != Config.BOT_OWNER_ID:
                await ctx.send("Bot owner only.", delete_after=5)
                return
            if len(args) < 2:
                is_demoted = ctx.guild.id in self.owner_bypass_guilds
                status = "ENABLED" if is_demoted else "DISABLED"
                await ctx.send(f"Owner bypass in this guild: **{status}**\nWhen enabled, the server owner is treated as a regular user and must have BFOS permissions assigned.")
                return

            value = args[1].lower()
            if value in ('true', 'on'):
                self.owner_bypass_guilds.add(ctx.guild.id)
                await ctx.send(f"Owner bypass **ENABLED** for this guild.\nServer owner will be treated as a regular user (BFOS permissions required).")
                self.perm_log(f"Owner bypass ENABLED for guild {ctx.guild.id} ({ctx.guild.name})")
            elif value in ('false', 'off'):
                self.owner_bypass_guilds.discard(ctx.guild.id)
                await ctx.send(f"Owner bypass **DISABLED** for this guild.\nServer owner has full access again.")
                self.perm_log(f"Owner bypass DISABLED for guild {ctx.guild.id} ({ctx.guild.name})")
            else:
                await ctx.send("Usage: `;debug ownerbypass <true/false>`")
            return

        # ==================== ADMIN COMMANDS ====================

        # These require at minimum administrator permission
        if not ctx.author.guild_permissions.administrator and ctx.author.id != Config.BOT_OWNER_ID:
            await ctx.send("You need administrator permissions to use debug commands.", delete_after=5)
            return

        # Handle error code lookup
        if first_arg.startswith('0x') or first_arg.upper() in ERROR_CODES:
            code = first_arg.upper()
            if not code.startswith('0x'):
                code = '0x' + code

            if code in ERROR_CODES:
                error = ERROR_CODES[code]
                embed = discord.Embed(
                    title=f"Error: {code}",
                    description=f"**{error['name']}**\n\n{error['description']}",
                    color=0xE74C3C
                )

                solutions = "\n".join(f"- {s}" for s in error['solutions'])
                embed.add_field(name="Solutions", value=solutions, inline=False)

                embed.set_footer(text="BFOS Debug - If issue persists, contact support")
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"Unknown error code: `{code}`\n\nUse `;debug codes` to see all error codes.")
            return

        # List all error codes
        if first_arg == 'codes':
            embed = discord.Embed(
                title="Error Codes Reference",
                description="All BFOS error codes and their meanings.",
                color=0x9B59B6
            )

            codes_text = ""
            for code, data in list(ERROR_CODES.items())[:15]:
                codes_text += f"`{code}` - {data['name']}\n"

            embed.add_field(name="Error Codes", value=codes_text, inline=False)
            embed.set_footer(text="Use ;debug <code> for details")
            await ctx.send(embed=embed)
            return

        # Handle logging test
        if first_arg == 'logging' and len(args) > 1:
            if args[1].lower() in ['sendallemebds', 'sendallemeds', 'sendall', 'all']:
                await self.send_all_log_examples(ctx)
                return

        await ctx.send(f"Unknown debug command: `{' '.join(args)}`\n\nUse `;debug` for help.")
    
    async def send_all_log_examples(self, ctx):
        """Send examples of all logging embeds"""
        await ctx.send("📤 **Sending all log embed examples...**\n*This may take a moment to avoid rate limits.*")
        
        logging_cog = self.bot.get_cog('LoggingModule')
        if not logging_cog:
            await ctx.send("❌ Logging module not loaded.")
            return
        
        examples = [
            # Messages
            {
                'title': '🗑️ Message Deleted',
                'color': 0xE74C3C,
                'fields': [
                    ('Author', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Channel', ctx.channel.mention, True),
                    ('Sent', '<t:1234567890:R>', True),
                    ('Content', '```\nExample deleted message content\n```', False),
                    ('Deleted By', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                ]
            },
            {
                'title': '✏️ Message Edited',
                'color': 0x3498DB,
                'fields': [
                    ('Author', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Channel', ctx.channel.mention, True),
                    ('Jump', '[Click](https://discord.com)', True),
                    ('Before', '```\nOriginal message\n```', False),
                    ('After', '```\nEdited message\n```', False),
                ]
            },
            # Members
            {
                'title': '📥 Member Joined',
                'color': 0x2ECC71,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Account Age', '2 years old', True),
                    ('Member #', '100', True),
                ]
            },
            {
                'title': '📤 Member Left',
                'color': 0x95A5A6,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Joined', '<t:1234567890:R>', True),
                    ('Roles', '@Member, @Verified', True),
                ]
            },
            {
                'title': '🔨 Member Banned',
                'color': 0xE74C3C,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Banned By', f'{ctx.author.mention}', True),
                    ('Reason', 'Example ban reason', False),
                ]
            },
            {
                'title': '🔓 Member Unbanned',
                'color': 0x27AE60,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Unbanned By', f'{ctx.author.mention}', True),
                ]
            },
            # Roles
            {
                'title': '✨ Role Created',
                'color': 0x2ECC71,
                'fields': [
                    ('Role', '@NewRole (`123456789`)', True),
                    ('Color', '#FF0000', True),
                    ('Created By', f'{ctx.author.mention}', True),
                ]
            },
            {
                'title': '⚙️ Role Updated',
                'color': 0xF1C40F,
                'fields': [
                    ('Role', '@UpdatedRole (`123456789`)', True),
                    ('Changes', '**Name:** `Old` → `New`\n**Color:** `#000` → `#FFF`', False),
                ]
            },
            # Channels
            {
                'title': '📁 Channel Created',
                'color': 0x2ECC71,
                'fields': [
                    ('Channel', ctx.channel.mention, True),
                    ('Type', 'Text', True),
                    ('Created By', f'{ctx.author.mention}', True),
                ]
            },
            {
                'title': '🔐 Permission Update',
                'color': 0x9B59B6,
                'fields': [
                    ('Channel', ctx.channel.mention, False),
                    ('Changes\n👥 @everyone', '✅ View Channel\n❌ Send Messages\n✅ Read Message History', False),
                    ('Updated By', f'{ctx.author.mention}', True),
                ]
            },
            # Voice
            {
                'title': '🎤 Voice Join',
                'color': 0x2ECC71,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Channel', '🔊 General', True),
                ]
            },
            {
                'title': '🔇 Voice Leave',
                'color': 0x95A5A6,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Channel', '🔊 General', True),
                    ('Duration', '5 minutes', True),
                ]
            },
            # Moderation
            {
                'title': '⚠️ User Warned',
                'color': 0xFFAA00,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Moderator', f'{ctx.author.mention}', True),
                    ('Case', '`#1`', True),
                    ('Total Warnings', '`1`', True),
                    ('Reason', '```\nExample warning reason\n```', False),
                ]
            },
            {
                'title': '🔨 User Banned',
                'color': 0xE74C3C,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Moderator', f'{ctx.author.mention}', True),
                    ('Case', '`#2`', True),
                    ('Duration', '`7 days`', True),
                    ('Reason', '```\nExample ban reason\n```', False),
                ]
            },
            {
                'title': '👢 User Kicked',
                'color': 0xE67E22,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Moderator', f'{ctx.author.mention}', True),
                    ('Case', '`#3`', True),
                    ('Reason', '```\nExample kick reason\n```', False),
                ]
            },
            {
                'title': '🔇 User Muted',
                'color': 0x9B59B6,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Moderator', f'{ctx.author.mention}', True),
                    ('Case', '`#4`', True),
                    ('Duration', '`1 hour`', True),
                    ('Reason', '```\nExample mute reason\n```', False),
                ]
            },
            {
                'title': '🔊 User Unmuted',
                'color': 0x27AE60,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Moderator', f'{ctx.author.mention}', True),
                    ('Reason', '```\nMute expired\n```', False),
                ]
            },
            # Verification
            {
                'title': '✅ Verification Passed',
                'color': 0x2ECC71,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Status', '`SUCCESS`', True),
                    ('Response Q1', '```\nFound via Discord search\n```', False),
                ]
            },
            {
                'title': '❌ Verification Failed',
                'color': 0xE74C3C,
                'fields': [
                    ('User', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Status', '`FAILED`', True),
                    ('Submitted Code', '`123456`', True),
                ]
            },
            # BFOS
            {
                'title': '🤖 BFOS: Module',
                'color': 0x9B59B6,
                'fields': [
                    ('Executed By', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Module', '`warns`', True),
                    ('Action', '`enabled`', True),
                ]
            },
            {
                'title': '🤖 BFOS: Backup',
                'color': 0x00AAFF,
                'fields': [
                    ('Executed By', f'{ctx.author.mention} (`{ctx.author.id}`)', True),
                    ('Backup', '`ABC123`', True),
                    ('Action', '`created`', True),
                ]
            },
        ]
        
        # Send examples with delay to avoid rate limits
        for i, ex in enumerate(examples):
            embed = discord.Embed(
                title=ex['title'],
                color=ex['color'],
                timestamp=datetime.utcnow()
            )
            
            for name, value, inline in ex['fields']:
                embed.add_field(name=name, value=value, inline=inline)
            
            embed.set_footer(text=f"Example {i+1}/{len(examples)}")
            
            await ctx.send(embed=embed)
            await asyncio.sleep(1)  # 1 second delay between embeds
        
        await ctx.send(f"✅ **Sent {len(examples)} log embed examples!**")


async def setup(bot):
    await bot.add_cog(Debug(bot))
