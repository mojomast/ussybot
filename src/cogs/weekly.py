"""
BRRR Bot - Weekly Commands Cog
Handles /week start and /week retro
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import logging

logger = logging.getLogger('brrr.weekly')


class StartProjectButton(discord.ui.Button):
    """Button to quickly start a new project from week overview"""
    
    def __init__(self, bot):
        super().__init__(
            label="Start New Project",
            style=discord.ButtonStyle.success,
            emoji="🚀"
        )
        self.bot = bot
    
    async def callback(self, interaction: discord.Interaction):
        # Import here to avoid circular imports
        from src.cogs.projects import ProjectModal
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
        project_id = await self.bot.db.create_project(
            guild_id=interaction.guild.id,
            title=data['title'],
            description=data['description'],
            owners=[interaction.user.id],
            tags=data['tags']
        )
        
        # Create thread for the project if in a text channel
        thread = None
        if interaction.channel.type == discord.ChannelType.text:
            try:
                thread = await interaction.channel.create_thread(
                    name=f"🚀 {data['title']}",
                    type=discord.ChannelType.public_thread
                )
                await self.bot.db.update_project(project_id, thread_id=thread.id)
            except discord.Forbidden:
                pass  # No permission to create threads
        
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
        
        await interaction.followup.send(embed=embed)


class WeekView(discord.ui.View):
    """View for weekly overview with action buttons"""
    
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.add_item(StartProjectButton(bot))


class Weekly(commands.Cog):
    """Weekly rhythm commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @property
    def db(self):
        return self.bot.db
    
    week_group = app_commands.Group(
        name="week",
        description="Weekly rhythm commands",
        guild_only=True
    )
    
    @week_group.command(name="start", description="Start a new week with an overview")
    async def week_start(self, interaction: discord.Interaction):
        """Post weekly overview and start button"""
        
        # Get active projects
        active_projects = await self.db.get_guild_projects(
            interaction.guild.id,
            status='active'
        )
        
        # Get unused ideas
        ideas = await self.db.get_guild_ideas(interaction.guild.id, unused_only=True)
        
        # Build the week overview embed
        today = datetime.utcnow()
        week_num = today.isocalendar()[1]
        
        embed = discord.Embed(
            title=f"🗓️ Week {week_num} - Let's Go BRRRRRR!",
            description="New week, new opportunities to ship! Here's your overview.",
            color=discord.Color.gold()
        )
        
        # Active projects section
        if active_projects:
            project_lines = []
            for p in active_projects[:5]:
                tasks = await self.db.get_project_tasks(p['id'])
                done = sum(1 for t in tasks if t['is_done'])
                total = len(tasks)
                progress = f"[{done}/{total}]" if tasks else ""
                project_lines.append(f"• **{p['title']}** {progress}")
            
            embed.add_field(
                name=f"🚀 Active Projects ({len(active_projects)})",
                value="\n".join(project_lines) if project_lines else "No active projects",
                inline=False
            )
            
            if len(active_projects) > 5:
                embed.add_field(
                    name="",
                    value=f"*...and {len(active_projects) - 5} more*",
                    inline=False
                )
        else:
            embed.add_field(
                name="🚀 Active Projects",
                value="No active projects! Time to start something new!",
                inline=False
            )
        
        # Ideas backlog
        if ideas:
            idea_lines = [f"• {i['title']}" for i in ideas[:5]]
            embed.add_field(
                name=f"💡 Idea Backlog ({len(ideas)})",
                value="\n".join(idea_lines),
                inline=False
            )
        else:
            embed.add_field(
                name="💡 Idea Backlog",
                value="No ideas yet! Use `/idea add` to capture inspiration.",
                inline=False
            )
        
        # Weekly tips
        embed.add_field(
            name="📋 This Week's Focus",
            value="""
• **Pick ONE project** to focus on shipping
• **Break it down** into small, achievable tasks
• **Ship something** - done is better than perfect!
            """,
            inline=False
        )
        
        embed.set_footer(text="Click the button below to start a new project!")
        
        # Send with the start project button
        view = WeekView(self.bot)
        await interaction.response.send_message(embed=embed, view=view)
    
    @week_group.command(name="retro", description="Run retrospective for active projects")
    async def week_retro(self, interaction: discord.Interaction):
        """Post retro prompts to each active project"""
        
        active_projects = await self.db.get_guild_projects(
            interaction.guild.id,
            status='active'
        )
        
        if not active_projects:
            await interaction.response.send_message(
                "No active projects to retro! 🎉",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        today = datetime.utcnow()
        week_num = today.isocalendar()[1]
        
        # Main retro announcement
        main_embed = discord.Embed(
            title=f"🔄 Week {week_num} Retrospective",
            description=f"Time to reflect on {len(active_projects)} active project(s)!",
            color=discord.Color.purple()
        )
        
        retro_results = []
        
        for project in active_projects:
            tasks = await self.db.get_project_tasks(project['id'])
            done = sum(1 for t in tasks if t['is_done'])
            total = len(tasks)
            
            progress_pct = (done / total * 100) if total > 0 else 0
            
            # Generate AI summary if available
            ai_summary = None
            if self.bot.llm and tasks:
                try:
                    ai_summary = await self.bot.llm.generate_retro_summary(
                        project['title'],
                        tasks
                    )
                except Exception as e:
                    logger.error(f"Failed to generate retro summary: {e}")
            
            # Build project retro embed
            project_embed = discord.Embed(
                title=f"📊 {project['title']}",
                color=discord.Color.green() if progress_pct >= 80 else 
                       discord.Color.gold() if progress_pct >= 50 else
                       discord.Color.orange()
            )
            
            # Progress bar
            filled = int(progress_pct / 10)
            bar = "🟩" * filled + "⬜" * (10 - filled)
            project_embed.add_field(
                name="Progress",
                value=f"{bar} {done}/{total} tasks ({progress_pct:.0f}%)",
                inline=False
            )
            
            # Completed tasks
            completed_tasks = [t for t in tasks if t['is_done']]
            if completed_tasks:
                project_embed.add_field(
                    name="✅ Completed",
                    value="\n".join(f"• {t['label']}" for t in completed_tasks[:5]) +
                          (f"\n*...and {len(completed_tasks) - 5} more*" if len(completed_tasks) > 5 else ""),
                    inline=False
                )
            
            # Remaining tasks
            remaining_tasks = [t for t in tasks if not t['is_done']]
            if remaining_tasks:
                project_embed.add_field(
                    name="⬜ Remaining",
                    value="\n".join(f"• {t['label']}" for t in remaining_tasks[:5]) +
                          (f"\n*...and {len(remaining_tasks) - 5} more*" if len(remaining_tasks) > 5 else ""),
                    inline=False
                )
            
            # AI Summary
            if ai_summary:
                project_embed.add_field(
                    name="🤖 BRRR Bot Says",
                    value=ai_summary,
                    inline=False
                )
            
            # Retro prompts
            project_embed.add_field(
                name="🤔 Reflect",
                value="""
**What went well?**
**What could be better?**
**What's next?**
                """,
                inline=False
            )
            
            retro_results.append(project_embed)
            
            # Add to main summary
            status_emoji = "🎉" if progress_pct >= 80 else "💪" if progress_pct >= 50 else "🏃"
            main_embed.add_field(
                name=f"{status_emoji} {project['title']}",
                value=f"{done}/{total} tasks • {progress_pct:.0f}% complete",
                inline=True
            )
        
        main_embed.set_footer(text="Individual project retros posted below!")
        
        # Send main embed
        await interaction.followup.send(embed=main_embed)
        
        # Send individual project retros
        for embed in retro_results:
            await interaction.channel.send(embed=embed)
    
    @week_group.command(name="summary", description="Quick summary of the week's progress")
    async def week_summary(self, interaction: discord.Interaction):
        """Show a quick summary of all project progress"""
        
        active_projects = await self.db.get_guild_projects(
            interaction.guild.id,
            status='active'
        )
        
        archived_this_week = await self.db.get_guild_projects(
            interaction.guild.id,
            status='archived'
        )
        # Filter to this week (simplified - just last 7 days)
        
        total_tasks = 0
        completed_tasks = 0
        
        for project in active_projects:
            tasks = await self.db.get_project_tasks(project['id'])
            total_tasks += len(tasks)
            completed_tasks += sum(1 for t in tasks if t['is_done'])
        
        embed = discord.Embed(
            title="📈 Weekly Progress Summary",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Active Projects",
            value=str(len(active_projects)),
            inline=True
        )
        
        embed.add_field(
            name="Tasks Done",
            value=f"{completed_tasks}/{total_tasks}",
            inline=True
        )
        
        if total_tasks > 0:
            progress = completed_tasks / total_tasks * 100
            embed.add_field(
                name="Completion Rate",
                value=f"{progress:.1f}%",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Weekly(bot))
