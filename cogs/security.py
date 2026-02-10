"""
BlockForge OS Security Module v2.0.8
Handles Verification, Lockdown, and Raid Protection
"""

import discord
from discord.ext import commands, tasks
from discord import ui
import asyncio
from datetime import datetime, timedelta
import random
import string
from typing import Optional, Dict, List
from utils.database import Database


class VerificationCode:
    """Manages verification codes"""
    def __init__(self):
        self.codes: Dict[int, dict] = {}  # user_id -> {code, expires, guild_id}
    
    def generate(self, user_id: int, guild_id: int) -> str:
        code = ''.join(random.choices(string.digits, k=6))
        self.codes[user_id] = {
            'code': code,
            'expires': datetime.utcnow() + timedelta(minutes=5),
            'guild_id': guild_id
        }
        return code
    
    def verify(self, user_id: int, code: str, guild_id: int) -> bool:
        if user_id not in self.codes:
            return False
        data = self.codes[user_id]
        if data['guild_id'] != guild_id:
            return False
        if datetime.utcnow() > data['expires']:
            del self.codes[user_id]
            return False
        if data['code'] == code:
            del self.codes[user_id]
            return True
        return False
    
    def get_code(self, user_id: int) -> Optional[str]:
        if user_id in self.codes and datetime.utcnow() < self.codes[user_id]['expires']:
            return self.codes[user_id]['code']
        return None
    
    def cleanup(self):
        now = datetime.utcnow()
        expired = [uid for uid, data in self.codes.items() if now > data['expires']]
        for uid in expired:
            del self.codes[uid]


class VerificationModal(ui.Modal, title="Server Verification"):
    """Verification form modal"""
    
    def __init__(self, security_cog, guild_id: int, user_code: str, questions: List[dict]):
        super().__init__(timeout=300)
        self.security_cog = security_cog
        self.guild_id = guild_id
        self.user_code = user_code
        self.questions = questions
        self.answers = {}
        self.code_field_name = None  # Track which field is the code
        
        # Add question fields dynamically
        field_count = 0
        for i, q in enumerate(questions):
            if q['enabled']:
                field_count += 1
                field_name = f'q{field_count}'
                field = ui.TextInput(
                    label=q['question'][:45],  # Discord limit is 45 chars
                    style=discord.TextStyle.paragraph,
                    placeholder=q.get('placeholder', 'Enter your answer...'),
                    required=q.get('required', True),
                    max_length=500
                )
                setattr(self, field_name, field)
                self.add_item(field)
                
                # Track if this is the code field (has code in placeholder)
                if 'Your code:' in q.get('placeholder', ''):
                    self.code_field_name = field_name
    
    async def on_submit(self, interaction: discord.Interaction):
        # Collect answers
        answers = {}
        for i in range(1, 6):
            field = getattr(self, f'q{i}', None)
            if field:
                answers[f'q{i}'] = field.value
        
        # Get code answer from the tracked code field
        code_answer = ''
        if self.code_field_name:
            code_answer = answers.get(self.code_field_name, '').strip()
        else:
            # Fallback: check the last field or q5
            for key in reversed(sorted(answers.keys())):
                if answers[key]:
                    code_answer = answers[key].strip()
                    break
        
        # Verify code
        verified = self.security_cog.verification_codes.verify(
            interaction.user.id, code_answer, self.guild_id
        )
        
        if verified:
            await self.security_cog.complete_verification(interaction, answers)
        else:
            await self.security_cog.fail_verification(interaction, answers, code_answer)


class VerifyButton(ui.View):
    """Initial verify button view"""
    
    def __init__(self, security_cog):
        super().__init__(timeout=None)
        self.security_cog = security_cog
    
    @ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_start")
    async def verify_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.security_cog.start_verification(interaction)


class CodeRevealButton(ui.View):
    """Button to open verification form after seeing code"""
    
    def __init__(self, security_cog, guild_id: int, code: str):
        super().__init__(timeout=300)
        self.security_cog = security_cog
        self.guild_id = guild_id
        self.code = code
    
    @ui.button(label="Continue to Form", style=discord.ButtonStyle.primary, custom_id="verify_form")
    async def form_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.security_cog.show_verification_form(interaction, self.guild_id, self.code)


