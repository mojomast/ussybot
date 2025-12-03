"""
BRRR Bot - Chat Cog
Handles conversational AI with memory
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging

logger = logging.getLogger('brrr.chat')


class Chat(commands.Cog):
    """Conversational AI with persistent memory"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @property
    def db(self):
        return self.bot.db
    
    @property
    def llm(self):
        return self.bot.llm
    
    async def handle_mention(self, message: discord.Message):
        """Handle when the bot is mentioned in a message"""
        
        if not self.llm:
            return
        
        # Show typing indicator
        async with message.channel.typing():
            try:
                # Get user info (works for both users and bots!)
                user_id = message.author.id
                guild_id = message.guild.id if message.guild else 0
                channel_id = message.channel.id
                
                # Get display name
                user_name = message.author.display_name
                
                # Check if it's a bot
                is_bot = message.author.bot
                
                # Get user memories
                memories = await self.db.get_all_memories(user_id, guild_id)
                
                # Extract custom persona instructions if set
                custom_instructions = None
                if 'persona_instructions' in memories:
                    persona_data = memories['persona_instructions']
                    custom_instructions = persona_data.get('value') if isinstance(persona_data, dict) else persona_data
                
                # Get conversation history for context
                # For now, disable history to prevent stale context pollution
                # TODO: Implement proper conversation session management with timeouts
                raw_history = await self.db.get_recent_messages(user_id, guild_id, channel_id, limit=5)
                
                # Filter and sanitize conversation history
                history = []
                last_role = None
                for msg in raw_history:
                    msg_content = msg.get('content', '')
                    msg_role = msg.get('role', '')
                    
                    # Skip empty messages
                    if not msg_content.strip():
                        continue
                    
                    # Skip error/fallback messages from the bot
                    if msg_role == 'assistant' and "didn't quite get that" in msg_content:
                        continue
                    
                    # Skip messages that look like slash commands
                    if msg_content.startswith('/'):
                        continue
                    
                    # Skip messages that ask about commands/projects/help (command-like requests)
                    lower_content = msg_content.lower()
                    command_indicators = [
                        'describe the projects',
                        '/help', '/project', '/idea', '/week', '/memory', '/persona',
                        'what commands', 'list commands', 'show commands',
                        'what can you do', 'how do you help',
                        'Quick things I can do',  # Bot's command list response
                        'Start/manage projects:',  # Bot's help response patterns
                        'Useful commands',
                        'Quick commands to get started',  # Bot's greeting with command list
                        '/ping (latency)',  # Bot listing commands
                        '/brrr (bot status)',
                    ]
                    if any(indicator in msg_content or indicator in lower_content for indicator in command_indicators):
                        continue
                    
                    # Skip consecutive same-role messages (keeps only the latest one per role)
                    # This fixes malformed history with multiple user messages in a row
                    if msg_role == last_role:
                        # Replace the previous message of the same role
                        if history and history[-1].get('role') == msg_role:
                            history[-1] = msg
                            continue
                    
                    history.append(msg)
                    last_role = msg_role
                
                # Only keep the last 2 exchanges (4 messages max: user, assistant, user, assistant)
                # This prevents old context from polluting new conversations
                if len(history) > 4:
                    history = history[-4:]
                
                logger.debug(f"Filtered history: {len(raw_history)} -> {len(history)} messages")
                
                # Clean the message content (remove bot mention)
                content = message.content
                for mention in message.mentions:
                    content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
                content = content.strip()
                
                if not content:
                    content = "Hello!"
                
                # Add context about whether this is a bot
                if is_bot:
                    content = f"[This message is from another bot named {user_name}] {content}"
                
                # Initialize ToolExecutor
                from src.tools import TOOLS_SCHEMA, ToolExecutor
                import json
                tool_executor = ToolExecutor(self.db)
                
                # First LLM call - pass conversation history as context, current message as user_message
                response = await self.llm.chat(
                    user_message=content,
                    user_memories=memories,
                    user_name=user_name,
                    custom_instructions=custom_instructions,
                    conversation_context=history if history else None,
                    tools=TOOLS_SCHEMA
                )
                
                # Handle tool calls with multi-round support
                # The LLM may return tool calls that, when executed, lead to more tool calls
                # We loop until we get a final text response (max 5 rounds to prevent infinite loops)
                max_tool_rounds = 5
                tool_round = 0
                all_tool_calls = []  # Track all tool calls for building message history
                all_tool_results = []  # Track all results
                
                while response.tool_calls and tool_round < max_tool_rounds:
                    tool_round += 1
                    logger.debug(f"Tool round {tool_round}: processing {len(response.tool_calls)} tool calls")
                    
                    # Execute all tool calls in this round
                    current_tool_calls = response.tool_calls
                    current_tool_results = []
                    
                    for tool_call in current_tool_calls:
                        function_name = tool_call["function"]["name"]
                        try:
                            arguments = json.loads(tool_call["function"]["arguments"])
                        except json.JSONDecodeError:
                            arguments = {}
                        
                        # Execute tool
                        tool_result = await tool_executor.execute_tool(
                            function_name, 
                            arguments, 
                            context={"guild_id": guild_id, "user_id": user_id}
                        )
                        
                        current_tool_results.append({
                            "tool_call_id": tool_call["id"],
                            "name": function_name,
                            "result": tool_result
                        })
                    
                    # Accumulate for history
                    all_tool_calls.append(current_tool_calls)
                    all_tool_results.append(current_tool_results)
                    
                    # Send tool results back to LLM
                    response = await self.llm.chat_with_tool_results(
                        user_message=content,
                        assistant_tool_calls=current_tool_calls,
                        tool_results=current_tool_results,
                        user_memories=memories,
                        user_name=user_name,
                        custom_instructions=custom_instructions,
                        conversation_context=history if history else None,
                        tools=TOOLS_SCHEMA
                    )
                
                if tool_round >= max_tool_rounds and response.tool_calls:
                    logger.warning(f"Hit max tool rounds ({max_tool_rounds}), forcing response")
                    response.content = "I tried to complete your request but it required too many steps. Please try breaking it into smaller requests."
                
                # Save the conversation to history
                await self.db.add_message(user_id, guild_id, channel_id, "user", content)
                await self.db.add_message(user_id, guild_id, channel_id, "assistant", response.content)
                
                # Save any new memories
                for mem in response.memories_to_save:
                    await self.db.set_memory(
                        user_id=user_id,
                        guild_id=guild_id,
                        key=mem.get('key', 'misc'),
                        value=mem.get('value', ''),
                        context=mem.get('context')
                    )
                    logger.info(f"Saved memory for {user_name}: {mem['key']} = {mem['value']}")
                
                # Send response
                # Split if too long
                reply_content = response.content.strip()
                if not reply_content:
                    reply_content = "brrr... my brain went blank! Try asking again? 🔧"
                if len(reply_content) > 2000:
                    chunks = [reply_content[i:i+2000] for i in range(0, len(reply_content), 2000)]
                    for i, chunk in enumerate(chunks):
                        if i == 0:
                            await message.reply(chunk, mention_author=False)
                        else:
                            await message.channel.send(chunk)
                else:
                    await message.reply(reply_content, mention_author=False)
                    
            except Exception as e:
                logger.error(f"Error in chat handler: {e}", exc_info=True)
                await message.reply(
                    "brrr... something went wrong! Try again? 🔧",
                    mention_author=False
                )
    
    # Memory management commands
    memory_group = app_commands.Group(
        name="memory",
        description="Manage what the bot remembers about you",
        guild_only=True
    )
    
    @memory_group.command(name="show", description="See what the bot remembers about you")
    async def memory_show(self, interaction: discord.Interaction):
        """Show all memories for the user"""
        
        memories = await self.db.get_all_memories(
            interaction.user.id,
            interaction.guild.id
        )
        
        if not memories:
            await interaction.response.send_message(
                "I don't have any memories about you yet! Chat with me and I'll remember things. 🧠",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"🧠 What I Remember About {interaction.user.display_name}",
            color=discord.Color.purple()
        )
        
        for key, data in list(memories.items())[:25]:  # Discord field limit
            value = data['value'] if isinstance(data, dict) else data
            context = data.get('context', '') if isinstance(data, dict) else ''
            
            field_value = value
            if context:
                field_value += f"\n*{context}*"
            
            embed.add_field(
                name=key.replace('_', ' ').title(),
                value=field_value[:1024],
                inline=True
            )
        
        embed.set_footer(text="Use /memory forget <key> to remove a memory")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @memory_group.command(name="forget", description="Make the bot forget something specific")
    @app_commands.describe(key="The memory key to forget (e.g., 'skill_python')")
    async def memory_forget(self, interaction: discord.Interaction, key: str):
        """Delete a specific memory"""
        
        memory = await self.db.get_memory(
            interaction.user.id,
            interaction.guild.id,
            key
        )
        
        if not memory:
            await interaction.response.send_message(
                f"I don't have a memory with key `{key}`!",
                ephemeral=True
            )
            return
        
        await self.db.delete_memory(
            interaction.user.id,
            interaction.guild.id,
            key
        )
        
        await interaction.response.send_message(
            f"✅ Forgot: `{key}`",
            ephemeral=True
        )
    
    @memory_group.command(name="clear", description="Clear all memories about you")
    async def memory_clear(self, interaction: discord.Interaction):
        """Clear all memories for the user"""
        
        # Confirmation view
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.confirmed = False
            
            @discord.ui.button(label="Yes, forget everything", style=discord.ButtonStyle.danger)
            async def confirm(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.confirmed = True
                self.stop()
                await button_interaction.response.defer()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.stop()
                await button_interaction.response.defer()
        
        view = ConfirmView()
        await interaction.response.send_message(
            "⚠️ This will clear ALL my memories about you. Are you sure?",
            view=view,
            ephemeral=True
        )
        
        await view.wait()
        
        if view.confirmed:
            await self.db.clear_user_memories(
                interaction.user.id,
                interaction.guild.id
            )
            await interaction.edit_original_response(
                content="🧹 All memories cleared! Fresh start. 🧠",
                view=None
            )
        else:
            await interaction.edit_original_response(
                content="Cancelled - your memories are safe!",
                view=None
            )
    
    @memory_group.command(name="add", description="Manually add a memory")
    @app_commands.describe(
        key="Memory key (e.g., 'favorite_language')",
        value="Memory value (e.g., 'Python')"
    )
    async def memory_add(self, interaction: discord.Interaction, key: str, value: str):
        """Manually add a memory"""
        
        # Sanitize key
        key = key.lower().replace(' ', '_')
        
        await self.db.set_memory(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            key=key,
            value=value,
            context=f"Manually added by user"
        )
        
        await interaction.response.send_message(
            f"✅ I'll remember: `{key}` = `{value}`",
            ephemeral=True
        )
    
    # Direct chat command for when you don't want to @ the bot
    @app_commands.command(name="chat", description="Chat with the bot")
    @app_commands.guild_only()
    @app_commands.describe(message="What do you want to say?")
    async def chat_command(self, interaction: discord.Interaction, message: str):
        """Direct chat command"""
        
        if not self.llm:
            await interaction.response.send_message(
                "Chat is disabled - LLM not configured!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            user_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else 0
            channel_id = interaction.channel.id
            user_name = interaction.user.display_name
            
            memories = await self.db.get_all_memories(user_id, guild_id)
            history = await self.db.get_recent_messages(user_id, guild_id, channel_id, limit=5)
            
            # Extract custom persona instructions if set
            custom_instructions = None
            if 'persona_instructions' in memories:
                persona_data = memories['persona_instructions']
                custom_instructions = persona_data.get('value') if isinstance(persona_data, dict) else persona_data
            
            response = await self.llm.chat(
                user_message=message,
                user_memories=memories,
                user_name=user_name,
                custom_instructions=custom_instructions,
                conversation_context=history if history else None
            )
            
            # Save conversation
            await self.db.add_message(user_id, guild_id, channel_id, "user", message)
            await self.db.add_message(user_id, guild_id, channel_id, "assistant", response.content)
            
            # Save memories
            for mem in response.memories_to_save:
                await self.db.set_memory(
                    user_id=user_id,
                    guild_id=guild_id,
                    key=mem.get('key', 'misc'),
                    value=mem.get('value', ''),
                    context=mem.get('context')
                )
            
            reply_content = response.content.strip()
            # Build response embed
            if not reply_content:
                reply_content = "brrr... my brain went blank! Try asking again? 🔧"
            embed = discord.Embed(
                description=reply_content,
                color=discord.Color.blue()
            )
            embed.set_author(
                name="BRRR Bot",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in chat command: {e}", exc_info=True)
            await interaction.followup.send(
                "brrr... something went wrong! 🔧",
                ephemeral=True
            )
    
    # Persona customization commands
    persona_group = app_commands.Group(
        name="persona",
        description="Customize how the bot responds to you",
        guild_only=True
    )
    
    @persona_group.command(name="set", description="Set custom instructions for how the bot should respond")
    async def persona_set(self, interaction: discord.Interaction):
        """Set custom persona instructions via modal"""
        
        # Get current instructions to pre-fill
        current = await self.db.get_memory(
            interaction.user.id,
            interaction.guild.id,
            "persona_instructions"
        )
        
        class PersonaModal(discord.ui.Modal, title="Customize Bot Behavior"):
            instructions = discord.ui.TextInput(
                label="Custom Instructions",
                style=discord.TextStyle.paragraph,
                placeholder="Examples:\n- Be more concise\n- Explain things like I'm a beginner\n- Focus on Python/Rust/etc\n- Use more technical language\n- Be extra encouraging",
                max_length=1000,
                required=True,
                default=current or ""
            )
            
            async def on_submit(modal_self, modal_interaction: discord.Interaction):
                modal_self.result = modal_self.instructions.value
                await modal_interaction.response.defer()
        
        modal = PersonaModal()
        await interaction.response.send_modal(modal)
        
        try:
            await modal.wait()
        except:
            return
        
        if not hasattr(modal, 'result'):
            return
        
        await self.db.set_memory(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            key="persona_instructions",
            value=modal.result,
            context="Custom persona set by user"
        )
        
        embed = discord.Embed(
            title="✨ Persona Updated!",
            description="I'll now follow your custom instructions when chatting with you.",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="Your Instructions",
            value=modal.result[:500] + ("..." if len(modal.result) > 500 else ""),
            inline=False
        )
        embed.set_footer(text="Use /persona show to view • /persona clear to reset")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @persona_group.command(name="show", description="View your current persona settings")
    async def persona_show(self, interaction: discord.Interaction):
        """Show current persona instructions"""
        
        instructions = await self.db.get_memory(
            interaction.user.id,
            interaction.guild.id,
            "persona_instructions"
        )
        
        if not instructions:
            await interaction.response.send_message(
                "You haven't set any custom instructions yet!\n"
                "Use `/persona set` to customize how I respond to you.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🎭 Your Persona Settings",
            description=instructions,
            color=discord.Color.purple()
        )
        embed.set_footer(text="Use /persona set to change • /persona clear to reset")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @persona_group.command(name="clear", description="Reset to default bot behavior")
    async def persona_clear(self, interaction: discord.Interaction):
        """Clear custom persona instructions"""
        
        await self.db.delete_memory(
            interaction.user.id,
            interaction.guild.id,
            "persona_instructions"
        )
        
        await interaction.response.send_message(
            "✅ Persona reset to default! I'll respond with my standard personality now.",
            ephemeral=True
        )
    
    @persona_group.command(name="preset", description="Apply a preset persona style")
    @app_commands.describe(style="Choose a preset style")
    @app_commands.choices(style=[
        app_commands.Choice(name="🎯 Concise - Short, direct responses", value="concise"),
        app_commands.Choice(name="📚 Detailed - Thorough explanations", value="detailed"),
        app_commands.Choice(name="🌱 Beginner-Friendly - Simple language, more context", value="beginner"),
        app_commands.Choice(name="🔧 Technical - Advanced, precise terminology", value="technical"),
        app_commands.Choice(name="🎉 Hype - Extra enthusiastic and encouraging", value="hype"),
        app_commands.Choice(name="🧘 Calm - Relaxed, no pressure vibes", value="calm"),
    ])
    async def persona_preset(self, interaction: discord.Interaction, style: str):
        """Apply a preset persona"""
        
        presets = {
            "concise": "Keep responses very short and to the point. Avoid unnecessary explanation. Use bullet points when listing things. Skip pleasantries.",
            "detailed": "Provide thorough, comprehensive explanations. Include examples when helpful. Break down complex topics step by step. Don't assume prior knowledge.",
            "beginner": "Explain things as if I'm new to programming. Use simple analogies. Define technical terms. Be patient and encouraging. Suggest resources for learning more.",
            "technical": "Use precise technical terminology. Assume I have solid programming experience. Focus on implementation details, edge cases, and best practices. Be direct.",
            "hype": "Be SUPER enthusiastic! Celebrate every win, big or small. Use lots of emojis and energy. Make everything feel exciting. Pump me up to ship my projects!",
            "calm": "Keep a relaxed, no-pressure tone. Don't be overly energetic. Be supportive but chill. It's okay to take things slow. Focus on sustainable progress.",
        }
        
        instructions = presets.get(style)
        
        await self.db.set_memory(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            key="persona_instructions",
            value=instructions,
            context=f"Preset: {style}"
        )
        
        style_names = {
            "concise": "🎯 Concise",
            "detailed": "📚 Detailed", 
            "beginner": "🌱 Beginner-Friendly",
            "technical": "🔧 Technical",
            "hype": "🎉 Hype",
            "calm": "🧘 Calm"
        }
        
        embed = discord.Embed(
            title=f"✨ Persona: {style_names[style]}",
            description=f"I'll now respond in this style:\n\n*{instructions}*",
            color=discord.Color.purple()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Chat(bot))
