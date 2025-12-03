from typing import List, Dict, Any, Callable
import json
import logging

logger = logging.getLogger('brrr.tools')

# Tool Definitions (JSON Schema)
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_projects",
            "description": "Get a list of projects for the current guild, optionally filtered by status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "archived", "completed"],
                        "description": "Filter projects by status (e.g., 'active')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task for a specific project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "integer",
                        "description": "The ID of the project to add the task to"
                    },
                    "label": {
                        "type": "string",
                        "description": "The description of the task"
                    }
                },
                "required": ["project_id", "label"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_idea",
            "description": "Add a new project idea.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the idea"
                    },
                    "description": {
                        "type": "string",
                        "description": "A detailed description of the idea"
                    }
                },
                "required": ["title"]
            }
        }
    }
]

class ToolExecutor:
    def __init__(self, db):
        self.db = db

    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Execute a tool by name with arguments"""
        logger.info(f"Executing tool {tool_name} with args {tool_args}")
        
        try:
            if tool_name == "get_projects":
                return await self._get_projects(context.get("guild_id"), tool_args.get("status"))
            elif tool_name == "create_task":
                return await self._create_task(tool_args.get("project_id"), tool_args.get("label"), context.get("user_id"))
            elif tool_name == "add_idea":
                return await self._add_idea(context.get("guild_id"), context.get("user_id"), tool_args.get("title"), tool_args.get("description"))
            else:
                return f"Error: Unknown tool '{tool_name}'"
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return f"Error executing tool: {str(e)}"

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

    async def _create_task(self, project_id: int, label: str, user_id: int) -> str:
        if not project_id or not label:
            return "Error: Missing project_id or label"
        
        # Verify project exists
        project = await self.db.get_project(project_id)
        if not project:
            return f"Error: Project with ID {project_id} not found."
            
        task_id = await self.db.create_task(project_id, label, created_by=user_id)
        return f"Task created successfully! ID: {task_id}"

    async def _add_idea(self, guild_id: int, user_id: int, title: str, description: str = None) -> str:
        if not guild_id:
            return "Error: No guild context"
        
        idea_id = await self.db.create_idea(guild_id, user_id, title, description)
        return f"Idea added! ID: {idea_id}"
