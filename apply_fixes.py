#!/usr/bin/env python3
"""
BlockForge OS v2.0.5 Patch Script
Fixes:
1. Duplicate 'cmds' command registration
2. 'name' KeyError in error handler
3. Channels panel 2000 character limit

Run this script in your blockforge-os directory:
    python3 apply_fixes.py
"""

import os
import re

def fix_moderation_py():
    """Remove duplicate cmds command from moderation.py if present"""
    filepath = "cogs/moderation.py"
    if not os.path.exists(filepath):
        print(f"[WARN] {filepath} not found, skipping...")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    
    # Remove any cmds command from moderation.py (it belongs in help.py)
    # Pattern matches: @commands.command(name='cmds') followed by the function
    pattern = r"@commands\.command\(name=['\"]cmds['\"]\)[^@]*?async def \w+\(self, ctx\):.*?(?=\n    @commands|\nclass |\nasync def setup|\Z)"
    
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, "", content, flags=re.DOTALL)
        print("[FIX] Removed duplicate 'cmds' command from moderation.py")
    
    # Fix the error handler to show proper error messages
    # Replace the generic error handler with a better one
    old_handler = '''# Other errors - log them
        print(f"[ERROR] Command error in {ctx.command}: {error}")
        await ctx.send(f"❌ **An Error Occurred**\\n\\n{str(error)}\\n\\n*Error Code: 0xCMND*")'''
    
    new_handler = '''# Other errors - log them with proper formatting
        error_type = type(error).__name__
        error_msg = str(error) if str(error) else error_type
        print(f"[ERROR] Command error in {ctx.command}: {error_type}: {error_msg}")
        await ctx.send(f"❌ **An Error Occurred**\\n\\n`{error_type}`: {error_msg}\\n\\n*Error Code: 0xCMND*")'''
    
    if old_handler in content:
        content = content.replace(old_handler, new_handler)
        print("[FIX] Updated error handler in moderation.py")
    
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    
    print("[INFO] No changes needed in moderation.py")
    return False


def fix_terminal_channels():
    """Fix channels panel pagination to handle 2000 character limit"""
    filepath = "cogs/terminal_channels.py"
    if not os.path.exists(filepath):
        # Try alternate name
        filepath = "cogs/terminal.py"
        if not os.path.exists(filepath):
            print(f"[WARN] terminal_channels.py not found, skipping...")
            return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    
    # Add pagination helper if not present
    pagination_helper = '''
    def paginate_output(self, text, max_chars=1800):
        """Split output into chunks that fit Discord's 2000 char limit"""
        if len(text) <= max_chars:
            return [text]
        
        pages = []
        lines = text.split('\\n')
        current_page = ""
        
        for line in lines:
            if len(current_page) + len(line) + 1 > max_chars:
                if current_page:
                    pages.append(current_page)
                current_page = line
            else:
                current_page = current_page + "\\n" + line if current_page else line
        
        if current_page:
            pages.append(current_page)
        
        return pages
'''
    
    if 'def paginate_output' not in content:
        # Find a good place to insert it (after __init__ or at class level)
        init_match = re.search(r'(def __init__\(self.*?\):.*?\n\n)', content, re.DOTALL)
        if init_match:
            insert_pos = init_match.end()
            content = content[:insert_pos] + pagination_helper + content[insert_pos:]
            print("[FIX] Added paginate_output method to terminal channels")
    
    # Update channel list command to use pagination
    old_list_send = 'await self.send_large_output(output)'
    new_list_send = '''# Paginate output to avoid 2000 char limit
        pages = self.paginate_output(output)
        for page in pages:
            await self.send_large_output(page)'''
    
    if old_list_send in content and 'pages = self.paginate_output' not in content:
        content = content.replace(old_list_send, new_list_send, 1)
        print("[FIX] Updated channel list to use pagination")
    
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    
    print("[INFO] No changes needed in terminal channels")
    return False


