"""
BlockForge OS Logging Module v2.1.0
Comprehensive server logging with clean, compact Sapphire-style embeds
"""

import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Union, List, Dict, Any
import os
import json
import re
from collections import deque
from utils.database import Database


class LogQueue:
    """Rate-limited log queue with webhook support"""
    def __init__(self, rate: int = 5):
        self.queue = deque()
        self.rate = rate
        self.last_time = datetime.utcnow()
        self.count = 0

    async def add(self, channel, embed, file=None, files=None, content=None, webhook=None):
        self.queue.append({
            'channel': channel, 'embed': embed, 'file': file,
            'files': files, 'content': content, 'webhook': webhook
        })

    async def process(self):
        now = datetime.utcnow()
        if (now - self.last_time).total_seconds() >= 1:
            self.count = 0
            self.last_time = now

        while self.queue and self.count < self.rate:
            data = self.queue.popleft()
            try:
                kwargs = {
                    'embed': data['embed'],
                    'allowed_mentions': discord.AllowedMentions.none()
                }
                if data.get('files'):
                    kwargs['files'] = data['files']
                elif data.get('file'):
                    kwargs['file'] = data['file']
                if data.get('content'):
                    kwargs['content'] = data['content']

                sent = False
                # Try webhook first
                if data.get('webhook'):
                    try:
                        await data['webhook'].send(**kwargs, username="BFOS Logs")
                        sent = True
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        sent = False

                # Fallback to channel.send
                if not sent:
                    await data['channel'].send(**kwargs)

                self.count += 1
            except:
                pass
            await asyncio.sleep(0.1)


