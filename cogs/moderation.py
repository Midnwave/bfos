"""
BlockForge OS Moderation Module
Handles moderation commands for enabled modules
"""

import discord
from discord.ext import commands
from datetime import datetime, timedelta
import re
from utils.database import Database
from utils.config import Config
from utils.colors import Colors

# ==================== PERMISSION DECORATOR ====================
def is_server_owner():
    """Legacy decorator - kept for reference, use has_bfos_permission instead"""
    async def predicate(ctx):
        return ctx.author.id == ctx.guild.owner_id
    return commands.check(predicate)


def has_bfos_permission(permission_id: str):
    """
    Decorator that checks BFOS permissions.
    Priority: bot owner > server owner (unless debug-demoted) > BFOS permission > deny
    """
    async def predicate(ctx):
        # Bot owner always has everything (never demoted)
        if ctx.author.id == Config.BOT_OWNER_ID:
            debug_cog = ctx.bot.get_cog('Debug')
            if debug_cog:
                debug_cog.perm_log(f"PASS: Bot owner {ctx.author} for '{permission_id}'")
            return True

        # Server owner check - respect owner bypass debug setting
        if ctx.author.id == ctx.guild.owner_id:
            debug_cog = ctx.bot.get_cog('Debug')
            if debug_cog and debug_cog.is_owner_demoted(ctx.guild.id):
                if debug_cog.debug_permissions:
                    debug_cog.perm_log(f"OWNER DEMOTED in guild {ctx.guild.id} - checking BFOS permissions for {ctx.author}")
                # Fall through to BFOS permission check
            else:
                if debug_cog:
                    debug_cog.perm_log(f"PASS: Server owner {ctx.author} for '{permission_id}'")
                return True

        # Check BFOS permission from database
        db = Database()
        debug_cog = ctx.bot.get_cog('Debug')

        # Direct user permission
        if db.has_permission(ctx.guild.id, ctx.author.id, permission_id):
            if debug_cog:
                debug_cog.perm_log(f"PASS: {ctx.author} has direct permission '{permission_id}'")
            return True

        # Role-based permission
        for role in ctx.author.roles:
            if db.role_has_permission(ctx.guild.id, role.id, permission_id):
                if debug_cog:
                    debug_cog.perm_log(f"PASS: {ctx.author} has permission '{permission_id}' via role '{role.name}'")
                return True

        if debug_cog:
            debug_cog.perm_log(f"DENY: {ctx.author} lacks permission '{permission_id}'")
        return False
    return commands.check(predicate)

# ==================== ADVANCED ERROR HANDLING ====================
class AdvancedError:
    """Gaius-style error messages"""
    
    @staticmethod
    def invalid_input(detail):
        return f"❌ **Invalid Input Supplied**\n{detail}\n\n*Error Code: 0xINPT*"
    
    @staticmethod
    def command_not_found(command):
        return f"❌ **Command Not Found**\nThe command `{command}` was not recognized.\n\nUse `;help` to see available commands.\n\n*Error Code: 0xCMND*"
    
    @staticmethod
    def argument_error(missing_arg):
        return f"❌ **Argument Error**\nMissing required parameter: `{missing_arg}`\n\nPlease provide all required arguments.\n\n*Error Code: 0xARGS*"
    
    @staticmethod
    def user_not_found(user_input):
        return f"❌ **User Not Found**\nCould not find user: `{user_input}`\n\nTry using:\n• User ID\n• @mention\n• Username\n\n*Error Code: 0xUSER*"
    
    @staticmethod
    def invalid_duration(duration):
        return f"❌ **Invalid Duration Format**\nDuration `{duration}` is invalid.\n\n**Valid formats:**\n• `1d` (1 day)\n• `3h` (3 hours)\n• `30m` (30 minutes)\n• `1d3h` (1 day 3 hours)\n\n*Error Code: 0xDURA*"
    
    @staticmethod
    def duration_exceeded(max_duration):
        return f"❌ **Duration Exceeded**\nDuration exceeds maximum allowed: **{max_duration} days**\n\n*Error Code: 0xMAXD*"
    
    @staticmethod
    def module_disabled(module_name):
        return f"❌ **Module Disabled**\nThe `{module_name}` module is not enabled.\n\nEnable it in BFOS terminal: `.bfos()` → `modules` → `module enable {module_name}`\n\n*Error Code: 0xMODL*"
    
    @staticmethod
    def hierarchy_error(action, target):
        return f"❌ **Role Hierarchy Error**\nCannot {action} this user due to role hierarchy.\n\n**Details:**\nThe target user has a higher or equal role.\n\n**Target:** {target.mention} ({target.id})\n\n*Error Code: 0xHIER*"
    
    @staticmethod
    def permission_denied(action, permission):
        return f"❌ **Permission Denied**\nCannot {action} - missing required permission.\n\n**Required Permission:**\n`{permission}`\n\n*Error Code: 0xPERM*"

