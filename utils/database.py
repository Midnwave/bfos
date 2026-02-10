"""
Database Handler for BlockForge OS
Manages persistent storage of guild settings and configurations
"""

import sqlite3
import json
import os
from datetime import datetime

class Database:
    """SQLite database handler for BFOS"""
    
    def __init__(self, db_path='data/bfos.db'):
        self.db_path = db_path
        self._ensure_database_exists()
        self._initialize_tables()
    
    def _ensure_database_exists(self):
        """Ensure the data directory and database file exist"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def _initialize_tables(self):
        """Initialize database tables"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Guilds table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY,
                setup_channel_id INTEGER,
                setup_complete BOOLEAN DEFAULT 0,
                command_prefix TEXT DEFAULT ';',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Migrate existing guilds table to add command_prefix if it doesn't exist
        try:
            cursor.execute("SELECT command_prefix FROM guilds LIMIT 1")
        except sqlite3.OperationalError:
            # Column doesn't exist, add it
            print("[DATABASE] Migrating guilds table to add command_prefix column...")
            cursor.execute("ALTER TABLE guilds ADD COLUMN command_prefix TEXT DEFAULT ';'")
            print("[DATABASE] Migration completed!")
        
        # Guild settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                settings TEXT,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Module states table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS module_states (
                guild_id INTEGER,
                module_name TEXT,
                enabled BOOLEAN DEFAULT 0,
                PRIMARY KEY (guild_id, module_name),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Moderation cases table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS moderation_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                case_number INTEGER,
                case_type TEXT,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                duration TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Warn configurations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS warn_configs (
                guild_id INTEGER PRIMARY KEY,
                auto_punish_enabled BOOLEAN DEFAULT 0,
                warn_threshold INTEGER DEFAULT 0,
                punishment_type TEXT,
                punishment_duration TEXT,
                staff_immune BOOLEAN DEFAULT 0,
                dm_on_warn BOOLEAN DEFAULT 1,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Terminal sessions table (for logging/history)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS terminal_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                commands_executed INTEGER DEFAULT 0,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Command history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                command TEXT,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES terminal_sessions(session_id)
            )
        ''')
        
        # Staff roles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                role_id INTEGER,
                role_name TEXT,
                display_name TEXT,
                position INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Staff assignments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                staff_role_id INTEGER,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id),
                FOREIGN KEY (staff_role_id) REFERENCES staff_roles(id)
            )
        ''')
        
        # Embed configurations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS embed_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                embed_type TEXT,
                title TEXT,
                description TEXT,
                color TEXT DEFAULT '0x00ff00',
                thumbnail_url TEXT,
                image_url TEXT,
                footer_text TEXT,
                footer_icon_url TEXT,
                author_name TEXT,
                author_icon_url TEXT,
                fields TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Warnings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active BOOLEAN DEFAULT 1,
                case_id INTEGER,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Mutes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mutes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                duration TEXT,
                muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                unmuted_at TIMESTAMP,
                expires_at TIMESTAMP,
                active BOOLEAN DEFAULT 1,
                case_id INTEGER,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Cases table (comprehensive case system)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                case_number INTEGER,
                case_type TEXT,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                duration TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Backups table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_id TEXT,
                guild_id INTEGER,
                backup_name TEXT,
                backup_data TEXT,
                created_at TIMESTAMP,
                locked BOOLEAN DEFAULT 0,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Comprehensive backups table (new advanced system)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comprehensive_backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_id TEXT UNIQUE,
                guild_id INTEGER,
                backup_name TEXT,
                backup_data TEXT,
                file_size_bytes INTEGER DEFAULT 0,
                roles_count INTEGER DEFAULT 0,
                channels_count INTEGER DEFAULT 0,
                emojis_count INTEGER DEFAULT 0,
                stickers_count INTEGER DEFAULT 0,
                imported_from TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                locked BOOLEAN DEFAULT 0,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Backup settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backup_settings (
                guild_id INTEGER PRIMARY KEY,
                auto_backup BOOLEAN DEFAULT 0,
                auto_overwrite BOOLEAN DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Channel permission presets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                preset_name TEXT,
                preset_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # ==================== v2.0.9 NEW TABLES ====================
        
        # Mod notes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mod_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                note TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Channel locks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_locks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                lock_type TEXT,
                saved_permissions TEXT,
                locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                locked_by INTEGER,
                UNIQUE(guild_id, channel_id, lock_type),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Voice channel punishments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS voice_punishments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                punishment_type TEXT,
                reason TEXT,
                duration TEXT,
                expires_at TIMESTAMP,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active BOOLEAN DEFAULT 1,
                moderator_id INTEGER,
                case_id TEXT,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Moderation logs table (comprehensive logging)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS moderation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                action_type TEXT,
                user_id INTEGER,
                moderator_id INTEGER,
                case_id TEXT,
                reason TEXT,
                duration TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Permission assignments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS permission_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                role_id INTEGER,
                permission_id TEXT,
                assigned_by INTEGER,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, user_id, role_id, permission_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Permission groups table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS permission_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                group_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, group_name),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Group permissions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                permission_id TEXT,
                FOREIGN KEY (group_id) REFERENCES permission_groups(id)
            )
        ''')
        
        # Migrate cases table to add case_id column if it doesn't exist
        try:
            cursor.execute("SELECT case_id FROM cases LIMIT 1")
        except sqlite3.OperationalError:
            print("[DATABASE] Migrating cases table to add case_id column...")
            cursor.execute("ALTER TABLE cases ADD COLUMN case_id TEXT")
            print("[DATABASE] Migration completed!")
        
        # Migrate warnings table to add case_id TEXT column if it doesn't exist
        try:
            cursor.execute("SELECT case_id FROM warnings LIMIT 1")
        except sqlite3.OperationalError:
            print("[DATABASE] Migrating warnings table to add case_id column...")
            cursor.execute("ALTER TABLE warnings ADD COLUMN case_id TEXT")
            print("[DATABASE] Migration completed!")
        
        # ==================== END v2.0.9 NEW TABLES ====================
        
        # Migrate warn_configs table to add new columns if they don't exist
        try:
            cursor.execute("SELECT staff_immune FROM warn_configs LIMIT 1")
        except sqlite3.OperationalError:
            print("[DATABASE] Migrating warn_configs table to add staff_immune column...")
            cursor.execute("ALTER TABLE warn_configs ADD COLUMN staff_immune BOOLEAN DEFAULT 0")
            print("[DATABASE] Migration completed!")
        
        try:
            cursor.execute("SELECT dm_on_warn FROM warn_configs LIMIT 1")
        except sqlite3.OperationalError:
            print("[DATABASE] Migrating warn_configs table to add dm_on_warn column...")
            cursor.execute("ALTER TABLE warn_configs ADD COLUMN dm_on_warn BOOLEAN DEFAULT 1")
            print("[DATABASE] Migration completed!")
        
        conn.commit()
        conn.close()
    
    def guild_exists(self, guild_id):
        """Check if guild exists in database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM guilds WHERE guild_id = ?', (guild_id,))
        exists = cursor.fetchone() is not None
        
        conn.close()
        return exists
    
    def add_guild(self, guild_id, setup_channel_id):
        """Add a new guild to the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO guilds (guild_id, setup_channel_id, setup_complete)
            VALUES (?, ?, 0)
        ''', (guild_id, setup_channel_id))
        
        # Initialize default settings
        default_settings = {
            'prefix': '.',
            'admin_roles': [],
            'staff_roles': [],
            'custom_commands': {}
        }
        
        cursor.execute('''
            INSERT INTO guild_settings (guild_id, settings)
            VALUES (?, ?)
        ''', (guild_id, json.dumps(default_settings)))
        
        conn.commit()
        conn.close()
    
    def get_guild(self, guild_id):
        """Get guild data"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT guild_id, setup_channel_id, setup_complete, created_at, updated_at
            FROM guilds
            WHERE guild_id = ?
        ''', (guild_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'guild_id': row[0],
                'setup_channel_id': row[1],
                'setup_complete': bool(row[2]),
                'created_at': row[3],
                'updated_at': row[4]
            }
        return None
    
    def mark_setup_complete(self, guild_id):
        """Mark guild setup as complete"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE guilds
            SET setup_complete = 1, updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
        ''', (guild_id,))
        
        conn.commit()
        conn.close()
    
    def get_guild_settings(self, guild_id):
        """Get guild settings"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT settings FROM guild_settings WHERE guild_id = ?
        ''', (guild_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return {}
    
    def get_setting(self, guild_id, key, default=None):
        """Get a specific setting value"""
        settings = self.get_guild_settings(guild_id)
        return settings.get(key, default) if settings else default
    
    def set_setting(self, guild_id, key, value):
        """Set a specific setting value"""
        settings = self.get_guild_settings(guild_id) or {}
        settings[key] = value
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute('SELECT 1 FROM guild_settings WHERE guild_id = ?', (guild_id,))
        if cursor.fetchone():
            cursor.execute('''
                UPDATE guild_settings SET settings = ? WHERE guild_id = ?
            ''', (json.dumps(settings), guild_id))
        else:
            cursor.execute('''
                INSERT INTO guild_settings (guild_id, settings) VALUES (?, ?)
            ''', (guild_id, json.dumps(settings)))
        
        conn.commit()
        conn.close()
        return True
    
    def update_guild_settings(self, guild_id, settings):
        """Update guild settings"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE guild_settings
            SET settings = ?
            WHERE guild_id = ?
        ''', (json.dumps(settings), guild_id))
        
        cursor.execute('''
            UPDATE guilds
            SET updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
        ''', (guild_id,))
        
        conn.commit()
        conn.close()
    
    def create_session(self, guild_id, user_id):
        """Create a new terminal session"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO terminal_sessions (guild_id, user_id, started_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (guild_id, user_id))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return session_id
    
    def end_session(self, session_id, commands_executed):
        """End a terminal session"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE terminal_sessions
            SET ended_at = CURRENT_TIMESTAMP, commands_executed = ?
            WHERE session_id = ?
        ''', (commands_executed, session_id))
        
        conn.commit()
        conn.close()
    
    def log_command(self, session_id, command):
        """Log a command execution"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO command_history (session_id, command, executed_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (session_id, command))
        
        conn.commit()
        conn.close()
    
    # Module management methods
    def get_module_state(self, guild_id, module_name):
        """Get the state of a module for a guild"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT enabled FROM module_states
            WHERE guild_id = ? AND module_name = ?
        ''', (guild_id, module_name))
        
        row = cursor.fetchone()
        conn.close()
        
        return bool(row[0]) if row else False
    
    def set_module_state(self, guild_id, module_name, enabled):
        """Set the state of a module for a guild"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO module_states (guild_id, module_name, enabled)
            VALUES (?, ?, ?)
        ''', (guild_id, module_name, enabled))
        
        conn.commit()
        conn.close()
    
    def get_all_module_states(self, guild_id):
        """Get all module states for a guild"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT module_name, enabled FROM module_states
            WHERE guild_id = ?
        ''', (guild_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return {row[0]: bool(row[1]) for row in rows}
    
    def is_module_enabled(self, guild_id, module_name):
        """Check if a module is enabled for a guild (alias for get_module_state)"""
        return self.get_module_state(guild_id, module_name)
    
    # Prefix management
    def get_command_prefix(self, guild_id):
        """Get command prefix for a guild"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT command_prefix FROM guilds WHERE guild_id = ?
        ''', (guild_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else ';'
    
    def set_command_prefix(self, guild_id, prefix):
        """Set command prefix for a guild"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE guilds SET command_prefix = ?, updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
        ''', (prefix, guild_id))
        
        conn.commit()
        conn.close()
    
    # Case management
    def create_case(self, guild_id, case_type, user_id, moderator_id, reason, duration=None):
        """Create a new moderation case"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get next case number for this guild
        cursor.execute('''
            SELECT MAX(case_number) FROM moderation_cases WHERE guild_id = ?
        ''', (guild_id,))
        
        max_case = cursor.fetchone()[0]
        case_number = (max_case or 0) + 1
        
        cursor.execute('''
            INSERT INTO moderation_cases 
            (guild_id, case_number, case_type, user_id, moderator_id, reason, duration, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (guild_id, case_number, case_type, user_id, moderator_id, reason, duration))
        
        conn.commit()
        conn.close()
        
        return case_number
    
    def get_case(self, guild_id, case_number):
        """Get a specific case"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT case_number, case_type, user_id, moderator_id, reason, duration, timestamp
            FROM moderation_cases
            WHERE guild_id = ? AND case_number = ?
        ''', (guild_id, case_number))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'case_number': row[0],
                'case_type': row[1],
                'user_id': row[2],
                'moderator_id': row[3],
                'reason': row[4],
                'duration': row[5],
                'timestamp': row[6]
            }
        return None
    
    def get_user_cases(self, guild_id, user_id, case_type=None):
        """Get all cases for a user, optionally filtered by type"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if case_type:
            cursor.execute('''
                SELECT case_number, case_type, moderator_id, reason, duration, created_at
                FROM cases
                WHERE guild_id = ? AND user_id = ? AND case_type = ?
                ORDER BY case_number DESC
            ''', (guild_id, user_id, case_type))
        else:
            cursor.execute('''
                SELECT case_number, case_type, moderator_id, reason, duration, created_at
                FROM cases
                WHERE guild_id = ? AND user_id = ?
                ORDER BY case_number DESC
            ''', (guild_id, user_id))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'case_number': row[0],
            'case_type': row[1],
            'moderator_id': row[2],
            'reason': row[3],
            'duration': row[4],
            'timestamp': row[5]
        } for row in rows]
    
    def get_case_by_number(self, guild_id, case_number):
        """Get a specific case by its number"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT case_number, user_id, case_type, moderator_id, reason, duration, created_at
            FROM cases
            WHERE guild_id = ? AND case_number = ?
        ''', (guild_id, case_number))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'case_number': row[0],
                'user_id': row[1],
                'case_type': row[2],
                'moderator_id': row[3],
                'reason': row[4],
                'duration': row[5],
                'timestamp': row[6]
            }
        return None
    
    def delete_case(self, guild_id, case_number):
        """Delete a specific case"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM cases
                WHERE guild_id = ? AND case_number = ?
            ''', (guild_id, case_number))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to delete case: {e}")
            conn.close()
            return False
    
    # Warn configuration
    def get_warn_config(self, guild_id):
        """Get warn configuration for a guild"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT auto_punish_enabled, warn_threshold, punishment_type, punishment_duration, staff_immune, dm_on_warn
            FROM warn_configs WHERE guild_id = ?
        ''', (guild_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'auto_punish_enabled': bool(row[0]),
                'warn_threshold': row[1],
                'punishment_type': row[2],
                'punishment_duration': row[3],
                'staff_immune': bool(row[4]) if row[4] is not None else False,
                'dm_on_warn': bool(row[5]) if row[5] is not None else True
            }
        return {
            'auto_punish_enabled': False,
            'warn_threshold': 0,
            'punishment_type': None,
            'punishment_duration': None,
            'staff_immune': False,
            'dm_on_warn': True
        }
    
    def set_warn_config(self, guild_id, auto_punish_enabled, warn_threshold, punishment_type, punishment_duration, staff_immune=False, dm_on_warn=True):
        """Set warn configuration for a guild"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO warn_configs 
            (guild_id, auto_punish_enabled, warn_threshold, punishment_type, punishment_duration, staff_immune, dm_on_warn)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (guild_id, auto_punish_enabled, warn_threshold, punishment_type, punishment_duration, staff_immune, dm_on_warn))
        
        conn.commit()
        conn.close()
    
    def set_staff_immunity(self, guild_id, enabled):
        """Set staff immunity setting"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get existing config or create default
        config = self.get_warn_config(guild_id)
        
        cursor.execute('''
            INSERT OR REPLACE INTO warn_configs 
            (guild_id, auto_punish_enabled, warn_threshold, punishment_type, punishment_duration, staff_immune, dm_on_warn)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (guild_id, config['auto_punish_enabled'], config['warn_threshold'], 
              config['punishment_type'], config['punishment_duration'], enabled, config['dm_on_warn']))
        
        conn.commit()
        conn.close()
    
    def set_dm_on_warn(self, guild_id, enabled):
        """Set DM on warn setting"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get existing config or create default
        config = self.get_warn_config(guild_id)
        
        cursor.execute('''
            INSERT OR REPLACE INTO warn_configs 
            (guild_id, auto_punish_enabled, warn_threshold, punishment_type, punishment_duration, staff_immune, dm_on_warn)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (guild_id, config['auto_punish_enabled'], config['warn_threshold'], 
              config['punishment_type'], config['punishment_duration'], config['staff_immune'], enabled))
        
        conn.commit()
        conn.close()
    
    # Staff management methods
    def import_staff_role(self, guild_id, role_id, role_name, position):
        """Import a staff role"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if role already exists
        cursor.execute('''
            SELECT id FROM staff_roles WHERE guild_id = ? AND role_id = ?
        ''', (guild_id, role_id))
        
        if cursor.fetchone():
            conn.close()
            return None  # Already exists
        
        cursor.execute('''
            INSERT INTO staff_roles (guild_id, role_id, role_name, display_name, position)
            VALUES (?, ?, ?, ?, ?)
        ''', (guild_id, role_id, role_name, role_name, position))
        
        staff_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return staff_id
    
    def get_staff_role(self, guild_id, staff_id):
        """Get a staff role by ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, role_id, role_name, display_name, position
            FROM staff_roles
            WHERE guild_id = ? AND id = ?
        ''', (guild_id, staff_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'role_id': row[1],
                'role_name': row[2],
                'display_name': row[3],
                'position': row[4]
            }
        return None
    
    def get_all_staff_roles(self, guild_id):
        """Get all staff roles for a guild, sorted by position"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, role_id, role_name, display_name, position
            FROM staff_roles
            WHERE guild_id = ?
            ORDER BY position DESC
        ''', (guild_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'role_id': row[1],
            'role_name': row[2],
            'display_name': row[3],
            'position': row[4]
        } for row in rows]
    
    def rename_staff_role(self, guild_id, staff_id, new_display_name):
        """Rename a staff role's display name"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE staff_roles
            SET display_name = ?
            WHERE guild_id = ? AND id = ?
        ''', (new_display_name, guild_id, staff_id))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected > 0
    
    def delete_staff_role(self, guild_id, staff_id):
        """Delete a staff role"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Delete assignments first
        cursor.execute('''
            DELETE FROM staff_assignments
            WHERE guild_id = ? AND staff_role_id = ?
        ''', (guild_id, staff_id))
        
        # Delete the role
        cursor.execute('''
            DELETE FROM staff_roles
            WHERE guild_id = ? AND id = ?
        ''', (guild_id, staff_id))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected > 0
    
    def assign_staff_to_user(self, guild_id, user_id, staff_role_id):
        """Assign a staff role to a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if already assigned
        cursor.execute('''
            SELECT id FROM staff_assignments
            WHERE guild_id = ? AND user_id = ? AND staff_role_id = ?
        ''', (guild_id, user_id, staff_role_id))
        
        if cursor.fetchone():
            conn.close()
            return False  # Already assigned
        
        cursor.execute('''
            INSERT INTO staff_assignments (guild_id, user_id, staff_role_id)
            VALUES (?, ?, ?)
        ''', (guild_id, user_id, staff_role_id))
        
        conn.commit()
        conn.close()
        
        return True
    
    def remove_all_staff_from_user(self, guild_id, user_id):
        """Remove all staff assignments from a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM staff_assignments
            WHERE guild_id = ? AND user_id = ?
        ''', (guild_id, user_id))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected
    
    def get_user_staff_roles(self, guild_id, user_id):
        """Get all staff roles assigned to a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sr.id, sr.role_id, sr.role_name, sr.display_name, sr.position
            FROM staff_assignments sa
            JOIN staff_roles sr ON sa.staff_role_id = sr.id
            WHERE sa.guild_id = ? AND sa.user_id = ?
            ORDER BY sr.position DESC
        ''', (guild_id, user_id))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'role_id': row[1],
            'role_name': row[2],
            'display_name': row[3],
            'position': row[4]
        } for row in rows]
    
    def get_staff_members(self, guild_id):
        """Get all users with staff roles"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT user_id FROM staff_assignments
            WHERE guild_id = ?
        ''', (guild_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows]
    
    def clear_all_settings(self, guild_id):
        """Clear all server settings (except moderation cases and guild record)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Clear module states
            cursor.execute('DELETE FROM module_states WHERE guild_id = ?', (guild_id,))
            
            # Clear staff assignments (keeps roles, just clears assignments)
            cursor.execute('DELETE FROM staff_assignments WHERE guild_id = ?', (guild_id,))
            
            # Clear staff roles
            cursor.execute('DELETE FROM staff_roles WHERE guild_id = ?', (guild_id,))
            
            # Clear warn configurations
            cursor.execute('DELETE FROM warn_configs WHERE guild_id = ?', (guild_id,))
            
            # Clear embed configurations
            cursor.execute('DELETE FROM embed_configs WHERE guild_id = ?', (guild_id,))
            
            # Reset command prefix to default
            cursor.execute('''
                UPDATE guilds 
                SET command_prefix = ';' 
                WHERE guild_id = ?
            ''', (guild_id,))
            
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to clear settings: {type(e).__name__}: {e}")
            conn.close()
            return False
    
    # ==================== CASE SYSTEM ====================
    
    def generate_case_id(self, guild_id):
        """Generate a unique random 10-digit case ID"""
        import random
        conn = self._get_connection()
        cursor = conn.cursor()
        
        while True:
            case_id = str(random.randint(1000000000, 9999999999))
            cursor.execute('SELECT 1 FROM cases WHERE guild_id = ? AND case_id = ?', (guild_id, case_id))
            if not cursor.fetchone():
                conn.close()
                return case_id
    
    def create_case(self, guild_id, case_type, user_id, moderator_id, reason, duration=None, metadata=None):
        """Create a new moderation case with random 10-digit case ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Generate unique 10-digit case ID
        import random
        while True:
            case_id = str(random.randint(1000000000, 9999999999))
            cursor.execute('SELECT 1 FROM cases WHERE guild_id = ? AND case_id = ?', (guild_id, case_id))
            if not cursor.fetchone():
                break
        
        # Get next case number for this guild (for backwards compatibility)
        cursor.execute('SELECT MAX(case_number) FROM cases WHERE guild_id = ?', (guild_id,))
        max_case = cursor.fetchone()[0]
        case_number = (max_case + 1) if max_case else 1
        
        # Insert case with new case_id
        cursor.execute('''
            INSERT INTO cases (guild_id, case_number, case_id, case_type, user_id, moderator_id, reason, duration, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (guild_id, case_number, case_id, case_type, user_id, moderator_id, reason, duration, json.dumps(metadata) if metadata else None))
        
        db_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Return case_id (10-digit) instead of case_number
        return db_id, case_id
    
    def get_case_by_id(self, guild_id, case_id):
        """Get a specific case by 10-digit case ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, case_number, case_id, case_type, user_id, moderator_id, reason, duration, created_at, metadata
            FROM cases
            WHERE guild_id = ? AND case_id = ?
        ''', (guild_id, str(case_id)))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'case_number': row[1],
            'case_id': row[2],
            'case_type': row[3],
            'user_id': row[4],
            'moderator_id': row[5],
            'reason': row[6],
            'duration': row[7],
            'created_at': row[8],
            'metadata': json.loads(row[9]) if row[9] else None
        }
    
    def get_case(self, guild_id, case_number):
        """Get a specific case by case number"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, case_number, case_type, user_id, moderator_id, reason, duration, created_at, metadata
            FROM cases
            WHERE guild_id = ? AND case_number = ?
        ''', (guild_id, case_number))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'case_number': row[1],
            'case_type': row[2],
            'user_id': row[3],
            'moderator_id': row[4],
            'reason': row[5],
            'duration': row[6],
            'created_at': row[7],
            'metadata': json.loads(row[8]) if row[8] else None
        }
    
    def get_user_cases(self, guild_id, user_id, case_type=None):
        """Get all cases for a specific user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if case_type:
            cursor.execute('''
                SELECT id, case_number, case_type, user_id, moderator_id, reason, duration, created_at, metadata
                FROM cases
                WHERE guild_id = ? AND user_id = ? AND case_type = ?
                ORDER BY created_at DESC
            ''', (guild_id, user_id, case_type))
        else:
            cursor.execute('''
                SELECT id, case_number, case_type, user_id, moderator_id, reason, duration, created_at, metadata
                FROM cases
                WHERE guild_id = ? AND user_id = ?
                ORDER BY created_at DESC
            ''', (guild_id, user_id))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'case_number': row[1],
            'case_type': row[2],
            'user_id': row[3],
            'moderator_id': row[4],
            'reason': row[5],
            'duration': row[6],
            'created_at': row[7],
            'metadata': json.loads(row[8]) if row[8] else None
        } for row in rows]
    
    # ==================== WARNING SYSTEM ====================
    
    def add_warning(self, guild_id, user_id, moderator_id, reason, duration=None):
        """Add a warning to a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create case first
        case_id, case_number = self.create_case(guild_id, 'warn', user_id, moderator_id, reason, duration)
        
        # Calculate expiration
        expires_at = None
        if duration:
            from datetime import datetime, timedelta
            expires_at = datetime.utcnow() + self._parse_duration(duration)
        
        # Insert warning
        cursor.execute('''
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason, expires_at, case_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (guild_id, user_id, moderator_id, reason, expires_at, case_id))
        
        warning_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return warning_id, case_number
    
    def get_active_warnings(self, guild_id, user_id):
        """Get all active warnings for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, moderator_id, reason, created_at, expires_at, case_id
            FROM warnings
            WHERE guild_id = ? AND user_id = ? AND active = 1
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            ORDER BY created_at DESC
        ''', (guild_id, user_id))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'moderator_id': row[1],
            'reason': row[2],
            'created_at': row[3],
            'expires_at': row[4],
            'case_id': row[5]
        } for row in rows]
    
    def clear_warning(self, guild_id, user_id, warning_id):
        """Clear a specific warning"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE warnings
            SET active = 0
            WHERE guild_id = ? AND user_id = ? AND id = ?
        ''', (guild_id, user_id, warning_id))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected > 0
    
    def clear_all_warnings(self, guild_id, user_id):
        """Clear all warnings for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE warnings
            SET active = 0
            WHERE guild_id = ? AND user_id = ?
        ''', (guild_id, user_id))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected
    
    # ==================== MUTE SYSTEM ====================
    
    def add_mute(self, guild_id, user_id, moderator_id, reason, duration):
        """Add a mute record"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create case first
        case_id, case_number = self.create_case(guild_id, 'mute', user_id, moderator_id, reason, duration)
        
        # Calculate expiration
        from datetime import datetime, timedelta
        expires_at = datetime.utcnow() + self._parse_duration(duration)
        
        # Insert mute
        cursor.execute('''
            INSERT INTO mutes (guild_id, user_id, moderator_id, reason, duration, expires_at, case_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (guild_id, user_id, moderator_id, reason, duration, expires_at, case_id))
        
        mute_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return mute_id, case_number
    
    def remove_mute(self, guild_id, user_id):
        """Remove/deactivate a mute"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        from datetime import datetime
        cursor.execute('''
            UPDATE mutes
            SET active = 0, unmuted_at = ?
            WHERE guild_id = ? AND user_id = ? AND active = 1
        ''', (datetime.utcnow(), guild_id, user_id))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected > 0
    
    def get_active_mute(self, guild_id, user_id):
        """Get active mute for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, moderator_id, reason, duration, muted_at, expires_at, case_id
            FROM mutes
            WHERE guild_id = ? AND user_id = ? AND active = 1
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            ORDER BY muted_at DESC
            LIMIT 1
        ''', (guild_id, user_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'moderator_id': row[1],
            'reason': row[2],
            'duration': row[3],
            'muted_at': row[4],
            'expires_at': row[5],
            'case_id': row[6]
        }
    
    def get_user_mutes(self, guild_id, user_id):
        """Get all mutes for a user (including inactive)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, moderator_id, reason, duration, muted_at, unmuted_at, expires_at, active, case_id
            FROM mutes
            WHERE guild_id = ? AND user_id = ?
            ORDER BY muted_at DESC
        ''', (guild_id, user_id))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'moderator_id': row[1],
            'reason': row[2],
            'duration': row[3],
            'muted_at': row[4],
            'unmuted_at': row[5],
            'expires_at': row[6],
            'active': bool(row[7]),
            'case_id': row[8]
        } for row in rows]
    
    # ==================== EMBED CONFIGURATION ====================
    
    def save_embed_config(self, guild_id, embed_type, title=None, description=None, color=None, fields=None):
        """Save or update embed configuration"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        from datetime import datetime
        
        # Check if config exists
        cursor.execute('''
            SELECT id FROM embed_configs
            WHERE guild_id = ? AND embed_type = ?
        ''', (guild_id, embed_type))
        
        exists = cursor.fetchone()
        
        if exists:
            # Update existing
            cursor.execute('''
                UPDATE embed_configs
                SET title = ?, description = ?, color = ?, fields = ?, updated_at = ?
                WHERE guild_id = ? AND embed_type = ?
            ''', (title, description, color, json.dumps(fields) if fields else None, datetime.utcnow(), guild_id, embed_type))
        else:
            # Insert new
            cursor.execute('''
                INSERT INTO embed_configs (guild_id, embed_type, title, description, color, fields)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (guild_id, embed_type, title, description, color, json.dumps(fields) if fields else None))
        
        conn.commit()
        conn.close()
        
        return True
    
    def get_embed_config(self, guild_id, embed_type):
        """Get embed configuration"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT title, description, color, fields, updated_at
            FROM embed_configs
            WHERE guild_id = ? AND embed_type = ?
        ''', (guild_id, embed_type))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'title': row[0],
            'description': row[1],
            'color': row[2],
            'fields': json.loads(row[3]) if row[3] else [],
            'updated_at': row[4]
        }
    
    def delete_embed_config(self, guild_id, embed_type):
        """Delete embed configuration (reset to default)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM embed_configs
            WHERE guild_id = ? AND embed_type = ?
        ''', (guild_id, embed_type))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected > 0
    
    def build_embed_from_config(self, guild_id, embed_type, placeholders=None):
        """
        Build discord.Embed from stored config with placeholder replacement
        
        Args:
            guild_id: Server ID
            embed_type: Type of embed (e.g., 'warnings_response')
            placeholders: Dict of placeholders to replace
        
        Returns:
            dict with embed configuration ready to create discord.Embed
        """
        import discord
        from datetime import datetime
        
        if placeholders is None:
            placeholders = {}
        
        # Get configuration from database
        config = self.get_embed_config(guild_id, embed_type)
        
        if not config:
            # No custom config - use default
            config = self.get_default_embed_config(embed_type)
        
        # Replace placeholders in title
        title = config.get('title', 'No Title') or 'No Title'
        for placeholder, value in placeholders.items():
            title = title.replace('{' + placeholder + '}', str(value))
        
        # Replace placeholders in description
        description = config.get('description', '') or ''
        for placeholder, value in placeholders.items():
            description = description.replace('{' + placeholder + '}', str(value))
        
        # Parse color
        color_raw = config.get('color', '00FF00')
        if isinstance(color_raw, str):
            try:
                color_int = int(color_raw.replace('#', ''), 16)
            except:
                color_int = 0x00FF00
        else:
            color_int = color_raw if color_raw else 0x00FF00
        
        # Create embed
        embed = discord.Embed(
            title=title,
            description=description,
            color=color_int,
            timestamp=datetime.utcnow()
        )
        
        # Add fields with placeholder replacement
        fields = config.get('fields', [])
        if isinstance(fields, str):
            fields = json.loads(fields)
        
        if fields:
            for field in fields:
                field_name = field.get('name', 'Field')
                field_value = field.get('value', '')
                
                # Replace placeholders
                for placeholder, value in placeholders.items():
                    field_name = field_name.replace('{' + placeholder + '}', str(value))
                    field_value = field_value.replace('{' + placeholder + '}', str(value))
                
                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=field.get('inline', True)
                )
        
        return embed
    
    def get_default_embed_config(self, embed_type):
        """Get hardcoded default configuration for an embed type"""
        defaults = {
            'warnings_response': {
                'title': '⚠️ Warning Issued',
                'description': 'A user has been warned.',
                'color': 'FFAA00',
                'fields': [
                    {'name': 'User', 'value': '{user} (`{user_id}`)', 'inline': True},
                    {'name': 'Moderator', 'value': '{moderator}', 'inline': True},
                    {'name': 'Case', 'value': '`#{case}`', 'inline': True},
                    {'name': 'Reason', 'value': '{reason}', 'inline': False}
                ]
            },
            'warnings_dm': {
                'title': '⚠️ You Have Been Warned',
                'description': 'You received a warning in **{server}**.',
                'color': 'FF0000',
                'fields': [
                    {'name': 'Reason', 'value': '{reason}', 'inline': False},
                    {'name': 'Duration', 'value': '`{duration}`', 'inline': True},
                    {'name': 'Expires', 'value': '{expires}', 'inline': True},
                    {'name': 'Your Warnings', 'value': '{warnings_display}', 'inline': False}
                ]
            },
            'ban_response': {
                'title': '🔨 User Banned',
                'description': 'A user has been banned from the server.',
                'color': 'FF0000',
                'fields': [
                    {'name': 'User', 'value': '{user} (`{user_id}`)', 'inline': True},
                    {'name': 'Moderator', 'value': '{moderator}', 'inline': True},
                    {'name': 'Case', 'value': '`#{case}`', 'inline': True},
                    {'name': 'Duration', 'value': '`{duration}`', 'inline': True},
                    {'name': 'Reason', 'value': '{reason}', 'inline': False}
                ]
            },
            'ban_dm': {
                'title': '🔨 You Have Been Banned',
                'description': 'You have been banned from **{server}**.',
                'color': 'FF0000',
                'fields': [
                    {'name': 'Duration', 'value': '`{duration}`', 'inline': True},
                    {'name': 'Reason', 'value': '{reason}', 'inline': False},
                    {'name': 'Appeal', 'value': 'Contact server staff if you believe this was a mistake.', 'inline': False}
                ]
            },
            'kick_response': {
                'title': '👢 User Kicked',
                'description': 'A user has been kicked from the server.',
                'color': 'FF6600',
                'fields': [
                    {'name': 'User', 'value': '{user} (`{user_id}`)', 'inline': True},
                    {'name': 'Moderator', 'value': '{moderator}', 'inline': True},
                    {'name': 'Case', 'value': '`#{case}`', 'inline': True},
                    {'name': 'Reason', 'value': '{reason}', 'inline': False}
                ]
            },
            'kick_dm': {
                'title': '👢 You Have Been Kicked',
                'description': 'You have been kicked from **{server}**.',
                'color': 'FF6600',
                'fields': [
                    {'name': 'Reason', 'value': '{reason}', 'inline': False},
                    {'name': 'Note', 'value': 'You may rejoin the server if you have an invite.', 'inline': False}
                ]
            },
            'mute_response': {
                'title': '🔇 User Muted',
                'description': 'A user has been muted.',
                'color': 'FF9900',
                'fields': [
                    {'name': 'User', 'value': '{user} (`{user_id}`)', 'inline': True},
                    {'name': 'Moderator', 'value': '{moderator}', 'inline': True},
                    {'name': 'Case', 'value': '`#{case}`', 'inline': True},
                    {'name': 'Duration', 'value': '`{duration}`', 'inline': True},
                    {'name': 'Reason', 'value': '{reason}', 'inline': False}
                ]
            },
            'mute_dm': {
                'title': '🔇 You Have Been Muted',
                'description': 'You have been muted in **{server}**.',
                'color': 'FF9900',
                'fields': [
                    {'name': 'Duration', 'value': '`{duration}`', 'inline': True},
                    {'name': 'Expires', 'value': '{expires}', 'inline': True},
                    {'name': 'Reason', 'value': '{reason}', 'inline': False}
                ]
            },
            'unmute_response': {
                'title': '🔊 User Unmuted',
                'description': 'A user has been unmuted.',
                'color': '27AE60',
                'fields': [
                    {'name': 'User', 'value': '{user} (`{user_id}`)', 'inline': True},
                    {'name': 'Moderator', 'value': '{moderator}', 'inline': True},
                    {'name': 'Reason', 'value': '{reason}', 'inline': False}
                ]
            },
            'unban_response': {
                'title': '🔓 User Unbanned',
                'description': 'A user has been unbanned.',
                'color': '27AE60',
                'fields': [
                    {'name': 'User', 'value': '{user} (`{user_id}`)', 'inline': True},
                    {'name': 'Moderator', 'value': '{moderator}', 'inline': True},
                    {'name': 'Case', 'value': '`#{case}`', 'inline': True},
                    {'name': 'Reason', 'value': '{reason}', 'inline': False}
                ]
            },
            'unban_dm': {
                'title': '🔓 You Have Been Unbanned',
                'description': 'You have been unbanned from **{server}**.',
                'color': '27AE60',
                'fields': [
                    {'name': 'Reason', 'value': '{reason}', 'inline': False},
                    {'name': 'Note', 'value': 'You may now rejoin the server with an invite.', 'inline': False}
                ]
            },
            'verify_dm': {
                'title': 'Welcome to {server}!',
                'description': '✅ Your verification was successful!\n\nBe sure to check out the rules and turn on **Show All Channels** in the server dropdown.',
                'color': '2ECC71',
                'fields': []
            }
        }
        
        return defaults.get(embed_type, {
            'title': 'Default Title',
            'description': 'Default Description',
            'color': '00FF00',
            'fields': []
        })
    
    # ==================== UTILITY METHODS ====================
    
    def _parse_duration(self, duration_str):
        """Parse duration string (1d3h, 3h, 30m) into timedelta"""
        from datetime import timedelta
        import re
        
        if not duration_str:
            return timedelta(0)
        
        # Parse format: 1d3h2m or combinations
        pattern = r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?'
        match = re.match(pattern, duration_str.lower())
        
        if not match:
            return timedelta(0)
        
        days = int(match.group(1)) if match.group(1) else 0
        hours = int(match.group(2)) if match.group(2) else 0
        minutes = int(match.group(3)) if match.group(3) else 0
        
        return timedelta(days=days, hours=hours, minutes=minutes)
    
    def format_duration(self, duration_str):
        """Format duration string for display"""
        td = self._parse_duration(duration_str)
        
        parts = []
        if td.days > 0:
            parts.append(f"{td.days}d")
        hours = td.seconds // 3600
        if hours > 0:
            parts.append(f"{hours}h")
        minutes = (td.seconds % 3600) // 60
        if minutes > 0:
            parts.append(f"{minutes}m")
        
        return ' '.join(parts) if parts else '0m'
    
    def is_valid_duration(self, duration_str, max_days=None):
        """Check if duration string is valid and within limits"""
        import re
        
        pattern = r'^\d+[dhm](?:\d+[dhm])*$'
        if not re.match(pattern, duration_str.lower()):
            return False
        
        if max_days:
            td = self._parse_duration(duration_str)
            if td.days > max_days:
                return False
        
        return True


    # ==================== BACKUP SYSTEM ====================
    
    def create_backup(self, guild_id, backup_name, backup_data):
        """Create a new backup"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        import json
        from datetime import datetime
        import uuid
        
        backup_id = str(uuid.uuid4())[:8]  # Short ID
        
        cursor.execute('''
            INSERT INTO backups (backup_id, guild_id, backup_name, backup_data, created_at, locked)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (backup_id, guild_id, backup_name, json.dumps(backup_data), datetime.utcnow().isoformat(), 0))
        
        conn.commit()
        conn.close()
        
        return backup_id
    
    def get_server_backups(self, guild_id):
        """Get all backups for a server"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT backup_id, backup_name, created_at, locked
            FROM backups
            WHERE guild_id = ?
            ORDER BY created_at DESC
        ''', (guild_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'name': row[1],
            'created_at': row[2],
            'locked': bool(row[3])
        } for row in rows]
    
    def get_backup(self, guild_id, backup_id):
        """Get a specific backup"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        import json
        
        cursor.execute('''
            SELECT backup_id, backup_name, backup_data, created_at, locked
            FROM backups
            WHERE guild_id = ? AND backup_id = ?
        ''', (guild_id, backup_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'data': json.loads(row[2]),
                'created_at': row[3],
                'locked': bool(row[4])
            }
        return None
    
    def delete_backup(self, guild_id, backup_id):
        """Delete a backup"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if locked
        cursor.execute('''
            SELECT locked FROM backups
            WHERE guild_id = ? AND backup_id = ?
        ''', (guild_id, backup_id))
        
        row = cursor.fetchone()
        if not row or row[0]:
            conn.close()
            return False  # Doesn't exist or is locked
        
        cursor.execute('''
            DELETE FROM backups
            WHERE guild_id = ? AND backup_id = ?
        ''', (guild_id, backup_id))
        
        conn.commit()
        conn.close()
        return True
    
    def set_backup_lock(self, guild_id, backup_id, locked):
        """Set backup lock status"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE backups
            SET locked = ?
            WHERE guild_id = ? AND backup_id = ?
        ''', (1 if locked else 0, guild_id, backup_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def set_backup_auto(self, guild_id, enabled):
        """Set auto-backup status"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        from datetime import datetime
        
        cursor.execute('''
            INSERT OR REPLACE INTO backup_settings (guild_id, auto_backup, updated_at)
            VALUES (?, ?, ?)
        ''', (guild_id, 1 if enabled else 0, datetime.utcnow().isoformat()))
        
        conn.commit()
        conn.close()
    
    def set_backup_autooverwrite(self, guild_id, enabled):
        """Set auto-overwrite status"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        from datetime import datetime
        
        cursor.execute('''
            INSERT OR REPLACE INTO backup_settings (guild_id, auto_overwrite, updated_at)
            VALUES (?, ?, ?)
        ''', (guild_id, 1 if enabled else 0, datetime.utcnow().isoformat()))
        
        conn.commit()
        conn.close()

    # ==================== PERMISSION PRESETS ====================
    
    def save_channel_preset(self, guild_id, preset_name, preset_data):
        """Save a channel permission preset"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        import json
        from datetime import datetime
        
        # Check if preset exists
        cursor.execute('''
            SELECT id FROM channel_presets
            WHERE guild_id = ? AND preset_name = ?
        ''', (guild_id, preset_name))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing
            cursor.execute('''
                UPDATE channel_presets
                SET preset_data = ?, created_at = ?
                WHERE id = ?
            ''', (json.dumps(preset_data), datetime.utcnow().isoformat(), existing[0]))
        else:
            # Create new
            cursor.execute('''
                INSERT INTO channel_presets (guild_id, preset_name, preset_data, created_at)
                VALUES (?, ?, ?, ?)
            ''', (guild_id, preset_name, json.dumps(preset_data), datetime.utcnow().isoformat()))
        
        conn.commit()
        conn.close()
        return True
    
    def get_channel_preset(self, guild_id, preset_name):
        """Get a channel permission preset"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        import json
        
        cursor.execute('''
            SELECT preset_name, preset_data, created_at
            FROM channel_presets
            WHERE guild_id = ? AND preset_name = ?
        ''', (guild_id, preset_name))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'name': row[0],
                'data': json.loads(row[1]),
                'created_at': row[2]
            }
        return None
    
    def list_channel_presets(self, guild_id):
        """List all channel presets for a guild"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT preset_name, created_at
            FROM channel_presets
            WHERE guild_id = ?
            ORDER BY created_at DESC
        ''', (guild_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'name': row[0],
            'created_at': row[1]
        } for row in rows]
    
    def delete_channel_preset(self, guild_id, preset_name):
        """Delete a channel preset"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM channel_presets
            WHERE guild_id = ? AND preset_name = ?
        ''', (guild_id, preset_name))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    # ==================== COMPREHENSIVE BACKUP METHODS ====================
    
    def save_comprehensive_backup(self, guild_id, backup_id, backup_name, backup_data):
        """Save a comprehensive backup"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Count items for metadata
        roles_count = len(backup_data.get('roles', []))
        channels_count = len(backup_data.get('channels', [])) + len(backup_data.get('categories', []))
        emojis_count = len(backup_data.get('emojis', []))
        stickers_count = len(backup_data.get('stickers', []))
        file_size = backup_data.get('file_size_bytes', 0)
        imported_from = backup_data.get('imported_from')
        
        # Check if exists
        cursor.execute('SELECT id FROM comprehensive_backups WHERE backup_id = ?', (backup_id,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute('''
                UPDATE comprehensive_backups
                SET backup_name = ?, backup_data = ?, file_size_bytes = ?,
                    roles_count = ?, channels_count = ?, emojis_count = ?, stickers_count = ?
                WHERE backup_id = ?
            ''', (backup_name, json.dumps(backup_data), file_size, roles_count, 
                  channels_count, emojis_count, stickers_count, backup_id))
        else:
            cursor.execute('''
                INSERT INTO comprehensive_backups 
                (backup_id, guild_id, backup_name, backup_data, file_size_bytes,
                 roles_count, channels_count, emojis_count, stickers_count, imported_from, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (backup_id, guild_id, backup_name, json.dumps(backup_data), file_size,
                  roles_count, channels_count, emojis_count, stickers_count, imported_from,
                  datetime.utcnow()))
        
        conn.commit()
        conn.close()
        return True
    
    def get_comprehensive_backup(self, guild_id, backup_id):
        """Get a comprehensive backup by ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT backup_data FROM comprehensive_backups
            WHERE guild_id = ? AND backup_id = ?
        ''', (guild_id, backup_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def find_backup_by_id(self, backup_id):
        """Find a backup by ID from any guild (for import)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT backup_data FROM comprehensive_backups
            WHERE backup_id = ?
        ''', (backup_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def list_comprehensive_backups(self, guild_id):
        """List all comprehensive backups for a guild"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT backup_id, backup_name, file_size_bytes, roles_count, channels_count,
                   emojis_count, stickers_count, imported_from, created_at, locked
            FROM comprehensive_backups
            WHERE guild_id = ?
            ORDER BY created_at DESC
        ''', (guild_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'backup_id': row[0],
            'name': row[1],
            'file_size_bytes': row[2],
            'roles_count': row[3],
            'channels_count': row[4],
            'emojis_count': row[5],
            'stickers_count': row[6],
            'imported_from': row[7],
            'created_at': row[8],
            'locked': bool(row[9])
        } for row in rows]
    
    def delete_comprehensive_backup(self, guild_id, backup_id):
        """Delete a comprehensive backup"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM comprehensive_backups
            WHERE guild_id = ? AND backup_id = ?
        ''', (guild_id, backup_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def lock_comprehensive_backup(self, guild_id, backup_id, locked=True):
        """Lock or unlock a comprehensive backup"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE comprehensive_backups
            SET locked = ?
            WHERE guild_id = ? AND backup_id = ?
        ''', (locked, guild_id, backup_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    # ==================== v2.0.9 NEW METHODS ====================
    
    # ==================== MOD NOTES ====================
    
    def add_mod_note(self, guild_id, user_id, note, created_by):
        """Add a mod note for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO mod_notes (guild_id, user_id, note, created_by)
            VALUES (?, ?, ?, ?)
        ''', (guild_id, user_id, note, created_by))
        
        note_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return note_id
    
    def get_mod_notes(self, guild_id, user_id):
        """Get all mod notes for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, note, created_by, created_at
            FROM mod_notes
            WHERE guild_id = ? AND user_id = ?
            ORDER BY created_at DESC
        ''', (guild_id, user_id))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'note': row[1],
            'created_by': row[2],
            'created_at': row[3]
        } for row in rows]
    
    def delete_mod_notes(self, guild_id, user_id):
        """Delete all mod notes for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM mod_notes WHERE guild_id = ? AND user_id = ?', (guild_id, user_id))
        
        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count
    
    # ==================== CHANNEL LOCKS ====================
    
    def save_channel_lock(self, guild_id, channel_id, lock_type, saved_permissions, locked_by):
        """Save channel lock with previous permissions"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO channel_locks (guild_id, channel_id, lock_type, saved_permissions, locked_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (guild_id, channel_id, lock_type, json.dumps(saved_permissions), locked_by))
        
        conn.commit()
        conn.close()
        return True
    
    def get_channel_lock(self, guild_id, channel_id, lock_type):
        """Get saved channel lock data"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT saved_permissions, locked_at, locked_by
            FROM channel_locks
            WHERE guild_id = ? AND channel_id = ? AND lock_type = ?
        ''', (guild_id, channel_id, lock_type))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'saved_permissions': json.loads(row[0]) if row[0] else {},
            'locked_at': row[1],
            'locked_by': row[2]
        }
    
    def delete_channel_lock(self, guild_id, channel_id, lock_type):
        """Delete channel lock record"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM channel_locks WHERE guild_id = ? AND channel_id = ? AND lock_type = ?',
                      (guild_id, channel_id, lock_type))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    # ==================== VOICE PUNISHMENTS ====================
    
    def add_voice_punishment(self, guild_id, user_id, punishment_type, reason, duration, expires_at, moderator_id, case_id):
        """Add a voice channel punishment"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO voice_punishments (guild_id, user_id, punishment_type, reason, duration, expires_at, moderator_id, case_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (guild_id, user_id, punishment_type, reason, duration, expires_at, moderator_id, case_id))
        
        punishment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return punishment_id
    
    def get_active_voice_punishment(self, guild_id, user_id, punishment_type):
        """Get active voice punishment for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, reason, duration, expires_at, applied_at, moderator_id, case_id
            FROM voice_punishments
            WHERE guild_id = ? AND user_id = ? AND punishment_type = ? AND active = 1
            AND (expires_at IS NULL OR expires_at > datetime('now'))
        ''', (guild_id, user_id, punishment_type))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'reason': row[1],
            'duration': row[2],
            'expires_at': row[3],
            'applied_at': row[4],
            'moderator_id': row[5],
            'case_id': row[6]
        }
    
    def remove_voice_punishment(self, guild_id, user_id, punishment_type):
        """Remove/deactivate a voice punishment"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE voice_punishments SET active = 0
            WHERE guild_id = ? AND user_id = ? AND punishment_type = ? AND active = 1
        ''', (guild_id, user_id, punishment_type))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    # ==================== MODERATION LOGS ====================
    
    def add_mod_log(self, guild_id, action_type, user_id, moderator_id, case_id=None, reason=None, duration=None, details=None):
        """Add a moderation log entry"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO moderation_logs (guild_id, action_type, user_id, moderator_id, case_id, reason, duration, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (guild_id, action_type, user_id, moderator_id, case_id, reason, duration, json.dumps(details) if details else None))
        
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id
    
    def get_mod_logs(self, guild_id, user_id=None, duration_hours=None, limit=100):
        """Get moderation logs"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT id, action_type, user_id, moderator_id, case_id, reason, duration, details, timestamp FROM moderation_logs WHERE guild_id = ?'
        params = [guild_id]
        
        if user_id:
            query += ' AND user_id = ?'
            params.append(user_id)
        
        if duration_hours:
            query += f" AND timestamp > datetime('now', '-{int(duration_hours)} hours')"
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'action_type': row[1],
            'user_id': row[2],
            'moderator_id': row[3],
            'case_id': row[4],
            'reason': row[5],
            'duration': row[6],
            'details': json.loads(row[7]) if row[7] else None,
            'timestamp': row[8]
        } for row in rows]
    
    # ==================== PERMISSIONS ====================
    
    def assign_permission(self, guild_id, permission_id, user_id=None, role_id=None, assigned_by=None):
        """Assign a permission to a user or role"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO permission_assignments (guild_id, user_id, role_id, permission_id, assigned_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (guild_id, user_id, role_id, permission_id, assigned_by))
            conn.commit()
            success = True
        except sqlite3.IntegrityError:
            success = False  # Already exists
        
        conn.close()
        return success
    
    def remove_permission(self, guild_id, permission_id, user_id=None, role_id=None):
        """Remove a permission from a user or role"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('DELETE FROM permission_assignments WHERE guild_id = ? AND user_id = ? AND permission_id = ?',
                          (guild_id, user_id, permission_id))
        elif role_id:
            cursor.execute('DELETE FROM permission_assignments WHERE guild_id = ? AND role_id = ? AND permission_id = ?',
                          (guild_id, role_id, permission_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def has_permission(self, guild_id, user_id, permission_id):
        """Check if a user has a specific permission"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 1 FROM permission_assignments
            WHERE guild_id = ? AND user_id = ? AND permission_id = ?
        ''', (guild_id, user_id, permission_id))
        
        has_perm = cursor.fetchone() is not None
        conn.close()
        return has_perm
    
    def role_has_permission(self, guild_id, role_id, permission_id):
        """Check if a role has a specific permission"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 1 FROM permission_assignments
            WHERE guild_id = ? AND role_id = ? AND permission_id = ?
        ''', (guild_id, role_id, permission_id))
        
        has_perm = cursor.fetchone() is not None
        conn.close()
        return has_perm
    
    def get_user_permissions(self, guild_id, user_id):
        """Get all permissions for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT permission_id FROM permission_assignments
            WHERE guild_id = ? AND user_id = ?
        ''', (guild_id, user_id))
        
        perms = [row[0] for row in cursor.fetchall()]
        conn.close()
        return perms
    
    def get_role_permissions(self, guild_id, role_id):
        """Get all permissions for a role"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT permission_id FROM permission_assignments
            WHERE guild_id = ? AND role_id = ?
        ''', (guild_id, role_id))
        
        perms = [row[0] for row in cursor.fetchall()]
        conn.close()
        return perms
    
    def get_all_permissions(self, guild_id):
        """Get all permission assignments for a guild"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, role_id, permission_id, assigned_by, assigned_at
            FROM permission_assignments
            WHERE guild_id = ?
        ''', (guild_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'user_id': row[0],
            'role_id': row[1],
            'permission_id': row[2],
            'assigned_by': row[3],
            'assigned_at': row[4]
        } for row in rows]
    
    # ==================== PERMISSION GROUPS ====================
    
    def create_permission_group(self, guild_id, group_name):
        """Create a permission group"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('INSERT INTO permission_groups (guild_id, group_name) VALUES (?, ?)',
                          (guild_id, group_name))
            group_id = cursor.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            group_id = None  # Already exists
        
        conn.close()
        return group_id
    
    def add_permission_to_group(self, group_id, permission_id):
        """Add a permission to a group"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('INSERT INTO group_permissions (group_id, permission_id) VALUES (?, ?)',
                      (group_id, permission_id))
        
        conn.commit()
        conn.close()
        return True
    
    def get_group_permissions(self, guild_id, group_name):
        """Get all permissions in a group"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT gp.permission_id
            FROM group_permissions gp
            JOIN permission_groups pg ON gp.group_id = pg.id
            WHERE pg.guild_id = ? AND pg.group_name = ?
        ''', (guild_id, group_name))
        
        perms = [row[0] for row in cursor.fetchall()]
        conn.close()
        return perms
    
    def get_permission_group_id(self, guild_id, group_name):
        """Get group ID by name"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM permission_groups WHERE guild_id = ? AND group_name = ?',
                      (guild_id, group_name))
        
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    
    def list_permission_groups(self, guild_id):
        """List all permission groups for a guild"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, group_name, created_at FROM permission_groups WHERE guild_id = ?', (guild_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'name': row[1],
            'created_at': row[2]
        } for row in rows]
    
    # ==================== USER PUNISHMENTS (for ;punishments command) ====================
    
    def get_all_user_punishments(self, guild_id, user_id):
        """Get ALL punishments for a user across all types"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get from cases table
        cursor.execute('''
            SELECT case_id, case_type, reason, duration, created_at, moderator_id, metadata
            FROM cases
            WHERE guild_id = ? AND user_id = ?
            ORDER BY created_at DESC
        ''', (guild_id, user_id))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'case_id': row[0],
            'type': row[1],
            'reason': row[2],
            'duration': row[3],
            'created_at': row[4],
            'moderator_id': row[5],
            'metadata': json.loads(row[6]) if row[6] else None
        } for row in rows]
