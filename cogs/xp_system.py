"""
BlockForge OS - XP & Leveling System v2.2.0
Tracks XP from messages and voice, manages levels, role rewards, and leaderboards
"""

import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio
import json
import math
import time
import io
from typing import Optional, List, Dict
from utils.database import Database
from utils.config import Config

try:
    from utils.card_generator import generate_stats_card, generate_leaderboard_image
    CARDS_AVAILABLE = True
except ImportError:
    CARDS_AVAILABLE = False


class XPSystem(commands.Cog):
    """XP & Leveling system"""

    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self._init_tables()
        self._cooldowns = {}  # {(guild_id, user_id): last_xp_time}
        self._voice_tracking = {}  # {(guild_id, user_id): join_timestamp}
        self.voice_xp_task.start()
        self.reset_task.start()

    def cog_unload(self):
        self.voice_xp_task.cancel()
        self.reset_task.cancel()

    def _init_tables(self):
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute('''CREATE TABLE IF NOT EXISTS xp_config (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 1,
            xp_per_message INTEGER DEFAULT 15,
            xp_per_image INTEGER DEFAULT 20,
            xp_per_link INTEGER DEFAULT 10,
            xp_per_voice_minute INTEGER DEFAULT 5,
            spam_cooldown_seconds INTEGER DEFAULT 60,
            level_curve TEXT DEFAULT 'scaled',
            level_role_mode TEXT DEFAULT 'stack',
            levelup_channel_id INTEGER,
            levelup_message TEXT DEFAULT '{user} reached **Level {level}**!',
            voice_require_unmuted INTEGER DEFAULT 1,
            voice_require_undeafened INTEGER DEFAULT 1,
            voice_require_not_alone INTEGER DEFAULT 1,
            voice_exclude_afk INTEGER DEFAULT 1,
            leaderboard_periods TEXT DEFAULT '["all_time","weekly","monthly"]'
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS xp_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            total_xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            messages_sent INTEGER DEFAULT 0,
            voice_minutes INTEGER DEFAULT 0,
            weekly_xp INTEGER DEFAULT 0,
            monthly_xp INTEGER DEFAULT 0,
            weekly_reset_at TIMESTAMP,
            monthly_reset_at TIMESTAMP,
            last_message_xp_at REAL DEFAULT 0,
            UNIQUE(guild_id, user_id)
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS xp_level_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            level INTEGER,
            role_id INTEGER,
            UNIQUE(guild_id, level)
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS xp_multipliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            type TEXT,
            target_id INTEGER,
            multiplier REAL DEFAULT 1.0,
            expires_at TIMESTAMP
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS xp_excluded (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            type TEXT,
            target_id INTEGER,
            UNIQUE(guild_id, type, target_id)
        )''')

        conn.commit()
        conn.close()

    # ==================== DB HELPERS ====================

    def get_xp_config(self, guild_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM xp_config WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'guild_id': row[0], 'enabled': bool(row[1]),
            'xp_per_message': row[2], 'xp_per_image': row[3], 'xp_per_link': row[4],
            'xp_per_voice_minute': row[5], 'spam_cooldown_seconds': row[6],
            'level_curve': row[7], 'level_role_mode': row[8],
            'levelup_channel_id': row[9], 'levelup_message': row[10],
            'voice_require_unmuted': bool(row[11]), 'voice_require_undeafened': bool(row[12]),
            'voice_require_not_alone': bool(row[13]), 'voice_exclude_afk': bool(row[14]),
            'leaderboard_periods': json.loads(row[15]) if row[15] else ['all_time']
        }

    def set_xp_config(self, guild_id, **kwargs):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO xp_config (guild_id) VALUES (?)', (guild_id,))
        for key, value in kwargs.items():
            if key == 'leaderboard_periods':
                value = json.dumps(value)
            cursor.execute(f'UPDATE xp_config SET {key} = ? WHERE guild_id = ?', (value, guild_id))
        conn.commit()
        conn.close()

    def get_xp_user(self, guild_id, user_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM xp_users WHERE guild_id = ? AND user_id = ?', (guild_id, user_id))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'id': row[0], 'guild_id': row[1], 'user_id': row[2],
            'total_xp': row[3], 'level': row[4], 'messages_sent': row[5],
            'voice_minutes': row[6], 'weekly_xp': row[7], 'monthly_xp': row[8],
            'weekly_reset_at': row[9], 'monthly_reset_at': row[10],
            'last_message_xp_at': row[11] or 0,
        }

    def _ensure_xp_user(self, guild_id, user_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO xp_users (guild_id, user_id) VALUES (?, ?)', (guild_id, user_id))
        conn.commit()
        conn.close()

    def add_xp(self, guild_id, user_id, amount):
        self._ensure_xp_user(guild_id, user_id)
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE xp_users SET total_xp = total_xp + ?, weekly_xp = weekly_xp + ?, monthly_xp = monthly_xp + ? WHERE guild_id = ? AND user_id = ?',
            (amount, amount, amount, guild_id, user_id)
        )
        conn.commit()
        conn.close()

    def set_xp(self, guild_id, user_id, amount):
        self._ensure_xp_user(guild_id, user_id)
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE xp_users SET total_xp = ? WHERE guild_id = ? AND user_id = ?',
                       (amount, guild_id, user_id))
        conn.commit()
        conn.close()

    def remove_xp(self, guild_id, user_id, amount):
        self._ensure_xp_user(guild_id, user_id)
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE xp_users SET total_xp = MAX(0, total_xp - ?) WHERE guild_id = ? AND user_id = ?',
            (amount, guild_id, user_id)
        )
        conn.commit()
        conn.close()

    def increment_messages(self, guild_id, user_id):
        self._ensure_xp_user(guild_id, user_id)
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE xp_users SET messages_sent = messages_sent + 1 WHERE guild_id = ? AND user_id = ?',
                       (guild_id, user_id))
        conn.commit()
        conn.close()

    def add_voice_minutes(self, guild_id, user_id, minutes):
        self._ensure_xp_user(guild_id, user_id)
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE xp_users SET voice_minutes = voice_minutes + ? WHERE guild_id = ? AND user_id = ?',
                       (minutes, guild_id, user_id))
        conn.commit()
        conn.close()

    def set_last_message_xp(self, guild_id, user_id, timestamp):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE xp_users SET last_message_xp_at = ? WHERE guild_id = ? AND user_id = ?',
                       (timestamp, guild_id, user_id))
        conn.commit()
        conn.close()

    def update_user_level(self, guild_id, user_id, level):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE xp_users SET level = ? WHERE guild_id = ? AND user_id = ?',
                       (level, guild_id, user_id))
        conn.commit()
        conn.close()

    def get_user_rank(self, guild_id, user_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) + 1 FROM xp_users WHERE guild_id = ? AND total_xp > (SELECT COALESCE(total_xp, 0) FROM xp_users WHERE guild_id = ? AND user_id = ?)',
            (guild_id, guild_id, user_id)
        )
        rank = cursor.fetchone()[0]
        conn.close()
        return rank

    def get_leaderboard(self, guild_id, period='all_time', limit=10):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        xp_col = {'weekly': 'weekly_xp', 'monthly': 'monthly_xp'}.get(period, 'total_xp')
        cursor.execute(
            f'SELECT user_id, {xp_col}, level, messages_sent, voice_minutes FROM xp_users WHERE guild_id = ? AND {xp_col} > 0 ORDER BY {xp_col} DESC LIMIT ?',
            (guild_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [{'user_id': r[0], 'xp': r[1], 'level': r[2], 'messages': r[3], 'voice': r[4]} for r in rows]

    def get_xp_level_roles(self, guild_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT level, role_id FROM xp_level_roles WHERE guild_id = ? ORDER BY level', (guild_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{'level': r[0], 'role_id': r[1]} for r in rows]

    def set_xp_level_role(self, guild_id, level, role_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO xp_level_roles (guild_id, level, role_id) VALUES (?, ?, ?)',
                       (guild_id, level, role_id))
        conn.commit()
        conn.close()

    def remove_xp_level_role(self, guild_id, level):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM xp_level_roles WHERE guild_id = ? AND level = ?', (guild_id, level))
        conn.commit()
        conn.close()

    def get_xp_multipliers(self, guild_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, type, target_id, multiplier, expires_at FROM xp_multipliers WHERE guild_id = ?', (guild_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{'id': r[0], 'type': r[1], 'target_id': r[2], 'multiplier': r[3], 'expires_at': r[4]} for r in rows]

    def add_xp_multiplier(self, guild_id, mult_type, target_id, multiplier, expires_at=None):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO xp_multipliers (guild_id, type, target_id, multiplier, expires_at) VALUES (?, ?, ?, ?, ?)',
            (guild_id, mult_type, target_id, multiplier, expires_at)
        )
        mult_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return mult_id

    def remove_xp_multiplier(self, mult_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM xp_multipliers WHERE id = ?', (mult_id,))
        conn.commit()
        conn.close()

    def get_user_multiplier(self, guild_id, user: discord.Member, channel_id: int):
        """Calculate effective XP multiplier for a user in a channel."""
        multipliers = self.get_xp_multipliers(guild_id)
        now = datetime.utcnow().isoformat()
        total = 1.0

        for m in multipliers:
            # Check expiry
            if m['expires_at'] and m['expires_at'] < now:
                continue
            if m['type'] == 'global':
                total *= m['multiplier']
            elif m['type'] == 'channel' and m['target_id'] == channel_id:
                total *= m['multiplier']
            elif m['type'] == 'role':
                for role in user.roles:
                    if role.id == m['target_id']:
                        total *= m['multiplier']
                        break
        return total

    def add_xp_exclusion(self, guild_id, exc_type, target_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO xp_excluded (guild_id, type, target_id) VALUES (?, ?, ?)',
                       (guild_id, exc_type, target_id))
        conn.commit()
        conn.close()

    def remove_xp_exclusion(self, guild_id, exc_type, target_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM xp_excluded WHERE guild_id = ? AND type = ? AND target_id = ?',
                       (guild_id, exc_type, target_id))
        conn.commit()
        conn.close()

    def is_xp_excluded(self, guild_id, user: discord.Member, channel_id: int):
        """Check if user/channel/role is excluded from XP."""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Channel exclusion
        cursor.execute('SELECT 1 FROM xp_excluded WHERE guild_id = ? AND type = ? AND target_id = ?',
                       (guild_id, 'channel', channel_id))
        if cursor.fetchone():
            conn.close()
            return True

        # User exclusion
        cursor.execute('SELECT 1 FROM xp_excluded WHERE guild_id = ? AND type = ? AND target_id = ?',
                       (guild_id, 'user', user.id))
        if cursor.fetchone():
            conn.close()
            return True

        # Role exclusion
        for role in user.roles:
            cursor.execute('SELECT 1 FROM xp_excluded WHERE guild_id = ? AND type = ? AND target_id = ?',
                           (guild_id, 'role', role.id))
            if cursor.fetchone():
                conn.close()
                return True

        conn.close()
        return False

    def reset_weekly_xp(self, guild_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE xp_users SET weekly_xp = 0, weekly_reset_at = ? WHERE guild_id = ?',
                       (datetime.utcnow().isoformat(), guild_id))
        conn.commit()
        conn.close()

    def reset_monthly_xp(self, guild_id):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE xp_users SET monthly_xp = 0, monthly_reset_at = ? WHERE guild_id = ?',
                       (datetime.utcnow().isoformat(), guild_id))
        conn.commit()
        conn.close()

    # ==================== LEVEL CALCULATION ====================

    def xp_for_level(self, level: int, curve: str = 'scaled') -> int:
        """Total XP required to reach a given level."""
        if curve == 'linear':
            return level * 100
        elif curve == 'exponential':
            return 50 * level * level
        else:  # scaled (MEE6-like)
            total = 0
            for lvl in range(1, level + 1):
                total += 5 * (lvl ** 2) + 50 * lvl + 100
            return total

    def level_from_xp(self, total_xp: int, curve: str = 'scaled') -> int:
        """Calculate level from total XP."""
        level = 0
        while self.xp_for_level(level + 1, curve) <= total_xp:
            level += 1
        return level

    # ==================== XP AWARD FLOW ====================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        # Check module
        if not self.db.get_module_state(guild_id, 'xp'):
            return

        config = self.get_xp_config(guild_id)
        if not config or not config.get('enabled'):
            return

        # Check exclusions
        if self.is_xp_excluded(guild_id, message.author, message.channel.id):
            return

        # Spam cooldown
        cooldown_key = (guild_id, user_id)
        now = time.time()
        last_xp = self._cooldowns.get(cooldown_key, 0)
        if now - last_xp < config.get('spam_cooldown_seconds', 60):
            # Still count message but don't award XP
            self.increment_messages(guild_id, user_id)
            return

        # Calculate base XP
        base_xp = config.get('xp_per_message', 15)

        # Check for images
        if message.attachments:
            for att in message.attachments:
                if att.content_type and att.content_type.startswith('image/'):
                    base_xp = max(base_xp, config.get('xp_per_image', 20))
                    break

        # Check for links
        if 'http://' in message.content or 'https://' in message.content:
            base_xp = max(base_xp, config.get('xp_per_link', 10))

        # Apply multiplier
        multiplier = self.get_user_multiplier(guild_id, message.author, message.channel.id)
        final_xp = int(base_xp * multiplier)

        # Award XP
        self.add_xp(guild_id, user_id, final_xp)
        self.increment_messages(guild_id, user_id)
        self._cooldowns[cooldown_key] = now

        # Check level up
        user_data = self.get_xp_user(guild_id, user_id)
        if user_data:
            curve = config.get('level_curve', 'scaled')
            new_level = self.level_from_xp(user_data['total_xp'], curve)
            if new_level > user_data['level']:
                self.update_user_level(guild_id, user_id, new_level)
                await self._handle_level_up(message.guild, message.author, new_level, config, message.channel)

    async def _handle_level_up(self, guild, member, new_level, config, source_channel):
        """Handle level up: assign roles, send announcement."""
        # Role rewards
        level_roles = self.get_xp_level_roles(guild.id)
        role_mode = config.get('level_role_mode', 'stack')

        roles_to_add = []
        roles_to_remove = []

        for lr in level_roles:
            role = guild.get_role(lr['role_id'])
            if not role:
                continue

            if lr['level'] <= new_level:
                if role not in member.roles:
                    roles_to_add.append(role)
            elif role_mode == 'replace' and role in member.roles:
                roles_to_remove.append(role)

        try:
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason=f"XP Level {new_level}")
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason=f"XP role replacement (Level {new_level})")
        except discord.Forbidden:
            pass

        # Level up announcement
        levelup_msg = config.get('levelup_message', '{user} reached **Level {level}**!')
        text = levelup_msg.replace('{user}', member.mention).replace('{level}', str(new_level))

        channel = None
        if config.get('levelup_channel_id'):
            channel = guild.get_channel(config['levelup_channel_id'])
        if not channel:
            channel = source_channel

        try:
            embed = discord.Embed(
                title="\u2b50 Level Up!",
                description=text,
                color=0xF1C40F,
                timestamp=datetime.utcnow()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)
        except:
            pass

    # ==================== VOICE TRACKING ====================

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild_id = member.guild.id
        key = (guild_id, member.id)

        if not before.channel and after.channel:
            # Joined VC
            self._voice_tracking[key] = time.time()
        elif before.channel and not after.channel:
            # Left VC
            if key in self._voice_tracking:
                del self._voice_tracking[key]

    @tasks.loop(minutes=5)
    async def voice_xp_task(self):
        """Award voice XP to tracked users every 5 minutes."""
        for key, join_time in list(self._voice_tracking.items()):
            guild_id, user_id = key

            if not self.db.get_module_state(guild_id, 'xp'):
                continue

            config = self.get_xp_config(guild_id)
            if not config or not config.get('enabled'):
                continue

            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            member = guild.get_member(user_id)
            if not member or not member.voice:
                self._voice_tracking.pop(key, None)
                continue

            vc = member.voice

            # Check conditions
            if config.get('voice_require_unmuted') and vc.self_mute:
                continue
            if config.get('voice_require_undeafened') and vc.self_deaf:
                continue
            if config.get('voice_exclude_afk') and vc.channel == guild.afk_channel:
                continue
            if config.get('voice_require_not_alone'):
                real_members = [m for m in vc.channel.members if not m.bot]
                if len(real_members) < 2:
                    continue

            # Check exclusions
            if self.is_xp_excluded(guild_id, member, vc.channel.id):
                continue

            # Award 5 minutes of voice XP
            xp_per_min = config.get('xp_per_voice_minute', 5)
            multiplier = self.get_user_multiplier(guild_id, member, vc.channel.id)
            xp = int(xp_per_min * 5 * multiplier)

            self.add_xp(guild_id, user_id, xp)
            self.add_voice_minutes(guild_id, user_id, 5)

            # Check level up
            user_data = self.get_xp_user(guild_id, user_id)
            if user_data:
                curve = config.get('level_curve', 'scaled')
                new_level = self.level_from_xp(user_data['total_xp'], curve)
                if new_level > user_data['level']:
                    self.update_user_level(guild_id, user_id, new_level)
                    # Find a text channel for announcement
                    channel = guild.system_channel or (guild.text_channels[0] if guild.text_channels else None)
                    if config.get('levelup_channel_id'):
                        channel = guild.get_channel(config['levelup_channel_id']) or channel
                    if channel:
                        await self._handle_level_up(guild, member, new_level, config, channel)

    @voice_xp_task.before_loop
    async def before_voice_xp(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def reset_task(self):
        """Check and reset weekly/monthly XP counters."""
        now = datetime.utcnow()

        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT guild_id FROM xp_config')
        guild_ids = [r[0] for r in cursor.fetchall()]
        conn.close()

        for guild_id in guild_ids:
            config = self.get_xp_config(guild_id)
            if not config:
                continue

            # Check weekly reset (Monday)
            conn = self.db._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT weekly_reset_at FROM xp_users WHERE guild_id = ? LIMIT 1', (guild_id,))
            row = cursor.fetchone()
            conn.close()

            if row and row[0]:
                try:
                    last_reset = datetime.fromisoformat(row[0])
                    if (now - last_reset).days >= 7:
                        self.reset_weekly_xp(guild_id)
                except:
                    pass
            else:
                self.reset_weekly_xp(guild_id)

            # Check monthly reset
            conn = self.db._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT monthly_reset_at FROM xp_users WHERE guild_id = ? LIMIT 1', (guild_id,))
            row = cursor.fetchone()
            conn.close()

            if row and row[0]:
                try:
                    last_reset = datetime.fromisoformat(row[0])
                    if last_reset.month != now.month or last_reset.year != now.year:
                        self.reset_monthly_xp(guild_id)
                except:
                    pass
            else:
                self.reset_monthly_xp(guild_id)

    @reset_task.before_loop
    async def before_reset(self):
        await self.bot.wait_until_ready()

    # ==================== COMMANDS ====================

    @commands.command(name='stats', aliases=['rank', 'level'])
    async def stats_command(self, ctx, user: discord.Member = None):
        """Show XP stats card for a user"""
        if not self.db.get_module_state(ctx.guild.id, 'xp'):
            return

        target = user or ctx.author
        config = self.get_xp_config(ctx.guild.id)
        if not config:
            return

        self._ensure_xp_user(ctx.guild.id, target.id)
        user_data = self.get_xp_user(ctx.guild.id, target.id)
        if not user_data:
            await ctx.send("No XP data found.")
            return

        curve = config.get('level_curve', 'scaled')
        level = user_data['level']
        rank = self.get_user_rank(ctx.guild.id, target.id)
        xp_current = self.xp_for_level(level, curve)
        xp_next = self.xp_for_level(level + 1, curve)

        if not CARDS_AVAILABLE:
            # Fallback to embed
            embed = discord.Embed(
                title=f"{target.display_name}'s Stats",
                color=0x5865F2, timestamp=datetime.utcnow()
            )
            embed.add_field(name="Level", value=str(level), inline=True)
            embed.add_field(name="Rank", value=f"#{rank}", inline=True)
            embed.add_field(name="XP", value=f"{user_data['total_xp']}/{xp_next}", inline=True)
            embed.add_field(name="Messages", value=str(user_data['messages_sent']), inline=True)
            embed.add_field(name="Voice", value=f"{user_data['voice_minutes']}m", inline=True)
            embed.set_thumbnail(url=target.display_avatar.url)
            await ctx.send(embed=embed)
            return

        # Get avatar bytes
        avatar_bytes = await target.display_avatar.with_size(256).read()

        # Try to get accent color and banner
        accent_color = None
        banner_bytes = None
        try:
            fetched = await self.bot.fetch_user(target.id)
            accent_color = fetched.accent_color.value if fetched.accent_color else None
            if fetched.banner:
                banner_bytes = await fetched.banner.with_size(512).read()
        except:
            pass

        joined_at = target.joined_at.replace(tzinfo=None) if target.joined_at else None

        card_bytes = await generate_stats_card(
            username=target.display_name,
            avatar_bytes=avatar_bytes,
            level=level,
            total_xp=user_data['total_xp'],
            xp_for_current=xp_current,
            xp_for_next=xp_next,
            rank=rank,
            messages_sent=user_data['messages_sent'],
            voice_minutes=user_data['voice_minutes'],
            joined_at=joined_at,
            accent_color=accent_color,
            banner_bytes=banner_bytes,
        )

        if card_bytes:
            file = discord.File(io.BytesIO(card_bytes), filename="stats.png")
            await ctx.send(file=file)
        else:
            await ctx.send("Failed to generate stats card.")

    @commands.command(name='leaderboard', aliases=['lb', 'top'])
    async def leaderboard_command(self, ctx, period: str = 'all_time'):
        """Show the XP leaderboard"""
        if not self.db.get_module_state(ctx.guild.id, 'xp'):
            return

        if period not in ('all_time', 'weekly', 'monthly'):
            period = 'all_time'

        entries = self.get_leaderboard(ctx.guild.id, period, 10)
        if not entries:
            await ctx.send("No leaderboard data yet. Start chatting to earn XP!")
            return

        if not CARDS_AVAILABLE:
            # Fallback to embed
            desc = ""
            for i, entry in enumerate(entries):
                rank = i + 1
                member = ctx.guild.get_member(entry['user_id'])
                name = member.display_name if member else f"User {entry['user_id']}"
                medal = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}.get(rank, f"**{rank}.**")
                desc += f"{medal} {name} — Level {entry['level']} | {entry['xp']:,} XP\n"

            period_label = {"weekly": "Weekly", "monthly": "Monthly"}.get(period, "All Time")
            embed = discord.Embed(
                title=f"Leaderboard — {period_label}",
                description=desc,
                color=0xF1C40F, timestamp=datetime.utcnow()
            )
            await ctx.send(embed=embed)
            return

        # Get avatar data for top users
        avatar_data = {}
        for entry in entries:
            member = ctx.guild.get_member(entry['user_id'])
            if member:
                entry['username'] = member.display_name
                try:
                    avatar_data[entry['user_id']] = await member.display_avatar.with_size(64).read()
                except:
                    avatar_data[entry['user_id']] = None
            else:
                entry['username'] = f"User {entry['user_id']}"

        lb_bytes = await generate_leaderboard_image(
            guild_name=ctx.guild.name,
            period=period,
            entries=entries,
            avatar_data=avatar_data,
        )

        if lb_bytes:
            file = discord.File(io.BytesIO(lb_bytes), filename="leaderboard.png")
            await ctx.send(file=file)
        else:
            await ctx.send("Failed to generate leaderboard image.")

    @commands.command(name='xp')
    async def xp_admin_command(self, ctx, action: str = None, user: discord.Member = None, amount: int = None):
        """Admin XP management: ;xp add/remove/set @user amount"""
        if not self.db.get_module_state(ctx.guild.id, 'xp'):
            return

        # Permission check
        from cogs.moderation import has_bfos_permission
        # Manual check instead of decorator
        db = Database()
        has_perm = (ctx.author.id == Config.BOT_OWNER_ID or
                    ctx.author.id == ctx.guild.owner_id or
                    ctx.author.guild_permissions.administrator or
                    db.has_permission(ctx.guild.id, ctx.author.id, 'xp_admin'))
        if not has_perm:
            for role in ctx.author.roles:
                if db.role_has_permission(ctx.guild.id, role.id, 'xp_admin'):
                    has_perm = True
                    break
        if not has_perm:
            return

        if not action or not user or amount is None:
            await ctx.send("Usage: `;xp add/remove/set @user <amount>`")
            return

        action = action.lower()
        config = self.get_xp_config(ctx.guild.id)
        curve = config.get('level_curve', 'scaled') if config else 'scaled'

        if action == 'add':
            self.add_xp(ctx.guild.id, user.id, amount)
            # Recalculate level
            user_data = self.get_xp_user(ctx.guild.id, user.id)
            new_level = self.level_from_xp(user_data['total_xp'], curve)
            self.update_user_level(ctx.guild.id, user.id, new_level)
            await ctx.send(f"\u2705 Added **{amount}** XP to {user.mention}. Total: **{user_data['total_xp']}** XP (Level {new_level})")
        elif action == 'remove':
            self.remove_xp(ctx.guild.id, user.id, amount)
            user_data = self.get_xp_user(ctx.guild.id, user.id)
            new_level = self.level_from_xp(user_data['total_xp'], curve)
            self.update_user_level(ctx.guild.id, user.id, new_level)
            await ctx.send(f"\u2705 Removed **{amount}** XP from {user.mention}. Total: **{user_data['total_xp']}** XP (Level {new_level})")
        elif action == 'set':
            self.set_xp(ctx.guild.id, user.id, amount)
            new_level = self.level_from_xp(amount, curve)
            self.update_user_level(ctx.guild.id, user.id, new_level)
            await ctx.send(f"\u2705 Set {user.mention}'s XP to **{amount}** (Level {new_level})")
        else:
            await ctx.send("Invalid action. Use: `add`, `remove`, or `set`")


async def setup(bot):
    await bot.add_cog(XPSystem(bot))