def fix_help_py():
    """Ensure help.py uses cmd_name instead of name to avoid KeyError"""
    filepath = "cogs/help.py"
    if not os.path.exists(filepath):
        print(f"[WARN] {filepath} not found, will create it...")
        return create_help_py()
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    
    # Fix the 'name' KeyError by using 'cmd_name' consistently
    # Change all 'name' keys to 'cmd_name' in the commands data
    content = re.sub(r"'name':\s*'(;[^']+)'", r"'cmd_name': '\1'", content)
    
    # Also fix the field access
    content = content.replace("cmd['name']", "cmd.get('cmd_name', 'Unknown')")
    content = content.replace('cmd["name"]', 'cmd.get("cmd_name", "Unknown")')
    
    # Add .get() for safer dictionary access
    replacements = [
        ("cmd['usage']", "cmd.get('usage', 'N/A')"),
        ("cmd['description']", "cmd.get('description', 'No description')"),
        ("cmd['permission']", "cmd.get('permission', 'Unknown')"),
        ("cmd['module']", "cmd.get('module', 'system')"),
        ("cmd['examples']", "cmd.get('examples', [])"),
    ]
    
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
    
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print("[FIX] Updated help.py with safer dictionary access")
        return True
    
    print("[INFO] No changes needed in help.py")
    return False