class SecurityModule(commands.Cog):
    """Server security features: Verification, Lockdown, Raid Protection"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.verification_codes = VerificationCode()
        self.lockdown_tasks = {}  # guild_id -> task
        self._init_tables()
        self.cleanup_codes.start()
        
        # Register persistent views
        self.bot.add_view(VerifyButton(self))
    
    def _init_tables(self):
        """Initialize security tables"""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        # Verification config
        cursor.execute('''CREATE TABLE IF NOT EXISTS verification_config (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            channel_id INTEGER,
            verified_role_id INTEGER,
            unverified_role_id INTEGER,
            q1_enabled INTEGER DEFAULT 1,
            q1_question TEXT DEFAULT 'How did you hear about {server}?',
            q2_enabled INTEGER DEFAULT 1,
            q2_question TEXT DEFAULT 'Why do you want to join {server}?',
            q3_enabled INTEGER DEFAULT 0,
            q3_question TEXT DEFAULT 'What is your age?',
            q4_enabled INTEGER DEFAULT 0,
            q4_question TEXT DEFAULT 'Do you agree to follow the rules?',
            q5_enabled INTEGER DEFAULT 1,
            q5_question TEXT DEFAULT 'Enter your 6-digit verification code:',
            log_responses INTEGER DEFAULT 1
        )''')
        
        # Verification logs
        cursor.execute('''CREATE TABLE IF NOT EXISTS verification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            status TEXT,
            answers TEXT,
            submitted_code TEXT,
            expected_code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Lockdown state
        cursor.execute('''CREATE TABLE IF NOT EXISTS lockdown_state (
            guild_id INTEGER PRIMARY KEY,
            active INTEGER DEFAULT 0,
            lockdown_role_id INTEGER,
            started_at TIMESTAMP,
            started_by INTEGER,
            invite_pause_until TIMESTAMP
        )''')
        
        # Autoroles
        cursor.execute('''CREATE TABLE IF NOT EXISTS autoroles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            role_id INTEGER,
            UNIQUE(guild_id, role_id)
        )''')
        
        conn.commit()
        conn.close()
    
    def cog_unload(self):
        self.cleanup_codes.cancel()
        for task in self.lockdown_tasks.values():
            task.cancel()
    
    @tasks.loop(minutes=5)
    async def cleanup_codes(self):
        self.verification_codes.cleanup()
    
    # ==================== VERIFICATION ====================
    
    def get_verification_config(self, guild_id: int) -> dict:
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM verification_config WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {
                'enabled': False, 'channel_id': None, 'verified_role_id': None, 'unverified_role_id': None,
                'q1_enabled': True, 'q1_question': 'How did you hear about {server}?',
                'q2_enabled': True, 'q2_question': 'Why do you want to join {server}?',
                'q3_enabled': False, 'q3_question': 'What is your age?',
                'q4_enabled': False, 'q4_question': 'Do you agree to follow the rules?',
                'q5_enabled': True, 'q5_question': 'Enter your 6-digit verification code:',
                'log_responses': True
            }
        
        return {
            'enabled': bool(row[1]), 'channel_id': row[2], 'verified_role_id': row[3], 'unverified_role_id': row[4],
            'q1_enabled': bool(row[5]), 'q1_question': row[6],
            'q2_enabled': bool(row[7]), 'q2_question': row[8],
            'q3_enabled': bool(row[9]), 'q3_question': row[10],
            'q4_enabled': bool(row[11]), 'q4_question': row[12],
            'q5_enabled': bool(row[13]), 'q5_question': row[14],
            'log_responses': bool(row[15]) if len(row) > 15 else True
        }
    
    def save_verification_config(self, guild_id: int, config: dict):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO verification_config VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (guild_id, int(config.get('enabled', False)), config.get('channel_id'), 
             config.get('verified_role_id'), config.get('unverified_role_id'),
             int(config.get('q1_enabled', True)), config.get('q1_question', 'How did you hear about {server}?'),
             int(config.get('q2_enabled', True)), config.get('q2_question', 'Why do you want to join {server}?'),
             int(config.get('q3_enabled', False)), config.get('q3_question', 'What is your age?'),
             int(config.get('q4_enabled', False)), config.get('q4_question', 'Do you agree to follow the rules?'),
             int(config.get('q5_enabled', True)), config.get('q5_question', 'Enter your 6-digit verification code:'),
             int(config.get('log_responses', True))))
        conn.commit()
        conn.close()
    
    async def create_verification_embed(self, guild: discord.Guild) -> discord.Embed:
        """Create the main verification embed for the verification channel"""
        embed = discord.Embed(
            title=f"🔒 {guild.name} - Verification Required",
            color=0x2ECC71
        )
        embed.add_field(
            name="Welcome!",
            value="To access the server, you must complete verification.\nClick the green **Verify** button below to begin.",
            inline=False
        )
        embed.add_field(
            name="⚠️ *Verification is required to keep our community safe!*",
            value="",
            inline=False
        )
        
        if guild.icon:
            embed.set_image(url=guild.icon.url)
        
        return embed
    
    async def start_verification(self, interaction: discord.Interaction):
        """Handle verify button click - show code"""
        guild = interaction.guild
        config = self.get_verification_config(guild.id)
        
        if not config['enabled']:
            await interaction.response.send_message("❌ Verification is not enabled.", ephemeral=True)
            return
        
        # Generate code
        code = self.verification_codes.generate(interaction.user.id, guild.id)
        
        embed = discord.Embed(
            title="🔐 Verification Code",
            description=f"Your unique verification code is:\n\n# `{code}`\n\n"
                       f"⏰ **This code expires in 5 minutes.**\n\n"
                       f"📋 Copy this code, then click **Continue to Form** below.\n"
                       f"You will need to enter this code in the form.",
            color=0x3498DB
        )
        embed.set_footer(text="Do not share this code with anyone.")
        
        view = CodeRevealButton(self, guild.id, code)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def show_verification_form(self, interaction: discord.Interaction, guild_id: int, code: str):
        """Show the verification form modal"""
        guild = interaction.guild or self.bot.get_guild(guild_id)
        config = self.get_verification_config(guild_id)
        
        # Build questions list
        questions = []
        server_name = guild.name if guild else "the server"
        
        for i in range(1, 6):
            enabled = config.get(f'q{i}_enabled', False)
            question = config.get(f'q{i}_question', '').replace('{server}', server_name)
            
            if enabled and question:
                questions.append({
                    'enabled': True,
                    'question': question,
                    'required': (i == 5),  # Code is always required
                    'placeholder': f'Your code: {code}' if i == 5 else 'Enter your answer...'
                })
        
        if not questions:
            # At minimum, require code
            questions.append({
                'enabled': True,
                'question': 'Enter your 6-digit verification code:',
                'required': True,
                'placeholder': f'Your code: {code}'
            })
        
        modal = VerificationModal(self, guild_id, code, questions)
        await interaction.response.send_modal(modal)
    
    async def complete_verification(self, interaction: discord.Interaction, answers: dict):
        """Handle successful verification"""
        guild = interaction.guild
        config = self.get_verification_config(guild.id)
        
        # Log the verification
        self.log_verification(guild.id, interaction.user, 'success', answers)
        
        # Remove unverified role
        if config.get('unverified_role_id'):
            unverified_role = guild.get_role(config['unverified_role_id'])
            if unverified_role and unverified_role in interaction.user.roles:
                try:
                    await interaction.user.remove_roles(unverified_role, reason="Verification complete")
                    print(f"[SECURITY] Removed unverified role from {interaction.user}")
                except Exception as e:
                    print(f"[SECURITY] Failed to remove unverified role: {e}")
        
        # Add verified role
        if config.get('verified_role_id'):
            verified_role = guild.get_role(config['verified_role_id'])
            if verified_role:
                try:
                    await interaction.user.add_roles(verified_role, reason="Verification complete")
                    print(f"[SECURITY] Added verified role to {interaction.user}")
                except Exception as e:
                    print(f"[SECURITY] Failed to add verified role: {e}")
        
        # Add autoroles
        autoroles = self.get_autoroles(guild.id)
        for role_id in autoroles:
            role = guild.get_role(role_id)
            if role:
                try:
                    await interaction.user.add_roles(role, reason="Autorole on verification")
                except Exception as e:
                    print(f"[SECURITY] Failed to add autorole {role.name}: {e}")
        
        # Send success message
        embed = discord.Embed(
            title="✅ Verification Successful!",
            description="You now have access to the server.",
            color=0x2ECC71
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Send DM
        await self.send_verification_dm(interaction.user, guild)
        
        # Log to logging channel
        await self.log_verification_to_channel(guild, interaction.user, 'success', answers)
    
    async def fail_verification(self, interaction: discord.Interaction, answers: dict, submitted_code: str):
        """Handle failed verification"""
        guild = interaction.guild
        
        # Log the failure
        self.log_verification(guild.id, interaction.user, 'failed', answers, submitted_code)
        
        embed = discord.Embed(
            title="❌ Verification Failed",
            description="The code you entered is incorrect or expired.\n\nPlease click the **Verify** button again to get a new code.",
            color=0xE74C3C
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Log to logging channel
        await self.log_verification_to_channel(guild, interaction.user, 'failed', answers, submitted_code)
    
    async def send_verification_dm(self, user: discord.User, guild: discord.Guild):
        """Send verification success DM"""
        # Build embed from config
        embed = self.db.build_embed_from_config(
            guild.id, 
            'verify_dm',
            placeholders={
                'server': guild.name,
                'user': str(user),
                'user_id': str(user.id)
            }
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        try:
            await user.send(embed=embed)
        except:
            pass  # DMs disabled
    
    def log_verification(self, guild_id: int, user: discord.User, status: str, 
                        answers: dict, submitted_code: str = None):
        """Log verification attempt to database"""
        import json
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO verification_logs 
            (guild_id, user_id, user_name, status, answers, submitted_code) VALUES (?,?,?,?,?,?)''',
            (guild_id, user.id, str(user), status, json.dumps(answers), submitted_code))
        conn.commit()
        conn.close()
    
    async def log_verification_to_channel(self, guild: discord.Guild, user: discord.User, 
                                          status: str, answers: dict, submitted_code: str = None):
        """Log verification to logging channel"""
        logging_cog = self.bot.get_cog('LoggingModule')
        if not logging_cog:
            return
        
        if not logging_cog.is_log_type_enabled(guild.id, 'verify_log'):
            return
        
        color = 0x2ECC71 if status == 'success' else 0xE74C3C
        title = "✅ Verification Passed" if status == 'success' else "❌ Verification Failed"
        
        embed = discord.Embed(title=title, color=color, timestamp=datetime.utcnow())
        embed.set_author(name=str(user), icon_url=user.display_avatar.url if user.display_avatar else None)
        embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="Status", value=f"`{status.upper()}`", inline=True)
        
        # Show answers
        for key, value in answers.items():
            if key != 'q5':  # Don't show code in logs
                embed.add_field(name=f"Response {key.upper()}", value=f"```\n{value[:200]}\n```", inline=False)
        
        if status == 'failed' and submitted_code:
            embed.add_field(name="Submitted Code", value=f"`{submitted_code}`", inline=True)
        
        embed.set_footer(text=f"User ID: {user.id}")
        
        await logging_cog.send_log(guild, 'verify_log', embed)
    
    # ==================== AUTOROLES ====================
    
    def get_autoroles(self, guild_id: int) -> List[int]:
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT role_id FROM autoroles WHERE guild_id = ?', (guild_id,))
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]
    
    def add_autorole(self, guild_id: int, role_id: int) -> bool:
        conn = self.db._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT OR IGNORE INTO autoroles (guild_id, role_id) VALUES (?, ?)', (guild_id, role_id))
            conn.commit()
            success = cursor.rowcount > 0
        except:
            success = False
        conn.close()
        return success
    
    def remove_autorole(self, guild_id: int, role_id: int) -> bool:
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM autoroles WHERE guild_id = ? AND role_id = ?', (guild_id, role_id))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    
    # ==================== LOCKDOWN ====================
    
    def get_lockdown_state(self, guild_id: int) -> dict:
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM lockdown_state WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {'active': False, 'lockdown_role_id': None, 'started_at': None, 'started_by': None}
        
        return {
            'active': bool(row[1]),
            'lockdown_role_id': row[2],
            'started_at': row[3],
            'started_by': row[4],
            'invite_pause_until': row[5]
        }
    
    def save_lockdown_state(self, guild_id: int, state: dict):
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO lockdown_state VALUES (?,?,?,?,?,?)''',
            (guild_id, int(state.get('active', False)), state.get('lockdown_role_id'),
             state.get('started_at'), state.get('started_by'), state.get('invite_pause_until')))
        conn.commit()
        conn.close()
    
    async def activate_lockdown(self, guild: discord.Guild, moderator: discord.Member) -> tuple:
        """Activate server lockdown"""
        state = self.get_lockdown_state(guild.id)
        
        if state['active']:
            return False, "Server is already in lockdown."
        
        try:
            # Create lockdown role
            bot_top_role = guild.me.top_role
            lockdown_role = await guild.create_role(
                name="🔒 Lockdown",
                color=discord.Color.dark_gray(),
                reason="Server lockdown activated"
            )
            
            # Position it just below bot's highest role
            positions = {lockdown_role: bot_top_role.position - 1}
            await guild.edit_role_positions(positions)
            
            # Apply to all channels
            deny_perms = discord.PermissionOverwrite(
                send_messages=False,
                add_reactions=False,
                create_public_threads=False,
                create_private_threads=False,
                connect=False,
                speak=False
            )
            
            for channel in guild.channels:
                try:
                    await channel.set_permissions(lockdown_role, overwrite=deny_perms, 
                                                  reason="Server lockdown")
                except:
                    pass
            
            # Add role to all members
            for member in guild.members:
                if not member.bot:
                    try:
                        await member.add_roles(lockdown_role, reason="Server lockdown")
                    except:
                        pass
            
            # Pause invites
            try:
                await guild.edit(invites_disabled=True, reason="Server lockdown")
            except:
                pass
            
            # Save state
            state = {
                'active': True,
                'lockdown_role_id': lockdown_role.id,
                'started_at': datetime.utcnow().isoformat(),
                'started_by': moderator.id,
                'invite_pause_until': (datetime.utcnow() + timedelta(hours=24)).isoformat()
            }
            self.save_lockdown_state(guild.id, state)
            
            # Start invite pause loop
            self.start_invite_pause_loop(guild.id)
            
            return True, f"Lockdown activated. Role: {lockdown_role.mention}"
            
        except Exception as e:
            return False, f"Failed to activate lockdown: {str(e)}"
    
    async def deactivate_lockdown(self, guild: discord.Guild, remove_user_perms: bool = False) -> tuple:
        """Deactivate server lockdown"""
        state = self.get_lockdown_state(guild.id)
        
        if not state['active']:
            return False, "Server is not in lockdown."
        
        try:
            # Get and delete lockdown role
            if state['lockdown_role_id']:
                lockdown_role = guild.get_role(state['lockdown_role_id'])
                if lockdown_role:
                    await lockdown_role.delete(reason="Lockdown deactivated")
            
            # Re-enable invites
            try:
                await guild.edit(invites_disabled=False, reason="Lockdown deactivated")
            except:
                pass
            
            # Remove user permissions if flag set
            if remove_user_perms:
                for channel in guild.channels:
                    try:
                        for target, overwrite in channel.overwrites.items():
                            if isinstance(target, discord.Member):
                                await channel.set_permissions(target, overwrite=None,
                                                             reason="Lockdown cleanup - removing user perms")
                    except:
                        pass
            
            # Stop invite pause loop
            if guild.id in self.lockdown_tasks:
                self.lockdown_tasks[guild.id].cancel()
                del self.lockdown_tasks[guild.id]
            
            # Clear state
            state = {'active': False, 'lockdown_role_id': None, 'started_at': None, 'started_by': None}
            self.save_lockdown_state(guild.id, state)
            
            return True, "Lockdown deactivated."
            
        except Exception as e:
            return False, f"Failed to deactivate lockdown: {str(e)}"
    
    def start_invite_pause_loop(self, guild_id: int):
        """Start the invite pause renewal loop"""
        async def pause_loop():
            while True:
                await asyncio.sleep(23 * 60 * 60)  # 23 hours
                guild = self.bot.get_guild(guild_id)
                if guild:
                    state = self.get_lockdown_state(guild_id)
                    if state['active']:
                        try:
                            await guild.edit(invites_disabled=True, reason="Lockdown invite pause renewal")
                            state['invite_pause_until'] = (datetime.utcnow() + timedelta(hours=24)).isoformat()
                            self.save_lockdown_state(guild_id, state)
                        except:
                            pass
                    else:
                        break
                else:
                    break
        
        if guild_id in self.lockdown_tasks:
            self.lockdown_tasks[guild_id].cancel()
        
        self.lockdown_tasks[guild_id] = asyncio.create_task(pause_loop())
    
    # ==================== UNVERIFIED ROLE MANAGEMENT ====================
    
    async def create_unverified_role(self, guild: discord.Guild) -> discord.Role:
        """Create and configure the unverified role"""
        config = self.get_verification_config(guild.id)
        
        # Create role
        unverified_role = await guild.create_role(
            name="Unverified",
            color=discord.Color.dark_gray(),
            reason="Verification system setup"
        )
        
        # Deny view channels everywhere except verification channel
        for channel in guild.channels:
            try:
                if config['channel_id'] and channel.id == config['channel_id']:
                    # Allow viewing verification channel
                    await channel.set_permissions(unverified_role, 
                        view_channel=True, send_messages=False, add_reactions=True,
                        reason="Unverified role setup")
                else:
                    # Deny viewing other channels
                    await channel.set_permissions(unverified_role,
                        view_channel=False, reason="Unverified role setup")
            except:
                pass
        
        # Save to config
        config['unverified_role_id'] = unverified_role.id
        self.save_verification_config(guild.id, config)
        
        return unverified_role
    
    async def setup_verified_role(self, guild: discord.Guild, role: discord.Role):
        """Configure the verified role"""
        config = self.get_verification_config(guild.id)
        
        # Deny viewing verification channel for verified users
        if config['channel_id']:
            channel = guild.get_channel(config['channel_id'])
            if channel:
                try:
                    await channel.set_permissions(role, view_channel=False,
                                                  reason="Verified role setup")
                except:
                    pass
        
        # Save to config
        config['verified_role_id'] = role.id
        self.save_verification_config(guild.id, config)
    
    # ==================== EVENT LISTENERS ====================
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Assign unverified role to new members"""
        if member.bot:
            return
        
        config = self.get_verification_config(member.guild.id)
        
        if config['enabled'] and config['unverified_role_id']:
            role = member.guild.get_role(config['unverified_role_id'])
            if role:
                try:
                    await member.add_roles(role, reason="Unverified member joined")
                except:
                    pass
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Update unverified role for new channels"""
        config = self.get_verification_config(channel.guild.id)
        
        if config['enabled'] and config['unverified_role_id']:
            role = channel.guild.get_role(config['unverified_role_id'])
            if role:
                try:
                    await channel.set_permissions(role, view_channel=False,
                                                  reason="Auto-update unverified role")
                except:
                    pass


async def setup(bot):
    await bot.add_cog(SecurityModule(bot))