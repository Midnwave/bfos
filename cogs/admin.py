"""
BlockForge OS Admin Module
Administrative commands and features for bot staff
"""

import discord
from discord.ext import commands
from discord import app_commands
from utils.colors import Colors

class Admin(commands.Cog):
    """Administrative commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{Colors.GREEN}[✓] Admin cog loaded{Colors.RESET}")
    
    @commands.command(name='bfstatus')
    @commands.is_owner()
    async def bfstatus(self, ctx):
        """Get bot status - Owner only"""
        embed = discord.Embed(
            title="🤖 BlockForge OS Status",
            color=0x00ff88
        )
        
        embed.add_field(
            name="Servers",
            value=f"`{len(self.bot.guilds)}`",
            inline=True
        )
        
        embed.add_field(
            name="Users",
            value=f"`{len(self.bot.users)}`",
            inline=True
        )
        
        embed.add_field(
            name="Latency",
            value=f"`{round(self.bot.latency * 1000, 2)}ms`",
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='bfreload')
    @commands.is_owner()
    async def reload_cog(self, ctx, cog_name: str):
        """Reload a cog - Owner only"""
        try:
            await self.bot.reload_extension(f'cogs.{cog_name}')
            await ctx.send(f"✅ Reloaded cog: `{cog_name}`")
        except Exception as e:
            await ctx.send(f"❌ Failed to reload cog: `{e}`")
    
    @app_commands.command(name="say", description="Make the bot say something")
    @app_commands.describe(
        message="The message for the bot to send",
        channel="Channel to send the message (default: current channel)"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def say(
        self, 
        interaction: discord.Interaction, 
        message: str,
        channel: discord.TextChannel = None
    ):
        """Make the bot say a message"""
        target_channel = channel or interaction.channel
        
        try:
            await target_channel.send(message)
            await interaction.response.send_message(
                f"✅ Message sent to {target_channel.mention}",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {target_channel.mention}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error: {e}",
                ephemeral=True
            )
    
    @app_commands.command(name="embed", description="Make the bot send an embed")
    @app_commands.describe(
        title="Embed title",
        description="Embed description",
        color="Hex color (e.g., #FF0000)",
        channel="Channel to send the embed (default: current channel)"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def embed_cmd(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        color: str = "#00FF88",
        channel: discord.TextChannel = None
    ):
        """Send an embed message"""
        target_channel = channel or interaction.channel
        
        # Parse color
        try:
            color_value = int(color.replace('#', ''), 16)
        except:
            color_value = 0x00FF88
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color_value
        )
        
        try:
            await target_channel.send(embed=embed)
            await interaction.response.send_message(
                f"✅ Embed sent to {target_channel.mention}",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {target_channel.mention}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Admin(bot))