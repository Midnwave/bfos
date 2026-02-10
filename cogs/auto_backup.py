"""
BlockForge OS Auto-Backup Scheduler
Background task for automatic daily backups
"""

import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from utils.database import Database
from utils.colors import Colors
import asyncio

class AutoBackupScheduler(commands.Cog):
    """Handles automatic backup scheduling"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.backup_task.start()
        print(f"{Colors.GREEN}[✓] Auto-backup scheduler started{Colors.RESET}")
    
    def cog_unload(self):
        """Stop task when cog unloads"""
        self.backup_task.cancel()
    
    @tasks.loop(hours=24)
    async def backup_task(self):
        """Run backup task daily"""
        print(f"{Colors.CYAN}[BACKUP] Running daily backup check...{Colors.RESET}")
        
        # Get all guilds with auto-backup enabled
        guilds_to_backup = self.get_auto_backup_guilds()
        
        for guild_data in guilds_to_backup:
            guild_id = guild_data['guild_id']
            guild = self.bot.get_guild(guild_id)
            
            if not guild:
                print(f"{Colors.YELLOW}[BACKUP] Guild {guild_id} not found, skipping{Colors.RESET}")
                continue
            
            print(f"{Colors.CYAN}[BACKUP] Creating backup for: {guild.name}{Colors.RESET}")
            
            try:
                await self.create_auto_backup(guild, guild_data)
            except Exception as e:
                print(f"{Colors.RED}[BACKUP] Failed for {guild.name}: {e}{Colors.RESET}")
        
        print(f"{Colors.GREEN}[BACKUP] Daily backup check complete{Colors.RESET}")
    
    @backup_task.before_loop
    async def before_backup_task(self):
        """Wait until bot is ready"""
        await self.bot.wait_until_ready()
        print(f"{Colors.GREEN}[BACKUP] Scheduler ready, next run in 24 hours{Colors.RESET}")
    
    def get_auto_backup_guilds(self):
        """Get guilds with auto-backup enabled"""
        import sqlite3
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT guild_id, auto_backup, auto_overwrite
            FROM backup_settings
            WHERE auto_backup = 1
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'guild_id': row[0],
            'auto_overwrite': bool(row[2])
        } for row in rows]
    
    async def create_auto_backup(self, guild, settings):
        """Create automatic backup for a guild"""
        # Check if we need to handle overwrite
        backups = self.db.get_server_backups(guild.id)
        
        if len(backups) >= 10:
            if settings['auto_overwrite']:
                # Find oldest unlocked backup
                oldest_unlocked = None
                for backup in reversed(backups):  # Oldest first
                    if not backup.get('locked'):
                        oldest_unlocked = backup['id']
                        break
                
                if oldest_unlocked:
                    print(f"{Colors.YELLOW}[BACKUP] Deleting oldest backup: {oldest_unlocked}{Colors.RESET}")
                    self.db.delete_backup(guild.id, oldest_unlocked)
                else:
                    print(f"{Colors.YELLOW}[BACKUP] All backups locked, skipping {guild.name}{Colors.RESET}")
                    return
            else:
                print(f"{Colors.YELLOW}[BACKUP] Max backups reached, skipping {guild.name}{Colors.RESET}")
                return
        
        # Import backup panel for backup logic
        from cogs.terminal_backup import BackupPanel
        
        # Create temporary session object
        class TempSession:
            def __init__(self, bot, guild, db):
                self.bot = bot
                self.guild = guild
                self.db = db
            
            async def send_progress_update(self, text, delay=0.1):
                # Silent for auto-backups
                await asyncio.sleep(delay)
        
        temp_session = TempSession(self.bot, guild, self.db)
        panel = BackupPanel(temp_session)
        
        try:
            # Collect data
            channels_data = await panel.backup_channels()
            roles_data = await panel.backup_roles()
            settings_data = await panel.backup_settings()
            
            # Create backup object
            backup_name = f"auto-{datetime.utcnow().strftime('%Y%m%d')}"
            backup_data = {
                'name': backup_name,
                'created_at': datetime.utcnow().isoformat(),
                'channels': channels_data,
                'roles': roles_data,
                'settings': settings_data,
                'locked': False,
                'auto': True
            }
            
            # Save to database
            backup_id = self.db.create_backup(guild.id, backup_name, backup_data)
            
            print(f"{Colors.GREEN}[BACKUP] Created backup {backup_id} for {guild.name}{Colors.RESET}")
            
            # Try to notify server owner
            try:
                owner = guild.owner
                if owner:
                    embed = discord.Embed(
                        title="📦 Auto-Backup Created",
                        description=f"Automatic backup created for **{guild.name}**",
                        color=0x00FF00,
                        timestamp=datetime.utcnow()
                    )
                    embed.add_field(name="Backup Name", value=backup_name, inline=True)
                    embed.add_field(name="Backup ID", value=backup_id, inline=True)
                    embed.add_field(name="Channels", value=str(len(channels_data)), inline=True)
                    embed.add_field(name="Roles", value=str(len(roles_data)), inline=True)
                    embed.set_footer(text="Configure in BFOS: .bfos() > management > backup")
                    
                    await owner.send(embed=embed)
            except:
                pass  # Owner has DMs disabled
        
        except Exception as e:
            print(f"{Colors.RED}[BACKUP] Error creating backup for {guild.name}: {e}{Colors.RESET}")
            raise

async def setup(bot):
    await bot.add_cog(AutoBackupScheduler(bot))