class Moderation(commands.Cog):
    """Moderation commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    def get_logging_cog(self):
        """Get the logging cog for logging moderation actions"""
        return self.bot.get_cog('LoggingModule')
    
    def build_embed(self, guild_id: int, embed_type: str, placeholders: dict = None) -> discord.Embed:
        """
        Build embed from database config or default
        
        Args:
            guild_id: The guild ID
            embed_type: Type like 'warnings_dm', 'ban_dm', 'verify_dm' etc
            placeholders: Dict of placeholders to replace like {user}, {server}, etc
        
        Returns:
            discord.Embed with custom or default config
        """
        return self.db.build_embed_from_config(guild_id, embed_type, placeholders)
    
    async def log_mod_action(self, action_type: str, guild, user, moderator, reason: str, 
                             case_number: int, extra_data: dict = None):
        """Log a moderation action to the logging system"""
        logging_cog = self.get_logging_cog()
        if not logging_cog:
            return
        
        if action_type == 'warn':
            total_warns = extra_data.get('total_warnings', 1) if extra_data else 1
            await logging_cog.log_warn(guild, user, moderator, reason, case_number, total_warns)
        elif action_type == 'ban':
            await logging_cog.log_ban(guild, user, moderator, reason, case_number, 
                                      extra_data.get('duration') if extra_data else None)
        elif action_type == 'kick':
            await logging_cog.log_kick(guild, user, moderator, reason, case_number)
        elif action_type == 'mute':
            await logging_cog.log_mute(guild, user, moderator, reason, case_number,
                                       extra_data.get('duration') if extra_data else None)
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{Colors.GREEN}[✓] Moderation cog loaded{Colors.RESET}")
    
    async def resolve_user(self, ctx, user_input):
        """Resolve user from ID, mention, or username"""
        # Try as ID
        if user_input.isdigit():
            try:
                user = await ctx.guild.fetch_member(int(user_input))
                return user
            except:
                pass
        
        # Try as mention
        if user_input.startswith('<@') and user_input.endswith('>'):
            user_id = user_input[2:-1]
            if user_id.startswith('!'):
                user_id = user_id[1:]
            try:
                user = await ctx.guild.fetch_member(int(user_id))
                return user
            except:
                pass
        
        # Try as username
        user = discord.utils.get(ctx.guild.members, name=user_input)
        if user:
            return user
        
        # Try as display name
        user = discord.utils.get(ctx.guild.members, display_name=user_input)
        if user:
            return user
        
        return None
    
    def parse_advanced_duration(self, duration_str):
        """Parse complex duration like 1d3h30m"""
        if not duration_str:
            return None
        
        # Pattern: 1d3h2m
        pattern = r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?'
        match = re.match(pattern, duration_str.lower())
        
        if not match:
            return None
        
        days = int(match.group(1)) if match.group(1) else 0
        hours = int(match.group(2)) if match.group(2) else 0
        minutes = int(match.group(3)) if match.group(3) else 0
        
        if days == 0 and hours == 0 and minutes == 0:
            return None
        
        return timedelta(days=days, hours=hours, minutes=minutes)
    
    def validate_duration(self, duration_str, max_days=30):
        """Validate duration and check max limit"""
        td = self.parse_advanced_duration(duration_str)
        if not td:
            return False, "Invalid format"
        
        if td.days > max_days:
            return False, f"Exceeds maximum {max_days} days"
        
        return True, td
    
    def parse_duration(self, duration_str):
        """Parse duration string like '7d', '2h', '30m' into timedelta"""
        if not duration_str:
            return None
        
        match = re.match(r'^(\d+)([smhdw])$', duration_str.lower())
        if not match:
            return None
        
        amount, unit = match.groups()
        amount = int(amount)
        
        if unit == 's':
            return timedelta(seconds=amount)
        elif unit == 'm':
            return timedelta(minutes=amount)
        elif unit == 'h':
            return timedelta(hours=amount)
        elif unit == 'd':
            return timedelta(days=amount)
        elif unit == 'w':
            return timedelta(weeks=amount)
        
        return None
    
    def create_case_embed(self, case_type, user, moderator, reason, duration=None, case_number=None):
        """Create embed for punishment case"""
        color_map = {
            'ban': 0xFF0000,
            'kick': 0xFF6600,
            'warn': 0xFFFF00,
            'mute': 0xFF9900,
            'unban': 0x00FF00,
            'unmute': 0x00FF00
        }
        
        embed = discord.Embed(
            title=f"User {case_type.title()}",
            color=color_map.get(case_type, 0x808080),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name=f"{case_type.title()} by:",
            value=f"{moderator.mention} ({moderator.id})",
            inline=False
        )
        
        if duration:
            embed.add_field(name="Duration:", value=duration, inline=False)
        
        embed.add_field(name="Reason:", value=reason or "No reason provided", inline=False)
        
        if case_number:
            embed.add_field(name="Case:", value=f"#{case_number}", inline=False)
        
        embed.set_thumbnail(url=user.display_avatar.url if hasattr(user, 'display_avatar') else user.avatar.url)
        
        return embed
    
    def _user_has_any_bfos_permission(self, guild_id, member):
        """Check if a user has ANY BFOS permission (direct or via roles)."""
        # Bot owner always counts
        if member.id == Config.BOT_OWNER_ID:
            return True
        # Server owner always counts
        if member.guild and member.id == member.guild.owner_id:
            return True
        # Admin permission always counts
        if member.guild_permissions.administrator:
            return True
        # Check direct user permissions
        user_perms = self.db.get_user_permissions(guild_id, member.id)
        if user_perms:
            return True
        # Check role permissions
        for role in member.roles:
            role_perms = self.db.get_role_permissions(guild_id, role.id)
            if role_perms:
                return True
        return False

    def _build_error_embed(self, emoji, title, description, error_code, color, suggested_fix=None, usage=None):
        """Build a standardized BFOS error embed."""
        embed = discord.Embed(
            title=f"{emoji} {title}",
            description=f"**Error `{error_code}`**\n\n{description}",
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_author(name="BFOS Error", icon_url=self.bot.user.display_avatar.url if self.bot.user else None)
        if suggested_fix:
            embed.add_field(name="Suggested Fix", value=suggested_fix, inline=False)
        if usage:
            embed.add_field(name="Correct Usage", value=f"```\n{usage}\n```", inline=False)
        embed.set_footer(text=f"BlockForge OS v{Config.VERSION} | Use ;cmds for help")
        return embed

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle command errors globally"""
        # Ignore if command has local error handler
        if hasattr(ctx.command, 'on_error'):
            return

        # Get the original error if it's wrapped
        error = getattr(error, 'original', error)

        # Check failure — completely silent (no response at all)
        if isinstance(error, commands.CheckFailure):
            return

        # Missing required argument
        if isinstance(error, commands.MissingRequiredArgument):
            cmd_name = ctx.command.name if ctx.command else "command"
            usage = f"{ctx.prefix}{cmd_name} {ctx.command.signature}" if ctx.command else None
            embed = self._build_error_embed(
                emoji="\u26a0\ufe0f",
                title="Missing Argument",
                description=f"The parameter `{error.param.name}` is required but was not provided.",
                error_code="0xARGS",
                color=0xE67E22,
                suggested_fix=f"Make sure to include all required arguments when running this command.",
                usage=usage
            )
            await ctx.send(embed=embed)
            return

        # Bad argument
        if isinstance(error, commands.BadArgument):
            embed = self._build_error_embed(
                emoji="\u274c",
                title="Invalid Argument",
                description=f"{str(error)}",
                error_code="0xBADA",
                color=0xE67E22,
                suggested_fix="Check that you're providing the correct type of argument (e.g. a user mention, number, or channel)."
            )
            await ctx.send(embed=embed)
            return

        # Missing permissions (user)
        if isinstance(error, commands.MissingPermissions):
            embed = self._build_error_embed(
                emoji="\U0001f512",
                title="Missing Permissions",
                description=f"You need the following Discord permissions:\n" + ", ".join(f"`{p}`" for p in error.missing_permissions),
                error_code="0xPERM",
                color=0xE74C3C,
                suggested_fix="Ask a server administrator to grant you the required permissions."
            )
            await ctx.send(embed=embed)
            return

        # Bot missing permissions
        if isinstance(error, commands.BotMissingPermissions):
            embed = self._build_error_embed(
                emoji="\U0001f916",
                title="Bot Missing Permissions",
                description=f"I need the following Discord permissions to run this command:\n" + ", ".join(f"`{p}`" for p in error.missing_permissions),
                error_code="0xBPRM",
                color=0xE74C3C,
                suggested_fix="Check the bot's role permissions in Server Settings > Roles."
            )
            await ctx.send(embed=embed)
            return

        # Command not found
        if isinstance(error, commands.CommandNotFound):
            # Ignore bot mentions — AI system handles those
            bot_mention = f'<@{self.bot.user.id}>'
            bot_mention_nick = f'<@!{self.bot.user.id}>'
            msg_content = ctx.message.content

            if (ctx.message.mentions and self.bot.user in ctx.message.mentions) or \
               msg_content.startswith(bot_mention) or msg_content.startswith(bot_mention_nick):
                return

            # Check if CNF messages are enabled at all
            show_cnf = self.db.get_setting(ctx.guild.id, 'show_command_not_found', True)
            if not show_cnf:
                return

            # Silent for users with NO BFOS permissions
            if not self._user_has_any_bfos_permission(ctx.guild.id, ctx.author):
                return

            invoked = ctx.invoked_with
            embed = self._build_error_embed(
                emoji="\U0001f50d",
                title="Command Not Found",
                description=f"The command `{invoked}` does not exist.",
                error_code="0xCNTF",
                color=0xF1C40F,
                suggested_fix=f"Use `{ctx.prefix}cmds` to see all available commands. Did you misspell something?"
            )
            await ctx.send(embed=embed)
            return

        # Unknown / other errors
        print(f"[ERROR] Command error in {ctx.command}: {error}")
        embed = self._build_error_embed(
            emoji="\u2757",
            title="Unexpected Error",
            description=f"`{type(error).__name__}`: {str(error)[:200]}",
            error_code="0xFA11",
            color=0xC0392B,
            suggested_fix="This may be a bug. Try the command again or contact a server admin."
        )
        await ctx.send(embed=embed)
    
    async def check_module_enabled(self, ctx, module_name):
        """Check if a module is enabled"""
        if not self.db.get_module_state(ctx.guild.id, module_name):
            error_embed = discord.Embed(
                title="❌ Module Disabled",
                description=f"The {module_name} module is not enabled in this server.\n\n"
                           f"Enable it with: `.bfos()` → `modules` → `module enable {module_name}`",
                color=0xFF0000
            )
            error_embed.set_footer(text=f"Error Code: {Config.ERROR_CODES['MODULE_DISABLED']}")
            await ctx.send(embed=error_embed)
            return False
        return True
    
    async def get_dynamic_prefix(self, ctx):
        """Get the server's custom prefix"""
        return self.db.get_command_prefix(ctx.guild.id)
    
# REMOVED_DUPLICATE:     @commands.command(name='ban')
# REMOVED_DUPLICATE:     @commands.has_permissions(ban_members=True)
# REMOVED_DUPLICATE:     async def ban_member(self, ctx, member: discord.Member, duration: str = None, *, reason: str = None):
# REMOVED_DUPLICATE:         """Ban a member from the server"""
        # Check if bans module is enabled
# REMOVED_DUPLICATE:         if not await self.check_module_enabled(ctx, 'bans'):
# REMOVED_DUPLICATE:             return
# REMOVED_DUPLICATE:         
        # Can't ban yourself
# REMOVED_DUPLICATE:         if member.id == ctx.author.id:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ You cannot ban yourself. (ERR-{Config.ERROR_CODES['INVALID_INPUT']})")
# REMOVED_DUPLICATE:             return
# REMOVED_DUPLICATE:         
        # Can't ban bot
# REMOVED_DUPLICATE:         if member.id == self.bot.user.id:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ I cannot ban myself. (ERR-{Config.ERROR_CODES['INVALID_INPUT']})")
# REMOVED_DUPLICATE:             return
# REMOVED_DUPLICATE:         
        # Check hierarchy
