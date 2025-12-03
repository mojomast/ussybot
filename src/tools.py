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
            
            # Task assignment tools
            elif tool_name == "assign_task":
                return await self._assign_task(tool_args.get("task_id"), tool_args.get("user_id"))
            elif tool_name == "unassign_task":
                return await self._unassign_task(tool_args.get("task_id"))
            elif tool_name == "get_user_tasks":
                return await self._get_user_tasks(context.get("guild_id"), tool_args.get("user_id"), tool_args.get("include_done", False))
            
            # Idea tools
            elif tool_name == "add_idea":
                return await self._add_idea(context.get("guild_id"), context.get("user_id"), tool_args.get("title"), tool_args.get("description"))
            elif tool_name == "get_ideas":
                return await self._get_ideas(context.get("guild_id"), tool_args.get("unused_only", False))
            elif tool_name == "delete_idea":
                return await self._delete_idea(tool_args.get("idea_id"))
            
            # Notes tools
            elif tool_name == "add_project_note":
                return await self._add_project_note(tool_args.get("project_id"), context.get("user_id"), tool_args.get("content"))
            elif tool_name == "get_project_notes":
                return await self._get_project_notes(tool_args.get("project_id"))
            elif tool_name == "add_task_note":
                return await self._add_task_note(tool_args.get("task_id"), context.get("user_id"), tool_args.get("content"))
            elif tool_name == "get_task_notes":
                return await self._get_task_notes(tool_args.get("task_id"))
            
            # GitHub tools
            elif tool_name == "github_list_files":
                return await self._github_list_files(tool_args.get("repo"), tool_args.get("path", ""), tool_args.get("branch"))
            elif tool_name == "github_read_file":
                return await self._github_read_file(tool_args.get("repo"), tool_args.get("path"), tool_args.get("branch"))
            elif tool_name == "github_create_pr":
                return await self._github_create_pr(tool_args.get("repo"), tool_args.get("title"), tool_args.get("body"), tool_args.get("head"), tool_args.get("base", "main"))
            elif tool_name == "github_list_branches":
                return await self._github_list_branches(tool_args.get("repo"))
            elif tool_name == "github_update_file":
                return await self._github_update_file(tool_args.get("repo"), tool_args.get("path"), tool_args.get("content"), tool_args.get("message"), tool_args.get("branch"))
            elif tool_name == "github_list_prs":
                return await self._github_list_prs(tool_args.get("repo"), tool_args.get("state", "open"))
            
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

    # =========================================================================
    # TASK ASSIGNMENT TOOL IMPLEMENTATIONS
    # =========================================================================

    async def _assign_task(self, task_id: int, user_id: str) -> str:
        if not task_id or not user_id:
            return "Error: Missing task_id or user_id"
        
        # Convert user_id to int
        try:
            user_id_int = int(user_id)
        except (ValueError, TypeError):
            return f"Error: Invalid user_id format: {user_id}"
        
        task = await self.db.get_task(task_id)
        if not task:
            return f"Error: Task with ID {task_id} not found."
        
        await self.db.assign_task(task_id, user_id_int)
        return f"Task '{task['label']}' has been assigned to user <@{user_id_int}>."

    async def _unassign_task(self, task_id: int) -> str:
        if not task_id:
            return "Error: Missing task_id"
        
        task = await self.db.get_task(task_id)
        if not task:
            return f"Error: Task with ID {task_id} not found."
        
        if not task.get('assigned_to'):
            return f"Task '{task['label']}' is not currently assigned to anyone."
        
        await self.db.unassign_task(task_id)
        return f"Task '{task['label']}' has been unassigned."

    async def _get_user_tasks(self, guild_id: int, user_id: str, include_done: bool = False) -> str:
        if not guild_id or not user_id:
            return "Error: Missing guild_id or user_id"
        
        # Convert user_id to int
        try:
            user_id_int = int(user_id)
        except (ValueError, TypeError):
            return f"Error: Invalid user_id format: {user_id}"
        
        tasks = await self.db.get_user_tasks(guild_id, user_id_int, include_done)
        
        if not tasks:
            status_msg = " (including completed)" if include_done else ""
            return f"No tasks{status_msg} found assigned to <@{user_id_int}>."
        
        result = [f"**Tasks assigned to <@{user_id_int}>:**"]
        for t in tasks:
            status = "✅" if t.get('is_done') else "⬜"
            result.append(f"  {status} [{t['id']}] {t['label']} (Project: {t['project_id']})")
        
        completed = sum(1 for t in tasks if t.get('is_done'))
        if include_done:
            result.append(f"\nProgress: {completed}/{len(tasks)} completed")
        else:
            result.append(f"\n{len(tasks)} open task(s)")
        
        return "\n".join(result)

    # =========================================================================
    # NOTES TOOL IMPLEMENTATIONS
    # =========================================================================

    async def _add_project_note(self, project_id: int, author_id: int, content: str) -> str:
        if not project_id or not content:
            return "Error: Missing project_id or content"
        
        if not author_id:
            return "Error: No user context for note author"
        
        project = await self.db.get_project(project_id)
        if not project:
            return f"Error: Project with ID {project_id} not found."
        
        note_id = await self.db.add_project_note(project_id, author_id, content)
        return f"Note added to project '{project['title']}' (Note ID: {note_id})"

    async def _get_project_notes(self, project_id: int) -> str:
        if not project_id:
            return "Error: Missing project_id"
        
        project = await self.db.get_project(project_id)
        if not project:
            return f"Error: Project with ID {project_id} not found."
        
        notes = await self.db.get_project_notes(project_id)
        
        if not notes:
            return f"No notes found for project '{project['title']}'."
        
        result = [f"**Notes for {project['title']}:**"]
        for note in notes:
            result.append(f"\n[{note['id']}] By <@{note['author_id']}> at {note['created_at']}")
            result.append(f"  {note['content']}")
        
        return "\n".join(result)

    async def _add_task_note(self, task_id: int, author_id: int, content: str) -> str:
        if not task_id or not content:
            return "Error: Missing task_id or content"
        
        if not author_id:
            return "Error: No user context for note author"
        
        task = await self.db.get_task(task_id)
        if not task:
            return f"Error: Task with ID {task_id} not found."
        
        note_id = await self.db.add_task_note(task_id, author_id, content)
        return f"Note added to task '{task['label']}' (Note ID: {note_id})"

    async def _get_task_notes(self, task_id: int) -> str:
        if not task_id:
            return "Error: Missing task_id"
        
        task = await self.db.get_task(task_id)
        if not task:
            return f"Error: Task with ID {task_id} not found."
        
        notes = await self.db.get_task_notes(task_id)
        
        if not notes:
            return f"No notes found for task '{task['label']}'."
        
        result = [f"**Notes for task '{task['label']}':**"]
        for note in notes:
            result.append(f"\n[{note['id']}] By <@{note['author_id']}> at {note['created_at']}")
            result.append(f"  {note['content']}")
        
        return "\n".join(result)

    # =========================================================================
    # GITHUB TOOL IMPLEMENTATIONS
    # =========================================================================

    async def _github_list_files(self, repo: str, path: str = "", branch: str = None) -> str:
        """List files in a GitHub repository"""
        if not repo:
            return "Error: Missing repo parameter"
        
        try:
            from github import Github
            import os
            
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                return "Error: GITHUB_TOKEN environment variable not set. Please configure GitHub access."
            
            g = Github(token)
            repository = g.get_repo(repo)
            
            # Get contents at path
            contents = repository.get_contents(path, ref=branch)
            
            if not isinstance(contents, list):
                contents = [contents]
            
            result = [f"**Files in {repo}/{path or 'root'}:**"]
            for content in contents:
                icon = "📁" if content.type == "dir" else "📄"
                result.append(f"{icon} {content.path}")
            
            return "\n".join(result)
        except ImportError:
            return "Error: PyGithub library not installed. Run: pip install PyGithub"
        except Exception as e:
            logger.error(f"GitHub list files error: {e}", exc_info=True)
            return f"Error accessing GitHub: {str(e)}"

    async def _github_read_file(self, repo: str, path: str, branch: str = None) -> str:
        """Read a file from GitHub"""
        if not repo or not path:
            return "Error: Missing repo or path parameter"
        
        try:
            from github import Github
            import os
            
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                return "Error: GITHUB_TOKEN environment variable not set. Please configure GitHub access."
            
            g = Github(token)
            repository = g.get_repo(repo)
            
            # Get file content
            content = repository.get_contents(path, ref=branch)
            
            if content.type != "file":
                return f"Error: {path} is not a file"
            
            # Decode content
            file_content = content.decoded_content.decode('utf-8')
            
            # Truncate if too long
            max_length = 4000
            if len(file_content) > max_length:
                file_content = file_content[:max_length] + f"\n\n... (truncated, {len(file_content)} total chars)"
            
            result = [f"**File: {repo}/{path}**"]
            result.append(f"```\n{file_content}\n```")
            
            return "\n".join(result)
        except ImportError:
            return "Error: PyGithub library not installed. Run: pip install PyGithub"
        except Exception as e:
            logger.error(f"GitHub read file error: {e}", exc_info=True)
            return f"Error reading file from GitHub: {str(e)}"

    async def _github_create_pr(self, repo: str, title: str, body: str, head: str, base: str = "main") -> str:
        """Create a pull request on GitHub"""
        if not repo or not title or not head:
            return "Error: Missing required parameters (repo, title, head)"
        
        try:
            from github import Github
            import os
            
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                return "Error: GITHUB_TOKEN environment variable not set. Please configure GitHub access."
            
            g = Github(token)
            repository = g.get_repo(repo)
            
            # Create PR
            pr = repository.create_pull(
                title=title,
                body=body or "",
                head=head,
                base=base
            )
            
            return f"Pull request created successfully!\nTitle: {pr.title}\nNumber: #{pr.number}\nURL: {pr.html_url}"
        except ImportError:
            return "Error: PyGithub library not installed. Run: pip install PyGithub"
        except Exception as e:
            logger.error(f"GitHub create PR error: {e}", exc_info=True)
            return f"Error creating pull request: {str(e)}"

    async def _github_list_branches(self, repo: str) -> str:
        """List branches in a GitHub repository"""
        if not repo:
            return "Error: Missing repo parameter"
        
        try:
            from github import Github
            import os
            
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                return "Error: GITHUB_TOKEN environment variable not set. Please configure GitHub access."
            
            g = Github(token)
            repository = g.get_repo(repo)
            
            branches = repository.get_branches()
            
            result = [f"**Branches in {repo}:**"]
            for branch in branches:
                result.append(f"  • {branch.name}")
            
            return "\n".join(result)
        except ImportError:
            return "Error: PyGithub library not installed. Run: pip install PyGithub"
        except Exception as e:
            logger.error(f"GitHub list branches error: {e}", exc_info=True)
            return f"Error listing branches: {str(e)}"

    async def _github_update_file(self, repo: str, path: str, content: str, message: str, branch: str = None) -> str:
        """Update a file in a GitHub repository"""
        if not repo or not path or not content or not message:
            return "Error: Missing required parameters (repo, path, content, message)"
        
        try:
            from github import Github
            import os
            
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                return "Error: GITHUB_TOKEN environment variable not set. Please configure GitHub access."
            
            g = Github(token)
            repository = g.get_repo(repo)
            
            # Get current file to get its SHA
            try:
                file_contents = repository.get_contents(path, ref=branch)
                sha = file_contents.sha
                
                # Update the file
                result = repository.update_file(
                    path=path,
                    message=message,
                    content=content,
                    sha=sha,
                    branch=branch
                )
            except:
                # File doesn't exist, create it
                result = repository.create_file(
                    path=path,
                    message=message,
                    content=content,
                    branch=branch
                )
            
            commit_sha = result['commit'].sha
            return f"File updated successfully!\nPath: {path}\nCommit: {commit_sha[:7]}\nMessage: {message}"
        except ImportError:
            return "Error: PyGithub library not installed. Run: pip install PyGithub"
        except Exception as e:
            logger.error(f"GitHub update file error: {e}", exc_info=True)
            return f"Error updating file: {str(e)}"

    async def _github_list_prs(self, repo: str, state: str = "open") -> str:
        """List pull requests in a GitHub repository"""
        if not repo:
            return "Error: Missing repo parameter"
        
        try:
            from github import Github
            import os
            
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                return "Error: GITHUB_TOKEN environment variable not set. Please configure GitHub access."
            
            g = Github(token)
            repository = g.get_repo(repo)
            
            prs = repository.get_pulls(state=state)
            
            result = [f"**Pull Requests in {repo} ({state}):**"]
            
            pr_list = list(prs)[:20]  # Limit to 20
            if not pr_list:
                return f"No {state} pull requests found in {repo}."
            
            for pr in pr_list:
                result.append(f"\n#{pr.number}: {pr.title}")
                result.append(f"  By: {pr.user.login} | {pr.head.ref} → {pr.base.ref}")
                result.append(f"  URL: {pr.html_url}")
            
            return "\n".join(result)
        except ImportError:
            return "Error: PyGithub library not installed. Run: pip install PyGithub"
        except Exception as e:
            logger.error(f"GitHub list PRs error: {e}", exc_info=True)
            return f"Error listing pull requests: {str(e)}"
