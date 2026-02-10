"""
BlockForge OS Comprehensive Backup System
Full server backup with rate limit handling and file storage
"""

import discord
import json
import asyncio
import aiohttp
import os
import base64
import hashlib
from datetime import datetime
from typing import Optional, Callable, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class RateLimitBucket:
    """Track rate limits for different API endpoints"""
    
    def __init__(self):
        self.buckets: Dict[str, dict] = {}
        self.global_limit = False
        self.global_reset = 0
    
    async def wait_if_needed(self, bucket: str = "default"):
        """Wait if we're rate limited"""
        now = datetime.utcnow().timestamp()
        
        # Check global rate limit
        if self.global_limit and now < self.global_reset:
            wait_time = self.global_reset - now
            print(f"[BACKUP] Global rate limit, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time + 0.5)
        
        # Check bucket rate limit
        if bucket in self.buckets:
            bucket_data = self.buckets[bucket]
            if bucket_data.get('remaining', 1) <= 0:
                reset_time = bucket_data.get('reset', 0)
                if now < reset_time:
                    wait_time = reset_time - now
                    print(f"[BACKUP] Bucket '{bucket}' rate limited, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time + 0.5)
    
    def update_from_headers(self, headers: dict, bucket: str = "default"):
        """Update rate limit info from response headers"""
        if 'X-RateLimit-Remaining' in headers:
            self.buckets[bucket] = {
                'remaining': int(headers.get('X-RateLimit-Remaining', 1)),
                'limit': int(headers.get('X-RateLimit-Limit', 1)),
                'reset': float(headers.get('X-RateLimit-Reset', 0))
            }
        
        if headers.get('X-RateLimit-Global'):
            self.global_limit = True
            self.global_reset = float(headers.get('X-RateLimit-Reset-After', 5)) + datetime.utcnow().timestamp()


class BackupAPI:
    """
    Custom API wrapper for backup operations with built-in rate limiting.
    Queues requests and handles delays automatically.
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.rate_limiter = RateLimitBucket()
        self.request_queue: asyncio.Queue = asyncio.Queue()
        self.is_processing = False
        
        # Delays between different operation types (in seconds)
        self.delays = {
            'channel_create': 1.0,
            'channel_edit': 0.5,
            'role_create': 1.0,
            'role_edit': 0.5,
            'permission_edit': 0.3,
            'emoji_create': 2.0,
            'sticker_create': 2.0,
            'file_download': 0.2,
            'default': 0.5
        }
    
    async def execute_with_delay(self, operation_type: str, coro):
        """Execute a coroutine with appropriate delay and rate limit handling"""
        await self.rate_limiter.wait_if_needed(operation_type)
        
        try:
            result = await asyncio.wait_for(coro, timeout=30.0)  # 30 second timeout
            # Add delay after operation
            delay = self.delays.get(operation_type, self.delays['default'])
            await asyncio.sleep(delay)
            return result, None
        except asyncio.TimeoutError:
            print(f"[BACKUP] Operation {operation_type} timed out after 30s")
            return None, "Operation timed out"
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                retry_after = e.retry_after if hasattr(e, 'retry_after') else 5
                print(f"[BACKUP] Rate limited, waiting {retry_after}s")
                await asyncio.sleep(retry_after + 1)
                # Don't retry - just return error, let caller handle
                return None, f"Rate limited (waited {retry_after}s)"
            return None, str(e)
        except Exception as e:
            print(f"[BACKUP] Operation {operation_type} failed: {e}")
            return None, str(e)
    
    async def download_asset(self, url: str, save_path: str) -> Tuple[bool, Optional[str]]:
        """Download an asset (icon, emoji, etc.) with rate limiting"""
        if not url:
            return False, "No URL provided"
        
        await self.rate_limiter.wait_if_needed('file_download')
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        
                        # Ensure directory exists
                        os.makedirs(os.path.dirname(save_path), exist_ok=True)
                        
                        with open(save_path, 'wb') as f:
                            f.write(data)
                        
                        await asyncio.sleep(self.delays['file_download'])
                        return True, None
                    else:
                        return False, f"HTTP {response.status}"
        except Exception as e:
            return False, str(e)


@dataclass
class RoleBackup:
    """Backup data for a single role"""
    id: int
    name: str
    color: int
    permissions: int
    position: int
    mentionable: bool
    hoist: bool  # display_separately
    icon_path: Optional[str] = None
    unicode_emoji: Optional[str] = None


@dataclass
class ChannelPermissionOverwrite:
    """Permission overwrite for a channel"""
    target_id: int
    target_type: str  # 'role' or 'member'
    allow: int
    deny: int


@dataclass
class ChannelBackup:
    """Backup data for a single channel"""
    id: int
    name: str
    type: int  # discord.ChannelType value
    position: int
    category_id: Optional[int]
    topic: Optional[str] = None
    slowmode_delay: int = 0
    nsfw: bool = False
    bitrate: Optional[int] = None
    user_limit: Optional[int] = None
    rtc_region: Optional[str] = None
    default_auto_archive_duration: Optional[int] = None
    overwrites: List[dict] = None
    
    def __post_init__(self):
        if self.overwrites is None:
            self.overwrites = []


@dataclass
class EmojiBackup:
    """Backup data for a custom emoji"""
    id: int
    name: str
    animated: bool
    image_path: Optional[str] = None
    role_ids: List[int] = None
    
    def __post_init__(self):
        if self.role_ids is None:
            self.role_ids = []


@dataclass
class StickerBackup:
    """Backup data for a sticker"""
    id: int
    name: str
    description: str
    format_type: int
    image_path: Optional[str] = None


@dataclass
class SoundboardBackup:
    """Backup data for a soundboard sound"""
    id: int
    name: str
    volume: float
    emoji_name: Optional[str] = None
    emoji_id: Optional[int] = None
    file_path: Optional[str] = None


@dataclass
class ServerBackup:
    """Complete server backup"""
    backup_id: str
    guild_id: int
    guild_name: str
    created_at: str
    
    # Server settings
    icon_path: Optional[str] = None
    banner_path: Optional[str] = None
    splash_path: Optional[str] = None
    description: Optional[str] = None
    verification_level: int = 0
    default_notifications: int = 0
    explicit_content_filter: int = 0
    afk_channel_id: Optional[int] = None
    afk_timeout: int = 300
    system_channel_id: Optional[int] = None
    rules_channel_id: Optional[int] = None
    public_updates_channel_id: Optional[int] = None
    preferred_locale: str = "en-US"
    
    # Data lists
    roles: List[dict] = None
    categories: List[dict] = None
    channels: List[dict] = None
    emojis: List[dict] = None
    stickers: List[dict] = None
    soundboard_sounds: List[dict] = None
    
    # Metadata
    locked: bool = False
    file_size_bytes: int = 0
    
    def __post_init__(self):
        if self.roles is None:
            self.roles = []
        if self.categories is None:
            self.categories = []
        if self.channels is None:
            self.channels = []
        if self.emojis is None:
            self.emojis = []
        if self.stickers is None:
            self.stickers = []
        if self.soundboard_sounds is None:
            self.soundboard_sounds = []


class ComprehensiveBackupSystem:
    """
    Complete backup and restore system for Discord servers.
    Handles all server data including files with rate limit protection.
    """
    
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.api = BackupAPI(bot)
        self.backup_dir = "data/backups"
        
        # Ensure backup directory exists
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def _generate_backup_id(self) -> str:
        """Generate unique backup ID"""
        import uuid
        return uuid.uuid4().hex[:8]
    
    def _get_backup_path(self, backup_id: str) -> str:
        """Get the directory path for a backup"""
        path = os.path.join(self.backup_dir, backup_id)
        os.makedirs(path, exist_ok=True)
        return path
    
    # ==================== BACKUP CREATION ====================
    
    async def create_backup(
        self, 
        guild: discord.Guild, 
        name: str,
        progress_callback: Optional[Callable] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Create a comprehensive backup of the server.
        
        Returns: (success, message, backup_id)
        """
        backup_id = self._generate_backup_id()
        backup_path = self._get_backup_path(backup_id)
        
        try:
            if progress_callback:
                await progress_callback("📦 Starting comprehensive backup...")
            
            backup = ServerBackup(
                backup_id=backup_id,
                guild_id=guild.id,
                guild_name=guild.name,
                created_at=datetime.utcnow().isoformat(),
                description=guild.description,
                verification_level=guild.verification_level.value,
                default_notifications=guild.default_notifications.value,
                explicit_content_filter=guild.explicit_content_filter.value,
                afk_channel_id=guild.afk_channel.id if guild.afk_channel else None,
                afk_timeout=guild.afk_timeout,
                system_channel_id=guild.system_channel.id if guild.system_channel else None,
                rules_channel_id=guild.rules_channel.id if guild.rules_channel else None,
                public_updates_channel_id=guild.public_updates_channel.id if guild.public_updates_channel else None,
                preferred_locale=str(guild.preferred_locale)
            )
            
            # === BACKUP SERVER ASSETS ===
            if progress_callback:
                await progress_callback("🖼️ Downloading server assets...")
            
            # Server icon
            if guild.icon:
                icon_path = os.path.join(backup_path, "server_icon.png")
                success, _ = await self.api.download_asset(str(guild.icon.url), icon_path)
                if success:
                    backup.icon_path = icon_path
            
            # Server banner
            if guild.banner:
                banner_path = os.path.join(backup_path, "server_banner.png")
                success, _ = await self.api.download_asset(str(guild.banner.url), banner_path)
                if success:
                    backup.banner_path = banner_path
            
            # Splash image
            if guild.splash:
                splash_path = os.path.join(backup_path, "server_splash.png")
                success, _ = await self.api.download_asset(str(guild.splash.url), splash_path)
                if success:
                    backup.splash_path = splash_path
            
            # === BACKUP ROLES ===
            if progress_callback:
                await progress_callback(f"👥 Backing up {len(guild.roles)} roles...")
            
            for role in sorted(guild.roles, key=lambda r: r.position):
                if role.is_default():
                    continue  # Skip @everyone
                
                role_data = {
                    'id': role.id,
                    'name': role.name,
                    'color': role.color.value,
                    'permissions': role.permissions.value,
                    'position': role.position,
                    'mentionable': role.mentionable,
                    'hoist': role.hoist,
                    'icon_path': None,
                    'unicode_emoji': role.unicode_emoji
                }
                
                # Download role icon if exists
                if role.icon:
                    icon_path = os.path.join(backup_path, f"role_{role.id}_icon.png")
                    success, _ = await self.api.download_asset(str(role.icon.url), icon_path)
                    if success:
                        role_data['icon_path'] = icon_path
                
                backup.roles.append(role_data)
                await asyncio.sleep(0.1)  # Small delay
            
            # === BACKUP CATEGORIES ===
            if progress_callback:
                await progress_callback("📁 Backing up categories...")
            
            for category in guild.categories:
                cat_data = {
                    'id': category.id,
                    'name': category.name,
                    'position': category.position,
                    'overwrites': self._serialize_overwrites(category.overwrites)
                }
                backup.categories.append(cat_data)
            
            # === BACKUP CHANNELS ===
            if progress_callback:
                await progress_callback(f"📝 Backing up {len(guild.channels)} channels...")
            
            for channel in guild.channels:
                if isinstance(channel, discord.CategoryChannel):
                    continue  # Already backed up
                
                channel_data = {
                    'id': channel.id,
                    'name': channel.name,
                    'type': channel.type.value,
                    'position': channel.position,
                    'category_id': channel.category.id if channel.category else None,
                    'overwrites': self._serialize_overwrites(channel.overwrites)
                }
                
                # Text channel specific
                if isinstance(channel, discord.TextChannel):
                    channel_data['topic'] = channel.topic
                    channel_data['slowmode_delay'] = channel.slowmode_delay
                    channel_data['nsfw'] = channel.nsfw
                    channel_data['default_auto_archive_duration'] = channel.default_auto_archive_duration
                
                # Voice channel specific
                elif isinstance(channel, discord.VoiceChannel):
                    channel_data['bitrate'] = channel.bitrate
                    channel_data['user_limit'] = channel.user_limit
                    channel_data['rtc_region'] = str(channel.rtc_region) if channel.rtc_region else None
                
                # Stage channel specific
                elif isinstance(channel, discord.StageChannel):
                    channel_data['bitrate'] = channel.bitrate
                    channel_data['user_limit'] = channel.user_limit
                    channel_data['rtc_region'] = str(channel.rtc_region) if channel.rtc_region else None
                
                backup.channels.append(channel_data)
            
            # === BACKUP EMOJIS ===
            if progress_callback:
                await progress_callback(f"😀 Backing up {len(guild.emojis)} emojis...")
            
            for emoji in guild.emojis:
                emoji_data = {
                    'id': emoji.id,
                    'name': emoji.name,
                    'animated': emoji.animated,
                    'role_ids': [r.id for r in emoji.roles] if emoji.roles else [],
                    'image_path': None
                }
                
                # Download emoji image
                ext = "gif" if emoji.animated else "png"
                emoji_path = os.path.join(backup_path, f"emoji_{emoji.id}.{ext}")
                success, _ = await self.api.download_asset(str(emoji.url), emoji_path)
                if success:
                    emoji_data['image_path'] = emoji_path
                
                backup.emojis.append(emoji_data)
            
            # === BACKUP STICKERS ===
            if progress_callback:
                await progress_callback(f"🎨 Backing up {len(guild.stickers)} stickers...")
            
            for sticker in guild.stickers:
                sticker_data = {
                    'id': sticker.id,
                    'name': sticker.name,
                    'description': sticker.description,
                    'format_type': sticker.format.value,
                    'image_path': None
                }
                
                # Download sticker image
                sticker_path = os.path.join(backup_path, f"sticker_{sticker.id}.png")
                success, _ = await self.api.download_asset(str(sticker.url), sticker_path)
                if success:
                    sticker_data['image_path'] = sticker_path
                
                backup.stickers.append(sticker_data)
            
            # === BACKUP SOUNDBOARD (if available) ===
            # Note: Soundboard API is limited, may not be fully available
            try:
                if hasattr(guild, 'soundboard_sounds'):
                    if progress_callback:
                        await progress_callback("🔊 Backing up soundboard sounds...")
                    
                    for sound in guild.soundboard_sounds:
                        sound_data = {
                            'id': sound.id,
                            'name': sound.name,
                            'volume': sound.volume,
                            'emoji_name': sound.emoji.name if sound.emoji else None,
                            'emoji_id': sound.emoji.id if sound.emoji and hasattr(sound.emoji, 'id') else None,
                            'file_path': None
                        }
                        # Note: Sound file download may not be available via API
                        backup.soundboard_sounds.append(sound_data)
            except Exception as e:
                print(f"[BACKUP] Soundboard backup skipped: {e}")
            
            # === CALCULATE SIZE AND SAVE ===
            if progress_callback:
                await progress_callback("💾 Saving backup data...")
            
            # Calculate total file size
            total_size = 0
            for root, dirs, files in os.walk(backup_path):
                for file in files:
                    total_size += os.path.getsize(os.path.join(root, file))
            backup.file_size_bytes = total_size
            
            # Save backup data to JSON
            backup_json_path = os.path.join(backup_path, "backup.json")
            with open(backup_json_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(backup), f, indent=2, ensure_ascii=False)
            
            # Save to database
            self.db.save_comprehensive_backup(
                guild.id,
                backup_id,
                name,
                asdict(backup)
            )
            
            if progress_callback:
                await progress_callback(f"✅ Backup complete! ID: {backup_id}")
            
            return True, f"Backup created successfully! ID: {backup_id}", backup_id
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"Backup failed: {str(e)}", None
    
    def _serialize_overwrites(self, overwrites: dict) -> List[dict]:
        """Serialize permission overwrites to a list"""
        result = []
        for target, overwrite in overwrites.items():
            allow, deny = overwrite.pair()
            result.append({
                'target_id': target.id,
                'target_type': 'role' if isinstance(target, discord.Role) else 'member',
                'allow': allow.value,
                'deny': deny.value
            })
        return result
    
    # ==================== BACKUP RESTORATION ====================
    
    async def restore_backup(
        self,
        guild: discord.Guild,
        backup_id: str,
        progress_callback: Optional[Callable] = None,
        exclude_channel_id: Optional[int] = None,
        keep_current_channels: bool = False,
        keep_current_roles: bool = False
    ) -> Tuple[bool, str]:
        """
        Restore a backup to the server.
        
        Args:
            exclude_channel_id: Channel ID to preserve (e.g., terminal channel)
            keep_current_channels: If True, don't delete channels created after backup
            keep_current_roles: If True, don't delete roles created after backup
        """
        # Load backup data
        backup_data = self.db.get_comprehensive_backup(guild.id, backup_id)
        if not backup_data:
            # Try to load from file
            backup_path = self._get_backup_path(backup_id)
            json_path = os.path.join(backup_path, "backup.json")
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
            else:
                return False, "Backup not found"
        
        try:
            # Check bot's role position
            bot_top_role = guild.me.top_role
            if progress_callback:
                await progress_callback(f"🤖 Bot role: {bot_top_role.name} (position {bot_top_role.position})")
            
            if bot_top_role.position < len(guild.roles) - 2:
                if progress_callback:
                    await progress_callback(f"⚠️ Warning: Bot role should be highest for best results!")
            
            # Show flags status
            if progress_callback:
                flags = []
                if keep_current_channels:
                    flags.append("keep-channels")
                if keep_current_roles:
                    flags.append("keep-roles")
                if flags:
                    await progress_callback(f"🚩 Flags: {', '.join(flags)}")
            
            if progress_callback:
                await progress_callback("🔄 Starting restore process...")
            
            # Create mapping from old IDs to new IDs
            role_id_map = {}  # old_id -> new_role
            category_id_map = {}  # old_id -> new_category
            channel_id_map = {}  # old_id -> new_channel
            
            # Build list of protected channel IDs
            protected_channels = set()
            if guild.system_channel:
                protected_channels.add(guild.system_channel.id)
            if guild.rules_channel:
                protected_channels.add(guild.rules_channel.id)
            if exclude_channel_id:
                protected_channels.add(exclude_channel_id)
                excluded_channel = guild.get_channel(exclude_channel_id)
                if excluded_channel and excluded_channel.category:
                    protected_channels.add(excluded_channel.category.id)
            
            # Build sets of backup IDs for matching
            backup_channel_ids = {c.get('id') for c in backup_data.get('channels', []) if c.get('id')}
            backup_category_ids = {c.get('id') for c in backup_data.get('categories', []) if c.get('id')}
            backup_role_ids = {r.get('id') for r in backup_data.get('roles', []) if r.get('id')}
            
            # Also match by name as fallback
            backup_channel_names = {c.get('name', '').lower() for c in backup_data.get('channels', [])}
            backup_category_names = {c.get('name', '').lower() for c in backup_data.get('categories', [])}
            backup_role_names = {r.get('name', '').lower() for r in backup_data.get('roles', [])}
            
            # Get existing items mapped by ID
            existing_roles_by_id = {r.id: r for r in guild.roles}
            existing_channels_by_id = {c.id: c for c in guild.channels}
            
            # === STEP 1: DELETE EXISTING CHANNELS (except protected and backup matches) ===
            if keep_current_channels:
                if progress_callback:
                    await progress_callback("⏭️ Skipping channel deletion (--keepcurrentchannels)")
                deleted_count = 0
            else:
                if progress_callback:
                    await progress_callback("🗑️ Removing channels not in backup...")
                
                deleted_count = 0
                for channel in list(guild.channels):
                    if channel.id in protected_channels:
                        continue
                    # Keep if ID matches backup OR name matches backup
                    if channel.id in backup_channel_ids or channel.id in backup_category_ids:
                        continue
                    if channel.name.lower() in backup_channel_names or channel.name.lower() in backup_category_names:
                        continue
                    try:
                        await self.api.execute_with_delay('channel_edit', channel.delete(reason="Backup restore"))
                        deleted_count += 1
                    except:
                        pass
                
                if progress_callback:
                    await progress_callback(f"🗑️ Removed {deleted_count} channels")
            
            # === STEP 2: DELETE EXISTING ROLES (except protected and backup matches) ===
            bot_role_ids = {m.top_role.id for m in guild.members if m.bot}
            
            if keep_current_roles:
                if progress_callback:
                    await progress_callback("⏭️ Skipping role deletion (--keepcurrentroles)")
                deleted_roles = 0
            else:
                if progress_callback:
                    await progress_callback("🗑️ Removing roles not in backup...")
                
                deleted_roles = 0
                for role in list(guild.roles):
                    if role.is_default() or role.is_bot_managed() or role.id in bot_role_ids:
                        continue
                    if role.position >= guild.me.top_role.position:
                        continue
                    # Keep if ID matches backup OR name matches backup
                    if role.id in backup_role_ids:
                        continue
                    if role.name.lower() in backup_role_names:
                        continue
                    try:
                        await self.api.execute_with_delay('role_edit', role.delete(reason="Backup restore"))
                        deleted_roles += 1
                    except:
                        pass
                
                if progress_callback:
                    await progress_callback(f"🗑️ Removed {deleted_roles} roles")
            
            # === STEP 3: RESTORE ROLES (highest position first for proper hierarchy) ===
            roles_to_restore = backup_data.get('roles', [])
            total_roles = len(roles_to_restore)
            if progress_callback:
                await progress_callback(f"👥 Preparing to restore {total_roles} roles...")
            
            # Sort by position DESCENDING (highest first) to maintain hierarchy
            roles_to_restore = sorted(roles_to_restore, key=lambda r: r.get('position', 0), reverse=True)
            
            restored_roles = 0
            skipped_roles = 0
            
            # Build lookup maps for existing roles
            existing_roles_by_id = {r.id: r for r in guild.roles}
            existing_roles_by_name = {r.name.lower(): r for r in guild.roles}
            
            for i, role_data in enumerate(roles_to_restore):
                role_name = role_data.get('name', 'Restored Role')
                backup_role_id = role_data.get('id')
                
                # Skip @everyone role
                if role_name == '@everyone':
                    continue
                
                try:
                    permissions = discord.Permissions(role_data.get('permissions', 0))
                    color_value = role_data.get('color', 0)
                    color = discord.Color(color_value)
                    color_hex = f"#{color_value:06x}" if color_value else "none"
                    
                    # Build role info string
                    role_info = f"{role_name}"
                    if role_data.get('hoist'):
                        role_info += " [hoisted]"
                    if color_value:
                        role_info += f" ({color_hex})"
                    
                    # Check if role already exists - by ID first, then by name
                    existing_role = None
                    if backup_role_id and backup_role_id in existing_roles_by_id:
                        existing_role = existing_roles_by_id[backup_role_id]
                    elif role_name.lower() in existing_roles_by_name:
                        existing_role = existing_roles_by_name[role_name.lower()]
                    
                    if existing_role and not existing_role.is_bot_managed() and not existing_role.is_default():
                        # Update existing role
                        result, error = await self.api.execute_with_delay(
                            'role_edit',
                            existing_role.edit(
                                name=role_name,  # Update name too in case it changed
                                permissions=permissions,
                                color=color,
                                hoist=role_data.get('hoist', False),
                                mentionable=role_data.get('mentionable', False),
                                reason="Backup restore - update"
                            )
                        )
                        if error:
                            print(f"[RESTORE] Error updating role {role_name}: {error}")
                            skipped_roles += 1
                            if progress_callback and "Missing Permissions" in str(error):
                                await progress_callback(f"⚠️ Skip: {role_name} (no permission)")
                            elif progress_callback and "timed out" in str(error).lower():
                                await progress_callback(f"⚠️ Timeout: {role_name}")
                        else:
                            role_id_map[backup_role_id] = existing_role
                            restored_roles += 1
                            if progress_callback:
                                await progress_callback(f"✏️ Updated: {role_info}")
                    else:
                        # Create new role
                        new_role, error = await self.api.execute_with_delay(
                            'role_create',
                            guild.create_role(
                                name=role_name,
                                permissions=permissions,
                                color=color,
                                hoist=role_data.get('hoist', False),
                                mentionable=role_data.get('mentionable', False),
                                reason="Backup restore"
                            )
                        )
                        
                        if error:
                            print(f"[RESTORE] Error creating role {role_name}: {error}")
                            skipped_roles += 1
                            if progress_callback and "Missing Permissions" in str(error):
                                await progress_callback(f"⚠️ Skip: {role_name} (no permission)")
                            elif progress_callback and "timed out" in str(error).lower():
                                await progress_callback(f"⚠️ Timeout: {role_name}")
                        elif new_role:
                            role_id_map[backup_role_id] = new_role
                            restored_roles += 1
                            if progress_callback:
                                await progress_callback(f"✨ Created: {role_info}")
                            
                            # Restore role icon if exists (only for boosted servers)
                            icon_path = role_data.get('icon_path')
                            if icon_path and os.path.exists(icon_path) and guild.premium_tier >= 2:
                                try:
                                    with open(icon_path, 'rb') as f:
                                        icon_data = f.read()
                                    if len(icon_data) < 256 * 1024:  # 256KB limit
                                        await self.api.execute_with_delay('role_edit', new_role.edit(icon=icon_data))
                                except Exception as icon_err:
                                    print(f"[RESTORE] Role icon failed: {icon_err}")
                        else:
                            skipped_roles += 1
                            
                except Exception as e:
                    print(f"[RESTORE] Failed to restore role {role_name}: {e}")
                    skipped_roles += 1
                    if progress_callback:
                        err_short = str(e)[:50] if len(str(e)) > 50 else str(e)
                        await progress_callback(f"❌ Error: {role_name} - {err_short}")
                    continue  # Don't get stuck, move to next role
            
            # Final role summary
            if progress_callback:
                summary = f"👥 Roles: {restored_roles} restored"
                if skipped_roles > 0:
                    summary += f", {skipped_roles} skipped"
                await progress_callback(summary)
            
            # Refresh existing channels after role changes
            existing_channels = {c.name.lower(): c for c in guild.channels}
            
            # === STEP 4: RESTORE CATEGORIES ===
            categories = backup_data.get('categories', [])
            total_cats = len(categories)
            if progress_callback:
                await progress_callback(f"📁 Preparing to restore {total_cats} categories...")
            
            restored_cats = 0
            skipped_cats = 0
            
            # Build lookup maps for existing channels
            existing_channels_by_id = {c.id: c for c in guild.channels}
            existing_channels_by_name = {c.name.lower(): c for c in guild.channels}
            
            for cat_data in sorted(categories, key=lambda c: c.get('position', 0)):
                cat_name = cat_data.get('name', 'Restored Category')
                backup_cat_id = cat_data.get('id')
                
                try:
                    overwrites = self._deserialize_overwrites(cat_data.get('overwrites', []), guild, role_id_map)
                    
                    # Check if category exists - by ID first, then by name
                    existing_cat = None
                    if backup_cat_id and backup_cat_id in existing_channels_by_id:
                        ch = existing_channels_by_id[backup_cat_id]
                        if isinstance(ch, discord.CategoryChannel):
                            existing_cat = ch
                    if not existing_cat and cat_name.lower() in existing_channels_by_name:
                        ch = existing_channels_by_name[cat_name.lower()]
                        if isinstance(ch, discord.CategoryChannel):
                            existing_cat = ch
                    
                    if existing_cat:
                        # Update existing category
                        result, error = await self.api.execute_with_delay(
                            'channel_edit',
                            existing_cat.edit(name=cat_name, overwrites=overwrites, reason="Backup restore - update")
                        )
                        if error:
                            print(f"[RESTORE] Error updating category {cat_name}: {error}")
                            skipped_cats += 1
                        else:
                            category_id_map[backup_cat_id] = existing_cat
                            restored_cats += 1
                            if progress_callback:
                                await progress_callback(f"✏️ Updated: 📁 {cat_name}")
                    else:
                        # Create new category
                        new_category, error = await self.api.execute_with_delay(
                            'channel_create',
                            guild.create_category(
                                name=cat_name,
                                overwrites=overwrites,
                                reason="Backup restore"
                            )
                        )
                        if error:
                            print(f"[RESTORE] Error creating category {cat_name}: {error}")
                            skipped_cats += 1
                        elif new_category:
                            category_id_map[backup_cat_id] = new_category
                            restored_cats += 1
                            if progress_callback:
                                await progress_callback(f"✨ Created: 📁 {cat_name}")
                        else:
                            skipped_cats += 1
                except Exception as e:
                    print(f"[RESTORE] Failed to restore category {cat_name}: {e}")
                    skipped_cats += 1
                    continue  # Don't get stuck
            
            # Category summary
            if progress_callback:
                summary = f"📁 Categories: {restored_cats} restored"
                if skipped_cats > 0:
                    summary += f", {skipped_cats} skipped"
                await progress_callback(summary)
            
            # Refresh channels again
            existing_channels_by_id = {c.id: c for c in guild.channels}
            existing_channels_by_name = {c.name.lower(): c for c in guild.channels}
            
            # === STEP 5: RESTORE CHANNELS ===
            channels = backup_data.get('channels', [])
            total_channels = len(channels)
            if progress_callback:
                await progress_callback(f"📝 Preparing to restore {total_channels} channels...")
            
            # Channel type names for display
            channel_type_names = {
                0: "text",
                2: "voice", 
                5: "announcement",
                13: "stage",
                15: "forum"
            }
            
            restored_channels = 0
            skipped_channels = 0
            
            for channel_data in sorted(channels, key=lambda c: c.get('position', 0)):
                channel_name = channel_data.get('name', 'restored-channel')
                channel_type = channel_data.get('type', 0)
                backup_channel_id = channel_data.get('id')
                type_name = channel_type_names.get(channel_type, "unknown")
                
                try:
                    overwrites = self._deserialize_overwrites(channel_data.get('overwrites', []), guild, role_id_map)
                    
                    # Get category if exists
                    category = None
                    cat_name = ""
                    if channel_data.get('category_id'):
                        category = category_id_map.get(channel_data['category_id'])
                        if category:
                            cat_name = f" in {category.name}"
                    
                    # Build channel info
                    channel_info = f"#{channel_name} ({type_name}){cat_name}"
                    
                    # Check if channel exists - by ID first, then by name
                    existing_ch = None
                    if backup_channel_id and backup_channel_id in existing_channels_by_id:
                        ch = existing_channels_by_id[backup_channel_id]
                        if not isinstance(ch, discord.CategoryChannel):
                            existing_ch = ch
                    if not existing_ch and channel_name.lower() in existing_channels_by_name:
                        ch = existing_channels_by_name[channel_name.lower()]
                        if not isinstance(ch, discord.CategoryChannel):
                            existing_ch = ch
                    
                    if existing_ch:
                        # Update existing channel
                        edit_kwargs = {'name': channel_name, 'overwrites': overwrites, 'reason': "Backup restore - update"}
                        if channel_type == 0:  # Text
                            edit_kwargs['topic'] = channel_data.get('topic')
                            edit_kwargs['slowmode_delay'] = channel_data.get('slowmode_delay', 0)
                            edit_kwargs['nsfw'] = channel_data.get('nsfw', False)
                        if category:
                            edit_kwargs['category'] = category
                        
                        result, error = await self.api.execute_with_delay('channel_edit', existing_ch.edit(**edit_kwargs))
                        if error:
                            print(f"[RESTORE] Error updating channel {channel_name}: {error}")
                            skipped_channels += 1
                        else:
                            channel_id_map[backup_channel_id] = existing_ch
                            restored_channels += 1
                            if progress_callback:
                                await progress_callback(f"✏️ Updated: {channel_info}")
                        continue
                    
                    new_channel = None
                    error = None
                    
                    # Text channel
                    if channel_type == 0:
                        new_channel, error = await self.api.execute_with_delay(
                            'channel_create',
                            guild.create_text_channel(
                                name=channel_name,
                                topic=channel_data.get('topic'),
                                slowmode_delay=channel_data.get('slowmode_delay', 0),
                                nsfw=channel_data.get('nsfw', False),
                                category=category,
                                overwrites=overwrites,
                                reason="Backup restore"
                            )
                        )
                    
                    # Voice channel
                    elif channel_type == 2:
                        new_channel, error = await self.api.execute_with_delay(
                            'channel_create',
                            guild.create_voice_channel(
                                name=channel_name,
                                bitrate=min(channel_data.get('bitrate', 64000), guild.bitrate_limit),
                                user_limit=channel_data.get('user_limit', 0),
                                category=category,
                                overwrites=overwrites,
                                reason="Backup restore"
                            )
                        )
                    
                    # Announcement/News channel (type 5)
                    elif channel_type == 5:
                        new_channel, error = await self.api.execute_with_delay(
                            'channel_create',
                            guild.create_text_channel(
                                name=channel_name,
                                topic=channel_data.get('topic'),
                                category=category,
                                overwrites=overwrites,
                                news=True,
                                reason="Backup restore"
                            )
                        )
                    
                    # Stage channel
                    elif channel_type == 13:
                        new_channel, error = await self.api.execute_with_delay(
                            'channel_create',
                            guild.create_stage_channel(
                                name=channel_name,
                                category=category,
                                overwrites=overwrites,
                                reason="Backup restore"
                            )
                        )
                    
                    # Forum channel
                    elif channel_type == 15:
                        new_channel, error = await self.api.execute_with_delay(
                            'channel_create',
                            guild.create_forum(
                                name=channel_name,
                                topic=channel_data.get('topic'),
                                category=category,
                                overwrites=overwrites,
                                reason="Backup restore"
                            )
                        )
                    
                    if error:
                        print(f"[RESTORE] Error creating channel {channel_name}: {error}")
                        skipped_channels += 1
                    elif new_channel:
                        channel_id_map[channel_data['id']] = new_channel
                        restored_channels += 1
                        if progress_callback:
                            await progress_callback(f"✨ Created: {channel_info}")
                    else:
                        skipped_channels += 1
                        
                except Exception as e:
                    print(f"[RESTORE] Failed to restore channel {channel_name}: {e}")
                    skipped_channels += 1
                    continue  # Don't get stuck
            
            # Final channel summary
            if progress_callback:
                summary = f"📝 Channels: {restored_channels} restored"
                if skipped_channels > 0:
                    summary += f", {skipped_channels} skipped"
                await progress_callback(summary)
            
            # === STEP 6: RESTORE EMOJIS ===
            emojis = backup_data.get('emojis', [])
            if emojis:
                # Check emoji limits based on boost level
                emoji_limit = guild.emoji_limit
                current_emoji_count = len(guild.emojis)
                available_slots = emoji_limit - current_emoji_count
                
                if progress_callback:
                    await progress_callback(f"😀 Restoring emojis ({available_slots} slots available)...")
                
                if available_slots <= 0:
                    if progress_callback:
                        await progress_callback(f"⚠️ No emoji slots available (limit: {emoji_limit})")
                else:
                    restored_emojis = 0
                    skipped_emojis = 0
                    
                    for emoji_data in emojis:
                        if restored_emojis >= available_slots:
                            skipped_emojis += 1
                            continue
                        
                        try:
                            image_path = emoji_data.get('image_path')
                            emoji_name = emoji_data.get('name', 'restored_emoji')
                            
                            if image_path and os.path.exists(image_path):
                                with open(image_path, 'rb') as f:
                                    image_data = f.read()
                                
                                # Check file size (256KB limit)
                                if len(image_data) > 256 * 1024:
                                    skipped_emojis += 1
                                    continue
                                
                                # Map role restrictions
                                roles = []
                                for old_role_id in emoji_data.get('role_ids', []):
                                    if old_role_id in role_id_map:
                                        roles.append(role_id_map[old_role_id])
                                
                                new_emoji, error = await self.api.execute_with_delay(
                                    'emoji_create',
                                    guild.create_custom_emoji(
                                        name=emoji_name,
                                        image=image_data,
                                        roles=roles if roles else None,
                                        reason="Backup restore"
                                    )
                                )
                                
                                if new_emoji:
                                    restored_emojis += 1
                                    if progress_callback and restored_emojis % 3 == 0:
                                        await progress_callback(f"😀 Added emoji: :{emoji_name}:")
                                else:
                                    skipped_emojis += 1
                            else:
                                skipped_emojis += 1
                        except discord.HTTPException as e:
                            if e.code == 30008:  # Max emojis reached
                                if progress_callback:
                                    await progress_callback(f"⚠️ Emoji limit reached, skipping remaining...")
                                break
                            skipped_emojis += 1
                        except Exception as e:
                            skipped_emojis += 1
                            print(f"[RESTORE] Failed to restore emoji {emoji_data.get('name')}: {e}")
                    
                    if progress_callback:
                        msg = f"😀 Restored {restored_emojis} emojis"
                        if skipped_emojis > 0:
                            msg += f" ({skipped_emojis} skipped)"
                        await progress_callback(msg)
            
            # === STEP 7: RESTORE STICKERS ===
            stickers = backup_data.get('stickers', [])
            if stickers:
                sticker_limit = guild.sticker_limit
                current_sticker_count = len(guild.stickers)
                available_sticker_slots = sticker_limit - current_sticker_count
                
                if progress_callback:
                    await progress_callback(f"🎨 Restoring stickers ({available_sticker_slots} slots available)...")
                
                if available_sticker_slots <= 0:
                    if progress_callback:
                        await progress_callback(f"⚠️ No sticker slots available (limit: {sticker_limit})")
                else:
                    restored_stickers = 0
                    for sticker_data in stickers:
                        if restored_stickers >= available_sticker_slots:
                            break
                        
                        try:
                            image_path = sticker_data.get('image_path')
                            if image_path and os.path.exists(image_path):
                                with open(image_path, 'rb') as f:
                                    file = discord.File(f, filename=f"{sticker_data.get('name', 'sticker')}.png")
                                
                                new_sticker, error = await self.api.execute_with_delay(
                                    'sticker_create',
                                    guild.create_sticker(
                                        name=sticker_data.get('name', 'restored_sticker'),
                                        description=sticker_data.get('description', ''),
                                        emoji="⭐",
                                        file=file,
                                        reason="Backup restore"
                                    )
                                )
                                if new_sticker:
                                    restored_stickers += 1
                        except discord.HTTPException as e:
                            if e.code == 30039:  # Max stickers reached
                                break
                        except Exception as e:
                            print(f"[RESTORE] Failed to restore sticker {sticker_data.get('name')}: {e}")
                    
                    if progress_callback:
                        await progress_callback(f"🎨 Restored {restored_stickers} stickers")
            
            # === STEP 8: UPDATE SERVER SETTINGS ===
            if progress_callback:
                await progress_callback("⚙️ Restoring server settings...")
            
            try:
                edit_kwargs = {}
                
                if backup_data.get('description'):
                    edit_kwargs['description'] = backup_data['description']
                
                if 'verification_level' in backup_data:
                    edit_kwargs['verification_level'] = discord.VerificationLevel(backup_data['verification_level'])
                
                if 'default_notifications' in backup_data:
                    edit_kwargs['default_notifications'] = discord.NotificationLevel(backup_data['default_notifications'])
                
                if 'explicit_content_filter' in backup_data:
                    edit_kwargs['explicit_content_filter'] = discord.ContentFilter(backup_data['explicit_content_filter'])
                
                if backup_data.get('afk_channel_id') and backup_data['afk_channel_id'] in channel_id_map:
                    edit_kwargs['afk_channel'] = channel_id_map[backup_data['afk_channel_id']]
                    edit_kwargs['afk_timeout'] = backup_data.get('afk_timeout', 300)
                
                if edit_kwargs:
                    await self.api.execute_with_delay('channel_edit', guild.edit(**edit_kwargs))
                    if progress_callback:
                        await progress_callback("⚙️ Server settings updated")
                
                # Restore server icon
                icon_path = backup_data.get('icon_path')
                if icon_path and os.path.exists(icon_path):
                    with open(icon_path, 'rb') as f:
                        await self.api.execute_with_delay('channel_edit', guild.edit(icon=f.read()))
                    if progress_callback:
                        await progress_callback("🖼️ Server icon restored")
                
                # Restore server banner (requires boost level 2)
                banner_path = backup_data.get('banner_path')
                if banner_path and os.path.exists(banner_path) and guild.premium_tier >= 2:
                    with open(banner_path, 'rb') as f:
                        await self.api.execute_with_delay('channel_edit', guild.edit(banner=f.read()))
                    if progress_callback:
                        await progress_callback("🖼️ Server banner restored")
                        
            except Exception as e:
                print(f"[RESTORE] Failed to restore server settings: {e}")
            
            if progress_callback:
                await progress_callback("✅ Restore complete!")
            
            return True, "Backup restored successfully!"
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"Restore failed: {str(e)}"
    
    def _deserialize_overwrites(self, overwrites_data: List[dict], guild: discord.Guild, role_id_map: dict) -> dict:
        """Deserialize permission overwrites"""
        overwrites = {}
        
        for ow_data in overwrites_data:
            target = None
            
            if ow_data['target_type'] == 'role':
                # Try to find in mapped roles first
                if ow_data['target_id'] in role_id_map:
                    target = role_id_map[ow_data['target_id']]
                else:
                    # Try to find @everyone
                    target = guild.default_role
            else:
                # Member - try to find
                target = guild.get_member(ow_data['target_id'])
            
            if target:
                overwrites[target] = discord.PermissionOverwrite.from_pair(
                    discord.Permissions(ow_data['allow']),
                    discord.Permissions(ow_data['deny'])
                )
        
        return overwrites
    
    # ==================== BACKUP IMPORT/EXPORT ====================
    
    async def import_backup(self, target_guild_id: int, backup_id: str) -> Tuple[bool, str]:
        """
        Import a backup from any server to the target server's backup list.
        This copies the backup, not the actual server data.
        """
        # Find the backup in database (from any guild)
        backup_data = self.db.find_backup_by_id(backup_id)
        
        if not backup_data:
            # Try to load from file
            backup_path = self._get_backup_path(backup_id)
            json_path = os.path.join(backup_path, "backup.json")
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
            else:
                return False, f"Backup {backup_id} not found"
        
        # Generate new backup ID for the imported copy
        new_backup_id = self._generate_backup_id()
        
        # Copy backup files to new location
        old_path = self._get_backup_path(backup_id)
        new_path = self._get_backup_path(new_backup_id)
        
        if os.path.exists(old_path):
            import shutil
            shutil.copytree(old_path, new_path, dirs_exist_ok=True)
            
            # Update the JSON file with new ID
            json_path = os.path.join(new_path, "backup.json")
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data['backup_id'] = new_backup_id
                data['imported_from'] = backup_id
                data['imported_at'] = datetime.utcnow().isoformat()
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
        
        # Save to database for target guild
        original_name = backup_data.get('guild_name', 'Unknown')
        self.db.save_comprehensive_backup(
            target_guild_id,
            new_backup_id,
            f"[Imported] {original_name}",
            backup_data
        )
        
        return True, f"Backup imported successfully! New ID: {new_backup_id}"
    
    def list_backups(self, guild_id: int) -> List[dict]:
        """List all backups for a guild"""
        return self.db.list_comprehensive_backups(guild_id)
    
    def get_backup_info(self, guild_id: int, backup_id: str) -> Optional[dict]:
        """Get detailed info about a backup"""
        return self.db.get_comprehensive_backup(guild_id, backup_id)
    
    def delete_backup(self, guild_id: int, backup_id: str) -> bool:
        """Delete a backup and its files"""
        # Delete from database
        success = self.db.delete_comprehensive_backup(guild_id, backup_id)
        
        # Delete files
        backup_path = self._get_backup_path(backup_id)
        if os.path.exists(backup_path):
            import shutil
            shutil.rmtree(backup_path, ignore_errors=True)
        
        return success