class LoggingModule(commands.Cog):
    """Comprehensive server logging with Sapphire-style embeds"""
    
    LOGGING_TYPES = {
        'messages': {
            'message_delete': 'Message Deleted',
            'message_edit': 'Message Edited', 
            'message_bulk_delete': 'Bulk Delete',
            'message_pin': 'Message Pin',
        },
        'members': {
            'member_join': 'Member Join',
            'member_leave': 'Member Leave',
            'member_update': 'Member Update',
            'member_ban': 'Member Ban',
            'member_unban': 'Member Unban',
            'member_timeout': 'Timeout',
            'member_nickname': 'Nickname Change',
            'member_avatar': 'Avatar Change',
        },
        'roles': {
            'role_create': 'Role Create',
            'role_delete': 'Role Delete',
            'role_update': 'Role Update',
            'member_role_update': 'Role Assignment',
        },
        'channels': {
            'channel_create': 'Channel Create',
            'channel_delete': 'Channel Delete',
            'channel_update': 'Channel Update',
            'channel_perms': 'Permission Update',
            'thread_create': 'Thread Create',
            'thread_delete': 'Thread Delete',
        },
        'server': {
            'guild_update': 'Server Update',
            'emoji_update': 'Emoji Update',
            'sticker_update': 'Sticker Update',
            'invite_create': 'Invite Create',
            'invite_delete': 'Invite Delete',
            'webhook_update': 'Webhook Update',
        },
        'voice': {
            'voice_join': 'Voice Join',
            'voice_leave': 'Voice Leave',
            'voice_move': 'Voice Move',
            'voice_mute': 'Voice Mute',
            'voice_deafen': 'Voice Deafen',
        },
        'moderation': {
            'mod_warn': 'Warning',
            'mod_ban': 'Ban',
            'mod_kick': 'Kick',
            'mod_mute': 'Mute',
            'mod_unmute': 'Unmute',
            'mod_unban': 'Unban',
            'mod_unwarn': 'Clear Warning',
            'mod_purge': 'Purge',
        },
        'bfos': {
            'bfos_backup': 'Backup',
            'bfos_module': 'Module',
            'bfos_settings': 'Settings',
            'bfos_command': 'Command',
            'verify_log': 'Verification',
        }
    }
    
    COLORS = {
        'message_delete': 0xE74C3C, 'message_edit': 0x3498DB, 'message_bulk_delete': 0xC0392B, 'message_pin': 0xF39C12,
        'member_join': 0x2ECC71, 'member_leave': 0x95A5A6, 'member_update': 0x3498DB, 'member_ban': 0xE74C3C,
        'member_unban': 0x27AE60, 'member_timeout': 0x9B59B6, 'member_nickname': 0x1ABC9C, 'member_avatar': 0x1ABC9C,
        'role_create': 0x2ECC71, 'role_delete': 0xE74C3C, 'role_update': 0xF1C40F, 'member_role_update': 0x3498DB,
        'channel_create': 0x2ECC71, 'channel_delete': 0xE74C3C, 'channel_update': 0xF1C40F, 'channel_perms': 0x9B59B6,
        'thread_create': 0x00BCD4, 'thread_delete': 0xE74C3C,
        'guild_update': 0x9B59B6, 'emoji_update': 0xFFEB3B, 'sticker_update': 0xE91E63,
        'invite_create': 0x00BCD4, 'invite_delete': 0x607D8B, 'webhook_update': 0x795548,
        'voice_join': 0x2ECC71, 'voice_leave': 0x95A5A6, 'voice_move': 0x3498DB, 'voice_mute': 0xFFC107, 'voice_deafen': 0x607D8B,
        'mod_warn': 0xFFAA00, 'mod_ban': 0xE74C3C, 'mod_kick': 0xE67E22, 'mod_mute': 0x9B59B6, 'mod_unmute': 0x27AE60, 
        'mod_unban': 0x27AE60, 'mod_unwarn': 0x3498DB, 'mod_purge': 0x3498DB,
        'bfos_backup': 0x00AAFF, 'bfos_module': 0x9B59B6, 'bfos_settings': 0xF39C12, 'bfos_command': 0x607D8B,
        'verify_log': 0x2ECC71,
    }
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.log_queue = LogQueue()
        self.message_cache = {}
        self.process_queue.start()
        self._init_tables()
    
    def _init_tables(self):
        """Initialize logging tables"""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS logging_config (
            guild_id INTEGER, log_type TEXT, enabled INTEGER DEFAULT 0, channel_id INTEGER,
            PRIMARY KEY (guild_id, log_type))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS logging_cases (
            id INTEGER PRIMARY KEY, guild_id INTEGER, case_number INTEGER, case_type TEXT,
            user_id INTEGER, user_name TEXT, moderator_id INTEGER, moderator_name TEXT,
            reason TEXT, timestamp TEXT, extra_data TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS logging_webhooks (
            guild_id INTEGER, channel_id INTEGER,
            webhook_id INTEGER, webhook_url TEXT, webhook_token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, channel_id))''')
        conn.commit()
        conn.close()
        self._webhook_cache = {}  # {(guild_id, channel_id): discord.Webhook}
    
    def cog_unload(self):
        self.process_queue.cancel()
    
    @tasks.loop(seconds=1)
    async def process_queue(self):
        await self.log_queue.process()
    
    @process_queue.before_loop
    async def before_process_queue(self):
        await self.bot.wait_until_ready()
    
    # ==================== CONFIG METHODS ====================
    
    def is_log_type_enabled(self, guild_id: int, log_type: str) -> bool:
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT enabled FROM logging_config WHERE guild_id = ? AND log_type = ?', (guild_id, log_type))
        row = cursor.fetchone()
        conn.close()
        return bool(row and row[0])
    
    def get_log_channel(self, guild_id: int, log_type: str) -> Optional[int]:
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT channel_id FROM logging_config WHERE guild_id = ? AND log_type = ?', (guild_id, log_type))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    
    def enable_log_type(self, guild_id: int, log_type: str, enabled: bool = True):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO logging_config (guild_id, log_type, enabled, channel_id)
            VALUES (?, ?, ?, COALESCE((SELECT channel_id FROM logging_config WHERE guild_id = ? AND log_type = ?), NULL))''',
            (guild_id, log_type, int(enabled), guild_id, log_type))
        conn.commit()
        conn.close()
    
    def set_log_channel(self, guild_id: int, log_type: str, channel_id: int):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO logging_config (guild_id, log_type, enabled, channel_id)
            VALUES (?, ?, COALESCE((SELECT enabled FROM logging_config WHERE guild_id = ? AND log_type = ?), 1), ?)''',
            (guild_id, log_type, guild_id, log_type, channel_id))
        conn.commit()
        conn.close()
    
    def get_all_config(self, guild_id: int) -> Dict:
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT log_type, enabled, channel_id FROM logging_config WHERE guild_id = ?', (guild_id,))
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: {'enabled': bool(row[1]), 'channel_id': row[2]} for row in rows}
    
    # ==================== CASE SYSTEM ====================
    
    def get_next_case_number(self, guild_id: int) -> int:
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(case_number) FROM logging_cases WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        conn.close()
        return (row[0] or 0) + 1
    
    def create_case(self, guild_id: int, case_type: str, user_id: int, user_name: str,
                    mod_id: int, mod_name: str, reason: str = None, extra: dict = None) -> int:
        case_num = self.get_next_case_number(guild_id)
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO logging_cases 
            (guild_id, case_number, case_type, user_id, user_name, moderator_id, moderator_name, reason, timestamp, extra_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (guild_id, case_num, case_type, user_id, user_name, mod_id, mod_name, reason, datetime.utcnow().isoformat(), json.dumps(extra) if extra else None))
        conn.commit()
        conn.close()
        return case_num
    
    # ==================== WEBHOOK MANAGEMENT ====================

    def _get_stored_webhook(self, guild_id: int, channel_id: int):
        """Get stored webhook info from DB."""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT webhook_id, webhook_url, webhook_token FROM logging_webhooks WHERE guild_id = ? AND channel_id = ?',
            (guild_id, channel_id)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {'id': row[0], 'url': row[1], 'token': row[2]}
        return None

    def _store_webhook(self, guild_id: int, channel_id: int, webhook: discord.Webhook):
        """Store webhook info in DB."""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT OR REPLACE INTO logging_webhooks (guild_id, channel_id, webhook_id, webhook_url, webhook_token)
               VALUES (?, ?, ?, ?, ?)''',
            (guild_id, channel_id, webhook.id, webhook.url, webhook.token)
        )
        conn.commit()
        conn.close()

    def _delete_stored_webhook(self, guild_id: int, channel_id: int):
        """Remove stored webhook info from DB."""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM logging_webhooks WHERE guild_id = ? AND channel_id = ?',
            (guild_id, channel_id)
        )
        conn.commit()
        conn.close()
        self._webhook_cache.pop((guild_id, channel_id), None)

    async def _get_or_create_webhook(self, channel: discord.TextChannel) -> Optional[discord.Webhook]:
        """Get existing or create new BFOS Logs webhook for a channel."""
        cache_key = (channel.guild.id, channel.id)

        # Check memory cache
        if cache_key in self._webhook_cache:
            webhook = self._webhook_cache[cache_key]
            try:
                await webhook.fetch()
                return webhook
            except (discord.NotFound, discord.Forbidden):
                self._webhook_cache.pop(cache_key, None)
                self._delete_stored_webhook(channel.guild.id, channel.id)

        # Check DB for stored webhook
        stored = self._get_stored_webhook(channel.guild.id, channel.id)
        if stored:
            try:
                webhook = discord.Webhook.partial(stored['id'], stored['token'], session=self.bot.http._HTTPClient__session)
                test = await webhook.fetch()
                self._webhook_cache[cache_key] = test
                return test
            except (discord.NotFound, discord.Forbidden):
                self._delete_stored_webhook(channel.guild.id, channel.id)

        # Check channel for existing "BFOS Logs" webhook
        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.name == "BFOS Logs" and wh.user and wh.user.id == self.bot.user.id:
                    self._store_webhook(channel.guild.id, channel.id, wh)
                    self._webhook_cache[cache_key] = wh
                    return wh
        except discord.Forbidden:
            return None

        # Create new webhook
        try:
            avatar_bytes = None
            if self.bot.user.avatar:
                avatar_bytes = await self.bot.user.avatar.read()
            webhook = await channel.create_webhook(name="BFOS Logs", avatar=avatar_bytes)
            self._store_webhook(channel.guild.id, channel.id, webhook)
            self._webhook_cache[cache_key] = webhook
            return webhook
        except (discord.Forbidden, discord.HTTPException):
            return None

    # ==================== LOG SENDING ====================

    async def send_log(self, guild: discord.Guild, log_type: str, embed: discord.Embed, file=None, files=None):
        if not self.is_log_type_enabled(guild.id, log_type):
            return
        channel_id = self.get_log_channel(guild.id, log_type)
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if channel:
            webhook = await self._get_or_create_webhook(channel)
            await self.log_queue.add(channel, embed, file=file, files=files, webhook=webhook)
    
    # ==================== EMBED HELPERS ====================
    
    def make_embed(self, title: str, color: int, description: str = None) -> discord.Embed:
        embed = discord.Embed(title=title, color=color, timestamp=datetime.utcnow())
        if description:
            embed.description = description
        return embed
    
    def format_user(self, user: Union[discord.User, discord.Member]) -> str:
        return f"{user.mention} (`{user.id}`)"
    
    def format_channel(self, channel) -> str:
        return f"{channel.mention}" if channel else "Unknown"
    
    def format_role(self, role: discord.Role) -> str:
        return f"{role.mention}" if role else "Unknown"
    
    def format_perms(self, before_perms, after_perms, target_name: str) -> str:
        """Format permission changes compactly"""
        changes = []
        
        # Get all permission names
        all_perms = [p[0] for p in discord.Permissions()]
        
        for perm in all_perms:
            before_val = getattr(before_perms, perm, None)
            after_val = getattr(after_perms, perm, None)
            
            if before_val != after_val:
                perm_name = perm.replace('_', ' ').title()
                if after_val is True:
                    changes.append(f"✅ {perm_name}")
                elif after_val is False:
                    changes.append(f"❌ {perm_name}")
                else:
                    changes.append(f"⬜ {perm_name}")
        
        return "\n".join(changes[:15]) if changes else "No changes"
    
    def get_audit_entry(self, guild: discord.Guild, action, target_id: int = None):
        """Helper to get audit log entry"""
        async def _get():
            try:
                await asyncio.sleep(0.5)
                async for entry in guild.audit_logs(limit=5, action=action):
                    if target_id is None or entry.target.id == target_id:
                        if (datetime.utcnow() - entry.created_at.replace(tzinfo=None)).total_seconds() < 10:
                            return entry
            except:
                pass
            return None
        return _get()
    
    # ==================== MESSAGE EVENTS ====================
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild:
            self.message_cache[message.id] = {
                'content': message.content,
                'author_id': message.author.id,
                'author_name': str(message.author),
                'channel_id': message.channel.id,
                'attachments': [{'name': a.filename, 'url': a.url} for a in message.attachments],
                'time': datetime.utcnow()
            }
            # Clean old cache
            cutoff = datetime.utcnow() - timedelta(hours=1)
            self.message_cache = {k: v for k, v in self.message_cache.items() if v.get('time', datetime.utcnow()) > cutoff}
    
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or message.author.bot:
            return
        
        embed = self.make_embed("🗑️ Message Deleted", self.COLORS['message_delete'])
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url if message.author.display_avatar else None)
        
        embed.add_field(name="Author", value=self.format_user(message.author), inline=True)
        embed.add_field(name="Channel", value=self.format_channel(message.channel), inline=True)
        embed.add_field(name="Sent", value=f"<t:{int(message.created_at.timestamp())}:R>", inline=True)
        
        if message.content:
            content = message.content[:1000] + ("..." if len(message.content) > 1000 else "")
            embed.add_field(name="Content", value=f"```\n{content}\n```", inline=False)
        
        # Get deleter from audit log
        entry = await self.get_audit_entry(message.guild, discord.AuditLogAction.message_delete, message.author.id)
        if entry:
            embed.add_field(name="Deleted By", value=self.format_user(entry.user), inline=True)
        
        # Jump link to nearby
        try:
            async for msg in message.channel.history(limit=1, before=message.created_at):
                embed.add_field(name="Context", value=f"[Jump]({msg.jump_url})", inline=True)
                break
        except: pass
        
        embed.set_footer(text=f"Author: {message.author.id} • Message: {message.id}")
        
        # Handle attachments - download and re-upload
        attachment_files = []
        if message.attachments:
            import aiohttp
            import io
            
            for attachment in message.attachments[:3]:  # Limit to 3 files
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(attachment.url) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                if len(data) < 8_000_000:  # 8MB limit
                                    file = discord.File(io.BytesIO(data), filename=attachment.filename)
                                    attachment_files.append(file)
                except:
                    pass
            
            if not attachment_files:
                # Couldn't download, just list them
                embed.add_field(name="Attachments", value=", ".join(f"`{a.filename}`" for a in message.attachments[:5]), inline=False)
        
        await self.send_log(message.guild, 'message_delete', embed, files=attachment_files if attachment_files else None)
    
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not before.guild or before.author.bot or before.content == after.content:
            return
        
        embed = self.make_embed("✏️ Message Edited", self.COLORS['message_edit'])
        embed.set_author(name=str(before.author), icon_url=before.author.display_avatar.url if before.author.display_avatar else None)
        
        embed.add_field(name="Author", value=self.format_user(before.author), inline=True)
        embed.add_field(name="Channel", value=self.format_channel(before.channel), inline=True)
        embed.add_field(name="Jump", value=f"[Click]({after.jump_url})", inline=True)
        
        before_text = (before.content[:400] + "...") if len(before.content or "") > 400 else (before.content or "*empty*")
        after_text = (after.content[:400] + "...") if len(after.content or "") > 400 else (after.content or "*empty*")
        
        embed.add_field(name="Before", value=f"```\n{before_text}\n```", inline=False)
        embed.add_field(name="After", value=f"```\n{after_text}\n```", inline=False)
        
        embed.set_footer(text=f"Author: {before.author.id} • Message: {before.id}")
        await self.send_log(before.guild, 'message_edit', embed)
    
    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages:
            return
        guild = messages[0].guild
        if not guild:
            return
        
        embed = self.make_embed("🗑️ Bulk Delete", self.COLORS['message_bulk_delete'], 
                                f"**{len(messages)}** messages deleted in {messages[0].channel.mention}")
        
        # Create log file
        log_content = f"Bulk Delete Log - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        log_content += f"Channel: #{messages[0].channel.name} ({messages[0].channel.id})\n"
        log_content += f"Messages: {len(messages)}\n\n"
        
        for msg in sorted(messages, key=lambda m: m.created_at):
            log_content += f"[{msg.created_at.strftime('%H:%M:%S')}] {msg.author}: {msg.content or '[no content]'}\n"
        
        import io
        file = discord.File(io.BytesIO(log_content.encode()), filename=f"bulk_delete_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt")
        
        embed.add_field(name="Channel", value=self.format_channel(messages[0].channel), inline=True)
        embed.add_field(name="Count", value=str(len(messages)), inline=True)
        embed.set_footer(text=f"Channel: {messages[0].channel.id}")
        
        await self.send_log(guild, 'message_bulk_delete', embed, file)
    
    # ==================== MEMBER EVENTS ====================
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = self.make_embed("📥 Member Joined", self.COLORS['member_join'])
        embed.set_author(name=str(member), icon_url=member.display_avatar.url if member.display_avatar else None)
        embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
        
        embed.add_field(name="User", value=self.format_user(member), inline=True)
        embed.add_field(name="Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        
        # Account age warning
        age = (datetime.utcnow() - member.created_at.replace(tzinfo=None)).days
        if age < 7:
            embed.add_field(name="⚠️ New Account", value=f"{age} days old", inline=True)
        
        embed.add_field(name="Member #", value=str(member.guild.member_count), inline=True)
        embed.set_footer(text=f"User ID: {member.id}")
        
        await self.send_log(member.guild, 'member_join', embed)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = self.make_embed("📤 Member Left", self.COLORS['member_leave'])
        embed.set_author(name=str(member), icon_url=member.display_avatar.url if member.display_avatar else None)
        embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
        
        embed.add_field(name="User", value=self.format_user(member), inline=True)
        embed.add_field(name="Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown", inline=True)
        
        if member.roles[1:]:
            roles = ", ".join(r.mention for r in member.roles[1:][:10])
            embed.add_field(name="Roles", value=roles, inline=False)
        
        # Check if kicked/banned
        entry = await self.get_audit_entry(member.guild, discord.AuditLogAction.kick, member.id)
        if entry:
            embed.add_field(name="Kicked By", value=self.format_user(entry.user), inline=True)
            if entry.reason:
                embed.add_field(name="Reason", value=entry.reason[:200], inline=False)
        
        embed.set_footer(text=f"User ID: {member.id}")
        await self.send_log(member.guild, 'member_leave', embed)
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Nickname change
        if before.nick != after.nick:
            embed = self.make_embed("📝 Nickname Changed", self.COLORS['member_nickname'])
            embed.set_author(name=str(after), icon_url=after.display_avatar.url if after.display_avatar else None)
            embed.add_field(name="User", value=self.format_user(after), inline=True)
            embed.add_field(name="Before", value=f"`{before.nick or 'None'}`", inline=True)
            embed.add_field(name="After", value=f"`{after.nick or 'None'}`", inline=True)
            embed.set_footer(text=f"User ID: {after.id}")
            await self.send_log(after.guild, 'member_nickname', embed)
        
        # Role changes
        if before.roles != after.roles:
            added = [r for r in after.roles if r not in before.roles]
            removed = [r for r in before.roles if r not in after.roles]
            
            if added or removed:
                embed = self.make_embed("🏷️ Roles Updated", self.COLORS['member_role_update'])
                embed.set_author(name=str(after), icon_url=after.display_avatar.url if after.display_avatar else None)
                embed.add_field(name="User", value=self.format_user(after), inline=True)
                
                if added:
                    embed.add_field(name="➕ Added", value=" ".join(r.mention for r in added[:10]), inline=False)
                if removed:
                    embed.add_field(name="➖ Removed", value=" ".join(r.mention for r in removed[:10]), inline=False)
                
                # Get who did it
                entry = await self.get_audit_entry(after.guild, discord.AuditLogAction.member_role_update, after.id)
                if entry:
                    embed.add_field(name="By", value=self.format_user(entry.user), inline=True)
                
                embed.set_footer(text=f"User ID: {after.id}")
                await self.send_log(after.guild, 'member_role_update', embed)
        
        # Timeout change
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until:
                embed = self.make_embed("⏰ Member Timed Out", self.COLORS['member_timeout'])
                embed.add_field(name="User", value=self.format_user(after), inline=True)
                embed.add_field(name="Until", value=f"<t:{int(after.timed_out_until.timestamp())}:R>", inline=True)
            else:
                embed = self.make_embed("✅ Timeout Removed", 0x27AE60)
                embed.add_field(name="User", value=self.format_user(after), inline=True)
            
            entry = await self.get_audit_entry(after.guild, discord.AuditLogAction.member_update, after.id)
            if entry:
                embed.add_field(name="By", value=self.format_user(entry.user), inline=True)
                if entry.reason:
                    embed.add_field(name="Reason", value=entry.reason[:200], inline=False)
            
            embed.set_footer(text=f"User ID: {after.id}")
            await self.send_log(after.guild, 'member_timeout', embed)
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = self.make_embed("🔨 Member Banned", self.COLORS['member_ban'])
        embed.set_author(name=str(user), icon_url=user.display_avatar.url if user.display_avatar else None)
        embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
        
        embed.add_field(name="User", value=self.format_user(user), inline=True)
        
        entry = await self.get_audit_entry(guild, discord.AuditLogAction.ban, user.id)
        if entry:
            embed.add_field(name="Banned By", value=self.format_user(entry.user), inline=True)
            if entry.reason:
                embed.add_field(name="Reason", value=f"```\n{entry.reason[:500]}\n```", inline=False)
        
        embed.set_footer(text=f"User ID: {user.id}")
        await self.send_log(guild, 'member_ban', embed)
    
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        embed = self.make_embed("🔓 Member Unbanned", self.COLORS['member_unban'])
        embed.set_author(name=str(user), icon_url=user.display_avatar.url if user.display_avatar else None)
        
        embed.add_field(name="User", value=self.format_user(user), inline=True)
        
        entry = await self.get_audit_entry(guild, discord.AuditLogAction.unban, user.id)
        if entry:
            embed.add_field(name="Unbanned By", value=self.format_user(entry.user), inline=True)
            if entry.reason:
                embed.add_field(name="Reason", value=entry.reason[:200], inline=False)
        
        embed.set_footer(text=f"User ID: {user.id}")
        await self.send_log(guild, 'member_unban', embed)
    
    # ==================== ROLE EVENTS ====================
    
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        embed = self.make_embed("✨ Role Created", self.COLORS['role_create'])
        embed.add_field(name="Role", value=f"{role.mention} (`{role.id}`)", inline=True)
        embed.add_field(name="Color", value=f"`{str(role.color)}`", inline=True)
        embed.add_field(name="Position", value=str(role.position), inline=True)
        
        entry = await self.get_audit_entry(role.guild, discord.AuditLogAction.role_create, role.id)
        if entry:
            embed.add_field(name="Created By", value=self.format_user(entry.user), inline=True)
        
        embed.set_footer(text=f"Role ID: {role.id}")
        await self.send_log(role.guild, 'role_create', embed)
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        embed = self.make_embed("🗑️ Role Deleted", self.COLORS['role_delete'])
        embed.add_field(name="Role", value=f"`{role.name}` (`{role.id}`)", inline=True)
        embed.add_field(name="Color", value=f"`{str(role.color)}`", inline=True)
        embed.add_field(name="Members", value=str(len(role.members)), inline=True)
        
        entry = await self.get_audit_entry(role.guild, discord.AuditLogAction.role_delete, role.id)
        if entry:
            embed.add_field(name="Deleted By", value=self.format_user(entry.user), inline=True)
        
        embed.set_footer(text=f"Role ID: {role.id}")
        await self.send_log(role.guild, 'role_delete', embed)
    
    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        changes = []
        
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.color != after.color:
            changes.append(f"**Color:** `{before.color}` → `{after.color}`")
        if before.hoist != after.hoist:
            changes.append(f"**Hoisted:** `{before.hoist}` → `{after.hoist}`")
        if before.mentionable != after.mentionable:
            changes.append(f"**Mentionable:** `{before.mentionable}` → `{after.mentionable}`")
        if before.position != after.position:
            changes.append(f"**Position:** `{before.position}` → `{after.position}`")
        if before.permissions != after.permissions:
            changes.append("**Permissions:** Modified")
        
        if not changes:
            return
        
        embed = self.make_embed("⚙️ Role Updated", self.COLORS['role_update'])
        embed.add_field(name="Role", value=f"{after.mention} (`{after.id}`)", inline=True)
        embed.add_field(name="Changes", value="\n".join(changes[:10]), inline=False)
        
        # Permission changes detail
        if before.permissions != after.permissions:
            perm_changes = []
            for perm, val in after.permissions:
                old_val = getattr(before.permissions, perm)
                if old_val != val:
                    icon = "✅" if val else "❌"
                    perm_changes.append(f"{icon} {perm.replace('_', ' ').title()}")
            if perm_changes:
                embed.add_field(name="Permission Changes", value="\n".join(perm_changes[:15]), inline=False)
        
        entry = await self.get_audit_entry(after.guild, discord.AuditLogAction.role_update, after.id)
        if entry:
            embed.add_field(name="Updated By", value=self.format_user(entry.user), inline=True)
        
        embed.set_footer(text=f"Role ID: {after.id}")
        await self.send_log(after.guild, 'role_update', embed)
    
    # ==================== CHANNEL EVENTS ====================
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = self.make_embed("📁 Channel Created", self.COLORS['channel_create'])
        
        channel_type = str(channel.type).replace('_', ' ').title()
        embed.add_field(name="Channel", value=f"{channel.mention} (`{channel.id}`)", inline=True)
        embed.add_field(name="Type", value=channel_type, inline=True)
        
        if hasattr(channel, 'category') and channel.category:
            embed.add_field(name="Category", value=channel.category.name, inline=True)
        
        entry = await self.get_audit_entry(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        if entry:
            embed.add_field(name="Created By", value=self.format_user(entry.user), inline=True)
        
        embed.set_footer(text=f"Channel ID: {channel.id}")
        await self.send_log(channel.guild, 'channel_create', embed)
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = self.make_embed("🗑️ Channel Deleted", self.COLORS['channel_delete'])
        
        channel_type = str(channel.type).replace('_', ' ').title()
        embed.add_field(name="Channel", value=f"`#{channel.name}` (`{channel.id}`)", inline=True)
        embed.add_field(name="Type", value=channel_type, inline=True)
        
        if hasattr(channel, 'category') and channel.category:
            embed.add_field(name="Category", value=channel.category.name, inline=True)
        
        entry = await self.get_audit_entry(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        if entry:
            embed.add_field(name="Deleted By", value=self.format_user(entry.user), inline=True)
        
        embed.set_footer(text=f"Channel ID: {channel.id}")
        await self.send_log(channel.guild, 'channel_delete', embed)
    
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        changes = []
        perm_changes = []
        
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        
        if hasattr(before, 'topic') and before.topic != after.topic:
            changes.append(f"**Topic:** Changed")
        
        if hasattr(before, 'slowmode_delay') and before.slowmode_delay != after.slowmode_delay:
            changes.append(f"**Slowmode:** `{before.slowmode_delay}s` → `{after.slowmode_delay}s`")
        
        if hasattr(before, 'nsfw') and before.nsfw != after.nsfw:
            changes.append(f"**NSFW:** `{before.nsfw}` → `{after.nsfw}`")
        
        if before.position != after.position:
            changes.append(f"**Position:** `{before.position}` → `{after.position}`")
        
        # Check permission overwrites - show ALL permissions
        if before.overwrites != after.overwrites:
            for target, after_overwrite in after.overwrites.items():
                before_overwrite = before.overwrites.get(target)
                
                # Format target with actual mention (won't ping due to AllowedMentions.none())
                if isinstance(target, discord.Role):
                    target_type = "👥"
                    target_name = target.mention
                elif isinstance(target, (discord.Member, discord.User)):
                    target_type = "👤"
                    target_name = target.mention
                else:
                    target_type = "❓"
                    target_name = str(target)
                
                if before_overwrite is None:
                    # New overwrite created - show all set permissions
                    all_perms = []
                    for perm, val in after_overwrite:
                        if val is True:
                            all_perms.append(f"✅ {perm.replace('_', ' ').title()}")
                        elif val is False:
                            all_perms.append(f"❌ {perm.replace('_', ' ').title()}")
                    
                    if all_perms:
                        perm_changes.append({
                            'target': f"{target_type} {target_name}",
                            'changes': all_perms
                        })
                        
                elif before_overwrite != after_overwrite:
                    # Overwrite modified - show ALL changed permissions
                    all_perms = []
                    for perm, val in after_overwrite:
                        old_val = getattr(before_overwrite, perm, None) if before_overwrite else None
                        if old_val != val:
                            perm_name = perm.replace('_', ' ').title()
                            if val is True:
                                all_perms.append(f"✅ {perm_name}")
                            elif val is False:
                                all_perms.append(f"❌ {perm_name}")
                            else:
                                all_perms.append(f"⬜ {perm_name}")
                    
                    if all_perms:
                        perm_changes.append({
                            'target': f"{target_type} {target_name}",
                            'changes': all_perms
                        })
            
            # Check for removed overwrites
            for target in before.overwrites:
                if target not in after.overwrites:
                    # Format target with actual mention
                    if isinstance(target, discord.Role):
                        target_type = "👥"
                        target_name = target.mention
                    elif isinstance(target, (discord.Member, discord.User)):
                        target_type = "👤"
                        target_name = target.mention
                    else:
                        target_type = "❓"
                        target_name = str(target)
                    
                    perm_changes.append({
                        'target': f"{target_type} {target_name}",
                        'changes': ["🗑️ All overwrites removed"]
                    })
        
        if not changes and not perm_changes:
            return
        
        embed = self.make_embed("⚙️ Channel Updated", self.COLORS['channel_update'])
        embed.add_field(name="Channel", value=f"{after.mention}", inline=True)
        
        if changes:
            embed.add_field(name="Changes", value="\n".join(changes[:8]), inline=False)
        
        if perm_changes:
            # Send permission changes in channel_perms log type
            perm_embed = self.make_embed("🔐 Permission Update", self.COLORS['channel_perms'])
            
            # Format channel - mention already includes # for text channels
            perm_embed.add_field(name="Channel", value=after.mention, inline=False)
            
            # Show all permission changes for each target
            for perm_data in perm_changes[:3]:  # Limit to 3 targets per embed
                target = perm_data['target']
                perm_list = perm_data['changes']
                
                # Show ALL permissions, not limited
                perm_text = "\n".join(perm_list)
                if len(perm_text) > 1000:
                    perm_text = perm_text[:997] + "..."
                
                # Put target in VALUE (mentions render in values, not names)
                perm_embed.add_field(name="Changes", value=f"{target}\n{perm_text}", inline=False)
            
            entry = await self.get_audit_entry(after.guild, discord.AuditLogAction.overwrite_update, after.id)
            if not entry:
                entry = await self.get_audit_entry(after.guild, discord.AuditLogAction.overwrite_create, after.id)
            if entry:
                perm_embed.add_field(name="Updated By", value=self.format_user(entry.user), inline=True)
            
            perm_embed.set_footer(text=f"Channel ID: {after.id}")
            await self.send_log(after.guild, 'channel_perms', perm_embed)
        
        if changes:
            entry = await self.get_audit_entry(after.guild, discord.AuditLogAction.channel_update, after.id)
            if entry:
                embed.add_field(name="Updated By", value=self.format_user(entry.user), inline=True)
            
            embed.set_footer(text=f"Channel ID: {after.id}")
            await self.send_log(after.guild, 'channel_update', embed)
    
    # ==================== VOICE EVENTS ====================
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        
        # Join
        if before.channel is None and after.channel is not None:
            embed = self.make_embed("🔊 Voice Join", self.COLORS['voice_join'])
            embed.set_author(name=str(member), icon_url=member.display_avatar.url if member.display_avatar else None)
            embed.add_field(name="User", value=self.format_user(member), inline=True)
            embed.add_field(name="Channel", value=after.channel.mention, inline=True)
            embed.set_footer(text=f"User ID: {member.id}")
            await self.send_log(guild, 'voice_join', embed)
        
        # Leave
        elif before.channel is not None and after.channel is None:
            embed = self.make_embed("🔇 Voice Leave", self.COLORS['voice_leave'])
            embed.set_author(name=str(member), icon_url=member.display_avatar.url if member.display_avatar else None)
            embed.add_field(name="User", value=self.format_user(member), inline=True)
            embed.add_field(name="Channel", value=before.channel.mention, inline=True)
            embed.set_footer(text=f"User ID: {member.id}")
            await self.send_log(guild, 'voice_leave', embed)
        
        # Move
        elif before.channel != after.channel and before.channel and after.channel:
            embed = self.make_embed("🔀 Voice Move", self.COLORS['voice_move'])
            embed.set_author(name=str(member), icon_url=member.display_avatar.url if member.display_avatar else None)
            embed.add_field(name="User", value=self.format_user(member), inline=True)
            embed.add_field(name="From", value=before.channel.mention, inline=True)
            embed.add_field(name="To", value=after.channel.mention, inline=True)
            embed.set_footer(text=f"User ID: {member.id}")
            await self.send_log(guild, 'voice_move', embed)
        
        # Mute/Unmute
        if before.self_mute != after.self_mute or before.mute != after.mute:
            is_muted = after.self_mute or after.mute
            embed = self.make_embed(f"🔇 {'Muted' if is_muted else 'Unmuted'}", self.COLORS['voice_mute'])
            embed.add_field(name="User", value=self.format_user(member), inline=True)
            embed.add_field(name="Type", value="Server Mute" if after.mute else "Self Mute", inline=True)
            embed.set_footer(text=f"User ID: {member.id}")
            await self.send_log(guild, 'voice_mute', embed)
        
        # Deafen
        if before.self_deaf != after.self_deaf or before.deaf != after.deaf:
            is_deaf = after.self_deaf or after.deaf
            embed = self.make_embed(f"🔕 {'Deafened' if is_deaf else 'Undeafened'}", self.COLORS['voice_deafen'])
            embed.add_field(name="User", value=self.format_user(member), inline=True)
            embed.add_field(name="Type", value="Server Deaf" if after.deaf else "Self Deaf", inline=True)
            embed.set_footer(text=f"User ID: {member.id}")
            await self.send_log(guild, 'voice_deafen', embed)
    
    # ==================== SERVER EVENTS ====================
    
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        changes = []
        
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.icon != after.icon:
            changes.append("**Icon:** Changed")
        if before.banner != after.banner:
            changes.append("**Banner:** Changed")
        if before.description != after.description:
            changes.append("**Description:** Changed")
        if before.afk_channel != after.afk_channel:
            changes.append(f"**AFK Channel:** Changed")
        if before.afk_timeout != after.afk_timeout:
            changes.append(f"**AFK Timeout:** `{before.afk_timeout}` → `{after.afk_timeout}`")
        if before.verification_level != after.verification_level:
            changes.append(f"**Verification:** `{before.verification_level}` → `{after.verification_level}`")
        
        if not changes:
            return
        
        embed = self.make_embed("⚙️ Server Updated", self.COLORS['guild_update'])
        embed.add_field(name="Changes", value="\n".join(changes[:10]), inline=False)
        
        entry = await self.get_audit_entry(after, discord.AuditLogAction.guild_update)
        if entry:
            embed.add_field(name="Updated By", value=self.format_user(entry.user), inline=True)
        
        embed.set_footer(text=f"Server ID: {after.id}")
        await self.send_log(after, 'guild_update', embed)
    
    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        added = [e for e in after if e not in before]
        removed = [e for e in before if e not in after]
        
        if added:
            embed = self.make_embed("😀 Emoji Added", self.COLORS['emoji_update'])
            for emoji in added[:5]:
                embed.add_field(name=emoji.name, value=str(emoji), inline=True)
            entry = await self.get_audit_entry(guild, discord.AuditLogAction.emoji_create)
            if entry:
                embed.add_field(name="Added By", value=self.format_user(entry.user), inline=True)
            await self.send_log(guild, 'emoji_update', embed)
        
        if removed:
            embed = self.make_embed("😢 Emoji Removed", self.COLORS['emoji_update'])
            embed.add_field(name="Removed", value=", ".join(f"`{e.name}`" for e in removed[:10]), inline=False)
            entry = await self.get_audit_entry(guild, discord.AuditLogAction.emoji_delete)
            if entry:
                embed.add_field(name="Removed By", value=self.format_user(entry.user), inline=True)
            await self.send_log(guild, 'emoji_update', embed)
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        embed = self.make_embed("🔗 Invite Created", self.COLORS['invite_create'])
        embed.add_field(name="Code", value=f"`{invite.code}`", inline=True)
        embed.add_field(name="Channel", value=invite.channel.mention if invite.channel else "Unknown", inline=True)
        embed.add_field(name="Created By", value=self.format_user(invite.inviter) if invite.inviter else "Unknown", inline=True)
        
        if invite.max_uses:
            embed.add_field(name="Max Uses", value=str(invite.max_uses), inline=True)
        if invite.max_age:
            embed.add_field(name="Expires", value=f"<t:{int((datetime.utcnow() + timedelta(seconds=invite.max_age)).timestamp())}:R>", inline=True)
        
        embed.set_footer(text=f"Invite: {invite.code}")
        await self.send_log(invite.guild, 'invite_create', embed)
    
    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        embed = self.make_embed("🗑️ Invite Deleted", self.COLORS['invite_delete'])
        embed.add_field(name="Code", value=f"`{invite.code}`", inline=True)
        embed.add_field(name="Channel", value=invite.channel.mention if invite.channel else "Unknown", inline=True)
        
        entry = await self.get_audit_entry(invite.guild, discord.AuditLogAction.invite_delete)
        if entry:
            embed.add_field(name="Deleted By", value=self.format_user(entry.user), inline=True)
        
        embed.set_footer(text=f"Invite: {invite.code}")
        await self.send_log(invite.guild, 'invite_delete', embed)
    
    # ==================== MODERATION LOG METHODS ====================
    
    async def log_warn(self, guild, user, moderator, reason: str, case_num: int, total: int = 1):
        if not self.is_log_type_enabled(guild.id, 'mod_warn'):
            return
        embed = self.make_embed("⚠️ Warning Issued", self.COLORS['mod_warn'])
        embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
        embed.add_field(name="User", value=self.format_user(user), inline=True)
        embed.add_field(name="Moderator", value=self.format_user(moderator), inline=True)
        embed.add_field(name="Case", value=f"`#{case_num}`", inline=True)
        embed.add_field(name="Warnings", value=f"`{total}`", inline=True)
        embed.add_field(name="Reason", value=f"```\n{reason[:500] if reason else 'No reason'}\n```", inline=False)
        embed.set_footer(text=f"Case #{case_num} • User: {user.id}")
        await self.send_log(guild, 'mod_warn', embed)
    
    async def log_ban(self, guild, user, moderator, reason: str, case_num: int, duration: str = None):
        if not self.is_log_type_enabled(guild.id, 'mod_ban'):
            return
        embed = self.make_embed("🔨 User Banned", self.COLORS['mod_ban'])
        embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
        embed.add_field(name="User", value=self.format_user(user), inline=True)
        embed.add_field(name="Moderator", value=self.format_user(moderator), inline=True)
        embed.add_field(name="Case", value=f"`#{case_num}`", inline=True)
        embed.add_field(name="Duration", value=f"`{duration or 'Permanent'}`", inline=True)
        embed.add_field(name="Reason", value=f"```\n{reason[:500] if reason else 'No reason'}\n```", inline=False)
        embed.set_footer(text=f"Case #{case_num} • User: {user.id}")
        await self.send_log(guild, 'mod_ban', embed)
    
    async def log_kick(self, guild, user, moderator, reason: str, case_num: int):
        if not self.is_log_type_enabled(guild.id, 'mod_kick'):
            return
        embed = self.make_embed("👢 User Kicked", self.COLORS['mod_kick'])
        embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
        embed.add_field(name="User", value=self.format_user(user), inline=True)
        embed.add_field(name="Moderator", value=self.format_user(moderator), inline=True)
        embed.add_field(name="Case", value=f"`#{case_num}`", inline=True)
        embed.add_field(name="Reason", value=f"```\n{reason[:500] if reason else 'No reason'}\n```", inline=False)
        embed.set_footer(text=f"Case #{case_num} • User: {user.id}")
        await self.send_log(guild, 'mod_kick', embed)
    
    async def log_mute(self, guild, user, moderator, reason: str, case_num: int, duration: str = None):
        if not self.is_log_type_enabled(guild.id, 'mod_mute'):
            return
        embed = self.make_embed("🔇 User Muted", self.COLORS['mod_mute'])
        embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
        embed.add_field(name="User", value=self.format_user(user), inline=True)
        embed.add_field(name="Moderator", value=self.format_user(moderator), inline=True)
        embed.add_field(name="Case", value=f"`#{case_num}`", inline=True)
        if duration:
            embed.add_field(name="Duration", value=f"`{duration}`", inline=True)
        embed.add_field(name="Reason", value=f"```\n{reason[:500] if reason else 'No reason'}\n```", inline=False)
        embed.set_footer(text=f"Case #{case_num} • User: {user.id}")
        await self.send_log(guild, 'mod_mute', embed)
    
    async def log_unban(self, guild, user, moderator, reason: str, case_num: int):
        if not self.is_log_type_enabled(guild.id, 'mod_unban'):
            return
        embed = self.make_embed("🔓 User Unbanned", self.COLORS['mod_unban'])
        embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
        embed.add_field(name="User", value=self.format_user(user), inline=True)
        embed.add_field(name="Moderator", value=self.format_user(moderator), inline=True)
        embed.add_field(name="Case", value=f"`#{case_num}`", inline=True)
        embed.add_field(name="Reason", value=f"```\n{reason[:500] if reason else 'No reason'}\n```", inline=False)
        embed.set_footer(text=f"Case #{case_num} • User: {user.id}")
        await self.send_log(guild, 'mod_unban', embed)
    
    async def log_unwarn(self, guild, user, moderator, case_num: int, original_case: int):
        if not self.is_log_type_enabled(guild.id, 'mod_unwarn'):
            return
        embed = self.make_embed("📝 Warning Cleared", self.COLORS['mod_unwarn'])
        embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
        embed.add_field(name="User", value=self.format_user(user), inline=True)
        embed.add_field(name="Moderator", value=self.format_user(moderator), inline=True)
        embed.add_field(name="Original Case", value=f"`#{original_case}`", inline=True)
        embed.set_footer(text=f"User: {user.id}")
        await self.send_log(guild, 'mod_unwarn', embed)
    
    async def log_purge(self, ctx, count: int, target_user, filter_type: str, messages: List):
        if not self.is_log_type_enabled(ctx.guild.id, 'mod_purge'):
            return
        
        case_num = self.create_case(ctx.guild.id, 'purge', target_user.id if target_user else 0,
                                     str(target_user) if target_user else "All", ctx.author.id, str(ctx.author),
                                     f"Purged {count} messages", {'filter': filter_type})
        
        embed = self.make_embed("🗑️ Messages Purged", self.COLORS['mod_purge'])
        embed.add_field(name="Moderator", value=self.format_user(ctx.author), inline=True)
        embed.add_field(name="Channel", value=ctx.channel.mention, inline=True)
        embed.add_field(name="Count", value=f"`{count}`", inline=True)
        embed.add_field(name="Filter", value=f"`{filter_type}`", inline=True)
        if target_user:
            embed.add_field(name="Target", value=self.format_user(target_user), inline=True)
        
        # Create log file
        if messages:
            log = f"Purge Log - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            for msg in sorted(messages, key=lambda m: m.created_at):
                log += f"[{msg.created_at.strftime('%H:%M:%S')}] {msg.author}: {msg.content or '[no content]'}\n"
            
            import io
            file = discord.File(io.BytesIO(log.encode()), filename=f"purge_{case_num}.txt")
            embed.set_footer(text=f"Case #{case_num}")
            await self.send_log(ctx.guild, 'mod_purge', embed, file)
        else:
            embed.set_footer(text=f"Case #{case_num}")
            await self.send_log(ctx.guild, 'mod_purge', embed)
    
    # ==================== BFOS LOG METHODS ====================
    
    async def log_bfos_action(self, guild, action_type: str, user, description: str, details: dict = None):
        log_type = f"bfos_{action_type}"
        if not self.is_log_type_enabled(guild.id, log_type):
            return
        
        embed = self.make_embed(f"🤖 BFOS: {action_type.title()}", self.COLORS.get(log_type, 0x00AAFF), description)
        embed.set_author(name=str(user), icon_url=user.display_avatar.url if user.display_avatar else None)
        embed.add_field(name="Executed By", value=self.format_user(user), inline=True)
        
        if details:
            for k, v in list(details.items())[:5]:
                embed.add_field(name=k, value=f"`{str(v)[:100]}`", inline=True)
        
        embed.set_footer(text=f"BFOS • User: {user.id}")
        await self.send_log(guild, log_type, embed)


async def setup(bot):
    await bot.add_cog(LoggingModule(bot))
