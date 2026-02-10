"""
BlockForge OS Configuration Example
Copy this file and customize it for your needs
"""

class Config:
    """Bot configuration settings"""
    
    # ==========================================
    # REQUIRED SETTINGS
    # ==========================================
    
    # Your Discord Bot Token
    # Get it from: https://discord.com/developers/applications
    TOKEN = 'YOUR_BOT_TOKEN_HERE'
    
    # Bot Version (displayed in terminal header)
    VERSION = '1.5.6-DEV'
    
    # ==========================================
    # TERMINAL SETTINGS
    # ==========================================
    
    # Maximum characters before creating a new message
    # Discord limit is 2000, we use 1800 to be safe
    MAX_MESSAGE_LENGTH = 1800
    
    # How long before a session times out (in seconds)
    # 3600 = 1 hour
    SESSION_TIMEOUT = 3600
    
    # ==========================================
    # DATABASE SETTINGS
    # ==========================================
    
    # Path to SQLite database file
    # Will be created automatically if it doesn't exist
    DATABASE_PATH = 'data/bfos.db'
    
    # ==========================================
    # PERMISSION SETTINGS
    # ==========================================
    
    # Require administrator permissions to use BFOS
    # Set to False to allow all users
    REQUIRE_ADMIN = True
    
    # Allow specific user IDs to bypass permission checks
    # Example: ALLOWED_USERS = [123456789012345678, 987654321098765432]
    ALLOWED_USERS = []
    
    # ==========================================
    # ERROR CODES
    # ==========================================
    
    ERROR_CODES = {
        'INVALID_COMMAND': '0x0001',     # Unknown command
        'PERMISSION_DENIED': '0x0002',    # Insufficient permissions
        'SESSION_ACTIVE': '0x0003',       # User already has session
        'DATABASE_ERROR': '0x0004',       # Database operation failed
        'INVALID_INPUT': '0x0005',        # Invalid user input
        'COMMAND_FAILED': '0x0006',       # Command execution failed
        'SETUP_INCOMPLETE': '0x0007',     # Server setup not complete
        'CHANNEL_NOT_FOUND': '0x0008',    # Channel not found
        'RATE_LIMITED': '0x0009',         # Too many requests
        'UNKNOWN_ERROR': '0x00FF'         # Unknown error
    }
    
    # ==========================================
    # COMMAND DESCRIPTIONS
    # ==========================================
    
    COMMANDS = {
        'ping': 'Display bot latency and connection status',
        'exit': 'Exit the terminal and save all changes',
        'clr': 'Clear the terminal and delete all session messages',
        'version': 'Display BlockForge OS version information',
        'help': 'Display list of available commands'
    }
    
    # ==========================================
    # LOADING ANIMATION
    # ==========================================
    
    # Messages shown during boot sequence
    LOADING_MESSAGES = [
        "Initializing BlockForge OS...",
        "Loading system modules...",
        "Establishing secure connection...",
        "Validating permissions...",
        "Loading user interface...",
        "Finalizing setup...",
        "Ready!"
    ]
    
    # ==========================================
    # STYLING OPTIONS
    # ==========================================
    
    # Show mobile warning when user opens terminal
    SHOW_MOBILE_WARNING = True
    
    # Delay before showing mobile warning (seconds)
    MOBILE_WARNING_DELAY = 3
    
    # Show loading animation
    SHOW_LOADING_ANIMATION = True
    
    # Loading animation speed (seconds between updates)
    LOADING_ANIMATION_SPEED = 0.5
    
    # Delay at end of loading before showing menu (seconds)
    LOADING_FINAL_DELAY = 2
    
    # ==========================================
    # ADVANCED SETTINGS
    # ==========================================
    
    # Enable debug mode (more verbose logging)
    DEBUG_MODE = False
    
    # Log all commands to console
    LOG_COMMANDS = True
    
    # Auto-save interval (seconds)
    # Set to 0 to disable auto-save
    AUTO_SAVE_INTERVAL = 0
    
    # Maximum number of concurrent sessions per user
    MAX_SESSIONS_PER_USER = 1
    
    # Enable command cooldown (seconds)
    COMMAND_COOLDOWN = 0
