"""
BlockForge OS - Extended Moderation Commands
v2.0.9 - Comprehensive moderation system with embeds, voice channel moderation,
channel locking, mod notes, and more.
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Union
import re

# Processing emoji
PROCESSING_EMOJI_ID = 1342683115981639743


class ModerationExtended(commands.Cog):
    """Extended moderation commands with embeds and comprehensive logging"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db if hasattr(bot, 'db') else None
        self.voice_check_loop.start()
        
        # Embed colors
        self.COLORS = {
            'success': 0x2ECC71,
            'error': 0xE74C3C,
            'warning': 0xF39C12,
            'info': 0x3498DB,
            'mute': 0x9B59B6,
            'ban': 0xE74C3C,
            'kick': 0xE67E22,
            'warn': 0xF1C40F,
            'lock': 0x95A5A6,
            'voice': 0x1ABC9C,
            'role': 0x9B59B6,
            'note': 0x7289DA,
            'log': 0x34495E
        }
        
        # Permission IDs
        self.PERMISSIONS = {
            # Moderation
            'mod_warn': 'Warn users',
            'mod_ban': 'Ban users',
            'mod_kick': 'Kick users',
            'mod_mute': 'Mute users',
            'mod_unmute': 'Unmute users',
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
        }
    
    def cog_unload(self):
        self.voice_check_loop.cancel()
    
    # ==================== PERMISSION CHECKING ====================
    
    async def check_permission(self, ctx, permission_id: str) -> bool:
        """Check if user has permission to execute command"""
        debug_cog = self.bot.get_cog('Debug')

        # Bot owner always has permission
        if ctx.author.id == Config.BOT_OWNER_ID:
            if debug_cog:
                debug_cog.perm_log(f"PASS: Bot owner {ctx.author} for '{permission_id}'")
            return True

        # Server owner (unless demoted via debug)
        if ctx.author.id == ctx.guild.owner_id:
            if debug_cog and debug_cog.is_owner_demoted(ctx.guild.id):
                if debug_cog.debug_permissions:
                    debug_cog.perm_log(f"OWNER DEMOTED: {ctx.author} checking BFOS for '{permission_id}'")
            else:
                if debug_cog:
                    debug_cog.perm_log(f"PASS: Server owner {ctx.author} for '{permission_id}'")
                return True

        if not self.db:
            return False

        # Check user has direct permission
        if self.db.has_permission(ctx.guild.id, ctx.author.id, permission_id):
            if debug_cog:
                debug_cog.perm_log(f"PASS: {ctx.author} direct perm '{permission_id}'")
            return True

        # Check if user's roles have permission
        for role in ctx.author.roles:
            if self.db.role_has_permission(ctx.guild.id, role.id, permission_id):
                if debug_cog:
                    debug_cog.perm_log(f"PASS: {ctx.author} role '{role.name}' has '{permission_id}'")
                return True

        if debug_cog:
            debug_cog.perm_log(f"DENY: {ctx.author} lacks '{permission_id}'")
        return False
    
    async def permission_denied_embed(self, ctx, permission_id: str):
        """Send permission denied embed"""
        embed = discord.Embed(
            title="❌ Permission Denied",
            description=f"You don't have permission to use this command.",
            color=self.COLORS['error']
        )
        embed.add_field(name="Required Permission", value=f"`{permission_id}`", inline=False)
        embed.set_footer(text="Contact a server administrator for access.")
        await ctx.send(embed=embed, delete_after=10)
    
    # ==================== HELPER METHODS ====================
    
    def parse_duration(self, duration_str: str) -> Optional[timedelta]:
        """Parse duration string to timedelta. Returns None for permanent."""
        if not duration_str or duration_str.lower() in ['perm', 'permanent', 'forever', '0']:
            return None
        
        duration_str = duration_str.lower().strip()
        
        # Match patterns like 1d, 2h, 30m, 60s
        match = re.match(r'^(\d+)\s*(s|sec|second|seconds|m|min|minute|minutes|h|hr|hour|hours|d|day|days|w|week|weeks)$', duration_str)
        if not match:
            return None
        
        amount = int(match.group(1))
        unit = match.group(2)[0]  # First character
        
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
    
    def format_duration(self, td: Optional[timedelta]) -> str:
        """Format timedelta to human-readable string"""
        if td is None:
            return "Permanent"
        
        total_seconds = int(td.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds} seconds"
        elif total_seconds < 3600:
            return f"{total_seconds // 60} minutes"
        elif total_seconds < 86400:
            return f"{total_seconds // 3600} hours"
        elif total_seconds < 604800:
            return f"{total_seconds // 86400} days"
        else:
            return f"{total_seconds // 604800} weeks"
    
    async def get_user(self, ctx, user_input: str) -> Optional[Union[discord.Member, discord.User]]:
        """Get user from mention, ID, or name"""
        # Try to get member from guild first
        try:
            # Check if it's a mention
            if user_input.startswith('<@') and user_input.endswith('>'):
                user_id = int(user_input.strip('<@!>'))
                member = ctx.guild.get_member(user_id)
                if member:
                    return member
                return await self.bot.fetch_user(user_id)
            
            # Check if it's an ID
            if user_input.isdigit():
                user_id = int(user_input)
                member = ctx.guild.get_member(user_id)
                if member:
                    return member
                return await self.bot.fetch_user(user_id)
            
            # Try by name
            member = discord.utils.find(
                lambda m: m.name.lower() == user_input.lower() or 
                         (m.nick and m.nick.lower() == user_input.lower()),
                ctx.guild.members
            )
            return member
            
        except:
            return None
    
    def log_action(self, guild_id: int, action_type: str, user_id: int, moderator_id: int, 
                   case_id: str = None, reason: str = None, duration: str = None, details: dict = None):
        """Log a moderation action"""
        if self.db:
            self.db.add_mod_log(guild_id, action_type, user_id, moderator_id, case_id, reason, duration, json.dumps(details) if details else None)
        
        # Also write to file
        self.write_log_file(guild_id, action_type, user_id, moderator_id, case_id, reason, duration, details)
    
    def write_log_file(self, guild_id: int, action_type: str, user_id: int, moderator_id: int,
                       case_id: str = None, reason: str = None, duration: str = None, details: dict = None):
        """Write log entry to file"""
        log_dir = f"data/logs/{guild_id}"
        os.makedirs(log_dir, exist_ok=True)
        
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = f"{log_dir}/moderation_{date_str}.txt"
        
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        entry = f"[{timestamp}] {action_type.upper()} - User: {user_id} | Mod: {moderator_id}"
        if case_id:
            entry += f" | Case: {case_id}"
        if reason:
            entry += f" | Reason: {reason}"
        if duration:
            entry += f" | Duration: {duration}"
        if details:
            entry += f" | Details: {json.dumps(details)}"
        entry += "\n"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(entry)
    
    def is_staff_role(self, guild_id: int, role_id: int) -> bool:
        """Check if a role is a staff role"""
        if not self.db:
            return False
        
        staff_roles = self.db.get_all_staff_roles(guild_id)
        return any(r['role_id'] == role_id for r in staff_roles)
    
    def get_staff_role_ids(self, guild_id: int) -> list:
        """Get list of staff role IDs"""
        if not self.db:
            return []
        
        staff_roles = self.db.get_all_staff_roles(guild_id)
        return [r['role_id'] for r in staff_roles]
    
    # ==================== VOICE CHECK LOOP ====================
    
    @tasks.loop(seconds=30)
    async def voice_check_loop(self):
        """Check for voice punishments to apply when users join VC"""
        # This runs in background to check if users with pending voice punishments join VC
        pass  # Implementation handled in on_voice_state_update
    
    @voice_check_loop.before_loop
    async def before_voice_check(self):
        await self.bot.wait_until_ready()
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Apply pending voice punishments when user joins VC"""
        if not after.channel:  # User left VC
            return
        
        if before.channel == after.channel:  # No channel change
            return
        
        if not self.db:
            return
        
        guild_id = member.guild.id
        user_id = member.id
        
        # Check for pending vcmute
        mute_punishment = self.db.get_active_voice_punishment(guild_id, user_id, 'vcmute')
        if mute_punishment:
            try:
                await member.edit(mute=True, reason=f"Auto-applied vcmute (Case: {mute_punishment['case_id']})")
            except:
                pass
        
        # Check for pending vcdeafen
        deafen_punishment = self.db.get_active_voice_punishment(guild_id, user_id, 'vcdeafen')
        if deafen_punishment:
            try:
                await member.edit(deafen=True, reason=f"Auto-applied vcdeafen (Case: {deafen_punishment['case_id']})")
            except:
                pass
    
    # ==================== VIEWCASE COMMAND ====================
    
    @commands.command(name='viewcase')
    async def viewcase(self, ctx, case_id: str):
        """View detailed information about a punishment case"""
        if not await self.check_permission(ctx, 'case_view'):
            return await self.permission_denied_embed(ctx, 'case_view')
        
        if not self.db:
            return await ctx.send(embed=discord.Embed(title="❌ Database Error", color=self.COLORS['error']))
        
        case = self.db.get_case_by_id(ctx.guild.id, case_id)
        
        if not case:
            embed = discord.Embed(
                title="❌ Case Not Found",
                description=f"No case found with ID `{case_id}`",
                color=self.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Get user info
        try:
            user = await self.bot.fetch_user(case['user_id'])
            user_str = f"{user.mention} (`{user.id}`)"
        except:
            user_str = f"Unknown User (`{case['user_id']}`)"
        
        # Get moderator info
        try:
            mod = await self.bot.fetch_user(case['moderator_id'])
            mod_str = f"{mod.mention} (`{mod.id}`)"
        except:
            mod_str = f"Unknown Moderator (`{case['moderator_id']}`)"
        
        # Determine embed color based on case type
        case_type = case['case_type'].lower()
        if 'ban' in case_type:
            color = self.COLORS['ban']
        elif 'kick' in case_type:
            color = self.COLORS['kick']
        elif 'mute' in case_type:
            color = self.COLORS['mute']
        elif 'warn' in case_type:
            color = self.COLORS['warning']
        else:
            color = self.COLORS['info']
        
        # Type emoji
        type_emojis = {
            'warn': '⚠️',
            'ban': '🔨',
            'kick': '👢',
            'mute': '🔇',
            'unmute': '🔊',
            'unban': '🔓',
            'vcmute': '🎤',
            'vcunmute': '🎤',
            'vcdeafen': '🔇',
            'vcundeafen': '🔊',
        }
        emoji = type_emojis.get(case_type, '📋')
        
        embed = discord.Embed(
            title=f"{emoji} Case #{case_id}",
            color=color,
            timestamp=datetime.fromisoformat(case['created_at']) if case['created_at'] else datetime.utcnow()
        )
        
        embed.add_field(name="Type", value=case['case_type'].upper(), inline=True)
        embed.add_field(name="User", value=user_str, inline=True)
        embed.add_field(name="Moderator", value=mod_str, inline=True)
        embed.add_field(name="Reason", value=case['reason'] or "No reason provided", inline=False)
        
        if case['duration']:
            embed.add_field(name="Duration", value=case['duration'], inline=True)
        else:
            embed.add_field(name="Duration", value="Permanent", inline=True)
        
        embed.add_field(name="Created", value=f"<t:{int(datetime.fromisoformat(case['created_at']).timestamp())}:F>" if case['created_at'] else "Unknown", inline=True)
        
        if case['metadata']:
            meta = case['metadata']
            if 'expires_at' in meta and meta['expires_at']:
                embed.add_field(name="Expires", value=f"<t:{int(datetime.fromisoformat(meta['expires_at']).timestamp())}:R>", inline=True)
            if 'status' in meta:
                embed.add_field(name="Status", value=meta['status'], inline=True)
        
        embed.set_footer(text=f"Case ID: {case_id}")
        
        await ctx.send(embed=embed)
    
    # ==================== PUNISHMENTS COMMAND ====================
    
    @commands.command(name='punishments')
    async def punishments(self, ctx, user: str):
        """Show all punishments for a user"""
        if not await self.check_permission(ctx, 'case_view'):
            return await self.permission_denied_embed(ctx, 'case_view')
        
        if not self.db:
            return await ctx.send(embed=discord.Embed(title="❌ Database Error", color=self.COLORS['error']))
        
        # Get user
        target = await self.get_user(ctx, user)
        if not target:
            embed = discord.Embed(
                title="❌ User Not Found",
                description=f"Could not find user `{user}`",
                color=self.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Get all punishments
        punishments = self.db.get_all_user_punishments(ctx.guild.id, target.id)
        
        if not punishments:
            embed = discord.Embed(
                title="📋 Punishment History",
                description=f"No punishments found for {target.mention}",
                color=self.COLORS['info']
            )
            embed.set_thumbnail(url=target.display_avatar.url if hasattr(target, 'display_avatar') else target.avatar.url if target.avatar else None)
            return await ctx.send(embed=embed)
        
        # If more than 10 punishments, send as file
        if len(punishments) > 10:
            content = f"═══════════════════════════════════════════════════════\n"
            content += f"PUNISHMENT HISTORY - {target.name}#{target.discriminator if hasattr(target, 'discriminator') else '0'}\n"
            content += f"User ID: {target.id}\n"
            content += f"Server: {ctx.guild.name}\n"
            content += f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            content += f"Total Punishments: {len(punishments)}\n"
            content += f"═══════════════════════════════════════════════════════\n\n"
            
            for p in punishments:
                content += f"[{p['created_at']}] {p['type'].upper()}\n"
                content += f"  Case ID: {p['case_id']}\n"
                content += f"  Reason: {p['reason'] or 'No reason'}\n"
                content += f"  Duration: {p['duration'] or 'Permanent'}\n"
                content += f"  Moderator: {p['moderator_id']}\n"
                content += f"\n"
            
            # Save to file
            filename = f"punishments_{target.id}_{ctx.guild.id}.txt"
            filepath = f"data/temp/{filename}"
            os.makedirs("data/temp", exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            await ctx.send(
                f"📋 Found {len(punishments)} punishments for {target.mention}. Sending as file:",
                file=discord.File(filepath, filename=filename)
            )
            
            os.remove(filepath)
            return
        
        # Otherwise send as embeds
        embed = discord.Embed(
            title=f"📋 Punishment History",
            description=f"Showing {len(punishments)} punishment(s) for {target.mention}",
            color=self.COLORS['info']
        )
        embed.set_thumbnail(url=target.display_avatar.url if hasattr(target, 'display_avatar') else target.avatar.url if target.avatar else None)
        
        for p in punishments[:10]:
            type_emoji = {'warn': '⚠️', 'ban': '🔨', 'kick': '👢', 'mute': '🔇', 'unmute': '🔊', 'unban': '🔓'}.get(p['type'].lower(), '📋')
            
            value = f"**Reason:** {p['reason'] or 'No reason'}\n"
            value += f"**Duration:** {p['duration'] or 'Permanent'}\n"
            value += f"**Date:** <t:{int(datetime.fromisoformat(p['created_at']).timestamp())}:R>" if p['created_at'] else "Unknown"
            
            embed.add_field(
                name=f"{type_emoji} {p['type'].upper()} | Case: `{p['case_id']}`",
                value=value,
                inline=False
            )
        
        embed.set_footer(text=f"User ID: {target.id}")
        await ctx.send(embed=embed)
    
    # ==================== MODNOTE COMMANDS ====================
    
    @commands.group(name='modnote', invoke_without_command=True)
    async def modnote(self, ctx):
        """Mod note commands"""
        embed = discord.Embed(
            title="📝 Mod Notes",
            description="Manage moderator notes for users",
            color=self.COLORS['note']
        )
        embed.add_field(name="Commands", value="""