def create_help_py():
    """Create a fresh help.py if it doesn't exist"""
    content = '''"""
BlockForge OS Help System
Provides comprehensive command documentation with pagination
"""

import discord
from discord.ext import commands
from discord.ui import Button, View

try:
    from utils.colors import Colors
except ImportError:
    class Colors:
        GREEN = ""
        RED = ""
        RESET = ""


class CommandsView(View):
    """Paginated command view with buttons"""
    
    def __init__(self, pages, author_id):
        super().__init__(timeout=None)
        self.pages = pages
        self.current_page = 0
        self.author_id = author_id
        self.message = None
        self.update_buttons()
    
    def update_buttons(self):
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page >= len(self.pages) - 1
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can use these buttons.", ephemeral=True)
            return
        
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command author can use these buttons.", ephemeral=True)
            return
        
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)


class HelpCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{Colors.GREEN}[✓] Help cog loaded{Colors.RESET}")
    
    def get_all_commands(self):
        return {
            'warns': [
                {'cmd_name': ';warn', 'usage': ';warn <user> <duration> <reason>', 'description': 'Issue a warning', 'permission': 'Server Owner', 'examples': [';warn @User 7d Spam'], 'module': 'warns'},
                {'cmd_name': ';masswarn', 'usage': ';masswarn <users> <duration> <reason>', 'description': 'Warn multiple users', 'permission': 'Server Owner', 'examples': [';masswarn @U1,@U2 7d Spam'], 'module': 'warns'},
                {'cmd_name': ';clearwarning', 'usage': ';clearwarning <user> <case>', 'description': 'Clear a warning', 'permission': 'Server Owner', 'examples': [';clearwarning @User 5'], 'module': 'warns'},
                {'cmd_name': ';listwarnings', 'usage': ';listwarnings <user>', 'description': 'View warnings', 'permission': 'Server Owner', 'examples': [';listwarnings @User'], 'module': 'warns'},
            ],
            'mutes': [
                {'cmd_name': ';mute', 'usage': ';mute <user> <duration> <reason>', 'description': 'Mute a user', 'permission': 'Server Owner', 'examples': [';mute @User 1d Spam'], 'module': 'mutes'},
                {'cmd_name': ';unmute', 'usage': ';unmute <user> [reason]', 'description': 'Unmute a user', 'permission': 'Server Owner', 'examples': [';unmute @User'], 'module': 'mutes'},
                {'cmd_name': ';bulkmute', 'usage': ';bulkmute <users> <duration> <reason>', 'description': 'Mute multiple users', 'permission': 'Server Owner', 'examples': [';bulkmute @U1,@U2 1d'], 'module': 'mutes'},
                {'cmd_name': ';unbulkmute', 'usage': ';unbulkmute <users> [reason]', 'description': 'Unmute multiple users', 'permission': 'Server Owner', 'examples': [';unbulkmute @U1,@U2'], 'module': 'mutes'},
            ],
            'kicks': [
                {'cmd_name': ';kick', 'usage': ';kick <user> <reason>', 'description': 'Kick a user', 'permission': 'Server Owner', 'examples': [';kick @User Reason'], 'module': 'kicks'},
                {'cmd_name': ';masskick', 'usage': ';masskick <users> <reason>', 'description': 'Kick multiple users', 'permission': 'Server Owner', 'examples': [';masskick @U1,@U2 Reason'], 'module': 'kicks'},
            ],
            'bans': [
                {'cmd_name': ';ban', 'usage': ';ban <user> <duration|perm> <reason>', 'description': 'Ban a user', 'permission': 'Server Owner', 'examples': [';ban @User perm Reason'], 'module': 'bans'},
                {'cmd_name': ';unban', 'usage': ';unban <user_id> <reason>', 'description': 'Unban a user', 'permission': 'Server Owner', 'examples': [';unban 123456 Reason'], 'module': 'bans'},
                {'cmd_name': ';massban', 'usage': ';massban <ids> <duration|perm> <reason>', 'description': 'Ban multiple users', 'permission': 'Server Owner', 'examples': [';massban 111 222 perm Raid'], 'module': 'bans'},
            ],
            'purger': [
                {'cmd_name': ';purge', 'usage': ';purge <amount>', 'description': 'Delete messages', 'permission': 'Server Owner', 'examples': [';purge 50'], 'module': 'purger'},
            ],
            'system': [
                {'cmd_name': ';cmds', 'usage': ';cmds', 'description': 'Show this list', 'permission': 'Server Owner', 'examples': [';cmds'], 'module': 'system'},
                {'cmd_name': '.bfos()', 'usage': '.bfos()', 'description': 'Open BFOS terminal', 'permission': 'Server Owner', 'examples': ['.bfos()'], 'module': 'system'},
            ]
        }
    
    def create_command_pages(self, commands_data, max_per_page=15):
        all_commands = []
        for module, cmds in commands_data.items():
            all_commands.extend(cmds)
        
        pages = []
        total_pages = max(1, (len(all_commands) + max_per_page - 1) // max_per_page)
        
        for page_num in range(total_pages):
            start_idx = page_num * max_per_page
            end_idx = min(start_idx + max_per_page, len(all_commands))
            page_commands = all_commands[start_idx:end_idx]
            
            embed = discord.Embed(
                title="📖 BlockForge OS Commands",
                description=f"**Page {page_num + 1} of {total_pages}**",
                color=0x00AAFF,
                timestamp=discord.utils.utcnow()
            )
            
            for cmd in page_commands:
                field_value = f"**Usage:** `{cmd.get('usage', 'N/A')}`\\n"
                field_value += f"**Description:** {cmd.get('description', 'N/A')}\\n"
                field_value += f"**Module:** `{cmd.get('module', 'system')}`"
                
                examples = cmd.get('examples', [])
                if examples:
                    field_value += f"\\n**Example:** `{examples[0]}`"
                
                embed.add_field(name=cmd.get('cmd_name', 'Unknown'), value=field_value, inline=False)
            
            embed.set_footer(text=f"Use .bfos() to enable modules")
            pages.append(embed)
        
        return pages
    
    @commands.command(name='cmds')
    async def show_commands(self, ctx):
        try:
            if ctx.author.id != ctx.guild.owner_id:
                return
            
            commands_data = self.get_all_commands()
            pages = self.create_command_pages(commands_data, max_per_page=15)
            
            if not pages:
                await ctx.send("❌ No commands available.")
                return
            
            view = CommandsView(pages, ctx.author.id)
            message = await ctx.send(embed=pages[0], view=view)
            view.message = message
            
        except Exception as e:
            print(f"[ERROR] cmds command failed: {type(e).__name__}: {e}")
            await ctx.send(f"❌ **An Error Occurred**\\n\\n`{type(e).__name__}`: {str(e)}\\n\\n*Error Code: 0xCMDS*")


async def setup(bot):
    await bot.add_cog(HelpCommands(bot))
'''
    
    os.makedirs("cogs", exist_ok=True)
    with open("cogs/help.py", 'w') as f:
        f.write(content)
    print("[FIX] Created fresh help.py")
    return True


def main():
    print("=" * 50)
    print("BlockForge OS v2.0.5 Patch Script")
    print("=" * 50)
    print()
    
    fixes_applied = 0
    
    # Apply fixes
    if fix_moderation_py():
        fixes_applied += 1
    
    if fix_help_py():
        fixes_applied += 1
    
    if fix_terminal_channels():
        fixes_applied += 1
    
    print()
    print("=" * 50)
    print(f"✅ Patch complete! Applied {fixes_applied} fix(es)")
    print("=" * 50)
    print()
    print("Next steps:")
    print("1. Clear __pycache__: find . -name '__pycache__' -exec rm -rf {} +")
    print("2. Restart the bot: python bot.py")
    print()


if __name__ == "__main__":
    main()
