"""
BlockForge OS Discord Bot
Main entry point for the bot
"""

import discord
from discord.ext import commands
import asyncio
import json
import os
from datetime import datetime
from utils.database import Database
from utils.colors import Colors
from utils.config import Config

# Processing emoji - shown while command is being processed
PROCESSING_EMOJI_ID = 1342683115981639743

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# Database instance
print("🔄 Initializing database...")
try:
    db = Database()
    print("✅ Database initialized!")
except Exception as e:
    print(f"❌ Database initialization failed: {e}")
    db = None

# Dynamic prefix function
async def get_prefix(bot, message):
    """Get the appropriate prefix for the server"""
    if not message.guild:
        return '.'
    
    # Always respond to default prefix
    prefixes = ['.']
    
    # Add custom prefix for moderation commands
    if message.guild and db:
        try:
            custom_prefix = db.get_command_prefix(message.guild.id)
            if custom_prefix and custom_prefix not in prefixes:
                prefixes.append(custom_prefix)
        except:
            pass  # If database error, just use default
    
    return commands.when_mentioned_or(*prefixes)(bot, message)

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

# Attach database to bot for cog access
bot.db = db

# Store active terminal sessions
active_sessions = {}
bot.active_sessions = active_sessions

@bot.event
async def on_ready():
    """Bot startup event"""
    print(f'{Colors.GREEN}[✓] {bot.user.name} is online!{Colors.RESET}')
    print(f'{Colors.CYAN}[INFO] Connected to {len(bot.guilds)} guild(s){Colors.RESET}')
    print(f'{Colors.CYAN}[INFO] Bot ID: {bot.user.id}{Colors.RESET}')
    print(f'{Colors.YELLOW}[TIP] Try running .ping to test if the bot responds{Colors.RESET}')
    print(f'{Colors.YELLOW}[TIP] Run .bfos or .bfos() to start the terminal{Colors.RESET}')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f'{Colors.GREEN}[✓] Synced {len(synced)} slash command(s){Colors.RESET}')
    except Exception as e:
        print(f'{Colors.RED}[✗] Failed to sync slash commands: {e}{Colors.RESET}')
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="for .bfos() | BlockForge OS"
        )
    )

@bot.command(name='ping')
async def ping_command(ctx):
    """Simple ping command to test if bot is responding"""
    latency = round(bot.latency * 1000, 2)
    await ctx.send(f'🏓 Pong! Latency: {latency}ms')

@bot.command(name='test')
async def test_command(ctx):
    """Test command to verify bot is working"""
    await ctx.send('✅ Bot is working! You can now use `.bfos()` to start the terminal.')

@bot.event
async def on_guild_join(guild):
    """Handle bot joining a new server"""
    # Check if this is a new guild
    if not db.guild_exists(guild.id):
        print(f'{Colors.YELLOW}[NEW GUILD] Joined: {guild.name} (ID: {guild.id}){Colors.RESET}')
        
        # Create admin-only setup channel
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            # Add admin role permissions
            for role in guild.roles:
                if role.permissions.administrator:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            setup_channel = await guild.create_text_channel(
                'bfos-setup',
                overwrites=overwrites,
                topic='BlockForge OS Setup Channel - Run .bfos() to begin configuration'
            )
            
            # Send setup message
            embed = discord.Embed(
                title="🔧 BlockForge OS - Initial Setup Required",
                description=(
                    "Thank you for adding **BlockForge OS** to your server!\n\n"
                    "**To begin setup, run the following command:**\n"
                    "```\n.bfos()\n```\n"
                    "⚠️ **Note:** Only the server owner can run this command initially.\n"
                    "📱 **Mobile Warning:** BFOS is best experienced on desktop for optimal display."
                ),
                color=0x00ff88,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=f"BlockForge OS v{Config.VERSION}")
            
            await setup_channel.send(embed=embed)
            
            # Register guild in database
            db.add_guild(guild.id, setup_channel.id)
            
        except Exception as e:
            print(f'{Colors.RED}[ERROR] Failed to create setup channel: {e}{Colors.RESET}')