`;modnote set <user> <note>` - Add a note
`;modnote view <user>` - View notes
`;modnote delete <user>` - Delete all notes
        """, inline=False)
        await ctx.send(embed=embed)
    
    @modnote.command(name='set')
    async def modnote_set(self, ctx, user: str, *, note: str):
        """Add a mod note for a user"""
        if not await self.check_permission(ctx, 'modnote_set'):
            return await self.permission_denied_embed(ctx, 'modnote_set')
        
        target = await self.get_user(ctx, user)
        if not target:
            embed = discord.Embed(title="❌ User Not Found", color=self.COLORS['error'])
            return await ctx.send(embed=embed, delete_after=5)
        
        if self.db:
            self.db.add_mod_note(ctx.guild.id, target.id, note, ctx.author.id)
        
        # Log action
        self.log_action(ctx.guild.id, 'modnote_set', target.id, ctx.author.id, details={'note': note[:100]})
        
        # Delete command message and send confirmation
        try:
            await ctx.message.delete()
        except:
            pass
        
        confirm = await ctx.send("✓ Note added", delete_after=2)
    
    @modnote.command(name='view')
    async def modnote_view(self, ctx, user: str):
        """View mod notes for a user"""
        if not await self.check_permission(ctx, 'modnote_view'):
            return await self.permission_denied_embed(ctx, 'modnote_view')
        
        target = await self.get_user(ctx, user)
        if not target:
            embed = discord.Embed(title="❌ User Not Found", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        notes = self.db.get_mod_notes(ctx.guild.id, target.id) if self.db else []
        
        embed = discord.Embed(
            title=f"📝 Mod Notes for {target.display_name}",
            color=self.COLORS['note']
        )
        embed.set_thumbnail(url=target.display_avatar.url if hasattr(target, 'display_avatar') else target.avatar.url if target.avatar else None)
        
        if not notes:
            embed.description = "No mod notes found for this user."
        else:
            for i, note in enumerate(notes[:10], 1):
                try:
                    creator = await self.bot.fetch_user(note['created_by'])
                    creator_str = creator.name
                except:
                    creator_str = str(note['created_by'])
                
                embed.add_field(
                    name=f"Note #{i} - by {creator_str}",
                    value=f"{note['note'][:200]}\n*{note['created_at']}*",
                    inline=False
                )
        
        embed.set_footer(text=f"User ID: {target.id}")
        await ctx.send(embed=embed)
    
    @modnote.command(name='delete')
    async def modnote_delete(self, ctx, user: str):
        """Delete all mod notes for a user"""
        if not await self.check_permission(ctx, 'modnote_delete'):
            return await self.permission_denied_embed(ctx, 'modnote_delete')
        
        target = await self.get_user(ctx, user)
        if not target:
            embed = discord.Embed(title="❌ User Not Found", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        count = self.db.delete_mod_notes(ctx.guild.id, target.id) if self.db else 0
        
        # Log action
        self.log_action(ctx.guild.id, 'modnote_delete', target.id, ctx.author.id, details={'deleted_count': count})
        
        embed = discord.Embed(
            title="✓ Notes Deleted",
            description=f"Deleted {count} note(s) for {target.mention}",
            color=self.COLORS['success']
        )
        await ctx.send(embed=embed)
    
    # ==================== VOICE CHANNEL COMMANDS ====================
    
    @commands.command(name='vcmute')
    async def vcmute(self, ctx, user: str, duration: str = None, *, reason: str = None):
        """Mute a user in voice channel"""
        if not await self.check_permission(ctx, 'vc_mute'):
            return await self.permission_denied_embed(ctx, 'vc_mute')
        
        target = await self.get_user(ctx, user)
        if not target or not isinstance(target, discord.Member):
            embed = discord.Embed(title="❌ Member Not Found", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        # Parse duration
        td = self.parse_duration(duration) if duration else None
        expires_at = (datetime.utcnow() + td).isoformat() if td else None
        
        # Create case
        if self.db:
            _, case_id = self.db.create_case(
                ctx.guild.id, 'vcmute', target.id, ctx.author.id,
                reason or "No reason provided", self.format_duration(td),
                {'expires_at': expires_at}
            )
            
            # Store voice punishment
            self.db.add_voice_punishment(
                ctx.guild.id, target.id, 'vcmute', reason,
                self.format_duration(td), expires_at, ctx.author.id, case_id
            )
        else:
            case_id = "N/A"
        
        # Apply mute if in voice
        applied = False
        if target.voice and target.voice.channel:
            try:
                await target.edit(mute=True, reason=f"VCMute by {ctx.author} | Case: {case_id}")
                applied = True
            except discord.Forbidden:
                pass
        
        # Log action
        self.log_action(ctx.guild.id, 'vcmute', target.id, ctx.author.id, case_id, reason, self.format_duration(td))
        
        embed = discord.Embed(
            title="🎤 Voice Muted",
            color=self.COLORS['mute']
        )
        embed.add_field(name="User", value=f"{target.mention}", inline=True)
        embed.add_field(name="Duration", value=self.format_duration(td), inline=True)
        embed.add_field(name="Case ID", value=f"`{case_id}`", inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
        
        if not applied:
            embed.add_field(name="⚠️ Note", value="User not in voice. Mute will apply when they join.", inline=False)
        
        embed.set_footer(text=f"Moderator: {ctx.author}")
        await ctx.send(embed=embed)
    
    @commands.command(name='vcunmute')
    async def vcunmute(self, ctx, user: str, *, reason: str = None):
        """Unmute a user in voice channel"""
        if not await self.check_permission(ctx, 'vc_unmute'):
            return await self.permission_denied_embed(ctx, 'vc_unmute')
        
        target = await self.get_user(ctx, user)
        if not target or not isinstance(target, discord.Member):
            embed = discord.Embed(title="❌ Member Not Found", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        # Remove punishment from DB
        if self.db:
            self.db.remove_voice_punishment(ctx.guild.id, target.id, 'vcmute')
            _, case_id = self.db.create_case(ctx.guild.id, 'vcunmute', target.id, ctx.author.id, reason or "No reason provided")
        else:
            case_id = "N/A"
        
        # Apply unmute if in voice
        if target.voice and target.voice.channel:
            try:
                await target.edit(mute=False, reason=f"VCUnmute by {ctx.author}")
            except:
                pass
        
        # Log action
        self.log_action(ctx.guild.id, 'vcunmute', target.id, ctx.author.id, case_id, reason)
        
        embed = discord.Embed(
            title="🎤 Voice Unmuted",
            color=self.COLORS['success']
        )
        embed.add_field(name="User", value=f"{target.mention}", inline=True)
        embed.add_field(name="Case ID", value=f"`{case_id}`", inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
        embed.set_footer(text=f"Moderator: {ctx.author}")
        await ctx.send(embed=embed)
    
    @commands.command(name='vcdeafen')
    async def vcdeafen(self, ctx, user: str, duration: str = None, *, reason: str = None):
        """Deafen a user in voice channel"""
        if not await self.check_permission(ctx, 'vc_deafen'):
            return await self.permission_denied_embed(ctx, 'vc_deafen')
        
        target = await self.get_user(ctx, user)
        if not target or not isinstance(target, discord.Member):
            embed = discord.Embed(title="❌ Member Not Found", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        td = self.parse_duration(duration) if duration else None
        expires_at = (datetime.utcnow() + td).isoformat() if td else None
        
        if self.db:
            _, case_id = self.db.create_case(
                ctx.guild.id, 'vcdeafen', target.id, ctx.author.id,
                reason or "No reason provided", self.format_duration(td),
                {'expires_at': expires_at}
            )
            self.db.add_voice_punishment(
                ctx.guild.id, target.id, 'vcdeafen', reason,
                self.format_duration(td), expires_at, ctx.author.id, case_id
            )
        else:
            case_id = "N/A"
        
        applied = False
        if target.voice and target.voice.channel:
            try:
                await target.edit(deafen=True, reason=f"VCDeafen by {ctx.author} | Case: {case_id}")
                applied = True
            except:
                pass
        
        self.log_action(ctx.guild.id, 'vcdeafen', target.id, ctx.author.id, case_id, reason, self.format_duration(td))
        
        embed = discord.Embed(title="🔇 Voice Deafened", color=self.COLORS['mute'])
        embed.add_field(name="User", value=f"{target.mention}", inline=True)
        embed.add_field(name="Duration", value=self.format_duration(td), inline=True)
        embed.add_field(name="Case ID", value=f"`{case_id}`", inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
        if not applied:
            embed.add_field(name="⚠️ Note", value="User not in voice. Deafen will apply when they join.", inline=False)
        embed.set_footer(text=f"Moderator: {ctx.author}")
        await ctx.send(embed=embed)
    
    @commands.command(name='vcundeafen')
    async def vcundeafen(self, ctx, user: str, *, reason: str = None):
        """Undeafen a user in voice channel"""
        if not await self.check_permission(ctx, 'vc_undeafen'):
            return await self.permission_denied_embed(ctx, 'vc_undeafen')
        
        target = await self.get_user(ctx, user)
        if not target or not isinstance(target, discord.Member):
            embed = discord.Embed(title="❌ Member Not Found", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        if self.db:
            self.db.remove_voice_punishment(ctx.guild.id, target.id, 'vcdeafen')
            _, case_id = self.db.create_case(ctx.guild.id, 'vcundeafen', target.id, ctx.author.id, reason or "No reason provided")
        else:
            case_id = "N/A"
        
        if target.voice and target.voice.channel:
            try:
                await target.edit(deafen=False, reason=f"VCUndeafen by {ctx.author}")
            except:
                pass
        
        self.log_action(ctx.guild.id, 'vcundeafen', target.id, ctx.author.id, case_id, reason)
        
        embed = discord.Embed(title="🔊 Voice Undeafened", color=self.COLORS['success'])
        embed.add_field(name="User", value=f"{target.mention}", inline=True)
        embed.add_field(name="Case ID", value=f"`{case_id}`", inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
        embed.set_footer(text=f"Moderator: {ctx.author}")
        await ctx.send(embed=embed)
    
    @commands.command(name='vcdisconnect')
    async def vcdisconnect(self, ctx, user: str):
        """Disconnect a user from voice channel"""
        if not await self.check_permission(ctx, 'vc_disconnect'):
            return await self.permission_denied_embed(ctx, 'vc_disconnect')
        
        target = await self.get_user(ctx, user)
        if not target or not isinstance(target, discord.Member):
            embed = discord.Embed(title="❌ Member Not Found", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        if not target.voice or not target.voice.channel:
            embed = discord.Embed(title="❌ Not in Voice", description="User is not in a voice channel.", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        channel_name = target.voice.channel.name
        
        try:
            await target.move_to(None, reason=f"Disconnected by {ctx.author}")
        except discord.Forbidden:
            embed = discord.Embed(title="❌ Permission Denied", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        self.log_action(ctx.guild.id, 'vcdisconnect', target.id, ctx.author.id, details={'from_channel': channel_name})
        
        embed = discord.Embed(title="📤 Disconnected from Voice", color=self.COLORS['voice'])
        embed.add_field(name="User", value=f"{target.mention}", inline=True)
        embed.add_field(name="From Channel", value=channel_name, inline=True)
        embed.set_footer(text=f"Moderator: {ctx.author}")
        await ctx.send(embed=embed)
    
    @commands.command(name='vcmove')
    async def vcmove(self, ctx, user: str, channel_id: str):
        """Move a user to a different voice channel"""
        if not await self.check_permission(ctx, 'vc_move'):
            return await self.permission_denied_embed(ctx, 'vc_move')
        
        target = await self.get_user(ctx, user)
        if not target or not isinstance(target, discord.Member):
            embed = discord.Embed(title="❌ Member Not Found", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        try:
            channel = ctx.guild.get_channel(int(channel_id))
            if not channel or not isinstance(channel, discord.VoiceChannel):
                raise ValueError()
        except:
            embed = discord.Embed(title="❌ Invalid Channel", description="Please provide a valid voice channel ID.", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        from_channel = target.voice.channel.name if target.voice and target.voice.channel else "None"
        
        try:
            await target.move_to(channel, reason=f"Moved by {ctx.author}")
        except discord.Forbidden:
            embed = discord.Embed(title="❌ Permission Denied", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        self.log_action(ctx.guild.id, 'vcmove', target.id, ctx.author.id, details={'from': from_channel, 'to': channel.name})
        
        embed = discord.Embed(title="🔀 Moved to Voice Channel", color=self.COLORS['voice'])
        embed.add_field(name="User", value=f"{target.mention}", inline=True)
        embed.add_field(name="From", value=from_channel, inline=True)
        embed.add_field(name="To", value=channel.name, inline=True)
        embed.set_footer(text=f"Moderator: {ctx.author}")
        await ctx.send(embed=embed)
    
    # ==================== CHANNEL LOCK COMMANDS ====================
    
    @commands.command(name='hardlock')
    async def hardlock(self, ctx, channel_id: str = None):
        """Hardlock a channel (staff only access)"""
        if not await self.check_permission(ctx, 'channel_hardlock'):
            return await self.permission_denied_embed(ctx, 'channel_hardlock')
        
        # Get channel
        if channel_id:
            try:
                channel = ctx.guild.get_channel(int(channel_id))
            except:
                channel = None
        else:
            channel = ctx.channel
        
        if not channel or not isinstance(channel, discord.TextChannel):
            embed = discord.Embed(title="❌ Invalid Channel", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        # Save current permissions
        saved_perms = {}
        for target, overwrite in channel.overwrites.items():
            saved_perms[str(target.id)] = {
                'type': 'role' if isinstance(target, discord.Role) else 'member',
                'allow': overwrite.pair()[0].value,
                'deny': overwrite.pair()[1].value
            }
        
        if self.db:
            self.db.save_channel_lock(ctx.guild.id, channel.id, 'hardlock', saved_perms, ctx.author.id)
        
        # Get staff role IDs
        staff_role_ids = self.get_staff_role_ids(ctx.guild.id)
        
        # Apply hardlock - deny all for @everyone, allow for staff
        try:
            # Deny all for everyone
            await channel.set_permissions(ctx.guild.default_role, 
                view_channel=False,
                send_messages=False,
                reason=f"Hardlock by {ctx.author}"
            )
            
            # Allow for staff roles
            for role_id in staff_role_ids:
                role = ctx.guild.get_role(role_id)
                if role:
                    await channel.set_permissions(role, 
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        reason=f"Hardlock by {ctx.author}"
                    )
        except discord.Forbidden:
            embed = discord.Embed(title="❌ Permission Denied", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        self.log_action(ctx.guild.id, 'hardlock', channel.id, ctx.author.id, details={'channel': channel.name})
        
        embed = discord.Embed(
            title="🔒 Channel Hardlocked",
            description=f"{channel.mention} has been hardlocked.\nOnly staff can access this channel.",
            color=self.COLORS['lock']
        )
        embed.add_field(name="Previous Permissions", value="Saved for restoration", inline=True)
        embed.set_footer(text=f"Locked by: {ctx.author}")
        await ctx.send(embed=embed)
    
    @commands.command(name='unhardlock')
    async def unhardlock(self, ctx, channel_id: str = None):
        """Restore channel from hardlock"""
        if not await self.check_permission(ctx, 'channel_hardlock'):
            return await self.permission_denied_embed(ctx, 'channel_hardlock')
        
        if channel_id:
            try:
                channel = ctx.guild.get_channel(int(channel_id))
            except:
                channel = None
        else:
            channel = ctx.channel
        
        if not channel:
            embed = discord.Embed(title="❌ Invalid Channel", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        # Get saved permissions
        lock_data = self.db.get_channel_lock(ctx.guild.id, channel.id, 'hardlock') if self.db else None
        
        if not lock_data:
            embed = discord.Embed(title="❌ Not Hardlocked", description="This channel is not hardlocked.", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        # Restore permissions
        try:
            # Clear current overwrites first
            for target in list(channel.overwrites.keys()):
                await channel.set_permissions(target, overwrite=None)
            
            # Restore saved overwrites
            for target_id, perm_data in lock_data['saved_permissions'].items():
                if perm_data['type'] == 'role':
                    target = ctx.guild.get_role(int(target_id))
                else:
                    target = ctx.guild.get_member(int(target_id))
                
                if target:
                    overwrite = discord.PermissionOverwrite.from_pair(
                        discord.Permissions(perm_data['allow']),
                        discord.Permissions(perm_data['deny'])
                    )
                    await channel.set_permissions(target, overwrite=overwrite, reason=f"Unhardlock by {ctx.author}")
        except discord.Forbidden:
            embed = discord.Embed(title="❌ Permission Denied", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        # Delete lock record
        if self.db:
            self.db.delete_channel_lock(ctx.guild.id, channel.id, 'hardlock')
        
        self.log_action(ctx.guild.id, 'unhardlock', channel.id, ctx.author.id, details={'channel': channel.name})
        
        embed = discord.Embed(
            title="🔓 Channel Unhardlocked",
            description=f"{channel.mention} permissions have been restored.",
            color=self.COLORS['success']
        )
        embed.set_footer(text=f"Unlocked by: {ctx.author}")
        await ctx.send(embed=embed)
    
    @commands.command(name='lock')
    async def lock(self, ctx, channel_id: str = None):
        """Lock a channel (read-only)"""
        if not await self.check_permission(ctx, 'channel_lock'):
            return await self.permission_denied_embed(ctx, 'channel_lock')
        
        if channel_id:
            try:
                channel = ctx.guild.get_channel(int(channel_id))
            except:
                channel = None
        else:
            channel = ctx.channel
        
        if not channel or not isinstance(channel, discord.TextChannel):
            embed = discord.Embed(title="❌ Invalid Channel", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        # Save current permissions
        saved_perms = {}
        for target, overwrite in channel.overwrites.items():
            saved_perms[str(target.id)] = {
                'type': 'role' if isinstance(target, discord.Role) else 'member',
                'allow': overwrite.pair()[0].value,
                'deny': overwrite.pair()[1].value
            }
        
        if self.db:
            self.db.save_channel_lock(ctx.guild.id, channel.id, 'lock', saved_perms, ctx.author.id)
        
        staff_role_ids = self.get_staff_role_ids(ctx.guild.id)
        
        try:
            # Deny send for everyone but keep view
            await channel.set_permissions(ctx.guild.default_role,
                send_messages=False,
                add_reactions=False,
                reason=f"Lock by {ctx.author}"
            )
            
            # Keep staff unrestricted
            for role_id in staff_role_ids:
                role = ctx.guild.get_role(role_id)
                if role:
                    await channel.set_permissions(role,
                        send_messages=True,
                        reason=f"Lock by {ctx.author}"
                    )
        except discord.Forbidden:
            embed = discord.Embed(title="❌ Permission Denied", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        self.log_action(ctx.guild.id, 'lock', channel.id, ctx.author.id, details={'channel': channel.name})
        
        embed = discord.Embed(
            title="🔒 Channel Locked",
            description=f"{channel.mention} is now read-only.\nUsers can view but not send messages.",
            color=self.COLORS['lock']
        )
        embed.set_footer(text=f"Locked by: {ctx.author}")
        await ctx.send(embed=embed)
    
    @commands.command(name='unlock')
    async def unlock(self, ctx, channel_id: str = None):
        """Unlock a channel"""
        if not await self.check_permission(ctx, 'channel_unlock'):
            return await self.permission_denied_embed(ctx, 'channel_unlock')
        
        if channel_id:
            try:
                channel = ctx.guild.get_channel(int(channel_id))
            except:
                channel = None
        else:
            channel = ctx.channel
        
        if not channel:
            embed = discord.Embed(title="❌ Invalid Channel", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        lock_data = self.db.get_channel_lock(ctx.guild.id, channel.id, 'lock') if self.db else None
        
        if not lock_data:
            # Just restore default role send_messages
            try:
                await channel.set_permissions(ctx.guild.default_role, send_messages=None, add_reactions=None, reason=f"Unlock by {ctx.author}")
            except:
                pass
        else:
            # Restore saved permissions
            try:
                for target in list(channel.overwrites.keys()):
                    await channel.set_permissions(target, overwrite=None)
                
                for target_id, perm_data in lock_data['saved_permissions'].items():
                    if perm_data['type'] == 'role':
                        target = ctx.guild.get_role(int(target_id))
                    else:
                        target = ctx.guild.get_member(int(target_id))
                    
                    if target:
                        overwrite = discord.PermissionOverwrite.from_pair(
                            discord.Permissions(perm_data['allow']),
                            discord.Permissions(perm_data['deny'])
                        )
                        await channel.set_permissions(target, overwrite=overwrite, reason=f"Unlock by {ctx.author}")
            except:
                pass
            
            if self.db:
                self.db.delete_channel_lock(ctx.guild.id, channel.id, 'lock')
        
        self.log_action(ctx.guild.id, 'unlock', channel.id, ctx.author.id, details={'channel': channel.name})
        
        embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=f"{channel.mention} is now unlocked.",
            color=self.COLORS['success']
        )
        embed.set_footer(text=f"Unlocked by: {ctx.author}")
        await ctx.send(embed=embed)
    
    # ==================== SLOWMODE COMMAND ====================
    
    @commands.command(name='slowmode')
    async def slowmode(self, ctx, arg1: str = None, arg2: str = None):
        """Set slowmode for a channel"""
        if not await self.check_permission(ctx, 'channel_slowmode'):
            return await self.permission_denied_embed(ctx, 'channel_slowmode')
        
        # Parse arguments
        channel = ctx.channel
        duration_str = arg1
        
        if arg1 and arg2:
            # First arg is channel ID
            try:
                channel = ctx.guild.get_channel(int(arg1))
                duration_str = arg2
            except:
                pass
        
        if not channel or not isinstance(channel, discord.TextChannel):
            embed = discord.Embed(title="❌ Invalid Channel", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        if not duration_str:
            embed = discord.Embed(
                title="❌ Missing Duration",
                description="Please specify a duration (e.g., `5s`, `1m`, `0` to disable)",
                color=self.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Parse duration to seconds
        if duration_str in ['0', '0s', 'off', 'disable']:
            seconds = 0
        else:
            td = self.parse_duration(duration_str)
            if td:
                seconds = int(td.total_seconds())
            else:
                embed = discord.Embed(title="❌ Invalid Duration", color=self.COLORS['error'])
                return await ctx.send(embed=embed)
        
        # Discord slowmode max is 6 hours (21600 seconds)
        if seconds > 21600:
            seconds = 21600
        
        try:
            await channel.edit(slowmode_delay=seconds, reason=f"Slowmode set by {ctx.author}")
        except discord.Forbidden:
            embed = discord.Embed(title="❌ Permission Denied", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        self.log_action(ctx.guild.id, 'slowmode', channel.id, ctx.author.id, details={'seconds': seconds})
        
        if seconds == 0:
            embed = discord.Embed(
                title="⏱️ Slowmode Disabled",
                description=f"Slowmode has been disabled in {channel.mention}",
                color=self.COLORS['success']
            )
        else:
            embed = discord.Embed(
                title="⏱️ Slowmode Set",
                description=f"Slowmode in {channel.mention} set to **{seconds}** seconds",
                color=self.COLORS['info']
            )
        
        embed.set_footer(text=f"Set by: {ctx.author}")
        await ctx.send(embed=embed)
    
    # ==================== NICKNAME COMMANDS ====================
    
    @commands.command(name='nick')
    async def nick(self, ctx, user: str, *, new_nick: str = None):
        """Change a user's nickname"""
        if not await self.check_permission(ctx, 'user_nick'):
            return await self.permission_denied_embed(ctx, 'user_nick')
        
        # Check for reset subcommand
        if user.lower() == 'reset':
            if not new_nick:
                embed = discord.Embed(title="❌ Missing User", description="Usage: `;nick reset <user>`", color=self.COLORS['error'])
                return await ctx.send(embed=embed)
            
            target = await self.get_user(ctx, new_nick)
            if not target or not isinstance(target, discord.Member):
                embed = discord.Embed(title="❌ Member Not Found", color=self.COLORS['error'])
                return await ctx.send(embed=embed)
            
            old_nick = target.nick or target.name
            
            try:
                await target.edit(nick=None, reason=f"Nick reset by {ctx.author}")
            except discord.Forbidden:
                embed = discord.Embed(title="❌ Permission Denied", color=self.COLORS['error'])
                return await ctx.send(embed=embed)
            
            self.log_action(ctx.guild.id, 'nick_reset', target.id, ctx.author.id, details={'old': old_nick})
            
            embed = discord.Embed(
                title="✓ Nickname Reset",
                color=self.COLORS['success']
            )
            embed.add_field(name="User", value=target.mention, inline=True)
            embed.add_field(name="Old Nickname", value=old_nick, inline=True)
            embed.set_footer(text=f"Reset by: {ctx.author}")
            return await ctx.send(embed=embed)
        
        # Normal nick change
        target = await self.get_user(ctx, user)
        if not target or not isinstance(target, discord.Member):
            embed = discord.Embed(title="❌ Member Not Found", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        if not new_nick:
            embed = discord.Embed(title="❌ Missing Nickname", description="Usage: `;nick <user> <new nickname>`", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        old_nick = target.nick or target.name
        
        try:
            await target.edit(nick=new_nick, reason=f"Nick changed by {ctx.author}")
        except discord.Forbidden:
            embed = discord.Embed(title="❌ Permission Denied", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        self.log_action(ctx.guild.id, 'nick_change', target.id, ctx.author.id, details={'old': old_nick, 'new': new_nick})
        
        embed = discord.Embed(
            title="✓ Nickname Changed",
            color=self.COLORS['success']
        )
        embed.add_field(name="User", value=target.mention, inline=True)
        embed.add_field(name="Old", value=old_nick, inline=True)
        embed.add_field(name="New", value=new_nick, inline=True)
        embed.set_footer(text=f"Changed by: {ctx.author}")
        await ctx.send(embed=embed)
    
    # ==================== ROLE COMMANDS ====================
    
    @commands.group(name='role', invoke_without_command=True)
    async def role(self, ctx):
        """Role management commands"""
        embed = discord.Embed(
            title="👤 Role Management",
            color=self.COLORS['role']
        )
        embed.add_field(name="Commands", value="""
`;role add <user|all> <role_id>` - Add role(s)
`;role remove <user|all> <role_id>` - Remove role(s)

Multiple roles: separate with comma (no spaces)
Example: `;role add @User 123,456,789`
        """, inline=False)
        await ctx.send(embed=embed)
    
    @role.command(name='add')
    async def role_add(self, ctx, target: str, *, role_ids: str):
        """Add role(s) to user(s)"""
        if not await self.check_permission(ctx, 'role_add'):
            return await self.permission_denied_embed(ctx, 'role_add')
        
        # Parse role IDs
        role_id_list = [r.strip() for r in role_ids.replace(' ', '').split(',')]
        roles_to_add = []
        
        for rid in role_id_list:
            try:
                role = ctx.guild.get_role(int(rid))
                if role:
                    roles_to_add.append(role)
            except:
                pass
        
        if not roles_to_add:
            embed = discord.Embed(title="❌ No Valid Roles", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        # Add processing reaction
        processing_emoji = self.bot.get_emoji(PROCESSING_EMOJI_ID)
        if processing_emoji:
            try:
                await ctx.message.add_reaction(processing_emoji)
            except:
                pass
        
        success_count = 0
        fail_count = 0
        
        if target.lower() == 'all':
            # Add to all members
            for member in ctx.guild.members:
                try:
                    await member.add_roles(*roles_to_add, reason=f"Role add by {ctx.author}")
                    success_count += 1
                except:
                    fail_count += 1
            
            target_str = f"all members ({success_count} succeeded, {fail_count} failed)"
        else:
            member = await self.get_user(ctx, target)
            if not member or not isinstance(member, discord.Member):
                embed = discord.Embed(title="❌ Member Not Found", color=self.COLORS['error'])
                return await ctx.send(embed=embed)
            
            try:
                await member.add_roles(*roles_to_add, reason=f"Role add by {ctx.author}")
                success_count = 1
                target_str = member.mention
            except:
                fail_count = 1
                target_str = member.mention
        
        # Remove processing reaction
        if processing_emoji:
            try:
                await ctx.message.remove_reaction(processing_emoji, self.bot.user)
            except:
                pass
        
        self.log_action(ctx.guild.id, 'role_add', 0 if target.lower() == 'all' else member.id, ctx.author.id,
                       details={'roles': [r.id for r in roles_to_add], 'target': target})
        
        embed = discord.Embed(
            title="✓ Role(s) Added",
            color=self.COLORS['success']
        )
        embed.add_field(name="Target", value=target_str, inline=True)
        embed.add_field(name="Roles", value=", ".join([r.mention for r in roles_to_add]), inline=True)
        embed.set_footer(text=f"Added by: {ctx.author}")
        await ctx.send(embed=embed)
    
    @role.command(name='remove')
    async def role_remove(self, ctx, target: str, *, role_ids: str):
        """Remove role(s) from user(s)"""
        if not await self.check_permission(ctx, 'role_remove'):
            return await self.permission_denied_embed(ctx, 'role_remove')
        
        role_id_list = [r.strip() for r in role_ids.replace(' ', '').split(',')]
        roles_to_remove = []
        
        for rid in role_id_list:
            try:
                role = ctx.guild.get_role(int(rid))
                if role:
                    roles_to_remove.append(role)
            except:
                pass
        
        if not roles_to_remove:
            embed = discord.Embed(title="❌ No Valid Roles", color=self.COLORS['error'])
            return await ctx.send(embed=embed)
        
        processing_emoji = self.bot.get_emoji(PROCESSING_EMOJI_ID)
        if processing_emoji:
            try:
                await ctx.message.add_reaction(processing_emoji)
            except:
                pass
        
        success_count = 0
        fail_count = 0
        
        if target.lower() == 'all':
            for member in ctx.guild.members:
                try:
                    await member.remove_roles(*roles_to_remove, reason=f"Role remove by {ctx.author}")
                    success_count += 1
                except:
                    fail_count += 1
            
            target_str = f"all members ({success_count} succeeded, {fail_count} failed)"
        else:
            member = await self.get_user(ctx, target)
            if not member or not isinstance(member, discord.Member):
                embed = discord.Embed(title="❌ Member Not Found", color=self.COLORS['error'])
                return await ctx.send(embed=embed)
            
            try:
                await member.remove_roles(*roles_to_remove, reason=f"Role remove by {ctx.author}")
                success_count = 1
                target_str = member.mention
            except:
                fail_count = 1
                target_str = member.mention
        
        if processing_emoji:
            try:
                await ctx.message.remove_reaction(processing_emoji, self.bot.user)
            except:
                pass
        
        self.log_action(ctx.guild.id, 'role_remove', 0 if target.lower() == 'all' else member.id, ctx.author.id,
                       details={'roles': [r.id for r in roles_to_remove], 'target': target})
        
        embed = discord.Embed(
            title="✓ Role(s) Removed",
            color=self.COLORS['success']
        )
        embed.add_field(name="Target", value=target_str, inline=True)
        embed.add_field(name="Roles", value=", ".join([r.mention for r in roles_to_remove]), inline=True)
        embed.set_footer(text=f"Removed by: {ctx.author}")
        await ctx.send(embed=embed)
    
    # ==================== MODLOG COMMAND ====================
    
    @commands.command(name='modlog')
    async def modlog(self, ctx, user_id: str = None, duration: str = None):
        """View moderation logs"""
        if not await self.check_permission(ctx, 'modlog_view'):
            return await self.permission_denied_embed(ctx, 'modlog_view')
        
        # Parse user ID
        target_user_id = None
        if user_id and user_id.lower() != 'all':
            try:
                if user_id.startswith('<@') and user_id.endswith('>'):
                    target_user_id = int(user_id.strip('<@!>'))
                else:
                    target_user_id = int(user_id)
            except:
                # Might be a duration instead
                duration = user_id
                user_id = None
        
        # Parse duration to hours
        duration_hours = None
        if duration:
            td = self.parse_duration(duration)
            if td:
                duration_hours = td.total_seconds() / 3600
        
        # Get logs from database
        if self.db:
            logs = self.db.get_mod_logs(ctx.guild.id, target_user_id, duration_hours, limit=200)
        else:
            logs = []
        
        if not logs:
            embed = discord.Embed(
                title="📋 Moderation Log",
                description="No log entries found.",
                color=self.COLORS['log']
            )
            return await ctx.send(embed=embed)
        
        # If more than 10, send as file
        if len(logs) > 10:
            content = f"═══════════════════════════════════════════════════════\n"
            content += f"MODERATION LOG - {ctx.guild.name}\n"
            content += f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            if target_user_id:
                content += f"Filtered by User: {target_user_id}\n"
            if duration_hours:
                content += f"Time Range: Last {duration_hours} hours\n"
            content += f"Total Entries: {len(logs)}\n"
            content += f"═══════════════════════════════════════════════════════\n\n"
            
            for log in logs:
                content += f"[{log['timestamp']}] {log['action_type'].upper()}\n"
                content += f"  User: {log['user_id']}\n"
                content += f"  Moderator: {log['moderator_id']}\n"
                if log['case_id']:
                    content += f"  Case ID: {log['case_id']}\n"
                if log['reason']:
                    content += f"  Reason: {log['reason']}\n"
                if log['duration']:
                    content += f"  Duration: {log['duration']}\n"
                content += "\n"
            
            filename = f"modlog_{ctx.guild.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = f"data/temp/{filename}"
            os.makedirs("data/temp", exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            await ctx.send(
                f"📋 Found {len(logs)} log entries. Sending as file:",
                file=discord.File(filepath, filename=filename)
            )
            
            os.remove(filepath)
            return
        
        # Send as embeds
        embed = discord.Embed(
            title="📋 Moderation Log",
            description=f"Showing {len(logs)} entries",
            color=self.COLORS['log']
        )
        
        for log in logs[:10]:
            action_emoji = {
                'warn': '⚠️', 'ban': '🔨', 'kick': '👢', 'mute': '🔇',
                'unmute': '🔊', 'unban': '🔓', 'vcmute': '🎤', 'vcunmute': '🎤',
                'lock': '🔒', 'unlock': '🔓', 'role_add': '➕', 'role_remove': '➖',
                'nick_change': '✏️'
            }.get(log['action_type'].lower(), '📋')
            
            value = f"User: <@{log['user_id']}>\n"
            value += f"Mod: <@{log['moderator_id']}>\n"
            if log['case_id']:
                value += f"Case: `{log['case_id']}`\n"
            if log['reason']:
                value += f"Reason: {log['reason'][:50]}\n"
            
            embed.add_field(
                name=f"{action_emoji} {log['action_type'].upper()} - {log['timestamp'][:16]}",
                value=value,
                inline=False
            )
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ModerationExtended(bot))