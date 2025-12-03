"""
BRRR Bot - Project Commands Cog
Handles /project start, status, info, archive, checklist
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal
import logging

logger = logging.getLogger('brrr.projects')


class ProjectModal(discord.ui.Modal, title="Start New Project"):
    """Modal for creating a new project"""
    
    project_title = discord.ui.TextInput(
        label="Project Title",
        placeholder="What are you building?",
        max_length=100,
        required=True
    )
    
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        placeholder="Brief description of the project...",
        max_length=500,
        required=False
    )
    
    tags = discord.ui.TextInput(
        label="Tags (comma separated)",
        placeholder="python, discord, bot",
        max_length=100,
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Parse tags
        tag_list = []
        if self.tags.value:
            tag_list = [t.strip() for t in self.tags.value.split(',') if t.strip()]
        
        # Store data for the cog to use
        self.result = {
            'title': self.project_title.value,
            'description': self.description.value or None,
            'tags': tag_list
        }
        await interaction.response.defer()


class TaskModal(discord.ui.Modal, title="Add Task"):
    """Modal for adding a task"""
    
    task_label = discord.ui.TextInput(
        label="Task Description",
        placeholder="What needs to be done?",
        max_length=200,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        self.result = self.task_label.value
        await interaction.response.defer()


class ProjectSelectMenu(discord.ui.Select):
    """Dropdown to select a project"""
    
    def __init__(self, projects: list, callback_func):
        options = []
        for p in projects[:25]:  # Discord limit
            status_emoji = "🟢" if p['status'] == 'active' else "📦"
            options.append(
                discord.SelectOption(
                    label=p['title'][:100],
                    value=str(p['id']),
                    description=f"{status_emoji} {p['status'].capitalize()}",
                    emoji=status_emoji
                )
            )
        
        super().__init__(
            placeholder="Select a project...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.callback_func = callback_func
    
    async def callback(self, interaction: discord.Interaction):
        await self.callback_func(interaction, int(self.values[0]))


class TaskToggleView(discord.ui.View):
    """View with task toggle buttons"""
    
    def __init__(self, tasks: list, project_id: int, db):
        super().__init__(timeout=300)
        self.tasks = tasks
        self.project_id = project_id
        self.db = db
        self._build_buttons()
    
    def _build_buttons(self):
        self.clear_items()
        for i, task in enumerate(self.tasks[:20]):  # Limit to 20 tasks
            emoji = "✅" if task['is_done'] else "⬜"
            label = task['label'][:80]
            button = discord.ui.Button(
                label=f"{emoji} {label}",
                style=discord.ButtonStyle.secondary if task['is_done'] else discord.ButtonStyle.primary,
                custom_id=f"task_{task['id']}",
                row=i // 5
            )
            button.callback = self._make_callback(task['id'], i)
            self.add_item(button)
    
    def _make_callback(self, task_id: int, index: int):
        async def callback(interaction: discord.Interaction):
            await self.db.toggle_task(task_id)
            self.tasks[index]['is_done'] = not self.tasks[index]['is_done']
            self._build_buttons()
            await interaction.response.edit_message(view=self)
        return callback


class Projects(commands.Cog):
    """Project management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @property
    def db(self):
        return self.bot.db
    
    project_group = app_commands.Group(
        name="project",
        description="Project management commands",
        guild_only=True
    )
    
    @project_group.command(name="start", description="Start a new project")
    async def project_start(self, interaction: discord.Interaction):
        """Start a new project with a modal form"""
        modal = ProjectModal()
        await interaction.response.send_modal(modal)
        
        # Wait for modal submission
        try:
            await modal.wait()
        except:
            return
        
        if not hasattr(modal, 'result'):
            return
        
        data = modal.result
        
        # Create the project
        project_id = await self.db.create_project(
            guild_id=interaction.guild.id,
            title=data['title'],
            description=data['description'],
            owners=[interaction.user.id],
            tags=data['tags']
        )
        
        # Create thread for the project
        thread = None
        if interaction.channel.type == discord.ChannelType.text:
            try:
                thread = await interaction.channel.create_thread(
                    name=f"🚀 {data['title']}",
                    type=discord.ChannelType.public_thread
                )
                await self.db.update_project(project_id, thread_id=thread.id)
            except discord.Forbidden:
                logger.warning(f"No permission to create thread for project {project_id}")
            except discord.HTTPException as e:
                logger.error(f"Failed to create thread for project {project_id}: {e}")
        
        # Build the project embed
        embed = discord.Embed(
            title=f"🚀 Project Started: {data['title']}",
            description=data['description'] or "No description provided",
            color=discord.Color.green()
        )
        embed.add_field(name="ID", value=str(project_id), inline=True)
        embed.add_field(name="Owner", value=interaction.user.mention, inline=True)
        embed.add_field(name="Status", value="🟢 Active", inline=True)
        
        if data['tags']:
            embed.add_field(name="Tags", value=", ".join(f"`{t}`" for t in data['tags']), inline=False)
        
        if thread:
            embed.add_field(name="Thread", value=thread.mention, inline=False)
        
        embed.set_footer(text="Use /project checklist to add tasks!")
        
        # Send the announcement
        await interaction.followup.send(embed=embed)
        
        # If thread was created, send a welcome message there too
        if thread:
            thread_embed = discord.Embed(
                title=f"🏎️ {data['title']} - Let's go BRRRRR!",
                description="This is your project thread. Use it to discuss, share updates, and track progress!",
                color=discord.Color.blue()
            )
            thread_embed.add_field(
                name="Quick Commands",
                value="""
• `/project checklist add` - Add tasks
• `/project checklist list` - View tasks
• `/project info` - Project details
• `/project archive` - When you're done!
                """,
                inline=False
            )
            await thread.send(embed=thread_embed)
        
        # Auto-generate tasks if LLM is available
        if self.bot.llm and data['description']:
            try:
                tasks_text = await self.bot.llm.generate_project_plan(
                    data['title'],
                    data['description']
                )
                tasks = [t.strip() for t in tasks_text.strip().split('\n') if t.strip()]
                
                for task in tasks[:10]:  # Limit to 10 auto-tasks
                    await self.db.create_task(project_id, task, interaction.user.id)
                
                if thread and tasks:
                    tasks_embed = discord.Embed(
                        title="📋 Auto-generated Checklist",
                        description="\n".join(f"⬜ {t}" for t in tasks[:10]),
                        color=discord.Color.blue()
                    )
                    tasks_embed.set_footer(text="Use /project checklist to manage these tasks")
                    await thread.send(embed=tasks_embed)
            except Exception as e:
                logger.error(f"Failed to auto-generate tasks: {e}")
    
    @project_group.command(name="status", description="List all projects")
    @app_commands.describe(filter="Filter by project status")
    async def project_status(
        self,
        interaction: discord.Interaction,
        filter: Optional[Literal["active", "archived", "all"]] = "active"
    ):
        """Show all projects in the guild"""
        if filter == "all":
            projects = await self.db.get_guild_projects(interaction.guild.id)
        else:
            projects = await self.db.get_guild_projects(interaction.guild.id, status=filter)
        
        if not projects:
            await interaction.response.send_message(
                f"No {filter} projects found! Use `/project start` to create one. 🚀",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"📊 Projects ({filter.capitalize()})",
            color=discord.Color.blue()
        )
        
        for p in projects[:10]:  # Show first 10
            status_emoji = "🟢" if p['status'] == 'active' else "📦"
            tasks = await self.db.get_project_tasks(p['id'])
            done = sum(1 for t in tasks if t['is_done'])
            
            value = p['description'][:100] if p['description'] else "No description"
            if tasks:
                value += f"\n📋 Tasks: {done}/{len(tasks)} complete"
            if p['thread_id']:
                value += f"\n💬 <#{p['thread_id']}>"
            
            embed.add_field(
                name=f"{status_emoji} [{p['id']}] {p['title']}",
                value=value,
                inline=False
            )
        
        if len(projects) > 10:
            embed.set_footer(text=f"Showing 10 of {len(projects)} projects")
        
        await interaction.response.send_message(embed=embed)
    
    @project_group.command(name="info", description="Get detailed project info")
    @app_commands.describe(project_id="Project ID to view")
    async def project_info(self, interaction: discord.Interaction, project_id: int):
        """Show detailed project information"""
        project = await self.db.get_project(project_id)
        
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Project not found!", ephemeral=True)
            return
        
        status_emoji = "🟢" if project['status'] == 'active' else "📦"
        
        embed = discord.Embed(
            title=f"{status_emoji} {project['title']}",
            description=project['description'] or "No description",
            color=discord.Color.green() if project['status'] == 'active' else discord.Color.greyple()
        )
        
        embed.add_field(name="ID", value=str(project['id']), inline=True)
        embed.add_field(name="Status", value=project['status'].capitalize(), inline=True)
        embed.add_field(name="Created", value=project['created_at'][:10], inline=True)
        
        if project['owners']:
            owners = [f"<@{o}>" for o in project['owners']]
            embed.add_field(name="Owners", value=", ".join(owners), inline=False)
        
        if project['tags']:
            embed.add_field(name="Tags", value=", ".join(f"`{t}`" for t in project['tags']), inline=False)
        
        if project['thread_id']:
            embed.add_field(name="Thread", value=f"<#{project['thread_id']}>", inline=False)
        
        # Show tasks
        tasks = await self.db.get_project_tasks(project['id'])
        if tasks:
            done = sum(1 for t in tasks if t['is_done'])
            task_list = []
            for t in tasks[:10]:
                emoji = "✅" if t['is_done'] else "⬜"
                task_list.append(f"{emoji} {t['label']}")
            
            embed.add_field(
                name=f"📋 Tasks ({done}/{len(tasks)} done)",
                value="\n".join(task_list) if task_list else "No tasks",
                inline=False
            )
            if len(tasks) > 10:
                embed.set_footer(text=f"Showing 10 of {len(tasks)} tasks")
        
        await interaction.response.send_message(embed=embed)
    
    @project_group.command(name="archive", description="Archive a project")
    @app_commands.describe(project_id="Project ID to archive")
    async def project_archive(self, interaction: discord.Interaction, project_id: int):
        """Archive a completed project"""
        project = await self.db.get_project(project_id)
        
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Project not found!", ephemeral=True)
            return
        
        if project['status'] == 'archived':
            await interaction.response.send_message("Project is already archived!", ephemeral=True)
            return
        
        await self.db.archive_project(project_id)
        
        embed = discord.Embed(
            title=f"📦 Project Archived: {project['title']}",
            description="Great work! This project has been archived.",
            color=discord.Color.greyple()
        )
        
        tasks = await self.db.get_project_tasks(project_id)
        done = sum(1 for t in tasks if t['is_done'])
        embed.add_field(name="Tasks Completed", value=f"{done}/{len(tasks)}", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    # Checklist subcommand group
    checklist_group = app_commands.Group(
        name="checklist",
        description="Manage project tasks",
        parent=project_group
    )
    
    @checklist_group.command(name="add", description="Add a task to a project")
    @app_commands.describe(project_id="Project to add task to", task="Task description")
    async def checklist_add(
        self,
        interaction: discord.Interaction,
        project_id: int,
        task: str
    ):
        """Add a task to a project's checklist"""
        project = await self.db.get_project(project_id)
        
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Project not found!", ephemeral=True)
            return
        
        task_id = await self.db.create_task(project_id, task, interaction.user.id)
        
        await interaction.response.send_message(
            f"✅ Added task to **{project['title']}**: {task}",
            ephemeral=True
        )
    
    @checklist_group.command(name="list", description="View and toggle project tasks")
    @app_commands.describe(project_id="Project to view tasks for")
    async def checklist_list(self, interaction: discord.Interaction, project_id: int):
        """Show tasks with toggle buttons"""
        project = await self.db.get_project(project_id)
        
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Project not found!", ephemeral=True)
            return
        
        tasks = await self.db.get_project_tasks(project_id)
        
        if not tasks:
            await interaction.response.send_message(
                f"No tasks for **{project['title']}**. Use `/project checklist add` to add some!",
                ephemeral=True
            )
            return
        
        done = sum(1 for t in tasks if t['is_done'])
        
        embed = discord.Embed(
            title=f"📋 {project['title']} - Tasks",
            description=f"Progress: {done}/{len(tasks)} complete",
            color=discord.Color.green() if done == len(tasks) else discord.Color.blue()
        )
        
        task_list = []
        for t in tasks:
            emoji = "✅" if t['is_done'] else "⬜"
            task_list.append(f"{emoji} {t['label']}")
        
        embed.add_field(name="Tasks", value="\n".join(task_list[:20]), inline=False)
        
        view = TaskToggleView(tasks, project_id, self.db)
        await interaction.response.send_message(embed=embed, view=view)
    
    @checklist_group.command(name="toggle", description="Toggle a task's completion status")
    @app_commands.describe(task_id="Task ID to toggle")
    async def checklist_toggle(self, interaction: discord.Interaction, task_id: int):
        """Toggle a specific task"""
        task = await self.db.get_task(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        # Verify task belongs to a project in this guild
        project = await self.db.get_project(task['project_id'])
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        await self.db.toggle_task(task_id)
        status = "completed" if not task['is_done'] else "incomplete"
        await interaction.response.send_message(
            f"✅ Marked task as {status}: **{task['label']}**",
            ephemeral=True
        )
    
    @checklist_group.command(name="remove", description="Remove a task from a project")
    @app_commands.describe(task_id="Task ID to remove")
    async def checklist_remove(self, interaction: discord.Interaction, task_id: int):
        """Remove a task from a project"""
        task = await self.db.get_task(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        # Verify task belongs to a project in this guild
        project = await self.db.get_project(task['project_id'])
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        await self.db.delete_task(task_id)
        await interaction.response.send_message(
            f"🗑️ Removed task: **{task['label']}**",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Projects(bot))