# REMOVED_DUPLICATE:         if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ You cannot ban someone with a higher or equal role. (ERR-{Config.ERROR_CODES['PERMISSION_DENIED']})")
# REMOVED_DUPLICATE:             return
# REMOVED_DUPLICATE:         
# REMOVED_DUPLICATE:         try:
            # Parse duration if provided
# REMOVED_DUPLICATE:             duration_td = None
# REMOVED_DUPLICATE:             duration_str = None
# REMOVED_DUPLICATE:             if duration:
# REMOVED_DUPLICATE:                 duration_td = self.parse_duration(duration)
# REMOVED_DUPLICATE:                 if not duration_td:
# REMOVED_DUPLICATE:                     await ctx.send(f"❌ Invalid duration format. Use format like: 7d, 2h, 30m (ERR-{Config.ERROR_CODES['INVALID_DURATION']})")
# REMOVED_DUPLICATE:                     return
# REMOVED_DUPLICATE:                 duration_str = duration
# REMOVED_DUPLICATE:             
            # Create case in database
# REMOVED_DUPLICATE:             case_number = self.db.create_case(
# REMOVED_DUPLICATE:                 ctx.guild.id,
# REMOVED_DUPLICATE:                 'ban',
# REMOVED_DUPLICATE:                 member.id,
# REMOVED_DUPLICATE:                 ctx.author.id,
# REMOVED_DUPLICATE:                 reason,
# REMOVED_DUPLICATE:                 duration_str
# REMOVED_DUPLICATE:             )
# REMOVED_DUPLICATE:             
            # Ban the member
# REMOVED_DUPLICATE:             await member.ban(reason=f"[Case #{case_number}] {reason or 'No reason provided'}")
# REMOVED_DUPLICATE:             
            # Send embed
# REMOVED_DUPLICATE:             embed = self.create_case_embed('ban', member, ctx.author, reason, duration_str, case_number)
# REMOVED_DUPLICATE:             await ctx.send(embed=embed)
# REMOVED_DUPLICATE:             
            # TODO: If duration is set, schedule unban
# REMOVED_DUPLICATE:             
# REMOVED_DUPLICATE:         except discord.Forbidden:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ I don't have permission to ban this member. (ERR-{Config.ERROR_CODES['PERMISSION_DENIED']})")
# REMOVED_DUPLICATE:         except Exception as e:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ An error occurred: {e} (ERR-{Config.ERROR_CODES['COMMAND_FAILED']})")
# REMOVED_DUPLICATE:     
# REMOVED_DUPLICATE:     @commands.command(name='unban')
# REMOVED_DUPLICATE:     @commands.has_permissions(ban_members=True)
# REMOVED_DUPLICATE:     async def unban_member(self, ctx, user_id: int, *, reason: str = None):
# REMOVED_DUPLICATE:         """Unban a user from the server"""
        # Check if bans module is enabled
# REMOVED_DUPLICATE:         if not await self.check_module_enabled(ctx, 'bans'):
# REMOVED_DUPLICATE:             return
# REMOVED_DUPLICATE:         
# REMOVED_DUPLICATE:         try:
            # Get user
# REMOVED_DUPLICATE:             user = await self.bot.fetch_user(user_id)
# REMOVED_DUPLICATE:             
            # Unban
# REMOVED_DUPLICATE:             await ctx.guild.unban(user, reason=reason or "No reason provided")
# REMOVED_DUPLICATE:             
            # Create case in database
# REMOVED_DUPLICATE:             case_number = self.db.create_case(
# REMOVED_DUPLICATE:                 ctx.guild.id,
# REMOVED_DUPLICATE:                 'unban',
# REMOVED_DUPLICATE:                 user.id,
# REMOVED_DUPLICATE:                 ctx.author.id,
# REMOVED_DUPLICATE:                 reason
# REMOVED_DUPLICATE:             )
# REMOVED_DUPLICATE:             
            # Send embed
# REMOVED_DUPLICATE:             embed = self.create_case_embed('unban', user, ctx.author, reason, None, case_number)
# REMOVED_DUPLICATE:             await ctx.send(embed=embed)
# REMOVED_DUPLICATE:             
# REMOVED_DUPLICATE:         except discord.NotFound:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ User not found or not banned. (ERR-{Config.ERROR_CODES['MEMBER_NOT_FOUND']})")
# REMOVED_DUPLICATE:         except discord.Forbidden:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ I don't have permission to unban users. (ERR-{Config.ERROR_CODES['PERMISSION_DENIED']})")
# REMOVED_DUPLICATE:         except Exception as e:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ An error occurred: {e} (ERR-{Config.ERROR_CODES['COMMAND_FAILED']})")
# REMOVED_DUPLICATE:     
# REMOVED_DUPLICATE:     @commands.command(name='kick')
# REMOVED_DUPLICATE:     @commands.has_permissions(kick_members=True)
# REMOVED_DUPLICATE:     async def kick_member(self, ctx, member: discord.Member, *, reason: str = None):
# REMOVED_DUPLICATE:         """Kick a member from the server"""
        # Check if kicks module is enabled
# REMOVED_DUPLICATE:         if not await self.check_module_enabled(ctx, 'kicks'):
# REMOVED_DUPLICATE:             return
# REMOVED_DUPLICATE:         
        # Can't kick yourself
# REMOVED_DUPLICATE:         if member.id == ctx.author.id:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ You cannot kick yourself. (ERR-{Config.ERROR_CODES['INVALID_INPUT']})")
# REMOVED_DUPLICATE:             return
# REMOVED_DUPLICATE:         
        # Can't kick bot
# REMOVED_DUPLICATE:         if member.id == self.bot.user.id:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ I cannot kick myself. (ERR-{Config.ERROR_CODES['INVALID_INPUT']})")
# REMOVED_DUPLICATE:             return
# REMOVED_DUPLICATE:         
        # Check hierarchy
# REMOVED_DUPLICATE:         if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ You cannot kick someone with a higher or equal role. (ERR-{Config.ERROR_CODES['PERMISSION_DENIED']})")
# REMOVED_DUPLICATE:             return
# REMOVED_DUPLICATE:         
# REMOVED_DUPLICATE:         try:
            # Create case in database
# REMOVED_DUPLICATE:             case_number = self.db.create_case(
# REMOVED_DUPLICATE:                 ctx.guild.id,
# REMOVED_DUPLICATE:                 'kick',
# REMOVED_DUPLICATE:                 member.id,
# REMOVED_DUPLICATE:                 ctx.author.id,
# REMOVED_DUPLICATE:                 reason
# REMOVED_DUPLICATE:             )
# REMOVED_DUPLICATE:             
            # Kick the member
# REMOVED_DUPLICATE:             await member.kick(reason=f"[Case #{case_number}] {reason or 'No reason provided'}")
# REMOVED_DUPLICATE:             
            # Send embed
# REMOVED_DUPLICATE:             embed = self.create_case_embed('kick', member, ctx.author, reason, None, case_number)
# REMOVED_DUPLICATE:             await ctx.send(embed=embed)
# REMOVED_DUPLICATE:             
# REMOVED_DUPLICATE:         except discord.Forbidden:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ I don't have permission to kick this member. (ERR-{Config.ERROR_CODES['PERMISSION_DENIED']})")
# REMOVED_DUPLICATE:         except Exception as e:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ An error occurred: {e} (ERR-{Config.ERROR_CODES['COMMAND_FAILED']})")
# REMOVED_DUPLICATE:     
# REMOVED_DUPLICATE:     @commands.command(name='purge')
# REMOVED_DUPLICATE:     @commands.has_permissions(manage_messages=True)
# REMOVED_DUPLICATE:     async def purge_messages(self, ctx, amount: int):
# REMOVED_DUPLICATE:         """Delete multiple messages"""
        # Check if purger module is enabled
# REMOVED_DUPLICATE:         if not await self.check_module_enabled(ctx, 'purger'):
# REMOVED_DUPLICATE:             return
# REMOVED_DUPLICATE:         
# REMOVED_DUPLICATE:         if amount < 1 or amount > 100:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ Amount must be between 1 and 100. (ERR-{Config.ERROR_CODES['INVALID_INPUT']})")
# REMOVED_DUPLICATE:             return
# REMOVED_DUPLICATE:         
# REMOVED_DUPLICATE:         try:
            # Delete messages
# REMOVED_DUPLICATE:             deleted = await ctx.channel.purge(limit=amount + 1)  # +1 for command message
# REMOVED_DUPLICATE:             
            # Send confirmation (will auto-delete)
