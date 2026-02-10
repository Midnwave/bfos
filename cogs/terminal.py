"""
BlockForge OS Terminal System
Handles terminal sessions and command processing
"""

import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import time
import random
from utils.colors import ANSIColors, format_ansi, format_error, format_success, format_warning
from utils.colors import create_header, create_loading_bar, create_color_squares, format_command_output
from utils.config import Config

# Import new panels for Phase 2-5 features
try:
    from cogs.terminal_management import ManagementPanel
    from cogs.terminal_channels import ChannelsPanel
    from cogs.terminal_backup import BackupPanel
    from cogs.terminal_embeds import EmbedEditorPanel
    from cogs.terminal_logging import LoggingPanel
    from cogs.terminal_security import TerminalSecurityHandler
    from cogs.terminal_ai import AIPanel
    from cogs.terminal_tickets import TicketPanel
    from cogs.terminal_xp import XPPanel
    PANELS_AVAILABLE = True
except ImportError as e:
    PANELS_AVAILABLE = False
    print(f"[WARNING] New panels not available - {e}")

class TerminalSession:
    """
    Terminal Session with efficient message handling.
    
    Rules:
    - ALWAYS edit current message first
    - Only create new message when space runs out
    - NEVER delete old messages (except clr command)
    - Pre-calculate space before adding content
    - Gradual updates for long tasks
    """
    
    # Discord limits
    MAX_CHARS = 1900  # Safe limit (Discord max is 2000)
    
    def __init__(self, bot, ctx, db):
        self.bot = bot
        self.ctx = ctx
        self.db = db
        self.author = ctx.author
        self.channel = ctx.channel
        self.guild = ctx.guild
        
        self.start_time = time.time()
        self.messages = []  # All messages - NEVER delete except clr
        self.current_message = None  # The ONE message we edit
        self.commands_executed = 0
        self.session_id = None
        self.current_path = "System > Root"
        self.command_history = []  # Command/output lines
        self.is_active = True
        self.current_panel = "main"
        
        # State tracking
        self.pending_confirmation = None
        self.terminal_message = None
        self.operation_in_progress = False
        
        # Embed editor state
        self.editing_embed = None
        self.embed_data = {}
        self.current_content = ""
        
        # Initialize panels
        if PANELS_AVAILABLE:
            self.management_panel = ManagementPanel(self)
            self.channels_panel = ChannelsPanel(self)
            self.backup_panel = BackupPanel(self)
            self.embed_editor = EmbedEditorPanel(self)
            self.logging_panel = LoggingPanel(self)
            self.security_panel = TerminalSecurityHandler(self)
            self.ai_panel = AIPanel(self)
            self.ticket_panel = TicketPanel(self)
            self.xp_panel = XPPanel(self)
    
    # ==================== USER & PERMISSIONS ====================
    
    @property
    def user(self):
        """Get the session user (author)"""
        return self.author
    
    def is_bot_owner(self):
        """Check if session user is the bot owner"""
        return self.author.id == Config.BOT_OWNER_ID
    
    def has_permission(self, permission_id: str) -> bool:
        """
        Check if user has a specific BFOS permission.
        Bot owner ALWAYS has all permissions.
        Server owner has all permissions (unless debug-demoted).
        """
        # Bot owner bypasses all permission checks
        if self.is_bot_owner():
            return True

        # Server owner has all permissions (unless debug-demoted)
        if self.author.id == self.guild.owner_id:
            debug_cog = self.bot.get_cog('Debug')
            if not (debug_cog and debug_cog.is_owner_demoted(self.guild.id)):
                return True

        if not self.db:
            return False

        # Check direct user permission
        if self.db.has_permission(self.guild.id, self.author.id, permission_id):
            return True

        # Check role permissions
        for role in self.author.roles:
            if self.db.role_has_permission(self.guild.id, role.id, permission_id):
                return True

        return False
    
    # ==================== SPACE CALCULATIONS ====================
    
    def _get_header(self):
        """Get current header"""
        return create_header(Config.VERSION, self.get_elapsed_time())
    
    def _get_prompt(self):
        """Get current prompt"""
        return self.get_colored_prompt()
    
    def _calc_base_size(self):
        """Calculate header + prompt size"""
        header = format_ansi(self._get_header())
        prompt = format_ansi(self._get_prompt())
        return len(header) + len(prompt) + 20  # +20 for newlines
    
    def _calc_history_size(self):
        """Calculate current history size"""
        return len("\n".join(self.command_history))
    
    def _calc_remaining(self):
        """Calculate remaining chars available"""
        used = self._calc_base_size() + self._calc_history_size()
        return max(0, self.MAX_CHARS - used)
    
    def _will_fit(self, text):
        """Check if text will fit in current message"""
        needed = len(text) + 1  # +1 for newline
        return needed <= self._calc_remaining()
    
    # ==================== MESSAGE BUILDING ====================
    
    def _build_content(self, show_prompt=True):
        """Build full message content"""
        header = self._get_header()
        history = "\n".join(self.command_history)
        prompt = self._get_prompt() if show_prompt else ""
        
        if history.strip():
            if prompt:
                return f"{header}\n\n{history}\n{prompt}"
            return f"{header}\n\n{history}"
        else:
            if prompt:
                return f"{header}\n{prompt}"
            return header
    
    def _trim_history_to_fit(self):
        """Remove oldest history entries until content fits"""
        while self._calc_history_size() > (self.MAX_CHARS - self._calc_base_size() - 50):
            if len(self.command_history) <= 1:
                # Single item too big - it should have been sent as overflow
                # Just clear it since it was already sent as separate message
                if self.command_history:
                    self.command_history = []
                break
            self.command_history.pop(0)
    
    # ==================== CORE DISPLAY ====================
    
    async def _update_display(self, show_prompt=True):
        """
        Update the terminal display - EDIT FIRST, new message only if needed.
        """
        # Trim history if too big
        self._trim_history_to_fit()
        
        # Build content
        content = self._build_content(show_prompt)
        formatted = format_ansi(content)
        
        # Safety check
        if len(formatted) > 1990:
            # Force trim more aggressively
            while len(formatted) > 1900 and len(self.command_history) > 0:
                self.command_history.pop(0)
                content = self._build_content(show_prompt)
                formatted = format_ansi(content)
        
        # TRY EDIT FIRST
        if self.current_message:
            try:
                await self.current_message.edit(content=formatted)
                self.terminal_message = self.current_message
                return True
            except discord.NotFound:
                # Message was deleted, need new one
                self.current_message = None
            except discord.HTTPException as e:
                if "Must be 2000 or fewer" in str(e):
                    # Content too long despite checks, clear history
                    self.command_history = self.command_history[-1:] if self.command_history else []
                    content = self._build_content(show_prompt)
                    formatted = format_ansi(content)
                else:
                    # Other error, try new message
                    pass
        
        # CREATE NEW MESSAGE
        try:
            msg = await self.channel.send(formatted)
            self.current_message = msg
            self.terminal_message = msg
            self.messages.append(msg)
            return True
        except discord.HTTPException as e:
            print(f"[TERMINAL] Send failed: {e}")
            # Last resort - minimal message
            try:
                header = self._get_header()
                minimal = format_ansi(f"{header}\n{ANSIColors.BRIGHT_BLACK}[Display reset]{ANSIColors.RESET}\n{self._get_prompt()}")
                self.command_history = []
                msg = await self.channel.send(minimal)
                self.current_message = msg
                self.terminal_message = msg
                self.messages.append(msg)
            except:
                pass
            return False
    
    async def _force_new_message(self):
        """Force start a new message (when current is full)"""
        # Clear history for fresh start
        self.command_history = []

        content = self._build_content(show_prompt=True)
        formatted = format_ansi(content)

        try:
            msg = await self.channel.send(formatted)
            self.current_message = msg
            self.terminal_message = msg
            self.messages.append(msg)
        except discord.HTTPException as e:
            print(f"[TERMINAL] Failed to send new message: {e}")
    
    # Alias for compatibility
    async def _display_current_state(self, elapsed=None, show_prompt=True):
        """Alias for _update_display (backward compatibility)"""
        return await self._update_display(show_prompt)
    
    # ==================== PROGRESS UPDATES ====================
    
    async def send_progress_update(self, message, delay=0.3):
        """Send a progress update - edits current message"""
        progress = f"{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}{message}"
        
        # Check if it fits
        if not self._will_fit(progress):
            # Need new message
            await self._force_new_message()
        
        self.command_history.append(progress)
        await self._update_display(show_prompt=True)
        
        if delay > 0:
            await asyncio.sleep(delay)
    
    async def update_progress_line(self, message):
        """Update the last progress line (for animated progress)"""
        if self.command_history:
            progress = f"{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}{message}"
            self.command_history[-1] = progress
            await self._update_display(show_prompt=True)
    
    async def show_animated_list(self, categories, header="", footer=""):
        """Show a list with animated loading effect"""
        import asyncio

        self.operation_in_progress = True
        try:
            return await self._show_animated_list_inner(categories, header, footer)
        finally:
            self.operation_in_progress = False

    async def _show_animated_list_inner(self, categories, header="", footer=""):
        """Inner implementation of show_animated_list"""
        # Show header first
        if header:
            self.command_history.append(header)
            await self._update_display(show_prompt=False)
            await asyncio.sleep(0.3)
        
        # Add each category with animation
        for i, category in enumerate(categories):
            # Check if we need a new message
            if not self._will_fit(category):
                await self._force_new_message()
                # Re-add header if starting new message
                if header:
                    self.command_history.append(f"{ANSIColors.BRIGHT_BLACK}[Continued...]{ANSIColors.RESET}")
            
            self.command_history.append(category)
            await self._update_display(show_prompt=False)
            await asyncio.sleep(0.15)  # Small delay between categories
        
        # Show footer
        if footer:
            self.command_history.append(footer)
            await self._update_display(show_prompt=True)
        else:
            await self._update_display(show_prompt=True)
    
    # ==================== MAIN INPUT PROCESSING ====================
    
    async def process_input(self, user_input, author, original_message=None):
        """
        Process user input:
        1. Pre-calculate space
        2. Add command line + processing indicator
        3. Edit to show command + processing
        4. Delete user's original message
        5. Process command
        6. Pre-calculate output space
        7. Add output (start new msg if needed)
        8. Edit to show output + prompt
        """
        try:
            if author.id != self.author.id or not self.is_active:
                return
            
            if self.operation_in_progress:
                if user_input.lower().strip() not in ['cancel', 'stop']:
                    return
            
            # Log command
            try:
                self.db.log_command(self.session_id, user_input)
                self.commands_executed += 1
            except:
                pass

            # Debug logging
            debug_cog = self.bot.get_cog('Debug')
            if debug_cog:
                debug_cog.debug_log("TERMINAL", f"Command: '{user_input}' from {author.name} panel={self.current_panel}")
            
            command_lower = user_input.lower().strip()
            
            # === BUILD COMMAND LINE ===
            command_line = self._build_command_line(user_input)
            
            # === PRE-CALC: Does command fit? ===
            if not self._will_fit(command_line):
                await self._force_new_message()
            
            # === ADD & SHOW COMMAND + PROCESSING INDICATOR ===
            self.command_history.append(command_line)
            processing_line = f"{ANSIColors.BRIGHT_BLACK}► Processing...{ANSIColors.RESET}"
            self.command_history.append(processing_line)
            await self._update_display(show_prompt=False)

            # === DELETE USER'S MESSAGE (after processing indicator is visible) ===
            if original_message:
                try:
                    await original_message.delete()
                except Exception:
                    pass  # Message may already be deleted or bot lacks permission

            # === PROCESS COMMAND ===
            output = ""
            should_exit = False

            if self.pending_confirmation:
                output, should_exit = await self._handle_confirmation(command_lower)
            else:
                output, should_exit = await self._route_command(command_lower, user_input)

            # === REMOVE PROCESSING INDICATOR ===
            if self.command_history and self.command_history[-1] == processing_line:
                self.command_history.pop()
            
            # === HANDLE EXIT ===
            if should_exit:
                self.is_active = False
                from bot import active_sessions
                if self.author.id in active_sessions:
                    del active_sessions[self.author.id]
                return
            
            # === ADD OUTPUT ===
            if output and output.strip():
                # Pre-calc: Check if output is too long for a single message
                output_len = len(output)

                if output_len > 1800:
                    # Clean up old message (remove stale processing indicator)
                    await self._update_display(show_prompt=False)
                    # Output is too long - send as overflow message(s)
                    await self._send_overflow_output(output)
                    # Clear history and force new message for prompt
                    self.command_history = []
                    self.current_message = None  # Force _update_display to create new message
                else:
                    # Normal flow - check if it fits with history
                    if not self._will_fit(output):
                        # Clean up old message before creating new one
                        await self._update_display(show_prompt=False)
                        # Save the last command line before clearing
                        last_command = self.command_history[-1] if self.command_history else ""
                        # Force new message with fresh start
                        await self._force_new_message()
                        # Re-add only the last command so user sees context
                        if last_command:
                            self.command_history.append(last_command)

                    self.command_history.append(output)
            
            # === SHOW FINAL STATE ===
            await self._update_display(show_prompt=True)
        
        except Exception as e:
            print(f"[TERMINAL] Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    async def _send_overflow_output(self, output):
        """Send long output as separate message(s), then continue terminal"""
        MAX_CHUNK = 1850  # Safe limit per message
        
        lines = output.split('\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_len = len(line) + 1  # +1 for newline
            
            if current_size + line_len > MAX_CHUNK:
                # Save current chunk and start new one
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_len
            else:
                current_chunk.append(line)
                current_size += line_len
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        # Send all chunks as separate messages (not the terminal message)
        for i, chunk in enumerate(chunks):
            # Format as code block
            formatted = f"```ansi\n{chunk}\n```"
            
            # Add page indicator if multiple chunks
            if len(chunks) > 1:
                formatted = f"```ansi\n{ANSIColors.BRIGHT_BLACK}[Output {i+1}/{len(chunks)}]{ANSIColors.RESET}\n{chunk}\n```"
            
            try:
                await self.channel.send(formatted)
            except Exception as e:
                print(f"[TERMINAL] Failed to send overflow chunk: {e}")
        
        # Small delay before continuing
        await asyncio.sleep(0.3)
    
    def _truncate_output(self, output, max_len=None):
        """Truncate output to fit in a message"""
        if max_len is None:
            max_len = self.MAX_CHARS - 400
        if len(output) <= max_len:
            return output
        
        lines = output.split('\n')
        result = []
        size = 0
        for line in lines:
            if size + len(line) + 1 > max_len:
                result.append(f"{ANSIColors.BRIGHT_BLACK}[Output truncated...]{ANSIColors.RESET}")
                break
            result.append(line)
            size += len(line) + 1
        return '\n'.join(result)
    
    # ==================== HELPER METHODS ====================
    
    def get_elapsed_time(self):
        """Get elapsed time in seconds"""
        return int(time.time() - self.start_time)
    
    def get_colored_prompt(self):
        """Get the colored prompt based on current panel"""
        panel_prompts = {
            "main": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "modules": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.YELLOW}Modules{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "config": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.GREEN}Config{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "warn_config": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.YELLOW}Warns{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.GREEN}Config{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "staff": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.MAGENTA}Staff{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "permissions": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.MAGENTA}Staff{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_CYAN}Permissions{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "test": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}Test{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "embeds": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.GREEN}Config{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_MAGENTA}Embeds{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "management": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_BLUE}Management{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "channels": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_BLUE}Channels{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "backup": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_BLUE}Backup{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "logging": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.GREEN}Config{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_YELLOW}Logging{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "security": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_RED}Security{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "verification": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_RED}Security{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.GREEN}Verification{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "autoroles": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_RED}Security{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.GREEN}Autoroles{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "ai": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_MAGENTA}AI{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "tickets": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_GREEN}Tickets{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
            "xp": f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_YELLOW}XP{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} ",
        }
        
        # Handle embed edit panels
        if self.current_panel.startswith("embed_edit_"):
            return f"{ANSIColors.BRIGHT_CYAN}BFOS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} {ANSIColors.BRIGHT_MAGENTA}Embed Editor{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}>{ANSIColors.RESET} "
        
        return panel_prompts.get(self.current_panel, panel_prompts["main"])
    
    def _build_command_line(self, user_input):
        """Build formatted command line"""
        # Use format_command_output for consistent BFOS > Path > command format
        return format_command_output(user_input, self.current_path)
    
    # ==================== TERMINAL STARTUP ====================
    
    async def animated_list(self, header, items, footer="", delay=0.4):
        """
        Display items with animation on the terminal.
        Adds all content to command_history for persistence.
        Uses the same message display system as process_input.
        """
        self.operation_in_progress = True
        try:
            return await self._animated_list_inner(header, items, footer, delay)
        finally:
            self.operation_in_progress = False

    async def _animated_list_inner(self, header, items, footer="", delay=0.4):
        """Inner implementation of animated_list"""
        # Build the full list output
        output_lines = [header, ""]
        
        elapsed = self.get_elapsed_time()
        
        # Check if the full output would be too long
        # If so, start fresh before animation begins
        estimated_len = len(header) + sum(len(item) for item in items) + len(footer) + (len(items) * 2)
        if estimated_len > 1200:
            # Clear old history for large outputs
            self.command_history = []
            # Send a fresh message before starting
            term_header = create_header(Config.VERSION, elapsed)
            content = f"{term_header}\n\n{header}\n{ANSIColors.BRIGHT_BLACK}Loading items...{ANSIColors.RESET}"
            try:
                msg = await self.channel.send(format_ansi(content))
                self.terminal_message = msg
                self.current_message = msg
                self.messages.append(msg)
            except:
                pass
        
        # Animate items onto the current message
        for i, item in enumerate(items):
            output_lines.append(item)
            
            # Every 3 items, update the display
            if (i + 1) % 3 == 0 or i == len(items) - 1:
                # Build current state
                current_output = "\n".join(output_lines)
                
                # Add footer if this is the last batch
                if i == len(items) - 1 and footer:
                    current_output += "\n\n" + footer
                
                # Display without clearing history
                await self._animate_display(elapsed, current_output)
                
                # Small delay between batches
                if i < len(items) - 1:
                    await asyncio.sleep(delay)
        
        # Build final output
        final_output = "\n".join(output_lines)
        if footer:
            final_output += "\n\n" + footer
        
        # Check if too long - send as overflow message(s) instead of truncating
        if len(final_output) > 1500:
            await self._send_overflow_output(final_output)
            # Clear history and force a NEW message for the prompt
            self.command_history = []
            self.current_message = None  # Force _update_display to create new message
        else:
            self.command_history.append(final_output)

        # Final display with prompt
        await self._display_current_state(elapsed, show_prompt=True)

        return ""
    
    async def _animate_display(self, elapsed, animated_content):
        """Display animated content without prompt (during animation)"""
        term_header = create_header(Config.VERSION, elapsed)
        
        # Calculate max content size
        header_len = len(format_ansi(term_header)) + 20
        max_content_len = 1800 - header_len
        
        # If content is too long, just show progress indicator
        # The full output will be sent as overflow messages at the end
        if len(animated_content) > max_content_len:
            # Count lines for progress
            line_count = animated_content.count('\n') + 1
            # Just show loading progress instead of truncated content
            animated_content = f"{ANSIColors.BRIGHT_BLACK}[Loading... {line_count} lines]{ANSIColors.RESET}"
        
        # Build with existing history + animated content
        history_parts = self.command_history.copy()
        history_parts.append(animated_content)
        history_text = "\n".join(history_parts)
        
        content = f"{term_header}\n\n{history_text}"
        formatted = format_ansi(content)
        
        # Check if we need a new message
        if len(formatted) > 1900:
            # Too long - clear history and use just animated content
            self.command_history = []
            content = f"{term_header}\n\n{animated_content}"
            formatted = format_ansi(content)
            
            try:
                msg = await self.channel.send(formatted)
                self.terminal_message = msg
                self.current_message = msg
                self.messages.append(msg)
            except Exception as e:
                print(f"[TERMINAL] Animation send error: {e}")
        else:
            try:
                if self.current_message:
                    await self.current_message.edit(content=formatted)
                    self.terminal_message = self.current_message
                else:
                    msg = await self.channel.send(formatted)
                    self.terminal_message = msg
                    self.current_message = msg
                    self.messages.append(msg)
            except discord.NotFound:
                # Message deleted, send new
                msg = await self.channel.send(formatted)
                self.terminal_message = msg
                self.current_message = msg
                self.messages.append(msg)
            except Exception as e:
                print(f"[TERMINAL] Animation edit error: {e}")
    
    async def start(self):
        """Start the terminal session with loading animation"""
        try:
            print(f"[TERMINAL] Starting terminal session for {self.author.name}")
            
            # Send mobile warning
            print(f"[TERMINAL] Sending mobile warning...")
            try:
                warning_embed = discord.Embed(
                    title="📱 Mobile User Notice",
                    description=(
                        "BlockForge OS terminal interface is optimized for desktop viewing.\n"
                        "For the best experience, it is **highly recommended** to access BFOS from a PC.\n\n"
                        "The terminal will load in **3 seconds**..."
                    ),
                    color=0xffaa00
                )
                warning_msg = await self.channel.send(embed=warning_embed)
                print(f"[TERMINAL] Mobile warning sent")
                await asyncio.sleep(3)
                await warning_msg.delete()
                print(f"[TERMINAL] Mobile warning deleted")
            except Exception as e:
                print(f"[TERMINAL ERROR] Failed to show mobile warning: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                # Continue anyway
            
            # Create loading message
            print(f"[TERMINAL] Creating loading message...")
            try:
                loading_msg = await self.channel.send("```ansi\nInitializing...```")
                self.messages.append(loading_msg)
                print(f"[TERMINAL] Loading message created: {loading_msg.id}")
            except Exception as e:
                print(f"[TERMINAL ERROR] Failed to create loading message: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # Loading animation
            print(f"[TERMINAL] Starting loading animation...")
            try:
                for i, message in enumerate(Config.LOADING_MESSAGES):
                    percentage = int(((i + 1) / len(Config.LOADING_MESSAGES)) * 100)
                    
                    # Create loading screen
                    squares = create_color_squares()
                    loading_bar = create_loading_bar(percentage)
                    
                    content = f"""{ANSIColors.BRIGHT_CYAN}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.BOLD}{ANSIColors.BRIGHT_GREEN}BlockForge OS{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}v{Config.VERSION}{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}{'═' * 50}{ANSIColors.RESET}

{squares}

{loading_bar}

{ANSIColors.CYAN}{message}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Please wait...{ANSIColors.RESET}"""
                    
                    await loading_msg.edit(content=format_ansi(content))
                    await asyncio.sleep(0.5)
                
                print(f"[TERMINAL] Loading animation completed")
            except Exception as e:
                print(f"[TERMINAL ERROR] Failed during loading animation: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # Final loading phase - wait 2 seconds
            print(f"[TERMINAL] Final loading phase...")
            await asyncio.sleep(2)
            
            # Create session in database
            print(f"[TERMINAL] Creating database session...")
            try:
                self.session_id = self.db.create_session(self.guild.id, self.author.id)
                print(f"[TERMINAL] Database session created: {self.session_id}")
            except Exception as e:
                print(f"[TERMINAL ERROR] Failed to create database session: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # Show main menu
            print(f"[TERMINAL] Showing main menu...")
            try:
                await self.show_main_menu()
                print(f"[TERMINAL] Main menu displayed successfully")
                print(f"[TERMINAL] Terminal session started successfully!")
            except Exception as e:
                print(f"[TERMINAL ERROR] Failed to show main menu: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                raise
        
        except Exception as e:
            print(f"[TERMINAL FATAL] Fatal error in terminal start: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def show_main_menu(self):
        """Display the main menu"""
        header = create_header(Config.VERSION, self.get_elapsed_time())
        
        content = f"""{header}

{format_command_output("", self.current_path)}"""
        
        # Update or create message
        if self.current_message:
            await self.current_message.edit(content=format_ansi(content))
        else:
            # Delete loading message if it exists
            if self.messages:
                try:
                    await self.messages[0].delete()
                    self.messages.clear()
                except:
                    pass
            
            self.current_message = await self.channel.send(format_ansi(content))
            self.messages.append(self.current_message)
        
        # Set terminal_message reference
        self.terminal_message = self.current_message
        
        self.current_content = content
    
    async def _handle_confirmation(self, command_lower):
        """Handle pending confirmation - always use execute_pending_confirmation"""
        if command_lower == "confirm":
            output, should_exit = await self.execute_pending_confirmation()
            self.pending_confirmation = None
            return output, should_exit
        elif command_lower == "cancel":
            self.pending_confirmation = None
            return f"{ANSIColors.YELLOW}Action cancelled.{ANSIColors.RESET}", False
        else:
            return f"{ANSIColors.RED}Please type 'confirm' to proceed or 'cancel' to abort.{ANSIColors.RESET}", False
    
    async def _route_command(self, command_lower, user_input):
        """Route command to appropriate panel handler"""
        try:
            # Global commands that work in ALL panels
            if command_lower == "exit":
                return await self.handle_exit(), True
            
            handlers = {
                "main": lambda: self.handle_main_panel(command_lower, user_input),
                "modules": lambda: self.handle_modules_panel(command_lower, user_input),
                "config": lambda: self.handle_config_panel(command_lower, user_input),
                "warn_config": lambda: self.handle_warn_config_panel(command_lower, user_input),
                "staff": lambda: self.handle_staff_panel(command_lower, user_input),
                "test": lambda: self.handle_test_panel(command_lower, user_input),
                "embeds": lambda: self.handle_embed_panel(command_lower, user_input),
            }
            
            if self.current_panel in handlers:
                return await handlers[self.current_panel]()
            elif self.current_panel == "permissions":
                # Handle permissions panel
                from cogs.terminal_permissions import TerminalPermissions
                return await TerminalPermissions(self).handle_command(command_lower, user_input)
            elif PANELS_AVAILABLE:
                if self.current_panel == "management":
                    return await self.management_panel.handle_command(command_lower, user_input)
                elif self.current_panel == "channels":
                    return await self.channels_panel.handle_command(command_lower, user_input)
                elif self.current_panel == "backup":
                    return await self.backup_panel.handle_command(command_lower, user_input)
                elif self.current_panel == "logging":
                    return await self.logging_panel.handle_command(command_lower, user_input)
                elif self.current_panel == "ai":
                    return await self.ai_panel.handle_command(command_lower, user_input), False
                elif self.current_panel == "tickets":
                    return await self.ticket_panel.handle_command(command_lower, user_input)
                elif self.current_panel == "xp":
                    return await self.xp_panel.handle_command(command_lower, user_input)
                elif self.current_panel in ["security", "verification", "autoroles"]:
                    output = await self.security_panel.handle_command(user_input)
                    if output == "EXIT_TERMINAL":
                        return await self.handle_exit(), True
                    return output, False
                elif self.current_panel.startswith("embed_edit_"):
                    return await self.embed_editor.handle_command(command_lower, user_input)
            
            return format_error(f"Unknown panel: {self.current_panel}", Config.ERROR_CODES['INVALID_COMMAND']), False
        
        except Exception as e:
            print(f"[TERMINAL ERROR] Handler failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return format_error(f"Internal error: {e}", Config.ERROR_CODES['COMMAND_FAILED']), False
    
    async def send_large_output(self, output, title="Output"):
        """
        Send large output split into multiple messages if needed.
        First message: header + first chunk (NO old history)
        Subsequent messages: ONLY chunk content (NO header, NO duplication)
        """
        chunks = self.split_large_output(output)

        if len(chunks) == 1:
            # Single chunk - let normal flow handle it
            return

        elapsed = self.get_elapsed_time()
        prompt = self.get_colored_prompt()

        # FIRST MESSAGE: Header + first chunk only (no old history)
        first_chunk = chunks[0]
        header = create_header(Config.VERSION, elapsed)
        first_content = f"{header}\n\n{first_chunk}"

        try:
            await self.terminal_message.edit(content=format_ansi(first_content))
        except (discord.NotFound, discord.HTTPException) as e:
            print(f"[TERMINAL] Edit failed in send_large_output: {e}")
            msg = await self.channel.send(format_ansi(first_content))
            self.terminal_message = msg
            self.current_message = msg
            self.messages.append(msg)
        
        # CONTINUATION MESSAGES: Only chunk content (NO header, NO history)
        for i, chunk in enumerate(chunks[1:], 2):
            await asyncio.sleep(1.0)  # Delay between pages
            
            # Just the chunk content, NO header, NO previous content
            continuation_content = chunk
            
            # Last chunk gets the prompt
            if i == len(chunks):
                continuation_content += f"\n{prompt}"
            
            try:
                # Send as NEW message (continuation)
                new_msg = await self.channel.send(format_ansi(continuation_content))
                self.terminal_message = new_msg
                self.current_message = new_msg
                self.messages.append(new_msg)
            except Exception as e:
                print(f"[TERMINAL] Failed to send chunk {i}: {e}")
                break
        
        # Clear history and add summary for next command
        self.command_history = [f"{ANSIColors.BRIGHT_BLACK}[Displayed {len(chunks)} pages]{ANSIColors.RESET}"]
    
    async def handle_ping(self):
        """Handle ping command"""
        latency = round(self.bot.latency * 1000, 2)
        
        if latency < 100:
            status = f"{ANSIColors.GREEN}Excellent{ANSIColors.RESET}"
        elif latency < 200:
            status = f"{ANSIColors.YELLOW}Good{ANSIColors.RESET}"
        else:
            status = f"{ANSIColors.RED}Poor{ANSIColors.RESET}"
        
        return f"""
{ANSIColors.BRIGHT_CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}        {ANSIColors.BOLD}Network Diagnostics{ANSIColors.RESET}              {ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}Bot Latency:    {ANSIColors.BRIGHT_WHITE}{latency}ms{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}Connection:     {status}
{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}Status:         {ANSIColors.GREEN}● Online{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}Gateway:        {ANSIColors.GREEN}Connected{ANSIColors.RESET}
"""
    
    async def handle_main_panel(self, command_lower, user_input):
        """Handle commands in main panel"""
        output = ""
        should_exit = False
        
        if command_lower == "exit":
            output = await self.handle_exit()
            should_exit = True
        elif command_lower == "clr" or command_lower == "clear":
            await self.handle_clear()
            return "", False
        elif command_lower == "ping":
            output = await self.handle_ping()
        elif command_lower == "version":
            output = self.handle_version()
        elif command_lower == "help":
            output = self.handle_help()
        elif command_lower == "modules":
            self.current_panel = "modules"
            self.current_path = "Modules"
            output = self.show_modules_menu()
        elif command_lower == "config":
            self.current_panel = "config"
            self.current_path = "Configuration"
            output = self.show_config_menu()
        elif command_lower == "security":
            self.current_panel = "security"
            self.current_path = "Security"
            output = self.show_security_menu()
        elif command_lower == "staff":
            self.current_panel = "staff"
            self.current_path = "Staff"
            output = self.show_staff_menu()
        elif command_lower == "test":
            self.current_panel = "test"
            self.current_path = "Test"
            output = self.show_test_menu()
        elif command_lower == "management":
            if PANELS_AVAILABLE:
                self.current_panel = "management"
                self.current_path = "Management"
                output = self.management_panel.show_help()
            else:
                output = format_error("Management panel not available. Check installation.", Config.ERROR_CODES['COMMAND_FAILED'])
        elif command_lower == "ai":
            if PANELS_AVAILABLE:
                self.current_panel = "ai"
                self.current_path = "AI Management"
                output = self.ai_panel.show_help()
            else:
                output = format_error("AI panel not available. Check installation.", Config.ERROR_CODES['COMMAND_FAILED'])
        elif command_lower == "tickets":
            if PANELS_AVAILABLE:
                self.current_panel = "tickets"
                self.current_path = "Tickets"
                output = self.ticket_panel.show_help()
            else:
                output = format_error("Tickets panel not available. Check installation.", Config.ERROR_CODES['COMMAND_FAILED'])
        elif command_lower == "xp":
            if PANELS_AVAILABLE:
                self.current_panel = "xp"
                self.current_path = "XP System"
                output = self.xp_panel.show_help()
            else:
                output = format_error("XP panel not available. Check installation.", Config.ERROR_CODES['COMMAND_FAILED'])
        else:
            output = format_error(
                f"Invalid command '{user_input}'. Type 'help' for available commands.",
                Config.ERROR_CODES['INVALID_COMMAND']
            )
        
        return output, should_exit
    
    def handle_version(self):
        """Handle version command"""
        return f"""
{ANSIColors.BRIGHT_CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}         {ANSIColors.BOLD}Version Information{ANSIColors.RESET}             {ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}System:         {ANSIColors.BRIGHT_GREEN}BlockForge OS{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}Version:        {ANSIColors.BRIGHT_WHITE}{Config.VERSION}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}Build:          {ANSIColors.YELLOW}Development{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}Discord.py:     {ANSIColors.BRIGHT_WHITE}2.4.0{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}Python:         {ANSIColors.BRIGHT_WHITE}3.12{ANSIColors.RESET}
"""
    
    def handle_help(self):
        """Handle help command"""
        commands_list = ""
        for cmd, desc in Config.COMMANDS.items():
            commands_list += f"{ANSIColors.BRIGHT_BLACK}  {ANSIColors.BRIGHT_CYAN}{cmd.upper():<12}{ANSIColors.RESET} - {desc}\n"
        
        return f"""
{ANSIColors.BRIGHT_CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}        {ANSIColors.BOLD}Available Commands{ANSIColors.RESET}               {ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}{'═' * 46}{ANSIColors.RESET}

{commands_list}
{ANSIColors.BRIGHT_BLACK}Type any command to execute it.{ANSIColors.RESET}
"""
    
    async def handle_clear(self):
        """Handle clear command"""
        # Delete all previous messages
        for msg in self.messages:
            try:
                await msg.delete()
            except discord.NotFound:
                pass  # Message already deleted
            except discord.Forbidden:
                print(f"[TERMINAL] Cannot delete message {msg.id} - missing permissions")
            except discord.HTTPException as e:
                print(f"[TERMINAL] Failed to delete message {msg.id}: {e}")

        self.messages.clear()
        self.current_message = None
        self.current_content = ""
        self.command_history = []  # Clear command history

        # Show fresh menu
        try:
            await self.show_main_menu()
        except Exception as e:
            print(f"[TERMINAL] Failed to show main menu after clear: {e}")
            # Emergency recovery
            try:
                header = self._get_header()
                msg = await self.channel.send(format_ansi(f"{header}\n{self._get_prompt()}"))
                self.current_message = msg
                self.terminal_message = msg
                self.messages.append(msg)
            except Exception as e2:
                print(f"[TERMINAL] Emergency recovery failed: {e2}")
    
    async def handle_exit(self):
        """Handle exit command"""
        elapsed = self.get_elapsed_time()
        
        # End session in database
        self.db.end_session(self.session_id, self.commands_executed)
        
        # Build exit message
        header = create_header(Config.VERSION, elapsed)
        command_line = format_command_output("exit", self.current_path if self.current_panel == "main" else self.current_panel.title())
        
        exit_message = f"""
{ANSIColors.BRIGHT_GREEN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_GREEN}║{ANSIColors.RESET}        {ANSIColors.BOLD}Terminal Session Ended{ANSIColors.RESET}           {ANSIColors.BRIGHT_GREEN}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_GREEN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}Session Duration:    {ANSIColors.BRIGHT_WHITE}{elapsed}s{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}Commands Executed:   {ANSIColors.BRIGHT_WHITE}{self.commands_executed}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}► {ANSIColors.RESET}Status:              {ANSIColors.GREEN}All changes saved{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Thank you for using BlockForge OS.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Run .bfos() to start a new session.{ANSIColors.RESET}
"""
        
        # Build full exit content
        full_content = f"""{header}

{command_line}
{exit_message}"""
        
        # Send as NEW message (not editing)
        await self.channel.send(format_ansi(full_content))
        
        return exit_message
    
    async def handle_modules_panel(self, command_lower, user_input):
        """Handle commands in modules panel"""
        output = ""
        should_exit = False
        
        if command_lower == "exit":
            output = await self.handle_exit()
            should_exit = True
        elif command_lower == "back":
            self.current_panel = "main"
            self.current_path = "System > Root"
            output = f"{ANSIColors.GREEN}Returned to main menu.{ANSIColors.RESET}"
        elif command_lower == "help":
            output = self.show_module_help()
        elif command_lower == "module list":
            await self.show_module_list_animated()
            return "", False  # Already displayed via animation
        elif command_lower == "module enable":
            # Show usage when user types just "module enable"
            output = f"""{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}module enable <module_id>{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Examples:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_CYAN}module enable bans{ANSIColors.RESET}    - Enable ban system
  {ANSIColors.BRIGHT_CYAN}module enable warns{ANSIColors.RESET}   - Enable warning system
  {ANSIColors.BRIGHT_CYAN}module enable mutes{ANSIColors.RESET}   - Enable mute system

{ANSIColors.BRIGHT_BLACK}Use 'module list' to see all available modules.{ANSIColors.RESET}"""
        elif command_lower == "module disable":
            # Show usage when user types just "module disable"
            output = f"""{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}module disable <module_id>{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Examples:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_CYAN}module disable bans{ANSIColors.RESET}   - Disable ban system
  {ANSIColors.BRIGHT_CYAN}module disable kicks{ANSIColors.RESET}  - Disable kick system

{ANSIColors.BRIGHT_BLACK}Use 'module list' to see all available modules.{ANSIColors.RESET}"""
        elif command_lower == "module configure":
            # Show usage when user types just "module configure"
            output = f"""{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}module configure <module_id>{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Examples:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_CYAN}module configure warns{ANSIColors.RESET}  - Configure warning system

{ANSIColors.BRIGHT_BLACK}Note: Only some modules are configurable.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Use 'module list' to see which modules can be configured.{ANSIColors.RESET}"""
        elif command_lower.startswith("module enable "):
            module_name = user_input[14:].strip().lower()
            if not module_name:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}module enable <module_id>{ANSIColors.RESET}"
            else:
                output = await self.handle_module_enable(module_name)
        elif command_lower.startswith("module disable "):
            module_name = user_input[15:].strip().lower()
            if not module_name:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}module disable <module_id>{ANSIColors.RESET}"
            else:
                output = await self.handle_module_disable(module_name)
        elif command_lower.startswith("module configure "):
            module_name = user_input[17:].strip().lower()
            if not module_name:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}module configure <module_id>{ANSIColors.RESET}"
            else:
                output = await self.handle_module_configure(module_name)
        elif command_lower == "module":
            # Show general module usage
            output = f"""{ANSIColors.YELLOW}Module Commands:{ANSIColors.RESET}

  {ANSIColors.BRIGHT_CYAN}module list{ANSIColors.RESET}                - List all modules
  {ANSIColors.BRIGHT_CYAN}module enable <id>{ANSIColors.RESET}        - Enable a module
  {ANSIColors.BRIGHT_CYAN}module disable <id>{ANSIColors.RESET}       - Disable a module
  {ANSIColors.BRIGHT_CYAN}module configure <id>{ANSIColors.RESET}     - Configure a module

{ANSIColors.BRIGHT_BLACK}Type 'help' for all available commands.{ANSIColors.RESET}"""
        else:
            output = format_error(
                f"Invalid command '{user_input}'. Type 'help' for module commands.",
                Config.ERROR_CODES['INVALID_COMMAND']
            )
        
        return output, should_exit
    
    async def handle_config_panel(self, command_lower, user_input):
        """Handle commands in config panel"""
        output = ""
        should_exit = False
        
        if command_lower == "exit":
            output = await self.handle_exit()
            should_exit = True
        elif command_lower == "back":
            self.current_panel = "main"
            self.current_path = "System > Root"
            output = f"{ANSIColors.GREEN}Returned to main menu.{ANSIColors.RESET}"
        elif command_lower == "help":
            output = self.show_config_help()
        elif command_lower == "prefix show":
            prefix = self.db.get_command_prefix(self.guild.id)
            output = f"{ANSIColors.BRIGHT_CYAN}Current command prefix:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}{prefix}{ANSIColors.RESET}"
        elif command_lower == "prefix":
            # Show usage when user types just "prefix"
            current_prefix = self.db.get_command_prefix(self.guild.id)
            output = f"""{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}prefix <new_prefix>{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Examples:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_CYAN}prefix !{ANSIColors.RESET}     - Set prefix to !
  {ANSIColors.BRIGHT_CYAN}prefix ?{ANSIColors.RESET}     - Set prefix to ?
  {ANSIColors.BRIGHT_CYAN}prefix show{ANSIColors.RESET}  - Show current prefix

{ANSIColors.BRIGHT_BLACK}Current prefix:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}{current_prefix}{ANSIColors.RESET}"""
        elif command_lower.startswith("prefix "):
            new_prefix = user_input[7:].strip()
            if not new_prefix:
                # User typed "prefix " with just space
                current_prefix = self.db.get_command_prefix(self.guild.id)
                output = f"""{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}prefix <new_prefix>{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Current prefix:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}{current_prefix}{ANSIColors.RESET}"""
            else:
                output = await self.handle_prefix_change(new_prefix)
        elif command_lower == "clearsettings":
            output = await self.handle_clearsettings_request()
        elif command_lower == "embeds":
            self.current_panel = "embeds"
            self.current_path = "Configuration > Embeds"
            output = self.show_embed_menu()
        elif command_lower == "logging":
            if PANELS_AVAILABLE:
                self.current_panel = "logging"
                self.current_path = "Configuration > Logging"
                output = await self.logging_panel.show_logging_list_animated()
            else:
                output = f"{ANSIColors.RED}❌ Logging panel not available.{ANSIColors.RESET}"
        elif command_lower == "settings":
            output = self.show_settings()
        elif command_lower == "settings cnf on":
            self.db.set_setting(self.guild.id, 'show_command_not_found', True)
            output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Command not found messages {ANSIColors.GREEN}enabled{ANSIColors.RESET}."
        elif command_lower == "settings cnf off":
            self.db.set_setting(self.guild.id, 'show_command_not_found', False)
            output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Command not found messages {ANSIColors.RED}disabled{ANSIColors.RESET}."
        else:
            output = format_error(
                f"Invalid command '{user_input}'. Type 'help' for config commands.",
                Config.ERROR_CODES['INVALID_COMMAND']
            )
        
        return output, should_exit
    
    async def handle_warn_config_panel(self, command_lower, user_input):
        """Handle commands in warn config panel"""
        output = ""
        should_exit = False
        
        if command_lower == "exit":
            output = await self.handle_exit()
            should_exit = True
        elif command_lower == "back":
            self.current_panel = "modules"
            self.current_path = "Modules"
            output = f"{ANSIColors.GREEN}Returned to modules menu.{ANSIColors.RESET}"
        elif command_lower == "help":
            output = self.show_warn_config_help()
        elif command_lower == "show":
            output = self.show_warn_config()
        elif command_lower == "auto enable":
            output = await self.handle_warn_auto_enable()
        elif command_lower == "auto disable":
            output = await self.handle_warn_auto_disable()
        elif command_lower.startswith("threshold "):
            threshold_str = user_input[10:].strip()
            output = await self.handle_warn_threshold(threshold_str)
        elif command_lower == "threshold":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}threshold <number>{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Example: threshold 3{ANSIColors.RESET}"
        elif command_lower.startswith("punishment "):
            punishment_type = user_input[11:].strip()
            output = await self.handle_warn_punishment_type(punishment_type)
        elif command_lower == "punishment":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}punishment <type>{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Types: mute, kick, ban{ANSIColors.RESET}"
        elif command_lower.startswith("duration "):
            duration_str = user_input[9:].strip()
            output = await self.handle_warn_duration(duration_str)
        elif command_lower == "duration":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}duration <time>{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Example: duration 1h, duration 30m{ANSIColors.RESET}"
        elif command_lower == "immunity on":
            output = await self.handle_warn_immunity(True)
        elif command_lower == "immunity off":
            output = await self.handle_warn_immunity(False)
        elif command_lower == "immunity":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}immunity on{ANSIColors.RESET} or {ANSIColors.BRIGHT_WHITE}immunity off{ANSIColors.RESET}"
        elif command_lower == "dm on":
            output = await self.handle_warn_dm(True)
        elif command_lower == "dm off":
            output = await self.handle_warn_dm(False)
        elif command_lower == "dm":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}dm on{ANSIColors.RESET} or {ANSIColors.BRIGHT_WHITE}dm off{ANSIColors.RESET}"
        else:
            output = format_error(
                f"Invalid command '{user_input}'. Type 'help' for warn config commands.",
                Config.ERROR_CODES['INVALID_COMMAND']
            )
        
        return output, should_exit
    
    def show_modules_menu(self):
        """Show modules panel menu"""
        return f"""
{ANSIColors.BRIGHT_GREEN}Entered modules panel.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Type 'help' for module commands or 'back' to return.{ANSIColors.RESET}
"""
    
    def show_config_menu(self):
        """Show config panel menu"""
        return f"""
{ANSIColors.BRIGHT_GREEN}Entered configuration panel.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Type 'help' for config commands or 'back' to return.{ANSIColors.RESET}
"""
    
    def show_security_menu(self):
        """Show security panel menu"""
        if PANELS_AVAILABLE and hasattr(self, 'security_panel'):
            return self.security_panel.show_security_help()
        return f"""
{ANSIColors.BRIGHT_GREEN}Entered security panel.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Type 'help' for security commands or 'back' to return.{ANSIColors.RESET}
"""
    
    def show_settings(self):
        """Show all server settings"""
        cnf_enabled = self.db.get_setting(self.guild.id, 'show_command_not_found', True)
        cnf_status = f"{ANSIColors.GREEN}enabled{ANSIColors.RESET}" if cnf_enabled else f"{ANSIColors.RED}disabled{ANSIColors.RESET}"
        
        prefix = self.db.get_command_prefix(self.guild.id)
        
        return f"""
{ANSIColors.BRIGHT_YELLOW}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.BRIGHT_YELLOW}║{ANSIColors.RESET}           Server Settings
{ANSIColors.BRIGHT_YELLOW}{'═' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}General:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}Command Prefix:{ANSIColors.RESET}              {prefix}

{ANSIColors.BRIGHT_CYAN}Error Messages:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}Command Not Found:{ANSIColors.RESET}           {cnf_status}
  
{ANSIColors.BRIGHT_BLACK}Toggle settings:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_CYAN}settings cnf on/off{ANSIColors.RESET}  - Toggle command not found messages
"""
    
    def show_module_help(self):
        """Show module commands help"""
        commands_list = ""
        for cmd, desc in Config.MODULE_COMMANDS.items():
            commands_list += f"{ANSIColors.BRIGHT_BLACK}  {ANSIColors.BRIGHT_CYAN}{cmd.upper():<18}{ANSIColors.RESET} - {desc}\n"
        
        return f"""
{ANSIColors.BRIGHT_CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}        {ANSIColors.BOLD}Module Commands{ANSIColors.RESET}                  {ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}{'═' * 46}{ANSIColors.RESET}

{commands_list}
{ANSIColors.BRIGHT_BLACK}Type any command to execute it.{ANSIColors.RESET}
"""
    
    def show_config_help(self):
        """Show config commands help"""
        commands_list = ""
        for cmd, desc in Config.CONFIG_COMMANDS.items():
            commands_list += f"{ANSIColors.BRIGHT_BLACK}  {ANSIColors.BRIGHT_CYAN}{cmd.upper():<18}{ANSIColors.RESET} - {desc}\n"
        
        return f"""
{ANSIColors.BRIGHT_CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}        {ANSIColors.BOLD}Configuration Commands{ANSIColors.RESET}          {ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}{'═' * 46}{ANSIColors.RESET}

{commands_list}
{ANSIColors.BRIGHT_BLACK}Type any command to execute it.{ANSIColors.RESET}
"""
    
    def show_warn_config_help(self):
        """Show warn config commands help"""
        return f"""
{ANSIColors.YELLOW}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.YELLOW}║{ANSIColors.RESET}     {ANSIColors.BOLD}Warning Configuration Commands{ANSIColors.RESET}      {ANSIColors.YELLOW}║{ANSIColors.RESET}
{ANSIColors.YELLOW}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Auto-Punishment:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}auto enable{ANSIColors.RESET}          Enable auto-punishment
  {ANSIColors.BRIGHT_WHITE}auto disable{ANSIColors.RESET}         Disable auto-punishment
  {ANSIColors.BRIGHT_WHITE}threshold <n>{ANSIColors.RESET}        Set warning threshold
  {ANSIColors.BRIGHT_WHITE}punishment <type>{ANSIColors.RESET}    Set punishment (mute/kick/ban)
  {ANSIColors.BRIGHT_WHITE}duration <time>{ANSIColors.RESET}      Set punishment duration

{ANSIColors.BRIGHT_CYAN}Staff & DM Settings:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}immunity on/off{ANSIColors.RESET}     Staff immune to auto-punish
  {ANSIColors.BRIGHT_WHITE}dm on/off{ANSIColors.RESET}           Send DM to warned users

{ANSIColors.BRIGHT_CYAN}Other:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}show{ANSIColors.RESET}                Show current configuration
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                Return to modules
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}                Exit terminal

{ANSIColors.BRIGHT_BLACK}Type 'show' to see current settings.{ANSIColors.RESET}
"""
    
    def show_warn_config(self):
        """Show current warning configuration"""
        config = self.db.get_warn_config(self.guild.id)
        
        # Format settings
        auto_status = f"{ANSIColors.GREEN}Enabled{ANSIColors.RESET}" if config['auto_punish_enabled'] else f"{ANSIColors.RED}Disabled{ANSIColors.RESET}"
        threshold = config['warn_threshold'] if config['warn_threshold'] > 0 else f"{ANSIColors.BRIGHT_BLACK}Not set{ANSIColors.RESET}"
        punishment = config['punishment_type'] if config['punishment_type'] else f"{ANSIColors.BRIGHT_BLACK}Not set{ANSIColors.RESET}"
        duration = config['punishment_duration'] if config['punishment_duration'] else f"{ANSIColors.BRIGHT_BLACK}Not set{ANSIColors.RESET}"
        immunity = f"{ANSIColors.GREEN}On{ANSIColors.RESET}" if config['staff_immune'] else f"{ANSIColors.RED}Off{ANSIColors.RESET}"
        dm_setting = f"{ANSIColors.GREEN}On{ANSIColors.RESET}" if config['dm_on_warn'] else f"{ANSIColors.RED}Off{ANSIColors.RESET}"
        
        return f"""
{ANSIColors.YELLOW}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.YELLOW}║{ANSIColors.RESET}      {ANSIColors.BOLD}Warning Configuration{ANSIColors.RESET}              {ANSIColors.YELLOW}║{ANSIColors.RESET}
{ANSIColors.YELLOW}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Auto-Punishment:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}Status:{ANSIColors.RESET}          {auto_status}
  {ANSIColors.BRIGHT_BLACK}Threshold:{ANSIColors.RESET}       {threshold}
  {ANSIColors.BRIGHT_BLACK}Punishment:{ANSIColors.RESET}      {punishment}
  {ANSIColors.BRIGHT_BLACK}Duration:{ANSIColors.RESET}        {duration}

{ANSIColors.BRIGHT_CYAN}Additional Settings:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}Staff Immunity:{ANSIColors.RESET}  {immunity}
  {ANSIColors.BRIGHT_BLACK}DM on Warn:{ANSIColors.RESET}      {dm_setting}

{ANSIColors.BRIGHT_BLACK}Type 'help' for configuration commands.{ANSIColors.RESET}
"""
    
    async def handle_warn_auto_enable(self):
        """Enable auto-punishment"""
        config = self.db.get_warn_config(self.guild.id)
        
        if config['auto_punish_enabled']:
            return f"{ANSIColors.YELLOW}Auto-punishment is already enabled.{ANSIColors.RESET}"
        
        # Check if threshold and punishment are set
        if not config['warn_threshold'] or config['warn_threshold'] <= 0:
            return format_error(
                "Please set a warning threshold first using 'threshold <number>'.",
                Config.ERROR_CODES['INVALID_INPUT']
            )
        
        if not config['punishment_type']:
            return format_error(
                "Please set a punishment type first using 'punishment <type>'.",
                Config.ERROR_CODES['INVALID_INPUT']
            )
        
        self.db.set_warn_config(
            self.guild.id,
            True,
            config['warn_threshold'],
            config['punishment_type'],
            config['punishment_duration'],
            config['staff_immune'],
            config['dm_on_warn']
        )
        
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Auto-punishment enabled at {ANSIColors.BRIGHT_WHITE}{config['warn_threshold']}{ANSIColors.RESET} warnings."
    
    async def handle_warn_auto_disable(self):
        """Disable auto-punishment"""
        config = self.db.get_warn_config(self.guild.id)
        
        if not config['auto_punish_enabled']:
            return f"{ANSIColors.YELLOW}Auto-punishment is already disabled.{ANSIColors.RESET}"
        
        self.db.set_warn_config(
            self.guild.id,
            False,
            config['warn_threshold'],
            config['punishment_type'],
            config['punishment_duration'],
            config['staff_immune'],
            config['dm_on_warn']
        )
        
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Auto-punishment disabled."
    
    async def handle_warn_threshold(self, threshold_str):
        """Set warning threshold"""
        try:
            threshold = int(threshold_str)
            if threshold <= 0:
                return format_error("Threshold must be a positive number.", Config.ERROR_CODES['INVALID_INPUT'])
        except ValueError:
            return format_error("Invalid threshold. Please provide a number.", Config.ERROR_CODES['INVALID_INPUT'])
        
        config = self.db.get_warn_config(self.guild.id)
        
        self.db.set_warn_config(
            self.guild.id,
            config['auto_punish_enabled'],
            threshold,
            config['punishment_type'],
            config['punishment_duration'],
            config['staff_immune'],
            config['dm_on_warn']
        )
        
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Warning threshold set to {ANSIColors.BRIGHT_WHITE}{threshold}{ANSIColors.RESET} warnings."
    
    async def handle_warn_punishment_type(self, punishment_type):
        """Set punishment type"""
        valid_types = ['mute', 'kick', 'ban']
        punishment_lower = punishment_type.lower()
        
        if punishment_lower not in valid_types:
            return format_error(
                f"Invalid punishment type. Valid types: {', '.join(valid_types)}",
                Config.ERROR_CODES['INVALID_INPUT']
            )
        
        config = self.db.get_warn_config(self.guild.id)
        
        self.db.set_warn_config(
            self.guild.id,
            config['auto_punish_enabled'],
            config['warn_threshold'],
            punishment_lower,
            config['punishment_duration'],
            config['staff_immune'],
            config['dm_on_warn']
        )
        
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Punishment type set to {ANSIColors.BRIGHT_WHITE}{punishment_lower}{ANSIColors.RESET}."
    
    async def handle_warn_duration(self, duration_str):
        """Set punishment duration"""
        # Basic duration validation
        if not duration_str:
            return format_error("Please provide a duration.", Config.ERROR_CODES['INVALID_INPUT'])
        
        # Accept formats like: 1h, 30m, 1d, etc.
        import re
        pattern = r'^\d+[mhd]$'
        if not re.match(pattern, duration_str.lower()):
            return format_error(
                "Invalid duration format. Use formats like: 30m, 1h, 1d",
                Config.ERROR_CODES['INVALID_DURATION']
            )
        
        config = self.db.get_warn_config(self.guild.id)
        
        self.db.set_warn_config(
            self.guild.id,
            config['auto_punish_enabled'],
            config['warn_threshold'],
            config['punishment_type'],
            duration_str.lower(),
            config['staff_immune'],
            config['dm_on_warn']
        )
        
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Punishment duration set to {ANSIColors.BRIGHT_WHITE}{duration_str}{ANSIColors.RESET}."
    
    async def handle_warn_immunity(self, enabled):
        """Toggle staff immunity"""
        self.db.set_staff_immunity(self.guild.id, enabled)
        
        status = f"{ANSIColors.GREEN}enabled{ANSIColors.RESET}" if enabled else f"{ANSIColors.RED}disabled{ANSIColors.RESET}"
        
        if enabled:
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Staff immunity {status}. Staff members will not be auto-punished."
        else:
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Staff immunity {status}. Staff members can be auto-punished."
    
    async def handle_warn_dm(self, enabled):
        """Toggle DM on warn"""
        self.db.set_dm_on_warn(self.guild.id, enabled)
        
        status = f"{ANSIColors.GREEN}enabled{ANSIColors.RESET}" if enabled else f"{ANSIColors.RED}disabled{ANSIColors.RESET}"
        
        if enabled:
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} DM on warn {status}. Users will receive a DM when warned."
        else:
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} DM on warn {status}. Users will not receive a DM when warned."
    
    def show_module_list(self):
        """Show list of all modules and their status"""
        # Get current module states
        states = self.db.get_all_module_states(self.guild.id)
        
        modules_text = ""
        for module_id, module_info in Config.MODULES.items():
            enabled = states.get(module_id, False)
            status = f"{ANSIColors.GREEN}ENABLED{ANSIColors.RESET}" if enabled else f"{ANSIColors.RED}DISABLED{ANSIColors.RESET}"
            placeholder = f" {ANSIColors.YELLOW}[PLACEHOLDER]{ANSIColors.RESET}" if module_info['placeholder'] else ""
            
            modules_text += f"{ANSIColors.BRIGHT_BLACK}► {ANSIColors.BRIGHT_CYAN}{module_info['name']:<20}{ANSIColors.RESET} {status}{placeholder}\n"
            modules_text += f"  {ANSIColors.BRIGHT_BLACK}{module_info['description']}{ANSIColors.RESET}\n"
            modules_text += f"  {ANSIColors.BRIGHT_BLACK}ID: {ANSIColors.BRIGHT_WHITE}{module_id}{ANSIColors.RESET}\n\n"
        
        return f"""
{ANSIColors.BRIGHT_CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}            Available Modules                  {ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}{'═' * 46}{ANSIColors.RESET}

{modules_text}
{ANSIColors.BRIGHT_BLACK}Use 'module enable/disable <id>' to toggle.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Example: module enable warns{ANSIColors.RESET}
"""
    
    async def show_module_list_animated(self):
        """Show list of all modules with animation"""
        states = self.db.get_all_module_states(self.guild.id)
        
        header = f"""{ANSIColors.BRIGHT_CYAN}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}              Available Modules                 {ANSIColors.BRIGHT_CYAN}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_CYAN}{'═' * 50}{ANSIColors.RESET}"""
        
        # Build items list
        items = []
        for module_id, module_info in Config.MODULES.items():
            enabled = states.get(module_id, False)
            status = f"{ANSIColors.GREEN}ENABLED{ANSIColors.RESET}" if enabled else f"{ANSIColors.RED}DISABLED{ANSIColors.RESET}"
            placeholder = f" {ANSIColors.YELLOW}[PLACEHOLDER]{ANSIColors.RESET}" if module_info.get('placeholder', False) else ""
            
            item = f"{ANSIColors.BRIGHT_BLACK}► {ANSIColors.BRIGHT_CYAN}{module_info['name']:<18}{ANSIColors.RESET} {status}{placeholder}\n"
            item += f"  {module_info['description']}\n"
            item += f"  {ANSIColors.BRIGHT_BLACK}ID:{ANSIColors.RESET} {ANSIColors.WHITE}{module_id}{ANSIColors.RESET}"
            items.append(item)
        
        footer = f"{ANSIColors.BRIGHT_BLACK}Use 'module enable <id>' or 'module disable <id>'{ANSIColors.RESET}"
        
        await self.animated_list(header, items, footer, delay=0.4)
        return ""
    
    
    async def handle_module_enable(self, module_name):
        """Enable a module"""
        if module_name not in Config.MODULES:
            # Show available module IDs
            valid_ids = ", ".join([f"{ANSIColors.BRIGHT_CYAN}{mid}{ANSIColors.RESET}" for mid in Config.MODULES.keys()])
            error_msg = format_error(f"Module '{module_name}' not found.", Config.ERROR_CODES['MODULE_NOT_FOUND'])
            return f"{error_msg}\n{ANSIColors.BRIGHT_BLACK}Valid IDs: {valid_ids}{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Use 'module list' to see all modules.{ANSIColors.RESET}"
        
        # Check if already enabled
        if self.db.get_module_state(self.guild.id, module_name):
            return format_error(
                f"Module '{module_name}' is already enabled.",
                Config.ERROR_CODES['MODULE_ALREADY_ENABLED']
            )
        
        # Enable module
        self.db.set_module_state(self.guild.id, module_name, True)
        
        # Log to logging module
        logging_cog = self.bot.get_cog('LoggingModule')
        if logging_cog:
            await logging_cog.log_bfos_action(
                self.guild, 'module', self.ctx.author,
                f"Module **{module_name}** was enabled",
                {'Module': module_name, 'Action': 'Enabled'}
            )
        
        module_info = Config.MODULES[module_name]
        placeholder_note = f"\n{ANSIColors.YELLOW}Note: This module is currently a placeholder.{ANSIColors.RESET}" if module_info['placeholder'] else ""
        
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Module '{ANSIColors.BRIGHT_CYAN}{module_info['name']}{ANSIColors.RESET}' has been {ANSIColors.GREEN}enabled{ANSIColors.RESET}.{placeholder_note}"
    
    async def handle_module_disable(self, module_name):
        """Disable a module"""
        if module_name not in Config.MODULES:
            # Show available module IDs
            valid_ids = ", ".join([f"{ANSIColors.BRIGHT_CYAN}{mid}{ANSIColors.RESET}" for mid in Config.MODULES.keys()])
            error_msg = format_error(f"Module '{module_name}' not found.", Config.ERROR_CODES['MODULE_NOT_FOUND'])
            return f"{error_msg}\n{ANSIColors.BRIGHT_BLACK}Valid IDs: {valid_ids}{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Use 'module list' to see all modules.{ANSIColors.RESET}"
        
        # Check if already disabled
        if not self.db.get_module_state(self.guild.id, module_name):
            return format_error(
                f"Module '{module_name}' is already disabled.",
                Config.ERROR_CODES['MODULE_ALREADY_DISABLED']
            )
        
        # Disable module
        self.db.set_module_state(self.guild.id, module_name, False)
        
        # Log to logging module
        logging_cog = self.bot.get_cog('LoggingModule')
        if logging_cog:
            await logging_cog.log_bfos_action(
                self.guild, 'module', self.ctx.author,
                f"Module **{module_name}** was disabled",
                {'Module': module_name, 'Action': 'Disabled'}
            )
        
        module_info = Config.MODULES[module_name]
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Module '{ANSIColors.BRIGHT_CYAN}{module_info['name']}{ANSIColors.RESET}' has been {ANSIColors.RED}disabled{ANSIColors.RESET}."
    
    async def handle_module_configure(self, module_name):
        """Configure a module"""
        if module_name not in Config.MODULES:
            # Show available module IDs
            valid_ids = ", ".join([f"{ANSIColors.BRIGHT_CYAN}{mid}{ANSIColors.RESET}" for mid in Config.MODULES.keys()])
            error_msg = format_error(f"Module '{module_name}' not found.", Config.ERROR_CODES['MODULE_NOT_FOUND'])
            return f"{error_msg}\n{ANSIColors.BRIGHT_BLACK}Valid IDs: {valid_ids}{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Use 'module list' to see all modules.{ANSIColors.RESET}"
        
        module_info = Config.MODULES[module_name]
        
        if not module_info['configurable']:
            return format_error(
                f"Module '{module_name}' is not configurable.",
                Config.ERROR_CODES['INVALID_COMMAND']
            )
        
        if module_name == "warns":
            self.current_panel = "warn_config"
            self.current_path = "Modules > Warns > Configuration"
            return f"{ANSIColors.BRIGHT_GREEN}Entering warn configuration...{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Type 'help' for options or 'back' to return.{ANSIColors.RESET}"
        
        return f"{ANSIColors.YELLOW}Configuration for this module is not yet implemented.{ANSIColors.RESET}"
    
    async def handle_prefix_change(self, new_prefix):
        """Change command prefix"""
        if len(new_prefix) > 5:
            return format_error(
                "Prefix must be 5 characters or less.",
                Config.ERROR_CODES['INVALID_PREFIX']
            )
        
        if not new_prefix or new_prefix.isspace():
            return format_error(
                "Prefix cannot be empty or whitespace.",
                Config.ERROR_CODES['INVALID_PREFIX']
            )
        
        self.db.set_command_prefix(self.guild.id, new_prefix)
        
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Command prefix changed to: {ANSIColors.BRIGHT_WHITE}{new_prefix}{ANSIColors.RESET}"
    
    async def handle_clearsettings_request(self):
        """Request confirmation for clearing all settings"""
        # Set pending confirmation
        self.pending_confirmation = {
            'action': 'clearsettings',
            'data': {}
        }
        
        return f"""
{ANSIColors.RED}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.RED}║{ANSIColors.RESET}    {ANSIColors.BOLD}{ANSIColors.RED}⚠  WARNING: Clear All Settings{ANSIColors.RESET}     {ANSIColors.RED}║{ANSIColors.RESET}
{ANSIColors.RED}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.YELLOW}This will clear:{ANSIColors.RESET}
  {ANSIColors.RED}✗{ANSIColors.RESET} Module states (enabled/disabled)
  {ANSIColors.RED}✗{ANSIColors.RESET} Staff role assignments
  {ANSIColors.RED}✗{ANSIColors.RESET} Staff roles configuration
  {ANSIColors.RED}✗{ANSIColors.RESET} Warning configurations
  {ANSIColors.RED}✗{ANSIColors.RESET} Embed configurations
  {ANSIColors.RED}✗{ANSIColors.RESET} Command prefix (resets to ';')

{ANSIColors.GREEN}This will NOT clear:{ANSIColors.RESET}
  {ANSIColors.GREEN}✓{ANSIColors.RESET} Discord roles (preserved)
  {ANSIColors.GREEN}✓{ANSIColors.RESET} User roles (preserved)
  {ANSIColors.GREEN}✓{ANSIColors.RESET} Moderation case history (preserved)

{ANSIColors.BRIGHT_WHITE}Type 'CONFIRM' to proceed or 'CANCEL' to abort.{ANSIColors.RESET}
"""
    
    async def execute_pending_confirmation(self):
        """Execute a pending confirmation action"""
        if not self.pending_confirmation:
            return format_error("No pending action to confirm.", Config.ERROR_CODES['COMMAND_FAILED']), False
        
        action = self.pending_confirmation.get('action', '').strip()
        details = self.pending_confirmation.get('details', {})
        
        print(f"[CONFIRM] Executing action: '{action}', details: {details}")
        
        if action == 'clearsettings':
            return await self.handle_clearsettings_execute()
        elif action == 'backup_restore':
            # Handle backup restore
            backup_id = details.get('backup_id')
            keep_channels = details.get('keep_channels', False)
            keep_roles = details.get('keep_roles', False)
            print(f"[CONFIRM] Backup restore: backup_id={backup_id}, keep_channels={keep_channels}, keep_roles={keep_roles}")
            if backup_id and hasattr(self, 'backup_panel'):
                result = await self.backup_panel.execute_backup_restore(backup_id, keep_channels, keep_roles)
                return result, False
            return format_error("Backup restore failed - missing backup ID.", Config.ERROR_CODES['COMMAND_FAILED']), False
        elif action == 'backup_delete':
            # Handle backup delete
            backup_id = details.get('backup_id')
            print(f"[CONFIRM] Backup delete: backup_id={backup_id}, has_panel={hasattr(self, 'backup_panel')}")
            if backup_id and hasattr(self, 'backup_panel'):
                result = await self.backup_panel.execute_backup_delete(backup_id)
                return result, False
            return format_error("Backup delete failed - missing backup ID.", Config.ERROR_CODES['COMMAND_FAILED']), False
        elif action == 'lockdown':
            # Handle lockdown activation
            if hasattr(self, 'security_panel'):
                result = await self.security_panel.execute_lockdown()
                return result, False
            return format_error("Security panel not available.", Config.ERROR_CODES['COMMAND_FAILED']), False
        
        print(f"[CONFIRM] Unknown action: '{action}'")
        return format_error(f"Unknown action: {action}", Config.ERROR_CODES['COMMAND_FAILED']), False
    
    async def handle_clearsettings_execute(self):
        """Execute the clearsettings action with progress updates"""
        await self.send_progress_update("Clearing module states...")
        await self.send_progress_update("Clearing staff assignments...")
        await self.send_progress_update("Clearing staff roles...")
        await self.send_progress_update("Clearing warning configurations...")
        await self.send_progress_update("Clearing embed configurations...")
        await self.send_progress_update("Resetting command prefix...")
        
        # Actually clear the settings
        success = self.db.clear_all_settings(self.guild.id)
        
        if success:
            output = f"""
{ANSIColors.GREEN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.GREEN}║{ANSIColors.RESET}      {ANSIColors.BOLD}Settings Cleared Successfully{ANSIColors.RESET}        {ANSIColors.GREEN}║{ANSIColors.RESET}
{ANSIColors.GREEN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.GREEN}✓{ANSIColors.RESET} All server settings have been cleared.
{ANSIColors.GREEN}✓{ANSIColors.RESET} Command prefix reset to: {ANSIColors.BRIGHT_WHITE};{ANSIColors.RESET}
{ANSIColors.GREEN}✓{ANSIColors.RESET} All modules disabled.

{ANSIColors.BRIGHT_BLACK}You can now reconfigure your server.{ANSIColors.RESET}
"""
            return output, False
        else:
            return format_error(
                "Failed to clear settings. Check database connection.",
                Config.ERROR_CODES['DATABASE_ERROR']
            ), False
    
    def show_staff_menu(self):
        """Show staff management menu"""
        return f"""
{ANSIColors.BLUE}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BLUE}║{ANSIColors.RESET}      {ANSIColors.BOLD}Staff Management Panel{ANSIColors.RESET}             {ANSIColors.BLUE}║{ANSIColors.RESET}
{ANSIColors.BLUE}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Manage server staff roles and assignments{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Available Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}staff list{ANSIColors.RESET}                - List all staff roles
  {ANSIColors.BRIGHT_WHITE}staff import <id>{ANSIColors.RESET}        - Import role(s)
  {ANSIColors.BRIGHT_WHITE}staff rename <id> <name>{ANSIColors.RESET} - Rename staff role
  {ANSIColors.BRIGHT_WHITE}staff delete <id>{ANSIColors.RESET}        - Delete staff role
  {ANSIColors.BRIGHT_WHITE}staff add <user> <role>{ANSIColors.RESET}  - Add staff to user
  {ANSIColors.BRIGHT_WHITE}staff remove <user>{ANSIColors.RESET}      - Remove all staff from user
  {ANSIColors.BRIGHT_WHITE}staff sync{ANSIColors.RESET}               - Sync Discord roles with database
  {ANSIColors.BRIGHT_WHITE}help{ANSIColors.RESET}                     - Show detailed help
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                     - Return to main menu
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}                     - Exit terminal

{ANSIColors.BRIGHT_BLACK}Type a command to continue...{ANSIColors.RESET}
"""
    
    def show_staff_help(self):
        """Show staff panel help"""
        return f"""
{ANSIColors.BLUE}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BLUE}║{ANSIColors.RESET}        {ANSIColors.BOLD}Staff Panel Commands{ANSIColors.RESET}            {ANSIColors.BLUE}║{ANSIColors.RESET}
{ANSIColors.BLUE}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}staff import <role_id> [role_id ...]{ANSIColors.RESET}
  Import one or more Discord roles as staff roles.
  Uses role name and hierarchy position.
  Example: {ANSIColors.BRIGHT_BLACK}staff import 123456789{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}staff rename <id> <new_name>{ANSIColors.RESET}
  Rename a staff role's display name.
  Example: {ANSIColors.BRIGHT_BLACK}staff rename 1 Head Admin{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}staff list{ANSIColors.RESET}
  List all staff roles, members, and their roles.
  Shows hierarchy from highest to lowest.

{ANSIColors.BRIGHT_CYAN}staff delete <id>{ANSIColors.RESET}
  Remove a staff role from the system.
  Does NOT delete the Discord role.
  Example: {ANSIColors.BRIGHT_BLACK}staff delete 1{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}staff add <user_id> <staff_id>{ANSIColors.RESET}
  Assign a staff role to a user.
  Example: {ANSIColors.BRIGHT_BLACK}staff add 987654321 1{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}staff remove <user_id>{ANSIColors.RESET}
  Remove all staff roles from a user.
  Removes both Discord role and database entry.
  Example: {ANSIColors.BRIGHT_BLACK}staff remove 987654321{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}staff sync{ANSIColors.RESET}
  Sync Discord roles with database.
  Fixes mismatches where users have role in Discord
  but not in database (or vice versa).
  Auto-runs when importing roles.

{ANSIColors.BRIGHT_CYAN}back{ANSIColors.RESET}
  Return to main menu.

{ANSIColors.BRIGHT_CYAN}exit{ANSIColors.RESET}
  Exit terminal and save all changes.
"""
    
    async def handle_staff_panel(self, command_lower, user_input):
        """Handle commands in staff panel"""
        output = ""
        should_exit = False
        
        if command_lower == "exit":
            output = await self.handle_exit()
            should_exit = True
        elif command_lower == "back":
            self.current_panel = "main"
            self.current_path = "System > Root"
            output = f"{ANSIColors.GREEN}Returned to main menu.{ANSIColors.RESET}"
        elif command_lower == "help":
            output = self.show_staff_help()
        elif command_lower == "permissions":
            # Enter permissions subpanel
            self.current_panel = "permissions"
            self.current_path = "Staff > Permissions"
            from cogs.terminal_permissions import TerminalPermissions
            output = TerminalPermissions(self).show_help()
        elif command_lower == "staff list":
            output = await self.handle_staff_list()
        elif command_lower.startswith("staff import "):
            role_ids_str = user_input[13:].strip()
            output = await self.handle_staff_import(role_ids_str)
        elif command_lower == "staff import":
            output = f"""{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}staff import <role_id> [role_id ...]{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Examples:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_CYAN}staff import 123456789{ANSIColors.RESET}              - Import one role
  {ANSIColors.BRIGHT_CYAN}staff import 123456789 987654321{ANSIColors.RESET}    - Import multiple roles"""
        elif command_lower.startswith("staff rename "):
            args = user_input[13:].strip().split(None, 1)
            if len(args) >= 2:
                output = await self.handle_staff_rename(args[0], args[1])
            else:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}staff rename <id> <new_name>{ANSIColors.RESET}"
        elif command_lower == "staff rename":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}staff rename <id> <new_name>{ANSIColors.RESET}"
        elif command_lower.startswith("staff delete "):
            staff_id_str = user_input[13:].strip()
            output = await self.handle_staff_delete(staff_id_str)
        elif command_lower == "staff delete":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}staff delete <id>{ANSIColors.RESET}"
        elif command_lower.startswith("staff add "):
            args = user_input[10:].strip().split(None, 1)
            if len(args) >= 2:
                output = await self.handle_staff_add_user(args[0], args[1])
            else:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}staff add <user_id> <staff_id>{ANSIColors.RESET}"
        elif command_lower == "staff add":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}staff add <user_id> <staff_id>{ANSIColors.RESET}"
        elif command_lower.startswith("staff remove "):
            user_id_str = user_input[13:].strip()
            output = await self.handle_staff_remove_user(user_id_str)
        elif command_lower == "staff remove":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}staff remove <user_id>{ANSIColors.RESET}"
        elif command_lower == "staff sync":
            output = await self.handle_staff_sync()
        elif command_lower == "staff":
            output = f"""{ANSIColors.YELLOW}Staff Commands:{ANSIColors.RESET}

  {ANSIColors.BRIGHT_CYAN}staff list{ANSIColors.RESET}                - List all staff
  {ANSIColors.BRIGHT_CYAN}staff import <id>{ANSIColors.RESET}        - Import role(s)
  {ANSIColors.BRIGHT_CYAN}staff rename <id> <name>{ANSIColors.RESET} - Rename role
  {ANSIColors.BRIGHT_CYAN}staff delete <id>{ANSIColors.RESET}        - Delete role
  {ANSIColors.BRIGHT_CYAN}staff add <user> <role>{ANSIColors.RESET}  - Add to user
  {ANSIColors.BRIGHT_CYAN}staff remove <user>{ANSIColors.RESET}      - Remove from user
  {ANSIColors.BRIGHT_CYAN}staff sync{ANSIColors.RESET}               - Sync roles

{ANSIColors.BRIGHT_BLACK}Type 'help' for detailed information.{ANSIColors.RESET}"""
        else:
            output = format_error(
                f"Invalid command '{user_input}'. Type 'help' for staff commands.",
                Config.ERROR_CODES['INVALID_COMMAND']
            )
        
        return output, should_exit
    
    async def handle_staff_list(self):
        """List all staff roles and members"""
        staff_roles = self.db.get_all_staff_roles(self.guild.id)
        staff_members = self.db.get_staff_members(self.guild.id)
        
        if not staff_roles:
            return f"{ANSIColors.YELLOW}No staff roles configured.{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Use 'staff import <role_id>' to add staff roles.{ANSIColors.RESET}"
        
        # Build roles list
        roles_text = ""
        for role in staff_roles:
            roles_text += f"{ANSIColors.BRIGHT_BLACK}► {ANSIColors.BRIGHT_CYAN}[{role['id']}]{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}{role['display_name']}{ANSIColors.RESET}\n"
            roles_text += f"  {ANSIColors.BRIGHT_BLACK}Role:{ANSIColors.RESET} {role['role_name']} {ANSIColors.BRIGHT_BLACK}│ Position:{ANSIColors.RESET} {role['position']}\n\n"
        
        # Build members list
        members_text = ""
        if staff_members:
            for user_id in staff_members:
                try:
                    member = await self.guild.fetch_member(user_id)
                    user_roles = self.db.get_user_staff_roles(self.guild.id, user_id)
                    role_names = [r['display_name'] for r in user_roles]
                    
                    members_text += f"{ANSIColors.BRIGHT_BLACK}► {ANSIColors.BRIGHT_WHITE}{member.name}{ANSIColors.RESET} {ANSIColors.BRIGHT_BLACK}({user_id}){ANSIColors.RESET}\n"
                    members_text += f"  {ANSIColors.BRIGHT_CYAN}{', '.join(role_names)}{ANSIColors.RESET}\n\n"
                except:
                    members_text += f"{ANSIColors.BRIGHT_BLACK}► User {user_id} (Not in server){ANSIColors.RESET}\n\n"
        else:
            members_text = f"{ANSIColors.BRIGHT_BLACK}No staff members assigned.{ANSIColors.RESET}\n"
        
        return f"""
{ANSIColors.BLUE}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BLUE}║{ANSIColors.RESET}          {ANSIColors.BOLD}Staff Roles{ANSIColors.RESET}                      {ANSIColors.BLUE}║{ANSIColors.RESET}
{ANSIColors.BLUE}{'═' * 46}{ANSIColors.RESET}

{roles_text}
{ANSIColors.BLUE}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BLUE}║{ANSIColors.RESET}          {ANSIColors.BOLD}Staff Members{ANSIColors.RESET}                    {ANSIColors.BLUE}║{ANSIColors.RESET}
{ANSIColors.BLUE}{'═' * 46}{ANSIColors.RESET}

{members_text}"""
    
    async def handle_staff_import(self, role_ids_str):
        """Import staff role(s) without auto-syncing members"""
        role_ids = role_ids_str.split()
        
        if not role_ids:
            return format_error("No role IDs provided.", Config.ERROR_CODES['INVALID_INPUT'])
        
        imported = []
        failed = []
        
        for role_id_str in role_ids:
            try:
                role_id = int(role_id_str)
                role = self.guild.get_role(role_id)
                
                if not role:
                    failed.append(f"{role_id} (not found)")
                    continue
                
                # Import the role (no auto-sync)
                staff_id = self.db.import_staff_role(
                    self.guild.id,
                    role_id,
                    role.name,
                    role.position
                )
                
                if staff_id:
                    imported.append(f"{ANSIColors.BRIGHT_CYAN}{role.name}{ANSIColors.RESET} (ID: {staff_id})")
                else:
                    failed.append(f"{role.name} (already exists)")
            
            except ValueError:
                failed.append(f"{role_id_str} (invalid ID)")
            except Exception as e:
                failed.append(f"{role_id_str} ({str(e)})")
        
        output = ""
        
        if imported:
            output += f"{ANSIColors.GREEN}✓ Imported {len(imported)} role(s):{ANSIColors.RESET}\n"
            for name in imported:
                output += f"  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {name}\n"
            output += f"\n{ANSIColors.BRIGHT_BLACK}Use 'staff sync' to sync existing members.{ANSIColors.RESET}"
        
        if failed:
            output += f"\n\n{ANSIColors.RED}✗ Failed {len(failed)} role(s):{ANSIColors.RESET}\n"
            for name in failed:
                output += f"  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {name}\n"
        
        return output if output else format_error("No roles imported.", Config.ERROR_CODES['COMMAND_FAILED'])
    
    async def handle_staff_rename(self, staff_id_str, new_name):
        """Rename a staff role"""
        try:
            staff_id = int(staff_id_str)
        except ValueError:
            return format_error("Invalid staff ID.", Config.ERROR_CODES['INVALID_STAFF_ID'])
        
        # Check if staff role exists
        staff_role = self.db.get_staff_role(self.guild.id, staff_id)
        if not staff_role:
            return format_error(f"Staff role {staff_id} not found.", Config.ERROR_CODES['STAFF_NOT_FOUND'])
        
        # Rename it
        success = self.db.rename_staff_role(self.guild.id, staff_id, new_name)
        
        if success:
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Staff role renamed to: {ANSIColors.BRIGHT_CYAN}{new_name}{ANSIColors.RESET}"
        else:
            return format_error("Failed to rename staff role.", Config.ERROR_CODES['COMMAND_FAILED'])
    
    async def handle_staff_delete(self, staff_id_str):
        """Delete a staff role"""
        try:
            staff_id = int(staff_id_str)
        except ValueError:
            return format_error("Invalid staff ID.", Config.ERROR_CODES['INVALID_STAFF_ID'])
        
        # Check if staff role exists
        staff_role = self.db.get_staff_role(self.guild.id, staff_id)
        if not staff_role:
            return format_error(f"Staff role {staff_id} not found.", Config.ERROR_CODES['STAFF_NOT_FOUND'])
        
        # Delete it
        success = self.db.delete_staff_role(self.guild.id, staff_id)
        
        if success:
            return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Staff role {ANSIColors.BRIGHT_CYAN}{staff_role['display_name']}{ANSIColors.RESET} has been deleted."
        else:
            return format_error("Failed to delete staff role.", Config.ERROR_CODES['COMMAND_FAILED'])
    
    async def handle_staff_add_user(self, user_id_str, staff_id_str):
        """Add staff role to user (gives Discord role + adds to database)"""
        try:
            user_id = int(user_id_str)
            staff_id = int(staff_id_str)
        except ValueError:
            return format_error("Invalid user ID or staff ID.", Config.ERROR_CODES['INVALID_INPUT'])
        
        # Check if staff role exists
        staff_role = self.db.get_staff_role(self.guild.id, staff_id)
        if not staff_role:
            return format_error(f"Staff role {staff_id} not found.", Config.ERROR_CODES['STAFF_NOT_FOUND'])
        
        # Get Discord role
        discord_role = self.guild.get_role(staff_role['role_id'])
        if not discord_role:
            return format_error(f"Discord role no longer exists. Consider deleting this staff role.", Config.ERROR_CODES['ROLE_NOT_FOUND'])
        
        # Check if user exists in server
        try:
            member = await self.guild.fetch_member(user_id)
        except:
            return format_error(f"User {user_id} not found in server.", Config.ERROR_CODES['MEMBER_NOT_FOUND'])
        
        # Check if user already has the role in database
        user_staff_roles = self.db.get_user_staff_roles(self.guild.id, user_id)
        already_has_in_db = any(r['id'] == staff_id for r in user_staff_roles)
        
        # Check if user has Discord role
        has_discord_role = discord_role in member.roles
        
        # Handle different scenarios
        if already_has_in_db and has_discord_role:
            return format_error("User already has this staff role.", Config.ERROR_CODES['STAFF_EXISTS'])
        
        if already_has_in_db and not has_discord_role:
            # In database but not Discord - fix it by giving role
            try:
                await member.add_roles(discord_role, reason="Staff role assignment via BFOS")
                return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Synced: Gave Discord role {ANSIColors.BRIGHT_CYAN}{staff_role['display_name']}{ANSIColors.RESET} to {ANSIColors.BRIGHT_WHITE}{member.name}{ANSIColors.RESET}"
            except discord.Forbidden:
                return format_error("Bot lacks permission to manage roles.", Config.ERROR_CODES['PERMISSION_DENIED'])
            except Exception as e:
                return format_error(f"Failed to give Discord role: {str(e)}", Config.ERROR_CODES['COMMAND_FAILED'])
        
        # Give Discord role if they don't have it
        if not has_discord_role:
            try:
                await member.add_roles(discord_role, reason="Staff role assignment via BFOS")
            except discord.Forbidden:
                return format_error("Bot lacks permission to manage roles. User not added.", Config.ERROR_CODES['PERMISSION_DENIED'])
            except Exception as e:
                return format_error(f"Failed to give Discord role: {str(e)}", Config.ERROR_CODES['COMMAND_FAILED'])
        
        # Add to database
        success = self.db.assign_staff_to_user(self.guild.id, user_id, staff_id)
        
        if success:
            if has_discord_role:
                return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Assigned {ANSIColors.BRIGHT_CYAN}{staff_role['display_name']}{ANSIColors.RESET} to {ANSIColors.BRIGHT_WHITE}{member.name}{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}(User already had Discord role, synced to database){ANSIColors.RESET}"
            else:
                return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Assigned {ANSIColors.BRIGHT_CYAN}{staff_role['display_name']}{ANSIColors.RESET} to {ANSIColors.BRIGHT_WHITE}{member.name}{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}(Gave Discord role + added to database){ANSIColors.RESET}"
        else:
            return format_error("Failed to add to database.", Config.ERROR_CODES['COMMAND_FAILED'])
    
    async def handle_staff_remove_user(self, user_id_str):
        """Remove all staff roles from user (removes Discord roles + database)"""
        try:
            user_id = int(user_id_str)
        except ValueError:
            return format_error("Invalid user ID.", Config.ERROR_CODES['INVALID_INPUT'])
        
        # Get user's staff roles before removing
        user_staff_roles = self.db.get_user_staff_roles(self.guild.id, user_id)
        
        if not user_staff_roles:
            return format_error("User has no staff roles.", Config.ERROR_CODES['STAFF_NOT_FOUND'])
        
        # Try to get member
        try:
            member = await self.guild.fetch_member(user_id)
            member_found = True
        except:
            member = None
            member_found = False
        
        # Remove Discord roles if member is in server
        removed_roles = []
        failed_roles = []
        
        if member_found:
            for staff_role in user_staff_roles:
                discord_role = self.guild.get_role(staff_role['role_id'])
                if discord_role and discord_role in member.roles:
                    try:
                        await member.remove_roles(discord_role, reason="Staff role removal via BFOS")
                        removed_roles.append(staff_role['display_name'])
                    except discord.Forbidden:
                        failed_roles.append(f"{staff_role['display_name']} (no permission)")
                    except Exception as e:
                        failed_roles.append(f"{staff_role['display_name']} ({str(e)})")
        
        # Remove from database
        count = self.db.remove_all_staff_from_user(self.guild.id, user_id)
        
        # Build response
        output = ""
        
        if member_found:
            if removed_roles:
                output += f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Removed {len(removed_roles)} staff role(s) from {ANSIColors.BRIGHT_WHITE}{member.name}{ANSIColors.RESET}\n"
                output += f"{ANSIColors.BRIGHT_BLACK}Roles removed: {', '.join(removed_roles)}{ANSIColors.RESET}"
            
            if failed_roles:
                output += f"\n\n{ANSIColors.YELLOW}⚠ Failed to remove Discord roles:{ANSIColors.RESET}\n"
                for role in failed_roles:
                    output += f"  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {role}\n"
                output += f"{ANSIColors.BRIGHT_BLACK}(Removed from database anyway){ANSIColors.RESET}"
        else:
            output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Removed {count} staff role(s) from user {user_id}\n"
            output += f"{ANSIColors.BRIGHT_BLACK}(User not in server, removed from database only){ANSIColors.RESET}"
        
        return output if output else format_error("Failed to remove staff roles.", Config.ERROR_CODES['COMMAND_FAILED'])
    
    async def handle_staff_sync(self):
        """Sync Discord roles with database - fixes mismatches"""
        # Show initial progress
        await self.send_progress_update("Checking staff roles...")
        
        staff_roles = self.db.get_all_staff_roles(self.guild.id)
        
        if not staff_roles:
            return f"{ANSIColors.YELLOW}No staff roles configured.{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Use 'staff import <role_id>' to add staff roles first.{ANSIColors.RESET}"
        
        await self.send_progress_update(f"Scanning {len(staff_roles)} staff role(s)...")
        
        synced = []
        added_to_db = []
        removed_from_db = []
        added_role = []
        removed_role = []
        errors = []
        
        for i, staff_role in enumerate(staff_roles, 1):
            # Progress update every few roles
            if i % 3 == 0 or i == len(staff_roles):
                await self.send_progress_update(f"Processing role {i}/{len(staff_roles)}...", delay=0.5)
            
            discord_role = self.guild.get_role(staff_role['role_id'])
            
            if not discord_role:
                errors.append(f"{staff_role['display_name']} - Discord role no longer exists")
                continue
            
            # Get all members with this Discord role
            members_with_role = [m for m in self.guild.members if discord_role in m.roles and not m.bot]
            
            # Get all users in database with this staff role
            db_user_ids = set()
            all_staff_members = self.db.get_staff_members(self.guild.id)
            for user_id in all_staff_members:
                user_staff_roles = self.db.get_user_staff_roles(self.guild.id, user_id)
                if any(r['id'] == staff_role['id'] for r in user_staff_roles):
                    db_user_ids.add(user_id)
            
            # Sync: Add to database if they have Discord role but not in DB
            for member in members_with_role:
                if member.id not in db_user_ids:
                    success = self.db.assign_staff_to_user(self.guild.id, member.id, staff_role['id'])
                    if success:
                        added_to_db.append(f"{member.name} → {staff_role['display_name']}")
            
            # Sync: Remove from database if in DB but don't have Discord role
            for user_id in db_user_ids:
                try:
                    member = await self.guild.fetch_member(user_id)
                    if discord_role not in member.roles:
                        # Give them the role back
                        try:
                            await member.add_roles(discord_role, reason="BFOS Staff Sync - restoring missing role")
                            added_role.append(f"{member.name} → {staff_role['display_name']}")
                        except:
                            errors.append(f"Can't give role to {member.name}")
                except:
                    # User not in server anymore
                    removed_from_db.append(f"User {user_id} (no longer in server)")
        
        await self.send_progress_update("Finalizing sync...")
        
        # Build output
        output = f"{ANSIColors.BLUE}{'═' * 46}{ANSIColors.RESET}\n"
        output += f"{ANSIColors.BLUE}║{ANSIColors.RESET}        {ANSIColors.BOLD}Staff Sync Results{ANSIColors.RESET}                {ANSIColors.BLUE}║{ANSIColors.RESET}\n"
        output += f"{ANSIColors.BLUE}{'═' * 46}{ANSIColors.RESET}\n\n"
        
        if added_to_db:
            output += f"{ANSIColors.GREEN}✓ Added to database ({len(added_to_db)}):{ANSIColors.RESET}\n"
            for item in added_to_db[:10]:  # Show max 10
                output += f"  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {item}\n"
            if len(added_to_db) > 10:
                output += f"  {ANSIColors.BRIGHT_BLACK}...and {len(added_to_db) - 10} more{ANSIColors.RESET}\n"
            output += "\n"
        
        if added_role:
            output += f"{ANSIColors.GREEN}✓ Gave Discord role ({len(added_role)}):{ANSIColors.RESET}\n"
            for item in added_role[:10]:
                output += f"  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {item}\n"
            if len(added_role) > 10:
                output += f"  {ANSIColors.BRIGHT_BLACK}...and {len(added_role) - 10} more{ANSIColors.RESET}\n"
            output += "\n"
        
        if errors:
            output += f"{ANSIColors.RED}✗ Errors ({len(errors)}):{ANSIColors.RESET}\n"
            for item in errors[:5]:
                output += f"  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {item}\n"
            if len(errors) > 5:
                output += f"  {ANSIColors.BRIGHT_BLACK}...and {len(errors) - 5} more{ANSIColors.RESET}\n"
            output += "\n"
        
        if not added_to_db and not added_role and not errors:
            output += f"{ANSIColors.GREEN}✓ Everything is already synced!{ANSIColors.RESET}\n"
        
        output += f"{ANSIColors.BRIGHT_BLACK}Sync complete.{ANSIColors.RESET}"
        
        return output
    
    def show_test_menu(self):
        """Show test panel menu"""
        return f"""
{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}           {ANSIColors.BOLD}Test Panel{ANSIColors.RESET}                     {ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Test and preview configurations{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Available Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}embed list{ANSIColors.RESET}              List all configured embeds
  {ANSIColors.BRIGHT_WHITE}embed preview <id>{ANSIColors.RESET}      Preview an embed
  {ANSIColors.BRIGHT_WHITE}help{ANSIColors.RESET}                    Show detailed help
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                    Return to main menu
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}                    Exit terminal

{ANSIColors.BRIGHT_BLACK}Type a command to continue...{ANSIColors.RESET}
"""
    
    async def handle_test_panel(self, command_lower, user_input):
        """Handle commands in test panel"""
        output = ""
        should_exit = False
        
        if command_lower == "exit":
            output = await self.handle_exit()
            should_exit = True
        elif command_lower == "back":
            self.current_panel = "main"
            self.current_path = "System > Root"
            output = f"{ANSIColors.GREEN}Returned to main menu.{ANSIColors.RESET}"
        elif command_lower == "help":
            output = self.show_test_help()
        elif command_lower == "embed list":
            output = await self.handle_test_embed_list()
        elif command_lower.startswith("embed preview "):
            # Check for -real flag
            parts = user_input[14:].strip().split()
            if len(parts) >= 2 and parts[-1] == "-real":
                embed_id = " ".join(parts[:-1])
                await self.handle_test_embed_preview_real(embed_id)
                output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Real embed sent below! Check the message."
            else:
                embed_id = user_input[14:].strip()
                output = await self.handle_test_embed_preview(embed_id)
        elif command_lower == "embed preview":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}embed preview <id>{ANSIColors.RESET} or {ANSIColors.BRIGHT_WHITE}embed preview <id> -real{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Example: embed preview warnings_dm -real{ANSIColors.RESET}"
        elif command_lower.startswith("import backup "):
            backup_id = user_input[14:].strip()
            output = await self.handle_import_backup(backup_id)
        elif command_lower == "import backup":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}import backup <backup_id>{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Example: import backup a1b2c3d4{ANSIColors.RESET}\n\n{ANSIColors.BRIGHT_BLACK}This imports a backup from any server into this server's backups.{ANSIColors.RESET}"
        else:
            output = format_error(
                f"Invalid command '{user_input}'. Type 'help' for test commands.",
                Config.ERROR_CODES['INVALID_COMMAND']
            )
        
        return output, should_exit
    
    async def handle_import_backup(self, backup_id):
        """Import a backup from any server into this server's backup list"""
        try:
            from cogs.backup_system import ComprehensiveBackupSystem
            backup_system = ComprehensiveBackupSystem(self.bot, self.db)
            
            # Import the backup to this guild
            success, message = await backup_system.import_backup(self.guild.id, backup_id)
            
            if success:
                return f"""
{ANSIColors.GREEN}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.GREEN}✓{ANSIColors.RESET} Backup Imported Successfully!
{ANSIColors.GREEN}{'═' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Source Backup ID:{ANSIColors.RESET}  {backup_id}
{ANSIColors.BRIGHT_CYAN}Server:{ANSIColors.RESET}            {self.guild.name}

{ANSIColors.BRIGHT_BLACK}{message}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}The backup is now available in Management > Backup.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Use 'list' in the backup panel to see it.{ANSIColors.RESET}
"""
            else:
                return f"{ANSIColors.RED}❌ Import failed: {message}{ANSIColors.RESET}"
        except Exception as e:
            return f"{ANSIColors.RED}❌ Import error: {str(e)}{ANSIColors.RESET}"
    
    def show_test_help(self):
        """Show test panel help"""
        return f"""
{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}        {ANSIColors.BOLD}Test Panel Commands{ANSIColors.RESET}              {ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Embed Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}embed list{ANSIColors.RESET}              List all configured embeds
  {ANSIColors.BRIGHT_WHITE}embed preview <id>{ANSIColors.RESET}      Preview an embed

{ANSIColors.BRIGHT_CYAN}Backup Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}import backup <id>{ANSIColors.RESET}      Import backup from any server

{ANSIColors.BRIGHT_BLACK}Available Embed IDs:{ANSIColors.RESET}
  warnings_response     Warning issued in channel
  warnings_dm           Warning DM to user

{ANSIColors.BRIGHT_CYAN}Navigation:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                    Return to main menu
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}                    Exit terminal

{ANSIColors.BRIGHT_BLACK}The import backup command allows you to copy a backup{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}from another server (by backup ID) to this server.{ANSIColors.RESET}
"""
    
    async def handle_test_embed_list(self):
        """List all configured embeds"""
        return f"""
{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}          {ANSIColors.BOLD}Configured Embeds{ANSIColors.RESET}              {ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Warning Embeds:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}warnings_response{ANSIColors.RESET}
    Shown in channel when warn command is used
  
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}warnings_dm{ANSIColors.RESET}
    Sent to user via DM when warned

{ANSIColors.BRIGHT_BLACK}Use 'embed preview <id>' to preview an embed.{ANSIColors.RESET}
"""
    
    async def handle_test_embed_preview(self, embed_id):
        """Preview an embed"""
        valid_ids = ['warnings_response', 'warnings_dm', 'ban_response', 'ban_dm',
                     'kick_response', 'kick_dm', 'mute_response', 'mute_dm', 'unmute_response']
        
        if embed_id not in valid_ids:
            return format_error(
                f"Invalid embed ID. Valid IDs: {', '.join(valid_ids)}",
                Config.ERROR_CODES['INVALID_INPUT']
            )
        
        if embed_id == 'warnings_response':
            return f"""
{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}          {ANSIColors.BOLD}Embed Preview{ANSIColors.RESET}                  {ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.YELLOW}⚠️ Warning Issued{ANSIColors.RESET}
A user has been warned.

{ANSIColors.BRIGHT_BLACK}User:{ANSIColors.RESET} TestUser#1234 (123456789)
{ANSIColors.BRIGHT_BLACK}Moderator:{ANSIColors.RESET} AdminName
{ANSIColors.BRIGHT_BLACK}Reason:{ANSIColors.RESET} Test warning reason
{ANSIColors.BRIGHT_BLACK}Expires:{ANSIColors.RESET} December 25, 2025
{ANSIColors.BRIGHT_BLACK}Total Warnings:{ANSIColors.RESET} 1/3

{ANSIColors.BRIGHT_BLACK}Thumbnail: [Server Icon]{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Footer: Warned at • Now{ANSIColors.RESET}

{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Note: This is a text preview. Actual embed
will be formatted with Discord's embed style.{ANSIColors.RESET}
"""
        
        elif embed_id == 'warnings_dm':
            return f"""
{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}          {ANSIColors.BOLD}Embed Preview{ANSIColors.RESET}                  {ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.RED}⚠️ You Have Been Warned{ANSIColors.RESET}
You received a warning in TestServer.

{ANSIColors.BRIGHT_BLACK}Reason:{ANSIColors.RESET} Test warning reason
{ANSIColors.BRIGHT_BLACK}Warned By:{ANSIColors.RESET} AdminName
{ANSIColors.BRIGHT_BLACK}Expires:{ANSIColors.RESET} December 25, 2025
{ANSIColors.BRIGHT_BLACK}Your Warnings:{ANSIColors.RESET} 1/3

{ANSIColors.BRIGHT_BLACK}Thumbnail: [Server Icon]{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Author: Moderator avatar + name{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Footer: TestServer • Now{ANSIColors.RESET}

{ANSIColors.BRIGHT_MAGENTA}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Note: This is a text preview. Actual embed
will be formatted with Discord's embed style.{ANSIColors.RESET}
"""
    
    async def handle_test_embed_preview_real(self, embed_id):
        """Send actual Discord embed for preview"""
        import discord
        from datetime import datetime, timedelta
        
        valid_ids = ['warnings_response', 'warnings_dm', 'ban_response', 'ban_dm',
                     'kick_response', 'kick_dm', 'mute_response', 'mute_dm', 'unmute_response']
        
        if embed_id not in valid_ids:
            return
        
        if embed_id == 'warnings_response':
            embed = discord.Embed(
                title="⚠️ Warning Issued",
                description="A user has been warned.",
                color=0xFFAA00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value="TestUser#1234 (123456789)", inline=False)
            embed.add_field(name="Moderator", value="AdminName", inline=True)
            embed.add_field(name="Reason", value="Test warning reason", inline=False)
            embed.add_field(name="Expires", value="December 25, 2025", inline=True)
            embed.add_field(name="Total Warnings", value="1/3", inline=True)
            
            if self.guild.icon:
                embed.set_thumbnail(url=self.guild.icon.url)
            
            embed.set_footer(text="Warned at")
            
            await self.channel.send(embed=embed)
        
        elif embed_id == 'warnings_dm':
            embed = discord.Embed(
                title="⚠️ You Have Been Warned",
                description=f"You received a warning in {self.guild.name}.",
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Reason", value="Test warning reason", inline=False)
            embed.add_field(name="Warned By", value="AdminName", inline=True)
            embed.add_field(name="Expires", value="December 25, 2025", inline=True)
            embed.add_field(name="Your Warnings", value="1/3", inline=False)
            
            if self.guild.icon:
                embed.set_thumbnail(url=self.guild.icon.url)
                embed.set_author(name="Moderator Name", icon_url=self.guild.icon.url)
            
            embed.set_footer(text=self.guild.name)
            
            await self.channel.send(embed=embed)
    
    # EMBEDS PANEL METHODS
    def show_embed_menu(self):
        """Show embed panel menu"""
        return f"""
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}        {ANSIColors.BOLD}Embed Configuration{ANSIColors.RESET}              {ANSIColors.CYAN}║{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_BLACK}Configure warning and moderation embeds{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Available Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}list{ANSIColors.RESET}                    List all configured embeds
  {ANSIColors.BRIGHT_WHITE}edit <id>{ANSIColors.RESET}               Edit an embed
  {ANSIColors.BRIGHT_WHITE}preview <id>{ANSIColors.RESET}            Preview an embed
  {ANSIColors.BRIGHT_WHITE}reset <id>{ANSIColors.RESET}              Reset embed to default
  {ANSIColors.BRIGHT_WHITE}help{ANSIColors.RESET}                    Show detailed help
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                    Return to configuration
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}                    Exit terminal

{ANSIColors.BRIGHT_BLACK}Type a command to continue...{ANSIColors.RESET}
"""
    
    async def handle_embed_panel(self, command_lower, user_input):
        """Handle commands in embed panel"""
        output = ""
        should_exit = False
        
        if command_lower == "exit":
            output = await self.handle_exit()
            should_exit = True
        elif command_lower == "back":
            self.current_panel = "config"
            self.current_path = "Configuration"
            output = f"{ANSIColors.GREEN}Returned to configuration.{ANSIColors.RESET}"
        elif command_lower == "help":
            output = self.show_embed_help()
        elif command_lower == "list":
            output = await self.handle_embed_list()
        elif command_lower.startswith("edit "):
            embed_id = user_input[5:].strip()
            output = await self.handle_embed_edit(embed_id)
        elif command_lower == "edit":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}edit <id>{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Example: edit warnings_response{ANSIColors.RESET}"
        elif command_lower.startswith("preview "):
            parts = user_input[8:].strip().split()
            if len(parts) >= 2 and parts[-1] == "-real":
                embed_id = " ".join(parts[:-1])
                # Send real embed
                await self.send_real_embed_preview(embed_id)
                output = f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Real embed preview sent below!"
            else:
                embed_id = user_input[8:].strip()
                output = await self.handle_embed_preview_panel(embed_id)
        elif command_lower == "preview":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}preview <id> [-real]{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Example: preview warnings_dm -real{ANSIColors.RESET}"
        elif command_lower.startswith("send "):
            parts = user_input[5:].strip().split()
            if len(parts) >= 2:
                embed_id = parts[0].lower()
                channel_id = parts[1]
                output = await self.handle_embed_send(embed_id, channel_id)
            else:
                output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}send <embed_id> <channel_id>{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Example: send verification_embed 123456789{ANSIColors.RESET}"
        elif command_lower == "send":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}send <embed_id> <channel_id>{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Example: send verification_embed 123456789{ANSIColors.RESET}\n\n{ANSIColors.BRIGHT_CYAN}Sendable Embeds:{ANSIColors.RESET}\n  {ANSIColors.BRIGHT_WHITE}verification_embed{ANSIColors.RESET} - Verification button embed"
        elif command_lower.startswith("reset "):
            embed_id = user_input[6:].strip()
            output = await self.handle_embed_reset(embed_id)
        elif command_lower == "reset":
            output = f"{ANSIColors.YELLOW}Usage:{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}reset <id>{ANSIColors.RESET}\n{ANSIColors.BRIGHT_BLACK}Example: reset warnings_response{ANSIColors.RESET}"
        else:
            output = format_error(
                f"Invalid command '{user_input}'. Type 'help' for embed commands.",
                Config.ERROR_CODES['INVALID_COMMAND']
            )
        
        return output, should_exit
    
    def show_embed_help(self):
        """Show embed panel help"""
        return f"""
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}      {ANSIColors.BOLD}Embed Configuration Commands{ANSIColors.RESET}      {ANSIColors.CYAN}║{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Embed Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}list{ANSIColors.RESET}                    List all configured embeds
  {ANSIColors.BRIGHT_WHITE}edit <id>{ANSIColors.RESET}               Edit an embed's properties
  {ANSIColors.BRIGHT_WHITE}preview <id>{ANSIColors.RESET}            Preview an embed
  {ANSIColors.BRIGHT_WHITE}reset <id>{ANSIColors.RESET}              Reset to default styling
  {ANSIColors.BRIGHT_WHITE}send <id> <channel>{ANSIColors.RESET}     Send embed to channel

{ANSIColors.BRIGHT_CYAN}Sendable Embeds:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}verification_embed{ANSIColors.RESET}      Verification button embed

{ANSIColors.BRIGHT_CYAN}Available Embed IDs:{ANSIColors.RESET}
  warnings_response         Warning issued in channel
  warnings_dm               Warning DM to user
  ban_response              Ban notification
  kick_response             Kick notification
  mute_response             Mute notification
  mute_dm                   Mute DM to user
  unmute_response           Unmute notification

{ANSIColors.BRIGHT_CYAN}Navigation:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                    Return to configuration
  {ANSIColors.BRIGHT_WHITE}exit{ANSIColors.RESET}                    Exit terminal

{ANSIColors.BRIGHT_BLACK}Type 'list' to see all configured embeds.{ANSIColors.RESET}
"""
    
    async def handle_embed_list(self):
        """List all configured embeds"""
        return f"""
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}
{ANSIColors.CYAN}║{ANSIColors.RESET}          {ANSIColors.BOLD}Configured Embeds{ANSIColors.RESET}              {ANSIColors.CYAN}║{ANSIColors.RESET}
{ANSIColors.CYAN}{'═' * 46}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Warning Embeds:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}warnings_response{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Status:{ANSIColors.RESET} {ANSIColors.GREEN}Default{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Usage:{ANSIColors.RESET} Shown in channel when warning issued
  
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}warnings_dm{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Status:{ANSIColors.RESET} {ANSIColors.GREEN}Default{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Usage:{ANSIColors.RESET} Sent to user via DM when warned

{ANSIColors.BRIGHT_CYAN}Moderation Embeds:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}ban_response{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Status:{ANSIColors.RESET} {ANSIColors.GREEN}Default{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Usage:{ANSIColors.RESET} Shown when member is banned
  
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}kick_response{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Status:{ANSIColors.RESET} {ANSIColors.GREEN}Default{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Usage:{ANSIColors.RESET} Shown when member is kicked
  
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}mute_response{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Status:{ANSIColors.RESET} {ANSIColors.GREEN}Default{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Usage:{ANSIColors.RESET} Shown when member is muted
  
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}mute_dm{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Status:{ANSIColors.RESET} {ANSIColors.GREEN}Default{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Usage:{ANSIColors.RESET} Sent to user via DM when muted
  
  {ANSIColors.BRIGHT_BLACK}►{ANSIColors.RESET} {ANSIColors.BRIGHT_WHITE}unmute_response{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Status:{ANSIColors.RESET} {ANSIColors.GREEN}Default{ANSIColors.RESET}
    {ANSIColors.BRIGHT_BLACK}Usage:{ANSIColors.RESET} Shown when member is unmuted

{ANSIColors.BRIGHT_BLACK}Use 'edit <id>' to customize an embed.{ANSIColors.RESET}
{ANSIColors.BRIGHT_BLACK}Use 'preview <id>' to preview an embed.{ANSIColors.RESET}
"""
    
    async def handle_embed_edit(self, embed_id):
        """Edit an embed - switch to embed editor subpanel"""
        valid_ids = ['warnings_response', 'warnings_dm', 'ban_response', 'ban_dm',
                     'kick_response', 'kick_dm', 'mute_response', 'mute_dm', 'unmute_response']
        
        if embed_id not in valid_ids:
            return format_error(
                f"Invalid embed ID. Valid IDs: {', '.join(valid_ids)}",
                Config.ERROR_CODES['INVALID_INPUT']
            )
        
        # Use the embed editor panel if available
        if PANELS_AVAILABLE and hasattr(self, 'embed_editor'):
            return await self.embed_editor.start_editing(embed_id)
        
        # Fallback: Switch panel manually
        self.current_panel = f"embed_edit_{embed_id}"
        self.editing_embed = embed_id
        
        return f"""
{ANSIColors.BRIGHT_MAGENTA}{'═' * 50}{ANSIColors.RESET}
{ANSIColors.BRIGHT_MAGENTA}║{ANSIColors.RESET}          Embed Editor: {embed_id}
{ANSIColors.BRIGHT_MAGENTA}{'═' * 50}{ANSIColors.RESET}

{ANSIColors.BRIGHT_CYAN}Edit Commands:{ANSIColors.RESET}
  {ANSIColors.BRIGHT_WHITE}title <text>{ANSIColors.RESET}           Set embed title
  {ANSIColors.BRIGHT_WHITE}description <text>{ANSIColors.RESET}     Set description
  {ANSIColors.BRIGHT_WHITE}color <hex>{ANSIColors.RESET}            Set color (e.g. FF0000)
  {ANSIColors.BRIGHT_WHITE}footer <text>{ANSIColors.RESET}          Set footer text
  {ANSIColors.BRIGHT_WHITE}field add <n> <v>{ANSIColors.RESET}      Add field
  {ANSIColors.BRIGHT_WHITE}field remove <n>{ANSIColors.RESET}       Remove field by name
  {ANSIColors.BRIGHT_WHITE}preview{ANSIColors.RESET}                Preview the embed
  {ANSIColors.BRIGHT_WHITE}save{ANSIColors.RESET}                   Save changes
  {ANSIColors.BRIGHT_WHITE}back{ANSIColors.RESET}                   Return to embeds

{ANSIColors.BRIGHT_CYAN}Placeholders:{ANSIColors.RESET}
  {{user}} {{user_id}} {{moderator}} {{reason}} {{duration}}
  {{total_warnings}} {{threshold}} {{server}} {{timestamp}}

{ANSIColors.BRIGHT_BLACK}Now editing: {ANSIColors.BRIGHT_WHITE}{embed_id}{ANSIColors.RESET}
"""

    async def handle_embed_preview_panel(self, embed_id):
        """Preview an embed from embeds panel"""
        valid_ids = ['warnings_response', 'warnings_dm', 'ban_response', 'ban_dm',
                     'kick_response', 'kick_dm', 'mute_response', 'mute_dm', 'unmute_response']
        
        if embed_id not in valid_ids:
            return format_error(
                f"Invalid embed ID. Valid IDs: {', '.join(valid_ids)}",
                Config.ERROR_CODES['INVALID_INPUT']
            )
        
        # Reuse test panel preview logic for warnings
        if embed_id in ['warnings_response', 'warnings_dm']:
            return await self.handle_test_embed_preview(embed_id)
        
        # Placeholder for other embeds
        return f"{ANSIColors.YELLOW}Preview for '{embed_id}' coming soon!{ANSIColors.RESET}"
    
    async def handle_embed_reset(self, embed_id):
        """Reset embed to default"""
        valid_ids = ['warnings_response', 'warnings_dm', 'ban_response', 'kick_response',
                     'mute_response', 'mute_dm', 'unmute_response']
        
        if embed_id not in valid_ids:
            return format_error(
                f"Invalid embed ID. Valid IDs: {', '.join(valid_ids)}",
                Config.ERROR_CODES['INVALID_INPUT']
            )
        
        return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Embed '{ANSIColors.BRIGHT_WHITE}{embed_id}{ANSIColors.RESET}' reset to default styling."
    
    async def handle_embed_send(self, embed_id, channel_id):
        """Send a sendable embed to a channel"""
        import discord
        
        # Only certain embeds can be sent
        sendable_embeds = ['verification_embed']
        
        if embed_id not in sendable_embeds:
            return format_error(
                f"Cannot send '{embed_id}'. Sendable embeds: {', '.join(sendable_embeds)}",
                Config.ERROR_CODES['INVALID_INPUT']
            )
        
        # Validate channel ID
        try:
            channel_id_int = int(channel_id)
        except ValueError:
            return format_error(
                "Invalid channel ID. Must be a number.",
                Config.ERROR_CODES['INVALID_INPUT']
            )
        
        # Get channel
        channel = self.guild.get_channel(channel_id_int)
        if not channel:
            return format_error(
                f"Channel with ID {channel_id} not found.",
                Config.ERROR_CODES['INVALID_INPUT']
            )
        
        # Check if it's a text channel
        if not isinstance(channel, discord.TextChannel):
            return format_error(
                "Channel must be a text channel.",
                Config.ERROR_CODES['INVALID_INPUT']
            )
        
        try:
            if embed_id == 'verification_embed':
                # Get security cog
                security_cog = self.bot.get_cog('SecurityModule')
                if not security_cog:
                    return format_error(
                        "Security module not loaded.",
                        Config.ERROR_CODES['MODULE_DISABLED']
                    )
                
                # Create verification embed
                embed = await security_cog.create_verification_embed(self.guild)
                
                # Create verify button
                from cogs.security import VerifyButton
                view = VerifyButton(security_cog)
                
                # Send to channel
                await channel.send(embed=embed, view=view)
                
                return f"{ANSIColors.GREEN}✓{ANSIColors.RESET} Verification embed sent to {ANSIColors.BRIGHT_WHITE}#{channel.name}{ANSIColors.RESET}!"
            
        except discord.Forbidden:
            return format_error(
                f"Missing permissions to send messages in #{channel.name}.",
                Config.ERROR_CODES['NO_PERMISSION']
            )
        except Exception as e:
            return format_error(
                f"Failed to send embed: {str(e)}",
                Config.ERROR_CODES['COMMAND_FAILED']
            )
    
    async def send_real_embed_preview(self, embed_id):
        """Send actual Discord embed for preview"""
        import discord
        
        valid_ids = ['warnings_response', 'warnings_dm', 'ban_response', 'kick_response',
                     'mute_response', 'mute_dm', 'unmute_response']
        
        if embed_id not in valid_ids:
            return
        
        # Default embed configurations
        embed_configs = {
            'warnings_response': {
                'title': '⚠️ Warning Issued',
                'description': 'A user has been warned.',
                'color': 0xFFAA00
            },
            'warnings_dm': {
                'title': '⚠️ You Have Been Warned',
                'description': 'You received a warning in {server}.',
                'color': 0xFF0000
            },
            'ban_response': {
                'title': '🔨 User Banned',
                'description': 'A user has been banned from the server.',
                'color': 0xFF0000
            },
            'kick_response': {
                'title': '👢 User Kicked',
                'description': 'A user has been kicked from the server.',
                'color': 0xFF6600
            },
            'mute_response': {
                'title': '🔇 User Muted',
                'description': 'A user has been muted.',
                'color': 0xFF9900
            },
            'mute_dm': {
                'title': '🔇 You Have Been Muted',
                'description': 'You have been muted in {server}.',
                'color': 0xFF0000
            },
            'unmute_response': {
                'title': '🔊 User Unmuted',
                'description': 'A user has been unmuted.',
                'color': 0x00FF00
            }
        }
        
        config = embed_configs.get(embed_id, {})
        
        # Replace placeholders with examples
        title = config.get('title', 'Embed Title').replace('{server}', self.guild.name)
        description = config.get('description', 'Description').replace('{server}', self.guild.name)
        description = description.replace('{user}', 'ExampleUser').replace('{moderator}', 'ModeratorName')
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=config.get('color', 0x00FF00),
            timestamp=datetime.utcnow()
        )
        
        # Add example fields
        embed.add_field(name="User", value="ExampleUser (123456789)", inline=False)
        embed.add_field(name="Moderator", value="ModeratorName", inline=True)
        embed.add_field(name="Reason", value="Example reason", inline=False)
        
        if 'mute' in embed_id or 'warn' in embed_id:
            embed.add_field(name="Duration", value="1d", inline=True)
        
        embed.add_field(name="Case", value="#123", inline=True)
        
        if self.guild.icon:
            embed.set_thumbnail(url=self.guild.icon.url)
        
        embed.set_footer(text=f"Preview of {embed_id}")
        
        await self.channel.send(embed=embed)

class Terminal(commands.Cog):
    """Terminal commands cog"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"[✓] Terminal cog loaded")

async def setup(bot):
    await bot.add_cog(Terminal(bot))