"""
ANSI Color Codes and Formatting Utilities for BFOS
Provides colors and styling for terminal-style Discord embeds
"""

import random


class Colors:
    """Terminal color codes for console output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Basic colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'


class ANSIColors:
    """ANSI color codes for Discord code blocks"""
    # These work in Discord's ANSI code blocks
    RESET = '\u001b[0m'
    BOLD = '\u001b[1m'
    UNDERLINE = '\u001b[4m'
    
    # Text colors
    BLACK = '\u001b[30m'
    RED = '\u001b[31m'
    GREEN = '\u001b[32m'
    YELLOW = '\u001b[33m'
    BLUE = '\u001b[34m'
    MAGENTA = '\u001b[35m'
    CYAN = '\u001b[36m'
    WHITE = '\u001b[37m'
    
    # Bright text colors
    BRIGHT_BLACK = '\u001b[30;1m'
    BRIGHT_RED = '\u001b[31;1m'
    BRIGHT_GREEN = '\u001b[32;1m'
    BRIGHT_YELLOW = '\u001b[33;1m'
    BRIGHT_BLUE = '\u001b[34;1m'
    BRIGHT_MAGENTA = '\u001b[35;1m'
    BRIGHT_CYAN = '\u001b[36;1m'
    BRIGHT_WHITE = '\u001b[37;1m'
    
    # Background colors
    BG_BLACK = '\u001b[40m'
    BG_RED = '\u001b[41m'
    BG_GREEN = '\u001b[42m'
    BG_YELLOW = '\u001b[43m'
    BG_BLUE = '\u001b[44m'
    BG_MAGENTA = '\u001b[45m'
    BG_CYAN = '\u001b[46m'
    BG_WHITE = '\u001b[47m'
    
    # Bright background colors
    BG_BRIGHT_BLACK = '\u001b[40;1m'
    BG_BRIGHT_RED = '\u001b[41;1m'
    BG_BRIGHT_GREEN = '\u001b[42;1m'
    BG_BRIGHT_YELLOW = '\u001b[43;1m'
    BG_BRIGHT_BLUE = '\u001b[44;1m'
    BG_BRIGHT_MAGENTA = '\u001b[45;1m'
    BG_BRIGHT_CYAN = '\u001b[46;1m'
    BG_BRIGHT_WHITE = '\u001b[47;1m'


# =============================================================================
# FORMATTING FUNCTIONS - Required by terminal.py
# =============================================================================

def format_ansi(text):
    """Wrap text in ANSI code block for Discord"""
    return f"```ansi\n{text}\n```"


def format_error(error_msg, error_code):
    """Format an error message with code"""
    return f"{ANSIColors.RED}Error: {error_msg} {ANSIColors.BRIGHT_BLACK}(ERR-{error_code}){ANSIColors.RESET}"


def format_success(msg):
    """Format a success message"""
    return f"{ANSIColors.GREEN}{msg}{ANSIColors.RESET}"


def format_warning(msg):
    """Format a warning message"""
    return f"{ANSIColors.YELLOW}⚠ {msg}{ANSIColors.RESET}"


def format_info(msg):
    """Format an info message"""
    return f"{ANSIColors.CYAN}[INFO] {msg}{ANSIColors.RESET}"


def create_header(version, elapsed_time):
    """Create the terminal header"""
    header = f"""{ANSIColors.BRIGHT_GREEN}BlockForge OS {ANSIColors.BRIGHT_BLACK}Version {version} {ANSIColors.YELLOW}| Time Elapsed: {elapsed_time}s{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Type 'EXIT' to close this terminal.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}{'─' * 55}{ANSIColors.RESET}"""
    return header


def create_loading_bar(percentage, width=30):
    """Create a loading bar with percentage"""
    filled = int((percentage / 100) * width)
    bar = '█' * filled + '░' * (width - filled)
    
    # Color based on percentage
    if percentage < 30:
        color = ANSIColors.RED
    elif percentage < 70:
        color = ANSIColors.YELLOW
    else:
        color = ANSIColors.GREEN
    
    return f"{color}[{bar}] {percentage}%{ANSIColors.RESET}"


def create_color_squares():
    """Create random colored squares for loading animation"""
    colors = [
        ANSIColors.BG_RED,
        ANSIColors.BG_GREEN,
        ANSIColors.BG_YELLOW,
        ANSIColors.BG_BLUE,
        ANSIColors.BG_MAGENTA,
        ANSIColors.BG_CYAN
    ]
    
    squares = ''.join([f"{random.choice(colors)}  {ANSIColors.RESET}" for _ in range(10)])
    return squares


def format_command_prompt(path="System > Root"):
    """Format the command prompt"""
    return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.GREEN}{path}{ANSIColors.RESET} > "


def format_command_output(command, path="System > Root"):
    """Format a command with its output path"""
    prompt = format_colored_path(path)
    return f"{prompt} > {ANSIColors.WHITE}{command}{ANSIColors.RESET}"


def format_colored_path(path):
    """Format path with unique colors for each panel"""
    # Normalize path - always use "Config" consistently  
    path = path.replace("Configuration", "Config")
    
    # Define color mappings for different panels
    if "Config" in path:
        if "Embeds" in path:
            return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.YELLOW}Config{ANSIColors.RESET} > {ANSIColors.BRIGHT_MAGENTA}Embeds{ANSIColors.RESET}"
        elif "Logging" in path:
            return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.YELLOW}Config{ANSIColors.RESET} > {ANSIColors.BRIGHT_BLUE}Logging{ANSIColors.RESET}"
        elif "Warns" in path:
            return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.YELLOW}Config{ANSIColors.RESET} > {ANSIColors.BRIGHT_RED}Warns{ANSIColors.RESET}"
        return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.YELLOW}Config{ANSIColors.RESET}"
    elif "Management" in path:
        if "Channels" in path:
            return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.BRIGHT_BLUE}Management{ANSIColors.RESET} > {ANSIColors.BRIGHT_CYAN}Channels{ANSIColors.RESET}"
        elif "Backup" in path:
            return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.BRIGHT_BLUE}Management{ANSIColors.RESET} > {ANSIColors.BRIGHT_YELLOW}Backup{ANSIColors.RESET}"
        return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.BRIGHT_BLUE}Management{ANSIColors.RESET}"
    elif "Modules" in path:
        if "Warns" in path:
            return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.CYAN}Modules{ANSIColors.RESET} > {ANSIColors.BRIGHT_RED}Warns{ANSIColors.RESET}"
        return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.CYAN}Modules{ANSIColors.RESET}"
    elif "Staff" in path:
        return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.MAGENTA}Staff{ANSIColors.RESET}"
    elif "Test" in path:
        return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.BRIGHT_WHITE}Test{ANSIColors.RESET}"
    elif path == "System > Root" or path == "" or not path:
        # Default: System > Root
        return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.GREEN}System{ANSIColors.RESET} > {ANSIColors.GREEN}Root{ANSIColors.RESET}"
    else:
        # Generic fallback - still show BFOS prefix
        return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} > {ANSIColors.GREEN}{path}{ANSIColors.RESET}"


def format_menu_item(number, name, description="", enabled=True):
    """Format a menu item with number"""
    if enabled:
        return f"{ANSIColors.CYAN}[{number}]{ANSIColors.RESET} {ANSIColors.WHITE}{name}{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}- {description}{ANSIColors.RESET}"
    else:
        return f"{ANSIColors.BRIGHT_BLACK}[{number}] {name} - {description} (disabled){ANSIColors.RESET}"


def format_table_row(columns, widths=None):
    """Format a table row with optional column widths"""
    if widths is None:
        widths = [15] * len(columns)
    
    formatted = ""
    for i, col in enumerate(columns):
        width = widths[i] if i < len(widths) else 15
        formatted += str(col).ljust(width)
    
    return formatted


def format_section_header(title):
    """Format a section header"""
    return f"\n{ANSIColors.BRIGHT_CYAN}━━━ {title} ━━━{ANSIColors.RESET}\n"


def format_key_value(key, value):
    """Format a key-value pair"""
    return f"{ANSIColors.YELLOW}{key}:{ANSIColors.RESET} {ANSIColors.WHITE}{value}{ANSIColors.RESET}"


def format_list_item(item, bullet="•"):
    """Format a list item with bullet"""
    return f"  {ANSIColors.CYAN}{bullet}{ANSIColors.RESET} {item}"


def format_status(status, text):
    """Format status indicator (ok, warn, error)"""
    if status == "ok" or status == "success":
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} {text}"
    elif status == "warn" or status == "warning":
        return f"{ANSIColors.YELLOW}⚠{ANSIColors.RESET} {text}"
    elif status == "error" or status == "fail":
        return f"{ANSIColors.RED}✗{ANSIColors.RESET} {text}"
    else:
        return f"{ANSIColors.BRIGHT_BLACK}○{ANSIColors.RESET} {text}"


def format_code(text):
    """Format inline code"""
    return f"{ANSIColors.BG_BRIGHT_BLACK}{ANSIColors.WHITE}{text}{ANSIColors.RESET}"


def format_highlight(text):
    """Highlight important text"""
    return f"{ANSIColors.BOLD}{ANSIColors.BRIGHT_WHITE}{text}{ANSIColors.RESET}"