# REMOVED_DUPLICATE:             msg = await ctx.send(f"✅ Deleted {len(deleted) - 1} messages.")
# REMOVED_DUPLICATE:             await msg.delete(delay=5)
# REMOVED_DUPLICATE:             
# REMOVED_DUPLICATE:         except discord.Forbidden:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ I don't have permission to delete messages. (ERR-{Config.ERROR_CODES['PERMISSION_DENIED']})")
# REMOVED_DUPLICATE:         except Exception as e:
# REMOVED_DUPLICATE:             await ctx.send(f"❌ An error occurred: {e} (ERR-{Config.ERROR_CODES['COMMAND_FAILED']})")
# REMOVED_DUPLICATE:     
    @commands.command(name='punishmentcase', aliases=['case'])
    async def view_case(self, ctx, case_number: int):
        """View details of a punishment case"""
        case = self.db.get_case(ctx.guild.id, case_number)
        
        if not case:
            await ctx.send(f"❌ Case #{case_number} not found. (ERR-{Config.ERROR_CODES['CASE_NOT_FOUND']})")
            return
        
        # Get user and moderator
        try:
            user = await self.bot.fetch_user(case['user_id'])
        except:
            user = None
        
        try:
            moderator = await self.bot.fetch_user(case['moderator_id'])
        except:
            moderator = None
        
        # Create embed
        embed = discord.Embed(
            title=f"Case #{case_number}",
            description=f"**Type:** {case['case_type'].title()}",
            color=0x00AAFF,
            timestamp=datetime.fromisoformat(case['timestamp'])
        )
        
        embed.add_field(
            name="User:",
            value=f"{user.mention if user else 'Unknown'} ({case['user_id']})",
            inline=False
        )
        
        embed.add_field(
            name="Moderator:",
            value=f"{moderator.mention if moderator else 'Unknown'} ({case['moderator_id']})",
            inline=False
        )
        
        if case['duration']:
            embed.add_field(name="Duration:", value=case['duration'], inline=False)
        
        embed.add_field(
            name="Reason:",
            value=case['reason'] or "No reason provided",
            inline=False
        )
        
        if user:
            embed.set_thumbnail(url=user.display_avatar.url if hasattr(user, 'display_avatar') else user.avatar.url)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='warn')
    @has_bfos_permission('mod_warn')
    async def warn(self, ctx, user: str, duration: str, *, reason: str):
        """Warn a user
        Usage: ;warn <user> <duration> <reason>
        Example: ;warn @User 7d Spamming in chat"""
        
        # Check if warns module is enabled
        if not self.db.is_module_enabled(ctx.guild.id, 'warns'):
            embed = discord.Embed(
                title="❌ Module Disabled",
                description="The warns module is not enabled. Enable it in BFOS terminal.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Parse user (ID, mention, or username)
        target = None
        
        # Try as ID
        if user.isdigit():
            try:
                target = await ctx.guild.fetch_member(int(user))
            except:
                pass
        
        # Try as mention
        if not target and user.startswith('<@') and user.endswith('>'):
            user_id = user.strip('<@!>')
            try:
                target = await ctx.guild.fetch_member(int(user_id))
            except:
                pass
        
        # Try as username
        if not target:
            target = discord.utils.find(lambda m: m.name.lower() == user.lower() or str(m).lower() == user.lower(), ctx.guild.members)
        
        if not target:
            embed = discord.Embed(
                title="❌ User Not Found",
                description=f"Could not find user: {user}",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Parse duration
        parsed_duration = self.parse_duration(duration)
        if not parsed_duration:
            embed = discord.Embed(
                title="❌ Invalid Duration",
                description=f"Invalid duration format: {duration}\nUse format like: 7d, 2h, 30m",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Create case - case_id is now a 10-digit random number
        _, case_id = self.db.create_case(
            ctx.guild.id,
            'warn',
            target.id,
            ctx.author.id,
            reason,
            duration
        )
        
        # Get warn config
        config = self.db.get_warn_config(ctx.guild.id)
        
        # Count user's warnings
        user_warns = self.db.get_user_cases(ctx.guild.id, target.id, 'warn')
        total_warns = len(user_warns)
        
        # Format threshold display
        threshold = config['warn_threshold']
        warns_display = f"{total_warns}" if not threshold else f"{total_warns}/{threshold}"
        
        # Send embed in channel
        embed = discord.Embed(
            title="⚠️ Warning Issued",
            color=0xFFAA00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{target.mention} (`{target.id}`)", inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Case ID", value=f"`{case_id}`", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Expires", value=f"<t:{int((datetime.utcnow() + parsed_duration).timestamp())}:R>", inline=True)
        embed.add_field(name="Total Warnings", value=warns_display, inline=True)
        embed.set_thumbnail(url=target.display_avatar.url if target.display_avatar else None)
        embed.set_footer(text=f"Case ID: {case_id}")
        
        await ctx.send(embed=embed)
        
        # Log to logging module
        await self.log_mod_action('warn', ctx.guild, target, ctx.author, reason, case_id,
                                  {'total_warnings': total_warns})
        
        # Send DM if enabled
        if config['dm_on_warn']:
            try:
                # Build embed from config
                dm_embed = self.build_embed(
                    ctx.guild.id, 
                    'warnings_dm',
                    placeholders={
                        'server': ctx.guild.name,
                        'user': str(target),
                        'user_id': str(target.id),
                        'moderator': str(ctx.author),
                        'reason': reason,
                        'duration': str(config['warn_duration']),
                        'expires': f"<t:{int((datetime.utcnow() + parsed_duration).timestamp())}:R>",
                        'warnings_display': warns_display,
                        'case': str(case_id)
                    }
                )
                dm_embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
                dm_embed.set_footer(text=ctx.guild.name)
                
                await target.send(embed=dm_embed)
            except:
                pass  # User has DMs disabled
        
        # Check auto-punishment
        if config['auto_punish_enabled'] and total_warns >= config['warn_threshold']:
            # Check staff immunity
            is_staff = self.db.get_user_staff_roles(ctx.guild.id, target.id)
            if config['staff_immune'] and is_staff:
                return  # Staff is immune
            
            # Auto-punish based on type
            if config['punishment_type'] == 'mute':
                # TODO: Implement mute
                pass
            elif config['punishment_type'] == 'kick':
                try:
                    await target.kick(reason=f"Auto-punishment: {config['warn_threshold']} warnings reached")
                    await ctx.send(f"✅ {target.mention} was automatically kicked for reaching {config['warn_threshold']} warnings.")
                except:
                    await ctx.send(f"❌ Failed to kick {target.mention}")
            elif config['punishment_type'] == 'ban':
                try:
                    await target.ban(reason=f"Auto-punishment: {config['warn_threshold']} warnings reached")
                    await ctx.send(f"✅ {target.mention} was automatically banned for reaching {config['warn_threshold']} warnings.")
                except:
                    await ctx.send(f"❌ Failed to ban {target.mention}")
    
    @commands.command(name='masswarn')
    @has_bfos_permission('mod_warn')
    async def masswarn(self, ctx, users: str, duration: str, *, reason: str):
        """Warn multiple users at once
        Usage: ;masswarn <user1,user2,user3> <duration> <reason>
        Example: ;masswarn 123,456,789 7d Mass spamming"""
        
        # Check if warns module is enabled
        if not self.db.is_module_enabled(ctx.guild.id, 'warns'):
            embed = discord.Embed(
                title="❌ Module Disabled",
                description="The warns module is not enabled.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Parse users
        user_ids = [u.strip() for u in users.split(',')]
        targets = []
        
        for user_id in user_ids:
            try:
                target = await ctx.guild.fetch_member(int(user_id))
                targets.append(target)
            except:
                pass
        
        if not targets:
            embed = discord.Embed(
                title="❌ No Users Found",
                description="Could not find any valid users from the list.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Parse duration
        parsed_duration = self.parse_duration(duration)
        if not parsed_duration:
            embed = discord.Embed(
                title="❌ Invalid Duration",
                description=f"Invalid duration format: {duration}",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Warn each user
        warned = []
        for target in targets:
            _, case_id = self.db.create_case(
                ctx.guild.id,
                'warn',
                target.id,
                ctx.author.id,
                reason,
                duration
            )
            warned.append(f"{target.mention} (Case `{case_id}`)")
        
        embed = discord.Embed(
            title="⚠️ Mass Warning Issued",
            description=f"Warned {len(warned)} users.",
            color=0xFFAA00
        )
        embed.add_field(name="Users", value="\n".join(warned), inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Duration", value=duration, inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='clearwarning')
    @has_bfos_permission('mod_warn')
    async def clearwarning(self, ctx, user: str, case_number: int):
        """Clear a specific warning
        Usage: ;clearwarning <user> <case_number>
        Example: ;clearwarning @User 42"""
        
        # Check if warns module is enabled
        if not self.db.is_module_enabled(ctx.guild.id, 'warns'):
            embed = discord.Embed(
                title="❌ Module Disabled",
                description="The warns module is not enabled.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Parse user
        target = None
        if user.isdigit():
            try:
                target = await ctx.guild.fetch_member(int(user))
            except:
                pass
        if not target and user.startswith('<@'):
            user_id = user.strip('<@!>')
            try:
                target = await ctx.guild.fetch_member(int(user_id))
            except:
                pass
        if not target:
            target = discord.utils.find(lambda m: m.name.lower() == user.lower(), ctx.guild.members)
        
        if not target:
            embed = discord.Embed(
                title="❌ User Not Found",
                description=f"Could not find user: {user}",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Get case
        case = self.db.get_case_by_number(ctx.guild.id, case_number)
        if not case or case['user_id'] != target.id or case['case_type'] != 'warn':
            embed = discord.Embed(
                title="❌ Warning Not Found",
                description=f"No warning found for {target.mention} with case #{case_number}",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Delete case
        success = self.db.delete_case(ctx.guild.id, case_number)
        
        if success:
            embed = discord.Embed(
                title="✅ Warning Cleared",
                description=f"Cleared warning case `#{case_number}` for {target.mention}",
                color=0x00FF00
            )
            await ctx.send(embed=embed)
            
            # Log the unwarn
            logging_cog = self.get_logging_cog()
            if logging_cog:
                await logging_cog.log_unwarn(ctx.guild, target, ctx.author, case_number, case_number)
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to clear warning.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
    
    @commands.command(name='listwarnings')
    @has_bfos_permission('mod_warn')
    async def listwarnings(self, ctx, user: str):
        """List all warnings for a user
        Usage: ;listwarnings <user>
        Example: ;listwarnings @User"""
        
        # Check if warns module is enabled
        if not self.db.is_module_enabled(ctx.guild.id, 'warns'):
            embed = discord.Embed(
                title="❌ Module Disabled",
                description="The warns module is not enabled.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Parse user
        target = None
        if user.isdigit():
            try:
                target = await ctx.guild.fetch_member(int(user))
            except:
                pass
        if not target and user.startswith('<@'):
            user_id = user.strip('<@!>')
            try:
                target = await ctx.guild.fetch_member(int(user_id))
            except:
                pass
        if not target:
            target = discord.utils.find(lambda m: m.name.lower() == user.lower(), ctx.guild.members)
        
        if not target:
            embed = discord.Embed(
                title="❌ User Not Found",
                description=f"Could not find user: {user}",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Get warnings
        warnings = self.db.get_user_cases(ctx.guild.id, target.id, 'warn')
        
        if not warnings:
            embed = discord.Embed(
                title=f"⚠️ Warnings for {target.name}",
                description="This user has no warnings.",
                color=0x00AA00
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            await ctx.send(embed=embed)
            return
        
        # Create embed with all warnings
        embed = discord.Embed(
            title=f"⚠️ Warnings for {target.name}",
            description=f"Total warnings: {len(warnings)}",
            color=0xFFAA00,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        
        for i, case in enumerate(warnings[:10], 1):  # Limit to 10 most recent
            try:
                moderator = await self.bot.fetch_user(case['moderator_id'])
                mod_name = str(moderator)
            except:
                mod_name = "Unknown"
            
            timestamp = datetime.fromisoformat(case['timestamp'])
            
            field_value = f"**Moderator:** {mod_name}\n**Reason:** {case['reason'] or 'No reason'}\n**Date:** <t:{int(timestamp.timestamp())}:R>\n**Duration:** {case['duration'] or 'N/A'}"
            
            embed.add_field(
                name=f"Case #{case['case_number']}",
                value=field_value,
                inline=False
            )
        
        if len(warnings) > 10:
            embed.set_footer(text=f"Showing 10 of {len(warnings)} warnings")
        else:
            embed.set_footer(text=f"{len(warnings)} warning(s)")
        
        await ctx.send(embed=embed)
    
    # ==================== MUTE SYSTEM ====================
    
    @commands.command(name='mute')
    @has_bfos_permission('mod_mute')
    async def mute_user(self, ctx, user_input: str = None, duration: str = None, *, reason: str = None):
        """
        Mute a user with timeout
        
        Usage: ;mute <user> <duration> <reason>
        Examples:
          ;mute @User 1d Spamming in chat
          ;mute 123456789 3h Breaking rules
          ;mute Username 1d3h Inappropriate behavior
        """
        # Check module
        if not self.db.get_module_state(ctx.guild.id, 'mutes'):
            await ctx.send(embed=AdvancedError.module_disabled('mutes'))
            return
        
        # Validate arguments
        if not user_input:
            error_msg = AdvancedError.argument_error('user')
            error_msg += "\n\n**Usage:** `;mute <user> <duration> <reason>`\n**Example:** `;mute @User 1d Spamming`"
            await ctx.send(error_msg)
            return
        
        if not duration:
            error_msg = AdvancedError.argument_error('duration')
            error_msg += "\n\n**Usage:** `;mute <user> <duration> <reason>`\n**Example:** `;mute @User 1d Spamming`"
            await ctx.send(error_msg)
            return
        
        if not reason:
            error_msg = AdvancedError.argument_error('reason')
            error_msg += "\n\n**Usage:** `;mute <user> <duration> <reason>`\n**Example:** `;mute @User 1d Spamming`"
            await ctx.send(error_msg)
            return
        
        # Resolve user
        user = await self.resolve_user(ctx, user_input)
        if not user:
            await ctx.send(AdvancedError.user_not_found(user_input))
            return
        
        # Validate duration
        valid, result = self.validate_duration(duration, max_days=30)
        if not valid:
            if "Invalid" in result:
                await ctx.send(AdvancedError.invalid_duration(duration))
            else:
                await ctx.send(AdvancedError.duration_exceeded(30))
            return
        
        duration_td = result
        
        # Check bot permissions
        if not ctx.guild.me.guild_permissions.moderate_members:
            await ctx.send(AdvancedError.permission_denied("mute users", "Moderate Members"))
            return
        
        # Check hierarchy
        if user.top_role >= ctx.guild.me.top_role:
            await ctx.send(AdvancedError.hierarchy_error("mute", user))
            return
        
        # Apply timeout
        try:
            await user.timeout(duration_td, reason=f"{reason} | By {ctx.author}")
            
            # Record in database
            mute_id, case_number = self.db.add_mute(
                ctx.guild.id,
                user.id,
                ctx.author.id,
                reason,
                duration
            )
            
            # Create embed
            embed = discord.Embed(
                title="🔇 User Muted",
                color=0xFF9900,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            embed.add_field(name="Case", value=f"`#{case_number}`", inline=True)
            embed.add_field(name="Duration", value=f"`{duration}`", inline=True)
            embed.add_field(name="Expires", value=f"<t:{int((datetime.utcnow() + duration_td).timestamp())}:R>", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
            
            embed.set_footer(text=f"Case #{case_number}")
            
            await ctx.send(embed=embed)
            
            # Log to logging module
            await self.log_mod_action('mute', ctx.guild, user, ctx.author, reason, case_number,
                                      {'duration': duration})
            
            # Try to DM user
            try:
                dm_embed = self.build_embed(
                    ctx.guild.id,
                    'mute_dm',
                    placeholders={
                        'server': ctx.guild.name,
                        'user': str(user),
                        'user_id': str(user.id),
                        'moderator': str(ctx.author),
                        'reason': reason,
                        'duration': duration,
                        'expires': f"<t:{int((datetime.utcnow() + duration_td).timestamp())}:R>",
                        'case': str(case_number)
                    }
                )
                
                if ctx.guild.icon:
                    dm_embed.set_thumbnail(url=ctx.guild.icon.url)
                
                dm_embed.set_footer(text=ctx.guild.name)
                
                await user.send(embed=dm_embed)
            except:
                pass  # User has DMs disabled
            
        except discord.Forbidden:
            await ctx.send(embed=AdvancedError.permission_denied("mute this user", "Moderate Members"))
        except Exception as e:
            await ctx.send(embed=AdvancedError.invalid_input(f"Failed to mute: {str(e)}"))
    
    @commands.command(name='unmute')
    @has_bfos_permission('mod_unmute')
    async def unmute_user(self, ctx, user_input: str = None, *, reason: str = None):
        """
        Unmute a user
        
        Usage: ;unmute <user> <reason>
        Examples:
          ;unmute @User Appeal accepted
          ;unmute 123456789 Timeout complete
        """
        # Check module
        if not self.db.get_module_state(ctx.guild.id, 'mutes'):
            await ctx.send(embed=AdvancedError.module_disabled('mutes'))
            return
        
        # Validate arguments
        if not user_input:
            error_msg = AdvancedError.argument_error('user')
            error_msg += "\n\n**Usage:** `;unmute <user> <reason>`\n**Example:** `;unmute @User Appeal accepted`"
            await ctx.send(error_msg)
            return
        
        if not reason:
            error_msg = AdvancedError.argument_error('reason')
            error_msg += "\n\n**Usage:** `;unmute <user> <reason>`\n**Example:** `;unmute @User Appeal accepted`"
            await ctx.send(error_msg)
            return
        
        # Resolve user
        user = await self.resolve_user(ctx, user_input)
        if not user:
            await ctx.send(AdvancedError.user_not_found(user_input))
            return
        
        # Remove timeout
        try:
            await user.timeout(None, reason=f"{reason} | By {ctx.author}")
            
            # Update database
            self.db.remove_mute(ctx.guild.id, user.id)
            
            # Create case
            case_id, case_number = self.db.create_case(
                ctx.guild.id,
                'unmute',
                user.id,
                ctx.author.id,
                reason
            )
            
            # Create embed
            embed = discord.Embed(
                title="🔊 User Unmuted",
                color=0x00FF00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            embed.add_field(name="Case", value=f"`#{case_number}`", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
            
            embed.set_footer(text=f"Case #{case_number}")
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send(embed=AdvancedError.permission_denied("unmute this user", "Moderate Members"))
        except Exception as e:
            await ctx.send(embed=AdvancedError.invalid_input(f"Failed to unmute: {str(e)}"))
    
    @commands.command(name='bulkmute')
    @has_bfos_permission('mod_mute')
    async def bulk_mute(self, ctx, users: commands.Greedy[discord.Member], duration: str = None, *, reason: str = None):
        """
        Mute multiple users at once
        
        Usage: ;bulkmute @user1 @user2 @user3 <duration> <reason>
        """
        # Check module
        if not self.db.get_module_state(ctx.guild.id, 'mutes'):
            await ctx.send(embed=AdvancedError.module_disabled('mutes'))
            return
        
        # Validate arguments
        if not users or len(users) == 0:
            await ctx.send(embed=AdvancedError.argument_error('users'))
            return
        
        if not duration:
            await ctx.send(embed=AdvancedError.argument_error('duration'))
            return
        
        if not reason:
            await ctx.send(embed=AdvancedError.argument_error('reason'))
            return
        
        # Validate duration
        valid, result = self.validate_duration(duration, max_days=30)
        if not valid:
            if "Invalid" in result:
                await ctx.send(embed=AdvancedError.invalid_duration(duration))
            else:
                await ctx.send(embed=AdvancedError.duration_exceeded(30))
            return
        
        duration_td = result
        
        # Mute each user
        success = []
        failed = []
        
        for user in users:
            try:
                await user.timeout(duration_td, reason=f"Bulk mute: {reason} | By {ctx.author}")
                
                mute_id, case_number = self.db.add_mute(
                    ctx.guild.id,
                    user.id,
                    ctx.author.id,
                    reason,
                    duration
                )
                
                success.append(f"{user.mention} (Case #{case_number})")
            except Exception as e:
                failed.append(f"{user.mention} ({str(e)[:30]}...)")
        
        # Create result embed
        embed = discord.Embed(
            title="🔇 Bulk Mute Results",
            description=f"Muted **{len(success)}/{len(users)}** users",
            color=0xFF9900 if success else 0xFF0000,
            timestamp=datetime.utcnow()
        )
        
        if success:
            embed.add_field(
                name=f"✅ Successful ({len(success)})",
                value="\n".join(success[:10]) + (f"\n*...and {len(success)-10} more*" if len(success) > 10 else ""),
                inline=False
            )
        
        if failed:
            embed.add_field(
                name=f"❌ Failed ({len(failed)})",
                value="\n".join(failed[:5]) + (f"\n*...and {len(failed)-5} more*" if len(failed) > 5 else ""),
                inline=False
            )
        
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Bulk mute by {ctx.author}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='unbulkmute')
    @has_bfos_permission('mod_unmute')
    async def bulk_unmute(self, ctx, users: commands.Greedy[discord.Member], *, reason: str = None):
        """
        Unmute multiple users at once
        
        Usage: ;unbulkmute @user1 @user2 @user3 <reason>
        """
        # Check module
        if not self.db.get_module_state(ctx.guild.id, 'mutes'):
            await ctx.send(embed=AdvancedError.module_disabled('mutes'))
            return
        
        # Validate arguments
        if not users or len(users) == 0:
            await ctx.send(embed=AdvancedError.argument_error('users'))
            return
        
        if not reason:
            await ctx.send(embed=AdvancedError.argument_error('reason'))
            return
        
        # Unmute each user
        success = []
        failed = []
        
        for user in users:
            try:
                await user.timeout(None, reason=f"Bulk unmute: {reason} | By {ctx.author}")
                
                self.db.remove_mute(ctx.guild.id, user.id)
                case_id, case_number = self.db.create_case(
                    ctx.guild.id,
                    'unmute',
                    user.id,
                    ctx.author.id,
                    reason
                )
                
                success.append(f"{user.mention} (Case #{case_number})")
            except Exception as e:
                failed.append(f"{user.mention} ({str(e)[:30]}...)")
        
        # Create result embed
        embed = discord.Embed(
            title="🔊 Bulk Unmute Results",
            description=f"Unmuted **{len(success)}/{len(users)}** users",
            color=0x00FF00 if success else 0xFF0000,
            timestamp=datetime.utcnow()
        )
        
        if success:
            embed.add_field(
                name=f"✅ Successful ({len(success)})",
                value="\n".join(success[:10]) + (f"\n*...and {len(success)-10} more*" if len(success) > 10 else ""),
                inline=False
            )
        
        if failed:
            embed.add_field(
                name=f"❌ Failed ({len(failed)})",
                value="\n".join(failed[:5]) + (f"\n*...and {len(failed)-5} more*" if len(failed) > 5 else ""),
                inline=False
            )
        
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Bulk unmute by {ctx.author}")
        
        await ctx.send(embed=embed)
    
    # ==================== KICKS MODULE ====================
    
    @commands.command(name='kick')
    @has_bfos_permission('mod_kick')
    async def kick_user(self, ctx, user_input: str = None, *, reason: str = None):
        """
        Kick a user from the server
        
        Usage: ;kick <user> <reason>
        Examples:
          ;kick @User Breaking rules
          ;kick 123456789 Spamming
        """
        # Check module
        if not self.db.get_module_state(ctx.guild.id, 'kicks'):
            await ctx.send(AdvancedError.module_disabled('kicks'))
            return
        
        # Validate arguments
        if not user_input:
            error_msg = AdvancedError.argument_error('user')
            error_msg += "\n\n**Usage:** `;kick <user> <reason>`\n**Example:** `;kick @User Breaking rules`"
            await ctx.send(error_msg)
            return
        
        if not reason:
            error_msg = AdvancedError.argument_error('reason')
            error_msg += "\n\n**Usage:** `;kick <user> <reason>`\n**Example:** `;kick @User Breaking rules`"
            await ctx.send(error_msg)
            return
        
        # Resolve user
        user = await self.resolve_user(ctx, user_input)
        if not user:
            await ctx.send(AdvancedError.user_not_found(user_input))
            return
        
        # Check bot permissions
        if not ctx.guild.me.guild_permissions.kick_members:
            await ctx.send(AdvancedError.permission_denied("kick users", "Kick Members"))
            return
        
        # Check hierarchy
        if user.top_role >= ctx.guild.me.top_role:
            await ctx.send(AdvancedError.hierarchy_error("kick", user))
            return
        
        # Kick user
        try:
            # Create case first
            case_id, case_number = self.db.create_case(
                ctx.guild.id,
                'kick',
                user.id,
                ctx.author.id,
                reason
            )
            
            # Try to DM user before kicking
            try:
                dm_embed = self.build_embed(
                    ctx.guild.id,
                    'kick_dm',
                    placeholders={
                        'server': ctx.guild.name,
                        'user': str(user),
                        'user_id': str(user.id),
                        'moderator': str(ctx.author),
                        'reason': reason,
                        'case': str(case_number)
                    }
                )
                
                if ctx.guild.icon:
                    dm_embed.set_thumbnail(url=ctx.guild.icon.url)
                
                dm_embed.set_footer(text=ctx.guild.name)
                
                await user.send(embed=dm_embed)
            except:
                pass  # User has DMs disabled
            
            # Kick the user
            await user.kick(reason=f"{reason} | By {ctx.author}")
            
            # Create embed
            embed = discord.Embed(
                title="👢 User Kicked",
                color=0xFF6600,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            embed.add_field(name="Case", value=f"`#{case_number}`", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
            
            embed.set_footer(text=f"Case #{case_number}")
            
            await ctx.send(embed=embed)
            
            # Log to logging module
            await self.log_mod_action('kick', ctx.guild, user, ctx.author, reason, case_number)
            
        except discord.Forbidden:
            await ctx.send(AdvancedError.permission_denied("kick this user", "Kick Members"))
        except Exception as e:
            await ctx.send(AdvancedError.invalid_input(f"Failed to kick: {str(e)}"))
    
    @commands.command(name='masskick')
    @has_bfos_permission('mod_kick')
    async def mass_kick(self, ctx, users: commands.Greedy[discord.Member], *, reason: str = None):
        """
        Kick multiple users at once
        
        Usage: ;masskick @user1 @user2 @user3 <reason>
        """
        # Check module
        if not self.db.get_module_state(ctx.guild.id, 'kicks'):
            await ctx.send(AdvancedError.module_disabled('kicks'))
            return
        
        # Validate arguments
        if not users or len(users) == 0:
            error_msg = AdvancedError.argument_error('users')
            error_msg += "\n\n**Usage:** `;masskick @user1 @user2 <reason>`"
            await ctx.send(error_msg)
            return
        
        if not reason:
            error_msg = AdvancedError.argument_error('reason')
            error_msg += "\n\n**Usage:** `;masskick @user1 @user2 <reason>`"
            await ctx.send(error_msg)
            return
        
        # Kick each user
        success = []
        failed = []
        
        for user in users:
            try:
                case_id, case_number = self.db.create_case(
                    ctx.guild.id,
                    'kick',
                    user.id,
                    ctx.author.id,
                    reason
                )
                
                await user.kick(reason=f"Mass kick: {reason} | By {ctx.author}")
                success.append(f"{user.mention} (Case `#{case_number}`)")
            except Exception as e:
                failed.append(f"{user.mention} ({str(e)[:30]}...)")
        
        # Create result embed
        embed = discord.Embed(
            title="👢 Mass Kick Results",
            description=f"Kicked **{len(success)}/{len(users)}** users",
            color=0xFF6600 if success else 0xFF0000,
            timestamp=datetime.utcnow()
        )
        
        if success:
            embed.add_field(
                name=f"✅ Successful ({len(success)})",
                value="\n".join(success[:10]) + (f"\n*...and {len(success)-10} more*" if len(success) > 10 else ""),
                inline=False
            )
        
        if failed:
            embed.add_field(
                name=f"❌ Failed ({len(failed)})",
                value="\n".join(failed[:5]) + (f"\n*...and {len(failed)-5} more*" if len(failed) > 5 else ""),
                inline=False
            )
        
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Mass kick by {ctx.author}")
        
        await ctx.send(embed=embed)
    
    # ==================== BANS MODULE ====================
    
    @commands.command(name='ban')
    @has_bfos_permission('mod_ban')
    async def ban_user(self, ctx, user_input: str = None, duration: str = None, *, reason: str = None):
        """
        Ban a user (temp or permanent)
        
        Usage: ;ban <user> <duration|perm> <reason>
        Examples:
          ;ban @User 7d Repeated violations
          ;ban 123456789 perm Serious offense
          ;ban Username 30d Harassment
        """
        # Check module
        if not self.db.get_module_state(ctx.guild.id, 'bans'):
            await ctx.send(AdvancedError.module_disabled('bans'))
            return
        
        # Validate arguments
        if not user_input:
            error_msg = AdvancedError.argument_error('user')
            error_msg += "\n\n**Usage:** `;ban <user> <duration|perm> <reason>`\n**Example:** `;ban @User 7d Repeated violations`"
            await ctx.send(error_msg)
            return
        
        if not duration:
            error_msg = AdvancedError.argument_error('duration')
            error_msg += "\n\n**Usage:** `;ban <user> <duration|perm> <reason>`\n**Example:** `;ban @User perm Serious offense`"
            await ctx.send(error_msg)
            return
        
        if not reason:
            error_msg = AdvancedError.argument_error('reason')
            error_msg += "\n\n**Usage:** `;ban <user> <duration|perm> <reason>`\n**Example:** `;ban @User 7d Repeated violations`"
            await ctx.send(error_msg)
            return
        
        # Resolve user (can be ID for already-left users)
        user = await self.resolve_user(ctx, user_input)
        if not user:
            # Try as direct ID for users not in server
            if user_input.isdigit():
                try:
                    user = await self.bot.fetch_user(int(user_input))
                except:
                    await ctx.send(AdvancedError.user_not_found(user_input))
                    return
            else:
                await ctx.send(AdvancedError.user_not_found(user_input))
                return
        
        # Check if permanent or temp
        is_permanent = duration.lower() in ['perm', 'permanent', 'forever']
        duration_td = None
        
        if not is_permanent:
            # Validate duration
            valid, result = self.validate_duration(duration, max_days=365)
            if not valid:
                if "Invalid" in result:
                    await ctx.send(AdvancedError.invalid_duration(duration))
                else:
                    error_msg = AdvancedError.duration_exceeded(365)
                    await ctx.send(error_msg)
                return
            duration_td = result
        
        # Check bot permissions
        if not ctx.guild.me.guild_permissions.ban_members:
            await ctx.send(AdvancedError.permission_denied("ban users", "Ban Members"))
            return
        
        # Check hierarchy (only if user is in server)
        if isinstance(user, discord.Member) and user.top_role >= ctx.guild.me.top_role:
            await ctx.send(AdvancedError.hierarchy_error("ban", user))
            return
        
        # Ban user
        try:
            # Create case first
            case_id, case_number = self.db.create_case(
                ctx.guild.id,
                'ban',
                user.id,
                ctx.author.id,
                reason,
                duration if not is_permanent else 'permanent'
            )
            
            # Try to DM user before banning (if in server)
            if isinstance(user, discord.Member):
                try:
                    dm_embed = self.build_embed(
                        ctx.guild.id,
                        'ban_dm',
                        placeholders={
                            'server': ctx.guild.name,
                            'user': str(user),
                            'user_id': str(user.id),
                            'moderator': str(ctx.author),
                            'reason': reason,
                            'duration': 'Permanent' if is_permanent else duration,
                            'expires': f"<t:{int((datetime.utcnow() + duration_td).timestamp())}:R>" if not is_permanent else 'Never',
                            'case': str(case_number)
                        }
                    )
                    
                    if ctx.guild.icon:
                        dm_embed.set_thumbnail(url=ctx.guild.icon.url)
                    
                    dm_embed.set_footer(text=ctx.guild.name)
                    
                    await user.send(embed=dm_embed)
                except:
                    pass
            
            # Ban the user
            await ctx.guild.ban(user, reason=f"{reason} | By {ctx.author}", delete_message_days=0)
            
            # Create embed
            embed = discord.Embed(
                title="🔨 User Banned",
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            embed.add_field(name="Case", value=f"`#{case_number}`", inline=True)
            
            if is_permanent:
                embed.add_field(name="Duration", value="`Permanent`", inline=True)
            else:
                embed.add_field(name="Duration", value=f"`{duration}`", inline=True)
                embed.add_field(name="Expires", value=f"<t:{int((datetime.utcnow() + duration_td).timestamp())}:R>", inline=True)
            
            embed.add_field(name="Reason", value=reason, inline=False)
            
            embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
            
            embed.set_footer(text=f"Case #{case_number}")
            
            await ctx.send(embed=embed)
            
            # Log to logging module
            await self.log_mod_action('ban', ctx.guild, user, ctx.author, reason, case_number,
                                      {'duration': duration if not is_permanent else 'Permanent'})
            
        except discord.Forbidden:
            await ctx.send(AdvancedError.permission_denied("ban this user", "Ban Members"))
        except Exception as e:
            await ctx.send(AdvancedError.invalid_input(f"Failed to ban: {str(e)}"))
    
    @commands.command(name='unban')
    @has_bfos_permission('mod_unban')
    async def unban_user(self, ctx, user_input: str = None, *, reason: str = None):
        """
        Unban a user
        
        Usage: ;unban <user_id> <reason>
        Example: ;unban 123456789 Appeal accepted
        """
        # Check module
        if not self.db.get_module_state(ctx.guild.id, 'bans'):
            await ctx.send(AdvancedError.module_disabled('bans'))
            return
        
        # Validate arguments
        if not user_input:
            error_msg = AdvancedError.argument_error('user_id')
            error_msg += "\n\n**Usage:** `;unban <user_id> <reason>`\n**Example:** `;unban 123456789 Appeal accepted`"
            await ctx.send(error_msg)
            return
        
        if not reason:
            error_msg = AdvancedError.argument_error('reason')
            error_msg += "\n\n**Usage:** `;unban <user_id> <reason>`\n**Example:** `;unban 123456789 Appeal accepted`"
            await ctx.send(error_msg)
            return
        
        # User must be ID for unbans
        if not user_input.isdigit():
            await ctx.send(AdvancedError.invalid_input("User ID must be numeric for unbans."))
            return
        
        try:
            user = await self.bot.fetch_user(int(user_input))
        except:
            await ctx.send(AdvancedError.user_not_found(user_input))
            return
        
        # Check bot permissions
        if not ctx.guild.me.guild_permissions.ban_members:
            await ctx.send(AdvancedError.permission_denied("unban users", "Ban Members"))
            return
        
        # Unban user
        try:
            await ctx.guild.unban(user, reason=f"{reason} | By {ctx.author}")
            
            # Create case
            case_id, case_number = self.db.create_case(
                ctx.guild.id,
                'unban',
                user.id,
                ctx.author.id,
                reason
            )
            
            # Create embed
            embed = discord.Embed(
                title="✅ User Unbanned",
                color=0x27AE60,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            embed.add_field(name="Case", value=f"`#{case_number}`", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
            
            embed.set_footer(text=f"Case #{case_number}")
            
            await ctx.send(embed=embed)
            
            # Log the unban
            logging_cog = self.get_logging_cog()
            if logging_cog:
                await logging_cog.log_unban(ctx.guild, user, ctx.author, reason, case_number)
            
            # Try to DM user
            try:
                dm_embed = self.build_embed(
                    ctx.guild.id,
                    'unban_dm',
                    placeholders={
                        'server': ctx.guild.name,
                        'user': str(user),
                        'user_id': str(user.id),
                        'moderator': str(ctx.author),
                        'reason': reason,
                        'case': str(case_number)
                    }
                )
                
                if ctx.guild.icon:
                    dm_embed.set_thumbnail(url=ctx.guild.icon.url)
                
                dm_embed.set_footer(text=ctx.guild.name)
                
                await user.send(embed=dm_embed)
            except:
                pass  # User has DMs disabled
            
        except discord.NotFound:
            await ctx.send(AdvancedError.invalid_input("User is not banned."))
        except discord.Forbidden:
            await ctx.send(AdvancedError.permission_denied("unban this user", "Ban Members"))
        except Exception as e:
            await ctx.send(AdvancedError.invalid_input(f"Failed to unban: {str(e)}"))
    
    @commands.command(name='massban')
    @has_bfos_permission('mod_ban')
    async def mass_ban(self, ctx, user_ids: str = None, duration: str = None, *, reason: str = None):
        """
        Ban multiple users at once
        
        Usage: ;massban <user_ids> <duration|perm> <reason>
        Example: ;massban 123,456,789 perm Raid attempt
        """
        # Check module
        if not self.db.get_module_state(ctx.guild.id, 'bans'):
            await ctx.send(AdvancedError.module_disabled('bans'))
            return
        
        # Validate arguments
        if not user_ids:
            error_msg = AdvancedError.argument_error('user_ids')
            error_msg += "\n\n**Usage:** `;massban <user_ids> <duration|perm> <reason>`\n**Example:** `;massban 123,456,789 perm Raid`"
            await ctx.send(error_msg)
            return
        
        if not duration:
            error_msg = AdvancedError.argument_error('duration')
            error_msg += "\n\n**Usage:** `;massban <user_ids> <duration|perm> <reason>`"
            await ctx.send(error_msg)
            return
        
        if not reason:
            error_msg = AdvancedError.argument_error('reason')
            error_msg += "\n\n**Usage:** `;massban <user_ids> <duration|perm> <reason>`"
            await ctx.send(error_msg)
            return
        
        # Parse user IDs
        ids = [uid.strip() for uid in user_ids.split(',') if uid.strip().isdigit()]
        
        if not ids:
            await ctx.send(AdvancedError.invalid_input("No valid user IDs found. Use comma-separated IDs: `123,456,789`"))
            return
        
        # Check if permanent or temp
        is_permanent = duration.lower() in ['perm', 'permanent', 'forever']
        duration_td = None
        
        if not is_permanent:
            valid, result = self.validate_duration(duration, max_days=365)
            if not valid:
                if "Invalid" in result:
                    await ctx.send(AdvancedError.invalid_duration(duration))
                else:
                    await ctx.send(AdvancedError.duration_exceeded(365))
                return
            duration_td = result
        
        # Ban each user
        success = []
        failed = []
        
        for user_id in ids:
            try:
                user = await self.bot.fetch_user(int(user_id))
                
                case_id, case_number = self.db.create_case(
                    ctx.guild.id,
                    'ban',
                    user.id,
                    ctx.author.id,
                    reason,
                    duration if not is_permanent else 'permanent'
                )
                
                await ctx.guild.ban(user, reason=f"Mass ban: {reason} | By {ctx.author}", delete_message_days=0)
                success.append(f"{user.mention} (Case #{case_number})")
            except Exception as e:
                failed.append(f"ID {user_id} ({str(e)[:30]}...)")
        
        # Create result embed
        embed = discord.Embed(
            title="🔨 Mass Ban Results",
            description=f"Banned **{len(success)}/{len(ids)}** users",
            color=0xFF0000 if success else 0xFF0000,
            timestamp=datetime.utcnow()
        )
        
        if success:
            embed.add_field(
                name=f"✅ Successful ({len(success)})",
                value="\n".join(success[:10]) + (f"\n*...and {len(success)-10} more*" if len(success) > 10 else ""),
                inline=False
            )
        
        if failed:
            embed.add_field(
                name=f"❌ Failed ({len(failed)})",
                value="\n".join(failed[:5]) + (f"\n*...and {len(failed)-5} more*" if len(failed) > 5 else ""),
                inline=False
            )
        
        embed.add_field(name="Duration", value="Permanent" if is_permanent else duration, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Mass ban by {ctx.author}")
        
        await ctx.send(embed=embed)
    
    # ==================== COMMANDS HELP ====================
    
        # Flatten all commands
        commands_list = []
        for module, cmds in all_commands.items():
            for cmd in cmds:
                commands_list.append({**cmd, 'module': module})
        
        # Create pages (15 commands per page)
        commands_per_page = 15
        pages = []
        
        for i in range(0, len(commands_list), commands_per_page):
            page_commands = commands_list[i:i + commands_per_page]
            
            embed = discord.Embed(
                title="📋 BlockForge OS Commands",
                description=f"Complete command reference",
                color=0x00AAFF,
                timestamp=datetime.utcnow()
            )
            
            for cmd in page_commands:
                field_value = f"**Usage:** `{cmd['usage']}`\n{cmd['desc']}\n**Permission:** {cmd['perm']}\n**Module:** `{cmd['module']}`"
                embed.add_field(
                    name=f"{cmd['name']}",
                    value=field_value,
                    inline=False
                )
            
            embed.set_footer(text=f"Page {len(pages) + 1} of {(len(commands_list) + commands_per_page - 1) // commands_per_page} • {len(commands_list)} total commands")
            
            if ctx.guild.icon:
                embed.set_thumbnail(url=ctx.guild.icon.url)
            
            pages.append(embed)
        
        # Send first page with navigation buttons
        if len(pages) == 1:
            await ctx.send(embed=pages[0])
            return
        
        # Create view with navigation buttons
        view = CommandsPaginationView(pages, timeout=None)  # No timeout as requested
        message = await ctx.send(embed=pages[0], view=view)
        view.message = message

class CommandsPaginationView(discord.ui.View):
    """Pagination view for commands list"""
    
    def __init__(self, pages, timeout=None):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current_page = 0
        self.message = None
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button enabled/disabled state"""
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == len(self.pages) - 1
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
