"""
BlockForge OS Discord Bot - SIMPLIFIED VERSION
Use this if the main bot.py isn't working
"""

import discord
from discord.ext import commands
import asyncio
from utils.database import Database
from utils.colors import Colors
from utils.config import Config

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# Create bot with simple prefix
bot = commands.Bot(command_prefix='.', intents=intents, help_command=None)

# Initialize database
print("Initializing database...")
db = Database()
print("Database initialized!")

# Store active terminal sessions
active_sessions = {}

@bot.event
async def on_ready():
    """Bot startup event"""
    print(f'{Colors.GREEN}[✓] {bot.user.name} is online!{Colors.RESET}')
    print(f'{Colors.CYAN}[INFO] Connected to {len(bot.guilds)} guild(s){Colors.RESET}')
    print(f'{Colors.CYAN}[INFO] Bot ID: {bot.user.id}{Colors.RESET}')
    print(f'{Colors.YELLOW}[TIP] Try running .ping to test if the bot responds{Colors.RESET}')
    print(f'{Colors.YELLOW}[TIP] Run .bfos or .bfos() to start the terminal{Colors.RESET}')
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="for .bfos() | BlockForge OS"
        )
    )

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
                color=0x00ff88
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
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Check if user has an active terminal session
    if message.author.id in active_sessions:
        session = active_sessions[message.author.id]
        
        # Delete user's message
        try:
            await message.delete()
        except:
            pass
        
        # Process terminal input
        await session.process_input(message.content, message.author)
        return
    
    # Process normal commands
    await bot.process_commands(message)

@bot.command(name='ping')
async def ping_command(ctx):
    """Simple ping command to test if bot is responding"""
    latency = round(bot.latency * 1000, 2)
    await ctx.send(f'🏓 Pong! Latency: {latency}ms')

@bot.command(name='test')
async def test_command(ctx):
    """Test command to verify bot is working"""
    await ctx.send('✅ Bot is working! You can now use `.bfos()` to start the terminal.')

@bot.command(name='bfos', aliases=['bfos()'])
async def bfos_command(ctx):
    """Initialize BFOS terminal session"""
    print(f'{Colors.CYAN}[DEBUG] BFOS command triggered by {ctx.author.name} in {ctx.guild.name}{Colors.RESET}')
    
    # Check if guild exists in database, if not create it
    if not db.guild_exists(ctx.guild.id):
        print(f'{Colors.YELLOW}[INFO] Guild not in database, creating entry...{Colors.RESET}')
        # Create the guild entry
        try:
            # Find or create setup channel
            setup_channel = discord.utils.get(ctx.guild.channels, name='bfos-setup')
            if not setup_channel:
                # Try to create it
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
            
            db.add_guild(ctx.guild.id, setup_channel.id)
            print(f'{Colors.GREEN}[✓] Guild entry created{Colors.RESET}')
        except Exception as e:
            print(f'{Colors.RED}[ERROR] Failed to setup guild: {e}{Colors.RESET}')
            await ctx.send("❌ Error setting up BFOS. Please ensure the bot has proper permissions.", delete_after=10)
            return
    
    guild_data = db.get_guild(ctx.guild.id)
    
    # Check permissions - only server owner can use initially
    if not guild_data['setup_complete']:
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send(
                "❌ **Access Denied:** Only the server owner can run this command during initial setup.",
                delete_after=10
            )
            return
    else:
        # After setup, check if user has permissions
        if not ctx.author.guild_permissions.administrator:
            await ctx.send(
                "❌ **Access Denied:** You need administrator permissions to access BFOS.",
                delete_after=10
            )
            return
    
    # Check if user already has an active session
    if ctx.author.id in active_sessions:
        await ctx.send(
            "⚠️ You already have an active BFOS session. Please close it first.",
            delete_after=5
        )
        return
    
    # Load BFOS cog
    if 'cogs.terminal' not in bot.extensions:
        try:
            await bot.load_extension('cogs.terminal')
            print(f'{Colors.GREEN}[✓] Loaded terminal cog{Colors.RESET}')
        except Exception as e:
            print(f'{Colors.RED}[ERROR] Failed to load terminal cog: {e}{Colors.RESET}')
            await ctx.send(f"❌ Error loading terminal: {e}", delete_after=10)
            return
    
    # Import terminal session
    from cogs.terminal import TerminalSession
    
    # Create new terminal session
    session = TerminalSession(bot, ctx, db)
    active_sessions[ctx.author.id] = session
    
    # Start the terminal
    await session.start()

# Load cogs
async def load_extensions():
    """Load all cog extensions"""
    extensions = [
        'cogs.terminal',
        'cogs.admin',
        'cogs.moderation'
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
        print(f'{Colors.CYAN}[INFO] Starting bot...{Colors.RESET}')
        await bot.start(Config.TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f'\n{Colors.YELLOW}[INFO] Bot stopped by user{Colors.RESET}')
    except Exception as e:
        print(f'{Colors.RED}[ERROR] Bot crashed: {e}{Colors.RESET}')
        import traceback
        traceback.print_exc()