@bot.event
async def on_message(message):
    """Handle incoming messages"""
    try:
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Ignore DMs for processing indicator
        is_dm = not message.guild
        
        # Log every message (can be disabled later if too verbose)
        if not is_dm:
            print(f'[MESSAGE] From {message.author.name} in #{message.channel.name}: {message.content[:50]}...')
        
        # Check if user has an active permission editor - skip terminal processing
        if hasattr(bot, '_perm_editor_active') and message.author.id in bot._perm_editor_active:
            print(f'[MESSAGE] User has active permission editor, skipping terminal')
            # Still process normal commands (but don't delete message)
            await bot.process_commands(message)
            return
        
        # Check if user has an active terminal session
        if message.author.id in active_sessions:
            session = active_sessions[message.author.id]
            
            # Only delete messages if session is actually active
            if session.is_active:
                print(f'[MESSAGE] User has active terminal session')
                
                # Process terminal input (message deletion handled inside process_input
                # AFTER the processing indicator is shown, so user sees feedback first)
                print(f'[MESSAGE] Processing terminal input...')
                try:
                    await session.process_input(message.content, message.author, message)
                    print(f'[MESSAGE] Terminal input processed successfully')
                except Exception as e:
                    print(f'[MESSAGE ERROR] Failed to process terminal input: {type(e).__name__}: {e}')
                    import traceback
                    traceback.print_exc()
                
                return
            else:
                # Session exists but is inactive, remove it
                print(f'[MESSAGE] Session exists but is inactive, cleaning up...')
                del active_sessions[message.author.id]
        
        # Process normal commands
        print(f'[MESSAGE] Processing as normal command')
        
        try:
            await bot.process_commands(message)
        except Exception as e:
            print(f'[MESSAGE ERROR] Failed to process command: {type(e).__name__}: {e}')
            import traceback
            traceback.print_exc()
    
    except Exception as e:
        print(f'[MESSAGE FATAL] Unhandled exception in on_message: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()

@bot.command(name='bfos', aliases=['bfos()'])
async def bfos_command(ctx):
    """Initialize BFOS terminal session"""
    try:
        print(f'{Colors.CYAN}[DEBUG] ========== BFOS COMMAND START =========={Colors.RESET}')
        print(f'{Colors.CYAN}[DEBUG] Triggered by: {ctx.author.name} ({ctx.author.id}){Colors.RESET}')
        print(f'{Colors.CYAN}[DEBUG] Guild: {ctx.guild.name} ({ctx.guild.id}){Colors.RESET}')
        print(f'{Colors.CYAN}[DEBUG] Channel: {ctx.channel.name} ({ctx.channel.id}){Colors.RESET}')
        
        # Check if guild exists in database, if not create it
        if not db.guild_exists(ctx.guild.id):
            print(f'{Colors.YELLOW}[INFO] Guild not in database, creating entry...{Colors.RESET}')
            try:
                # Find or create setup channel
                setup_channel = discord.utils.get(ctx.guild.channels, name='bfos-setup')
                if not setup_channel:
                    print(f'{Colors.YELLOW}[INFO] Creating bfos-setup channel...{Colors.RESET}')
                    overwrites = {
                        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    }
                    
                    for role in ctx.guild.roles:
                        if role.permissions.administrator:
                            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    
                    setup_channel = await ctx.guild.create_text_channel(
                        'bfos-setup',
                        overwrites=overwrites,
                        topic='BlockForge OS Setup Channel - Run .bfos() to begin configuration'
                    )
                    print(f'{Colors.GREEN}[✓] Setup channel created: {setup_channel.id}{Colors.RESET}')
                
                db.add_guild(ctx.guild.id, setup_channel.id)
                print(f'{Colors.GREEN}[✓] Guild entry created in database{Colors.RESET}')
            except Exception as e:
                print(f'{Colors.RED}[ERROR] Failed to setup guild: {type(e).__name__}: {e}{Colors.RESET}')
                import traceback
                traceback.print_exc()
                await ctx.send("❌ Error setting up BFOS. Check console for details.", delete_after=10)
                return
        else:
            print(f'{Colors.GREEN}[✓] Guild exists in database{Colors.RESET}')
        
        # Get guild data
        print(f'{Colors.CYAN}[DEBUG] Retrieving guild data...{Colors.RESET}')
        guild_data = db.get_guild(ctx.guild.id)
        if not guild_data:
            print(f'{Colors.RED}[ERROR] Guild data is None!{Colors.RESET}')
            await ctx.send("❌ Database error. Check console for details.", delete_after=10)
            return
        print(f'{Colors.GREEN}[✓] Guild data retrieved: setup_complete={guild_data["setup_complete"]}{Colors.RESET}')
        
        # Check permissions
        print(f'{Colors.CYAN}[DEBUG] Checking permissions...{Colors.RESET}')
        
        # Bot owner ALWAYS has access to all terminals
        is_bot_owner = ctx.author.id == Config.BOT_OWNER_ID
        if is_bot_owner:
            print(f'{Colors.GREEN}[✓] Permission check passed - BOT OWNER (global access){Colors.RESET}')
        elif not guild_data['setup_complete']:
            if ctx.author.id != ctx.guild.owner_id:
                print(f'{Colors.YELLOW}[INFO] Access denied - user is not server owner{Colors.RESET}')
                await ctx.send(
                    "❌ **Access Denied:** Only the server owner can run this command during initial setup.",
                    delete_after=10
                )
                return
            print(f'{Colors.GREEN}[✓] Permission check passed - server owner{Colors.RESET}')
        else:
            # Check: admin OR server owner OR bfos_access permission
            is_server_owner = ctx.author.id == ctx.guild.owner_id
            has_admin = ctx.author.guild_permissions.administrator

            # Check BFOS access permission from database
            has_bfos_access = False
            if db:
                has_bfos_access = db.has_permission(ctx.guild.id, ctx.author.id, 'bfos_access')
                if not has_bfos_access:
                    for role in ctx.author.roles:
                        if db.role_has_permission(ctx.guild.id, role.id, 'bfos_access'):
                            has_bfos_access = True
                            break

            if not is_server_owner and not has_admin and not has_bfos_access:
                print(f'{Colors.YELLOW}[INFO] Access denied - user lacks admin/owner/bfos_access{Colors.RESET}')
                await ctx.send(
                    "❌ **Access Denied:** You need administrator permissions or BFOS access permission.",
                    delete_after=10
                )
                return
            access_reason = "server owner" if is_server_owner else ("administrator" if has_admin else "bfos_access")
            print(f'{Colors.GREEN}[✓] Permission check passed - {access_reason}{Colors.RESET}')
        
        # Check for active session
        print(f'{Colors.CYAN}[DEBUG] Checking for active session...{Colors.RESET}')
        if ctx.author.id in active_sessions:
            print(f'{Colors.YELLOW}[INFO] User already has active session{Colors.RESET}')
            await ctx.send(
                "⚠️ You already have an active BFOS session. Please close it first.",
                delete_after=5
            )
            return
        print(f'{Colors.GREEN}[✓] No active session found{Colors.RESET}')
        
        # Load terminal cog
        print(f'{Colors.CYAN}[DEBUG] Checking if terminal cog is loaded...{Colors.RESET}')
        if 'cogs.terminal' not in bot.extensions:
            print(f'{Colors.YELLOW}[INFO] Loading terminal cog...{Colors.RESET}')
            try:
                await bot.load_extension('cogs.terminal')
                print(f'{Colors.GREEN}[✓] Terminal cog loaded successfully{Colors.RESET}')
            except Exception as e:
                print(f'{Colors.RED}[ERROR] Failed to load terminal cog: {type(e).__name__}: {e}{Colors.RESET}')
                import traceback
                traceback.print_exc()
                await ctx.send(f"❌ Error loading terminal. Check console for details.", delete_after=10)
                return
        else:
            print(f'{Colors.GREEN}[✓] Terminal cog already loaded{Colors.RESET}')
        
        # Import TerminalSession
        print(f'{Colors.CYAN}[DEBUG] Importing TerminalSession class...{Colors.RESET}')
        try:
            from cogs.terminal import TerminalSession
            print(f'{Colors.GREEN}[✓] TerminalSession imported successfully{Colors.RESET}')
        except Exception as e:
            print(f'{Colors.RED}[ERROR] Failed to import TerminalSession: {type(e).__name__}: {e}{Colors.RESET}')
            import traceback
            traceback.print_exc()
            await ctx.send(f"❌ Error importing terminal. Check console for details.", delete_after=10)
            return
        
        # Create terminal session
        print(f'{Colors.CYAN}[DEBUG] Creating terminal session...{Colors.RESET}')
        try:
            session = TerminalSession(bot, ctx, db)
            active_sessions[ctx.author.id] = session
            print(f'{Colors.GREEN}[✓] Terminal session created and stored{Colors.RESET}')
        except Exception as e:
            print(f'{Colors.RED}[ERROR] Failed to create terminal session: {type(e).__name__}: {e}{Colors.RESET}')
            import traceback
            traceback.print_exc()
            await ctx.send(f"❌ Error creating session. Check console for details.", delete_after=10)
            return
        
        # Start terminal
        print(f'{Colors.CYAN}[DEBUG] Starting terminal session...{Colors.RESET}')
        try:
            await session.start()
            print(f'{Colors.GREEN}[✓] Terminal session started successfully{Colors.RESET}')
            print(f'{Colors.CYAN}[DEBUG] ========== BFOS COMMAND END (SUCCESS) =========={Colors.RESET}')
        except Exception as e:
            print(f'{Colors.RED}[ERROR] Failed to start terminal session: {type(e).__name__}: {e}{Colors.RESET}')
            import traceback
            traceback.print_exc()
            # Clean up on failure
            if ctx.author.id in active_sessions:
                del active_sessions[ctx.author.id]
                print(f'{Colors.YELLOW}[INFO] Cleaned up failed session from active_sessions{Colors.RESET}')
            await ctx.send(f"❌ Error starting terminal. Check console for details.", delete_after=10)
            print(f'{Colors.CYAN}[DEBUG] ========== BFOS COMMAND END (FAILED) =========={Colors.RESET}')
            return
    
    except Exception as e:
        print(f'{Colors.RED}[FATAL ERROR] Unhandled exception in bfos_command: {type(e).__name__}: {e}{Colors.RESET}')
        import traceback
        traceback.print_exc()
        try:
            await ctx.send(f"❌ Fatal error. Check console for details.", delete_after=10)
        except:
            pass
        print(f'{Colors.CYAN}[DEBUG] ========== BFOS COMMAND END (FATAL ERROR) =========={Colors.RESET}')

# Load cogs
async def load_extensions():
    """Load all cog extensions"""
    extensions = [
        'cogs.terminal',
        'cogs.admin',
        'cogs.moderation',
        'cogs.moderation_extended',
        'cogs.help',
        'cogs.backup_commands',
        'cogs.auto_backup',
        'cogs.purge',
        'cogs.logging',
        'cogs.security',
        'cogs.debug',
        'cogs.ai_system',
        'cogs.tickets',
        'cogs.xp_system'
    ]
    
    for extension in extensions:
        try:
            await bot.load_extension(extension)
            print(f'{Colors.GREEN}[✓] Loaded extension: {extension}{Colors.RESET}')
        except Exception as e:
            print(f'{Colors.RED}[✗] Failed to load extension {extension}: {e}{Colors.RESET}')

async def main():
    """Main bot startup function"""
    async with bot:
        await load_extensions()
        await bot.start(Config.TOKEN)

if __name__ == '__main__':
    asyncio.run(main())