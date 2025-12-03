"""
BRRR Bot - Tool Executor
Handles execution of LLM tool calls.

Tool schemas are defined in src/tool_schemas.py - edit there to modify tool definitions.
This file contains the execution logic for each tool.
"""

from typing import List, Dict, Any, Callable
import json
import logging

# Import schemas from centralized location
from src.tool_schemas import TOOLS_SCHEMA, get_tool_names

logger = logging.getLogger('brrr.tools')


class ToolExecutor:
    def __init__(self, db):
        self.db = db

    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Execute a tool by name with arguments"""
        logger.info(f"Executing tool {tool_name} with args {tool_args}")
        
        try:
            # Project tools
            if tool_name == "get_projects":
                return await self._get_projects(context.get("guild_id"), tool_args.get("status"))
            elif tool_name == "create_project":
                return await self._create_project(context.get("guild_id"), context.get("user_id"), tool_args.get("title"), tool_args.get("description"))
            elif tool_name == "get_project_info":
                return await self._get_project_info(tool_args.get("project_id"))
            elif tool_name == "archive_project":
                return await self._archive_project(tool_args.get("project_id"))
            
            # Task tools
            elif tool_name == "create_task":
                return await self._create_task(tool_args.get("project_id"), tool_args.get("label"), context.get("user_id"))
            elif tool_name == "get_tasks":
                return await self._get_tasks(tool_args.get("project_id"))
            elif tool_name == "toggle_task":
                return await self._toggle_task(tool_args.get("task_id"))
            elif tool_name == "delete_task":
                return await self._delete_task(tool_args.get("task_id"))
            
            # Idea tools
            elif tool_name == "add_idea":
                return await self._add_idea(context.get("guild_id"), context.get("user_id"), tool_args.get("title"), tool_args.get("description"))
            elif tool_name == "get_ideas":
                return await self._get_ideas(context.get("guild_id"), tool_args.get("unused_only", False))
            elif tool_name == "delete_idea":
                return await self._delete_idea(tool_args.get("idea_id"))
            
            else:
                return f"Error: Unknown tool '{tool_name}'"
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return f"Error executing tool: {str(e)}"

    # =========================================================================
    # PROJECT TOOL IMPLEMENTATIONS
    # =========================================================================

    async def _get_projects(self, guild_id: int, status: str = None) -> str:
        if not guild_id:
            return "Error: No guild context"
        projects = await self.db.get_guild_projects(guild_id, status)
        if not projects:
            return "No projects found."
        
        result = []
        for p in projects:
            result.append(f"ID: {p['id']} | Title: {p['title']} | Status: {p['status']}")
        return "\n".join(result)

    async def _create_project(self, guild_id: int, user_id: int, title: str, description: str = None) -> str:
        if not guild_id:
            return "Error: No guild context"
        if not title:
            return "Error: Missing project title"
        
        project_id = await self.db.create_project(
            guild_id=guild_id,
            title=title,
            description=description,
            owners=[user_id] if user_id else []
        )
        return f"Project '{title}' created successfully! ID: {project_id}. You can now add tasks to this project using create_task with project_id={project_id}."

    async def _get_project_info(self, project_id: int) -> str:
        if not project_id:
            return "Error: Missing project_id"
        
        project = await self.db.get_project(project_id)
        if not project:
            return f"Error: Project with ID {project_id} not found."
        
        tasks = await self.db.get_project_tasks(project_id)
        completed = sum(1 for t in tasks if t.get('is_done'))
        
        result = [
            f"**{project['title']}** (ID: {project['id']})",
            f"Status: {project['status']}",
            f"Description: {project['description'] or 'No description'}",
            f"Created: {project['created_at']}",
            f"Tasks: {completed}/{len(tasks)} completed"
        ]
        
        if tasks:
            result.append("\nTask List:")
            for t in tasks:
                status = "✅" if t.get('is_done') else "⬜"
                result.append(f"  {status} [{t['id']}] {t['label']}")
        
        return "\n".join(result)

    async def _archive_project(self, project_id: int) -> str:
        if not project_id:
            return "Error: Missing project_id"
        
        project = await self.db.get_project(project_id)
        if not project:
            return f"Error: Project with ID {project_id} not found."
        
        if project['status'] == 'archived':
            return f"Project '{project['title']}' is already archived."
        
        await self.db.archive_project(project_id)
        return f"Project '{project['title']}' has been archived."

    # =========================================================================
    # TASK TOOL IMPLEMENTATIONS
    # =========================================================================

    async def _create_task(self, project_id: int, label: str, user_id: int) -> str:
        if not project_id or not label:
            return "Error: Missing project_id or label"
        
        project = await self.db.get_project(project_id)
        if not project:
            return f"Error: Project with ID {project_id} not found."
            
        task_id = await self.db.create_task(project_id, label, created_by=user_id)
        return f"Task created successfully! ID: {task_id}"

    async def _get_tasks(self, project_id: int) -> str:
        if not project_id:
            return "Error: Missing project_id"
        
        project = await self.db.get_project(project_id)
        if not project:
            return f"Error: Project with ID {project_id} not found."
        
        tasks = await self.db.get_project_tasks(project_id)
        if not tasks:
            return f"No tasks found for project '{project['title']}'."
        
        result = [f"Tasks for **{project['title']}**:"]
        for t in tasks:
            status = "✅" if t.get('is_done') else "⬜"
            result.append(f"  {status} [{t['id']}] {t['label']}")
        
        completed = sum(1 for t in tasks if t.get('is_done'))
        result.append(f"\nProgress: {completed}/{len(tasks)} completed")
        return "\n".join(result)

    async def _toggle_task(self, task_id: int) -> str:
        if not task_id:
            return "Error: Missing task_id"
        
        task = await self.db.get_task(task_id)
        if not task:
            return f"Error: Task with ID {task_id} not found."
        
        await self.db.toggle_task(task_id)
        new_status = "completed ✅" if not task.get('is_done') else "incomplete ⬜"
        return f"Task '{task['label']}' marked as {new_status}"

    async def _delete_task(self, task_id: int) -> str:
        if not task_id:
            return "Error: Missing task_id"
        
        task = await self.db.get_task(task_id)
        if not task:
            return f"Error: Task with ID {task_id} not found."
        
        await self.db.delete_task(task_id)
        return f"Task '{task['label']}' has been deleted."

    # =========================================================================
    # IDEA TOOL IMPLEMENTATIONS
    # =========================================================================

    async def _add_idea(self, guild_id: int, user_id: int, title: str, description: str = None) -> str:
        if not guild_id:
            return "Error: No guild context"
        
        idea_id = await self.db.create_idea(guild_id, user_id, title, description)
        return f"Idea added! ID: {idea_id}"

    async def _get_ideas(self, guild_id: int, unused_only: bool = False) -> str:
        if not guild_id:
            return "Error: No guild context"
        
        ideas = await self.db.get_guild_ideas(guild_id, unused_only=unused_only)
        if not ideas:
            filter_msg = " (unused)" if unused_only else ""
            return f"No ideas{filter_msg} found in the idea pool."
        
        result = ["**Idea Pool:**"]
        for idea in ideas:
            used = " (used)" if idea.get('used_project_id') else ""
            desc = f" - {idea['description'][:50]}..." if idea.get('description') else ""
            result.append(f"  [{idea['id']}] {idea['title']}{used}{desc}")
        
        return "\n".join(result)

    async def _delete_idea(self, idea_id: int) -> str:
        if not idea_id:
            return "Error: Missing idea_id"
        
        idea = await self.db.get_idea(idea_id)
        if not idea:
            return f"Error: Idea with ID {idea_id} not found."
        
        await self.db.delete_idea(idea_id)
        return f"Idea '{idea['title']}' has been deleted."
