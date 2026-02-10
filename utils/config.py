"""
BlockForge OS Configuration
Store your bot token and other settings here
"""
import os
from pathlib import Path

# Load .env file
_env_path = Path(__file__).resolve().parent.parent / '.env'
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _key, _val = _line.split('=', 1)
                os.environ.setdefault(_key.strip(), _val.strip())

class Config:
    """Bot configuration settings"""

    # Bot token - loaded from .env file (BFOS_TOKEN)
    TOKEN = os.environ.get('BFOS_TOKEN', '')
    
    # Bot version
    VERSION = '2.2.0'
    
    # ==========================================
    # BOT OWNER & STAFF SETTINGS
    # ==========================================
    
    # Bot Owner ID - Has access to everything everywhere
    BOT_OWNER_ID = 887845200502882304
    
    # BlockForge Studios Guild ID (for blacklist appeals)
    BLOCKFORGE_GUILD_ID = 1131588549892907089
    
    # Bot Staff Roles Hierarchy (highest to lowest)
    STAFF_ROLES = ['OWNER', 'EXECUTIVE', 'MANAGER', 'ADMIN', 'HEAD MODERATOR', 'MODERATOR', 'ANALYST']
    STAFF_AI_ACCESS = ['OWNER', 'EXECUTIVE', 'MANAGER', 'ADMIN', 'HEAD MODERATOR']  # Can use AI slash commands
    
    # ==========================================
    # AI CONFIGURATION
    # ==========================================
    
    # Ollama Server Configuration
    AI_CONFIG = {
        'host': os.environ.get('OLLAMA_HOST', 'http://localhost:11434'),
    }
    
    # Default AI model
    DEFAULT_AI_MODEL = 'echo'
    
    # AI Rate Limits (per user)
    AI_RATE_LIMITS = {
        'echo': {'requests': 30, 'period': 60},
        'sage': {'requests': 10, 'period': 60},
        'scorcher': {'requests': 20, 'period': 60},
        'scout': {'requests': 15, 'period': 60},
    }
    
    # AI Models Info
    AI_MODELS = {
        'echo': {
            'name': 'Echo',
            'description': 'Gen-Z chat friend',
            'ollama_model': 'gemma3:27b-cloud',
            'is_cloud': True
        },
        'sage': {
            'name': 'Sage',
            'description': 'Deep thinker with reasoning',
            'ollama_model': 'qwen3-next:80b-cloud',
            'is_cloud': True
        },
        'scorcher': {
            'name': 'Scorcher',
            'description': 'Roast master',
            'ollama_model': 'seangustavson/RoastLlama',
            'is_cloud': False
        },
        'scout': {
            'name': 'Scout',
            'description': 'Internet-connected AI',
            'ollama_model': 'llama3.1:8b',
            'is_cloud': False
        },
        'lens': {
            'name': 'Lens',
            'description': 'Image description',
            'ollama_model': 'llava:7b',
            'is_cloud': False
        }
    }
    
    # Terminal settings
    MAX_MESSAGE_LENGTH = 1800  # Maximum characters before creating new message
    SESSION_TIMEOUT = 3600  # Session timeout in seconds (1 hour)
    
    # Database settings
    DATABASE_PATH = 'data/bfos.db'
    
    # Permissions
    REQUIRE_ADMIN = True  # Require admin permissions to use BFOS
    
    # Error codes
    ERROR_CODES = {
        'INVALID_COMMAND': '0xDEAD',
        'PERMISSION_DENIED': '0xACCE',
        'SESSION_ACTIVE': '0xBUSY',
        'DATABASE_ERROR': '0xDB01',
        'INVALID_INPUT': '0xBAD1',
        'COMMAND_FAILED': '0xFA11',
        'SETUP_INCOMPLETE': '0x5E7F',
        'CHANNEL_NOT_FOUND': '0xCHA1',
        'RATE_LIMITED': '0x5LOW',
        'MODULE_NOT_FOUND': '0xMOD1',
        'MODULE_ALREADY_ENABLED': '0xMOD2',
        'MODULE_ALREADY_DISABLED': '0xMOD3',
        'INVALID_MODULE': '0xMOD4',
        'MEMBER_NOT_FOUND': '0xUSER',
        'INVALID_DURATION': '0xT1ME',
        'CASE_NOT_FOUND': '0xCASE',
        'MODULE_DISABLED': '0xOFF1',
        'INVALID_PREFIX': '0xPREF',
        'ROLE_NOT_FOUND': '0xROLE',
        'STAFF_NOT_FOUND': '0x5TAF',
        'STAFF_EXISTS': '0x5TA2',
        'INVALID_STAFF_ID': '0x5TA3',
        'CONFIRMATION_REQUIRED': '0xCONF',
        'CANCELLED': '0xCANC',
        'UNKNOWN_ERROR': '0xDEAF'
    }
    
    # Available modules
    MODULES = {
        'automod': {
            'name': 'Auto Moderation',
            'description': 'Automatic moderation features',
            'placeholder': True,
            'configurable': False
        },
        'commands': {
            'name': 'Custom Commands',
            'description': 'Create custom server commands',
            'placeholder': True,
            'configurable': False
        },
        'bans': {
            'name': 'Ban System',
            'description': 'Ban and unban members',
            'placeholder': False,
            'configurable': False
        },
        'kicks': {
            'name': 'Kick System',
            'description': 'Kick members from server',
            'placeholder': False,
            'configurable': False
        },
        'warns': {
            'name': 'Warning System',
            'description': 'Warn members and auto-punish',
            'placeholder': False,
            'configurable': True
        },
        'mutes': {
            'name': 'Mute System',
            'description': 'Timeout/mute members',
            'placeholder': False,
            'configurable': False
        },
        'embeds': {
            'name': 'Embed Configuration',
            'description': 'Customize moderation embeds',
            'placeholder': False,
            'configurable': True
        },
        'logging': {
            'name': 'Server Logging',
            'description': 'Comprehensive server event logging',
            'placeholder': False,
            'configurable': True
        },
        'purges': {
            'name': 'Message Purger',
            'description': 'Advanced message purging with filters',
            'placeholder': False,
            'configurable': False
        },
        'verification': {
            'name': 'Verification System',
            'description': 'Require users to verify before accessing server',
            'placeholder': False,
            'configurable': True
        },
        'tickets': {
            'name': 'Ticket System',
            'description': 'Support ticket system with categories and transcripts',
            'placeholder': False,
            'configurable': True
        },
        'xp': {
            'name': 'XP & Leveling',
            'description': 'XP tracking, levels, leaderboards, and role rewards',
            'placeholder': False,
            'configurable': True
        }
    }

    # Default module states
    DEFAULT_MODULES = {
        'automod': False,
        'commands': False,
        'bans': False,
        'kicks': False,
        'warns': False,
        'mutes': False,
        'embeds': False,
        'logging': False,
        'purges': False,
        'verification': False,
        'tickets': False,
        'xp': False
    }
    
    # Default command prefix for moderation commands
    DEFAULT_PREFIX = ';'
    
    # Command descriptions
    COMMANDS = {
        'ping': 'Display bot latency and connection status',
        'exit': 'Exit the terminal and save all changes',
        'clr': 'Clear the terminal and delete all session messages',
        'version': 'Display BlockForge OS version information',
        'help': 'Display list of available commands',
        'modules': 'Open modules management panel',
        'config': 'Open configuration panel',
        'security': 'Open security panel (verification, lockdown)',
        'staff': 'Open staff management panel',
        'management': 'Open server management (channels, backups)',
        'ai': 'Open AI management panel',
        'tickets': 'Open ticket system configuration',
        'xp': 'Open XP & Leveling configuration',
        'test': 'Open test panel for previewing configurations'
    }
    
    # Module panel commands
    MODULE_COMMANDS = {
        'help': 'Display module commands',
        'back': 'Return to main menu',
        'exit': 'Exit terminal and save changes',
        'module list': 'List all modules and their status',
        'module enable': 'Enable a module (module enable <name>)',
        'module disable': 'Disable a module (module disable <name>)',
        'module configure': 'Configure a module (module configure <name>)'
    }
    
    # Config panel commands
    CONFIG_COMMANDS = {
        'help': 'Display configuration commands',
        'back': 'Return to main menu',
        'exit': 'Exit terminal and save changes',
        'prefix': 'Set command prefix (prefix <new_prefix>)',
        'prefix show': 'Show current command prefix',
        'clearsettings': 'Clear all server settings (requires confirmation)',
        'embeds': 'Open embed configuration panel',
        'logging': 'Open logging configuration panel',
        'settings': 'Show all settings',
        'settings cnf on/off': 'Toggle command not found messages'
    }
    
    # Staff panel commands
    STAFF_COMMANDS = {
        'help': 'Display staff commands',
        'back': 'Return to main menu',
        'exit': 'Exit terminal and save changes',
        'staff import': 'Import role(s) (staff import <role_id> [role_id...])',
        'staff rename': 'Rename staff role (staff rename <id> <name>)',
        'staff list': 'List all staff roles',
        'staff delete': 'Delete staff role (staff delete <id>)',
        'staff add': 'Add staff to user (staff add <user_id> <staff_id>)',
        'staff remove': 'Remove all staff from user (staff remove <user_id>)',
        'staff sync': 'Sync Discord roles with database (fixes mismatches)'
    }
    
    # Test panel commands
    TEST_COMMANDS = {
        'help': 'Display test commands',
        'back': 'Return to main menu',
        'exit': 'Exit terminal and save changes',
        'embed list': 'List all configured embeds',
        'embed preview': 'Preview an embed (embed preview <id>)'
    }
    
    # Embed panel commands
    EMBED_COMMANDS = {
        'help': 'Display embed commands',
        'back': 'Return to configuration',
        'exit': 'Exit terminal and save changes',
        'list': 'List all configured embeds',
        'edit': 'Edit an embed (edit <id>)',
        'preview': 'Preview an embed (preview <id>)',
        'reset': 'Reset embed to default (reset <id>)'
    }
    
    # Loading messages for boot sequence
    LOADING_MESSAGES = [
        "Initializing BlockForge OS...",
        "Loading system modules...",
        "Establishing secure connection...",
        "Validating permissions...",
        "Loading user interface...",
        "Finalizing setup...",
        "Ready!"
    ]