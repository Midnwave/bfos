"""
BlockForge OS Purge Module
Advanced message purging with filters and detailed results
"""

import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Union, List
import re
from utils.database import Database


class PurgeModule(commands.Cog):
    """Advanced message purging system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.active_purges = {}  # guild_id -> True if purge in progress
        
    def is_module_enabled(self, guild_id: int) -> bool:
        """Check if purge module is enabled"""
        return self.db.is_module_enabled(guild_id, 'purges')
    
    @commands.command(name='purge')
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    async def purge_command(self, ctx, user: str = None, filter_type: str = None, amount: int = None):
        """
        Purge messages with advanced filters
        
        Usage: ;purge <user> <type> <amount>
        User: @mention, user ID, or "all"
        Type: all, bots, files, images, links, embeds, or custom text
        Amount: 1-3000
        """
        # Check if all arguments provided
        if user is None or filter_type is None or amount is None:
            embed = discord.Embed(
                title="❌ Error: Invalid Input Supplied",
                description="Missing required parameters. Please provide all arguments to execute this command.",
                color=0xFF0000
            )
            embed.add_field(
                name="Usage",
                value="`;purge <user|all> <type|all> <amount>`",
                inline=False
            )
            embed.add_field(
                name="Types",
                value="`all`, `bots`, `files`, `images`, `links`, `embeds`, or custom text to match",
                inline=False
            )
            embed.add_field(
                name="Example",
                value="`;purge all all 100` - Delete 100 messages from anyone\n`;purge @User bots 50` - Delete 50 bot messages mentioning user",
                inline=False
            )
            embed.set_footer(text="Error Code: 0xARGS")
            await ctx.send(embed=embed)
            return
        
        # Check if module is enabled
        if not self.is_module_enabled(ctx.guild.id):
            embed = discord.Embed(
                title="❌ Module Disabled",
                description="The **Purges** module is not enabled.\n\nEnable it in BFOS Terminal:\n`modules` → `enable purges`",
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Error Code: 0xMODL")
            await ctx.send(embed=embed)
            return
        
        # Check if purge already in progress
        if self.active_purges.get(ctx.guild.id):
            await ctx.send("⚠️ A purge is already in progress. Please wait.", delete_after=5)
            return
        
        # Validate amount
        if amount < 1:
            amount = 1
        elif amount > 3000:
            amount = 3000
        
        # Parse user
        target_user = None
        if user and user.lower() != "all":
            # Try to get member
            try:
                if user.isdigit():
                    target_user = ctx.guild.get_member(int(user))
                else:
                    # Try mention
                    match = re.match(r'<@!?(\d+)>', user)
                    if match:
                        target_user = ctx.guild.get_member(int(match.group(1)))
                    else:
                        # Try by name
                        target_user = discord.utils.find(
                            lambda m: m.name.lower() == user.lower() or (m.nick and m.nick.lower() == user.lower()),
                            ctx.guild.members
                        )
                
                if not target_user:
                    await ctx.send(f"❌ Could not find user: `{user}`", delete_after=5)
                    return
            except:
                await ctx.send(f"❌ Invalid user: `{user}`", delete_after=5)
                return
        
        # Mark purge as active
        self.active_purges[ctx.guild.id] = True
        
        try:
            # Build filter description
            filter_desc = self._get_filter_description(filter_type, target_user)
            
            # Send preparing message
            prep_embed = discord.Embed(
                title="🔄 Preparing to Purge Messages",
                description=f"**Channel:** {ctx.channel.mention}\n**Target:** {target_user.mention if target_user else 'All Users'}\n**Filter:** {filter_desc}\n**Amount:** {amount:,} messages",
                color=0xFFAA00,
                timestamp=datetime.utcnow()
            )
            prep_embed.set_footer(text="Scanning messages...")
            status_msg = await ctx.send(embed=prep_embed)
            
            # Delete the command message
            try:
                await ctx.message.delete()
            except:
                pass
            
            # Build check function
            check = self._build_check_function(target_user, filter_type)
            
            # Update status
            purge_embed = discord.Embed(
                title="🗑️ Purging Messages",
                description=f"**Channel:** {ctx.channel.mention}\n**Target:** {target_user.mention if target_user else 'All Users'}\n**Filter:** {filter_desc}\n**Amount:** {amount:,} messages",
                color=0xFF6600,
                timestamp=datetime.utcnow()
            )
            purge_embed.set_footer(text="Deleting messages...")
            await status_msg.edit(embed=purge_embed)
            
            # Attempt bulk delete first (messages < 14 days old)
            deleted_messages = []
            bulk_deleted = 0
            manual_deleted = 0
            failed = 0
            
            # Calculate cutoff for bulk delete
            bulk_cutoff = datetime.utcnow() - timedelta(days=14)
            
            # Collect messages
            messages_to_delete = []
            async for message in ctx.channel.history(limit=amount + 100):  # Extra buffer for filtering
                if len(messages_to_delete) >= amount:
                    break
                if message.id == status_msg.id:
                    continue
                if check(message):
                    messages_to_delete.append(message)
                    deleted_messages.append(message)
            
            # Split into bulk-deletable and old messages
            bulk_messages = [m for m in messages_to_delete if m.created_at.replace(tzinfo=None) > bulk_cutoff]
            old_messages = [m for m in messages_to_delete if m.created_at.replace(tzinfo=None) <= bulk_cutoff]
            
            # Bulk delete (100 at a time)
            if bulk_messages:
                for i in range(0, len(bulk_messages), 100):
                    batch = bulk_messages[i:i+100]
                    try:
                        await ctx.channel.delete_messages(batch)
                        bulk_deleted += len(batch)
                        
                        # Update progress
                        progress_embed = discord.Embed(
                            title="🗑️ Purging Messages",
                            description=f"**Progress:** {bulk_deleted + manual_deleted}/{len(messages_to_delete)}\n**Bulk deleted:** {bulk_deleted}\n**Manual deleted:** {manual_deleted}",
                            color=0xFF6600,
                            timestamp=datetime.utcnow()
                        )
                        await status_msg.edit(embed=progress_embed)
                        await asyncio.sleep(1)
                    except discord.HTTPException as e:
                        print(f"[PURGE] Bulk delete failed: {e}")
                        # Add to old messages for manual delete
                        old_messages.extend(batch)
            
            # Manual delete for old messages
            if old_messages:
                for msg in old_messages:
                    try:
                        await msg.delete()
                        manual_deleted += 1
                        
                        # Update progress every 10 messages
                        if manual_deleted % 10 == 0:
                            progress_embed = discord.Embed(
                                title="🗑️ Purging Messages (Manual Mode)",
                                description=f"**Progress:** {bulk_deleted + manual_deleted}/{len(messages_to_delete)}\n**Bulk deleted:** {bulk_deleted}\n**Manual deleted:** {manual_deleted}",
                                color=0xFF6600,
                                timestamp=datetime.utcnow()
                            )
                            progress_embed.set_footer(text="Deleting old messages one by one...")
                            await status_msg.edit(embed=progress_embed)
                        
                        await asyncio.sleep(1.5)  # Rate limit protection
                    except discord.HTTPException:
                        failed += 1
                    except:
                        failed += 1
            
            # Build results embed
            total_deleted = bulk_deleted + manual_deleted
            
            results_embed = discord.Embed(
                title="✅ Purge Complete",
                color=0x00FF00 if total_deleted > 0 else 0xFF0000,
                timestamp=datetime.utcnow()
            )
            
            results_embed.add_field(
                name="📊 Statistics",
                value=f"```\nTotal Deleted:  {total_deleted:,}\nBulk Delete:    {bulk_deleted:,}\nManual Delete:  {manual_deleted:,}\nFailed:         {failed:,}\n```",
                inline=False
            )
            
            results_embed.add_field(
                name="🎯 Filters Applied",
                value=f"**Target:** {target_user.mention if target_user else 'All Users'}\n**Type:** {filter_desc}\n**Channel:** {ctx.channel.mention}",
                inline=False
            )
            
            # Add breakdown by user if multiple users
            if not target_user and deleted_messages:
                user_counts = {}
                for msg in deleted_messages:
                    author_name = str(msg.author)
                    user_counts[author_name] = user_counts.get(author_name, 0) + 1
                
                # Sort and get top 5
                sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                if sorted_users:
                    breakdown = "\n".join([f"• **{name}**: {count}" for name, count in sorted_users])
                    if len(user_counts) > 5:
                        breakdown += f"\n*...and {len(user_counts) - 5} more*"
                    results_embed.add_field(
                        name="👥 Messages by User",
                        value=breakdown,
                        inline=False
                    )
            
            results_embed.set_footer(text=f"Executed by {ctx.author}", icon_url=ctx.author.display_avatar.url if ctx.author.display_avatar else None)
            
            await status_msg.edit(embed=results_embed)
            
            # Log the purge action
            await self._log_purge(ctx, total_deleted, target_user, filter_type, deleted_messages)
                
        except Exception as e:
            print(f"[PURGE] Error: {e}")
            import traceback
            traceback.print_exc()
            
            error_embed = discord.Embed(
                title="❌ Purge Failed",
                description=f"An error occurred: {str(e)[:200]}",
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            try:
                await status_msg.edit(embed=error_embed)
            except:
                await ctx.send(embed=error_embed, delete_after=10)
        
        finally:
            # Mark purge as complete
            self.active_purges[ctx.guild.id] = False
    
    def _get_filter_description(self, filter_type: str, target_user) -> str:
        """Get human-readable filter description"""
        filter_lower = filter_type.lower()
        
        if filter_lower == "all":
            return "All messages"
        elif filter_lower == "bots":
            return "Bot messages only"
        elif filter_lower == "files":
            return "Messages with attachments"
        elif filter_lower == "images":
            return "Messages with images"
        elif filter_lower == "links":
            return "Messages with links"
        elif filter_lower == "embeds":
            return "Messages with embeds"
        else:
            return f"Messages containing: `{filter_type}`"
    
    def _build_check_function(self, target_user, filter_type: str):
        """Build the message check function based on filters"""
        filter_lower = filter_type.lower()
        
        def check(message):
            # User filter
            if target_user and message.author.id != target_user.id:
                return False
            
            # Type filter
            if filter_lower == "all":
                return True
            elif filter_lower == "bots":
                return message.author.bot
            elif filter_lower == "files":
                return len(message.attachments) > 0
            elif filter_lower == "images":
                return any(
                    att.content_type and att.content_type.startswith('image/')
                    for att in message.attachments
                ) or any(
                    url in message.content.lower()
                    for url in ['.png', '.jpg', '.jpeg', '.gif', '.webp']
                )
            elif filter_lower == "links":
                return 'http://' in message.content or 'https://' in message.content
            elif filter_lower == "embeds":
                return len(message.embeds) > 0
            else:
                # Custom text filter
                return filter_type.lower() in message.content.lower()
        
        return check
    
    async def _log_purge(self, ctx, count: int, target_user, filter_type: str, messages: List[discord.Message]):
        """Log the purge action"""
        try:
            # Get logging cog if available
            logging_cog = self.bot.get_cog('LoggingModule')
            if logging_cog:
                await logging_cog.log_purge(ctx, count, target_user, filter_type, messages)
        except:
            pass


async def setup(bot):
    await bot.add_cog(PurgeModule(bot))
