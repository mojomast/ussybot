"""
BRRR Bot - Ideas Cog
Handles /idea add, list, pick
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging

logger = logging.getLogger('brrr.ideas')


class IdeaModal(discord.ui.Modal, title="Add New Idea"):
    """Modal for adding a new idea"""
    
    idea_title = discord.ui.TextInput(
        label="Idea Title",
        placeholder="What's your idea?",
        max_length=100,
        required=True
    )
    
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        placeholder="Describe the idea in more detail...",
        max_length=500,
        required=False
    )
    
    tags = discord.ui.TextInput(
        label="Tags (comma separated)",
        placeholder="web, api, fun",
        max_length=100,
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        tag_list = []
        if self.tags.value:
            tag_list = [t.strip() for t in self.tags.value.split(',') if t.strip()]
        
        self.result = {
            'title': self.idea_title.value,
            'description': self.description.value or None,
            'tags': tag_list
        }
        await interaction.response.defer()


class IdeaSelectView(discord.ui.View):
    """View for selecting an idea to turn into a project"""
    
    def __init__(self, ideas: list, bot):
        super().__init__(timeout=300)
        self.ideas = ideas
        self.bot = bot
        
        # Create select menu
        options = []
        for idea in ideas[:25]:
            options.append(
                discord.SelectOption(
                    label=idea['title'][:100],
                    value=str(idea['id']),
                    description=idea['description'][:100] if idea['description'] else "No description"
                )
            )
        
        self.select = discord.ui.Select(
            placeholder="Pick an idea to start...",
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)
    
    async def select_callback(self, interaction: discord.Interaction):
        idea_id = int(self.select.values[0])
        idea = next((i for i in self.ideas if i['id'] == idea_id), None)
        
        if not idea:
            await interaction.response.send_message("Idea not found!", ephemeral=True)
            return
        
        # Import and show project modal
        from src.cogs.projects import ProjectModal
        modal = ProjectModal()
        modal.project_title.default = idea['title']
        modal.description.default = idea['description'] or ""
        modal.tags.default = ", ".join(idea['tags']) if idea['tags'] else ""
        
        await interaction.response.send_modal(modal)
        
        try:
            await modal.wait()
        except:
            return
        
        if not hasattr(modal, 'result'):
            return
        
        # Create the project
        data = modal.result
        project_id = await self.bot.db.create_project(
            guild_id=interaction.guild.id,
            title=data['title'],
            description=data['description'],
            owners=[interaction.user.id],
            tags=data['tags']
        )
        
        # Mark idea as used
        await self.bot.db.mark_idea_used(idea_id, project_id)
        
        # Send confirmation
        embed = discord.Embed(
            title=f"🚀 Project Created from Idea!",
            description=f"**{data['title']}** is now a project (ID: {project_id})",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)


class Ideas(commands.Cog):
    """Idea pool management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @property
    def db(self):
        return self.bot.db
    
    idea_group = app_commands.Group(
        name="idea",
        description="Idea pool commands",
        guild_only=True
    )
    
    @idea_group.command(name="add", description="Add a new idea to the pool")
    async def idea_add(self, interaction: discord.Interaction):
        """Add a new idea via modal"""
        modal = IdeaModal()
        await interaction.response.send_modal(modal)
        
        try:
            await modal.wait()
        except:
            return
        
        if not hasattr(modal, 'result'):
            return
        
        data = modal.result
        
        idea_id = await self.db.create_idea(
            guild_id=interaction.guild.id,
            author_id=interaction.user.id,
            title=data['title'],
            description=data['description'],
            tags=data['tags']
        )
        
        embed = discord.Embed(
            title="💡 Idea Added!",
            description=data['title'],
            color=discord.Color.yellow()
        )
        
        if data['description']:
            embed.add_field(name="Description", value=data['description'], inline=False)
        
        if data['tags']:
            embed.add_field(name="Tags", value=", ".join(f"`{t}`" for t in data['tags']), inline=False)
        
        embed.set_footer(text=f"Idea #{idea_id} • Use /idea pick to turn it into a project!")
        
        await interaction.followup.send(embed=embed)
    
    @idea_group.command(name="quick", description="Quickly add an idea with just a title")
    @app_commands.describe(title="Your idea in a few words")
    async def idea_quick(self, interaction: discord.Interaction, title: str):
        """Quick way to add an idea without modal"""
        
        idea_id = await self.db.create_idea(
            guild_id=interaction.guild.id,
            author_id=interaction.user.id,
            title=title
        )
        
        await interaction.response.send_message(
            f"💡 Idea added: **{title}** (#{idea_id})",
            ephemeral=True
        )
    
    @idea_group.command(name="list", description="Browse all ideas")
    @app_commands.describe(show_used="Include ideas that became projects")
    async def idea_list(
        self,
        interaction: discord.Interaction,
        show_used: Optional[bool] = False
    ):
        """Show all ideas"""
        
        ideas = await self.db.get_guild_ideas(
            interaction.guild.id,
            unused_only=not show_used
        )
        
        if not ideas:
            await interaction.response.send_message(
                "No ideas yet! Use `/idea add` to capture some inspiration. 💡",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="💡 Idea Pool",
            description=f"{len(ideas)} idea(s) waiting to become projects!",
            color=discord.Color.yellow()
        )
        
        for idea in ideas[:15]:
            status = "✅ Used" if idea.get('used_project_id') else "💡 Available"
            value = idea['description'][:100] if idea['description'] else "No description"
            
            if idea['tags']:
                value += f"\n🏷️ {', '.join(idea['tags'][:3])}"
            
            embed.add_field(
                name=f"[{idea['id']}] {idea['title']} • {status}",
                value=value,
                inline=False
            )
        
        if len(ideas) > 15:
            embed.set_footer(text=f"Showing 15 of {len(ideas)} ideas")
        
        await interaction.response.send_message(embed=embed)
    
    @idea_group.command(name="pick", description="Pick an idea to turn into a project")
    async def idea_pick(self, interaction: discord.Interaction):
        """Interactive idea picker"""
        
        ideas = await self.db.get_guild_ideas(interaction.guild.id, unused_only=True)
        
        if not ideas:
            await interaction.response.send_message(
                "No unused ideas! Add some with `/idea add` first. 💡",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🎯 Pick an Idea",
            description="Select an idea from the dropdown to turn it into a project!",
            color=discord.Color.yellow()
        )
        
        view = IdeaSelectView(ideas, self.bot)
        await interaction.response.send_message(embed=embed, view=view)
    
    @idea_group.command(name="random", description="Get a random idea from the pool")
    async def idea_random(self, interaction: discord.Interaction):
        """Pick a random unused idea"""
        import random
        
        ideas = await self.db.get_guild_ideas(interaction.guild.id, unused_only=True)
        
        if not ideas:
            await interaction.response.send_message(
                "No unused ideas to pick from! 💡",
                ephemeral=True
            )
            return
        
        idea = random.choice(ideas)
        
        embed = discord.Embed(
            title="🎲 Random Idea!",
            description=idea['title'],
            color=discord.Color.yellow()
        )
        
        if idea['description']:
            embed.add_field(name="Description", value=idea['description'], inline=False)
        
        if idea['tags']:
            embed.add_field(name="Tags", value=", ".join(f"`{t}`" for t in idea['tags']), inline=False)
        
        embed.set_footer(text=f"Idea #{idea['id']} • Use /idea pick to start this project!")
        
        await interaction.response.send_message(embed=embed)
    
    @idea_group.command(name="delete", description="Delete an idea")
    @app_commands.describe(idea_id="ID of the idea to delete")
    async def idea_delete(self, interaction: discord.Interaction, idea_id: int):
        """Delete an idea from the pool"""
        
        idea = await self.db.get_idea(idea_id)
        
        if not idea or idea['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Idea not found!", ephemeral=True)
            return
        
        # Check if user is the author or has admin permissions
        if idea['author_id'] != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You can only delete your own ideas!",
                ephemeral=True
            )
            return
        
        await self.db.delete_idea(idea_id)
        
        await interaction.response.send_message(
            f"🗑️ Deleted idea: **{idea['title']}**",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Ideas(bot))
