"""
BRRR Bot - Tool Schemas
Centralized location for all LLM tool definitions (function calling).
Edit these to add, modify, or remove tools available to the bot.

Each tool schema follows the OpenAI function calling format:
{
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "What the tool does",
        "parameters": {
            "type": "object",
            "properties": { ... },
            "required": [...]
        }
    }
}
"""

from typing import List, Dict, Any


# =============================================================================
# PROJECT TOOLS
# =============================================================================

GET_PROJECTS_SCHEMA = {
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
}

CREATE_PROJECT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_project",
        "description": "Create a new project for the guild. Use this when a user wants to start a new project.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The title/name of the project"
                },
                "description": {
                    "type": "string",
                    "description": "A description of what the project is about"
                }
            },
            "required": ["title"]
        }
    }
}

GET_PROJECT_INFO_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_project_info",
        "description": "Get detailed information about a specific project, including its tasks.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "The ID of the project to get info for"
                }
            },
            "required": ["project_id"]
        }
    }
}

ARCHIVE_PROJECT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "archive_project",
        "description": "Archive a project (mark it as no longer active).",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "The ID of the project to archive"
                }
            },
            "required": ["project_id"]
        }
    }
}


# =============================================================================
# TASK TOOLS
# =============================================================================

CREATE_TASK_SCHEMA = {
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
}

GET_TASKS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_tasks",
        "description": "Get all tasks for a specific project.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "The ID of the project to get tasks for"
                }
            },
            "required": ["project_id"]
        }
    }
}

TOGGLE_TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "toggle_task",
        "description": "Toggle a task's completion status (mark as done or undone).",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "The ID of the task to toggle"
                }
            },
            "required": ["task_id"]
        }
    }
}

DELETE_TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "delete_task",
        "description": "Delete a task from a project.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "The ID of the task to delete"
                }
            },
            "required": ["task_id"]
        }
    }
}


# =============================================================================
# IDEA TOOLS
# =============================================================================

ADD_IDEA_SCHEMA = {
    "type": "function",
    "function": {
        "name": "add_idea",
        "description": "Add a new project idea to the idea pool.",
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

GET_IDEAS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_ideas",
        "description": "Get project ideas from the idea pool.",
        "parameters": {
            "type": "object",
            "properties": {
                "unused_only": {
                    "type": "boolean",
                    "description": "If true, only return ideas that haven't been used for a project yet"
                }
            },
            "required": []
        }
    }
}

DELETE_IDEA_SCHEMA = {
    "type": "function",
    "function": {
        "name": "delete_idea",
        "description": "Delete an idea from the idea pool.",
        "parameters": {
            "type": "object",
            "properties": {
                "idea_id": {
                    "type": "integer",
                    "description": "The ID of the idea to delete"
                }
            },
            "required": ["idea_id"]
        }
    }
}


# =============================================================================
# TASK ASSIGNMENT TOOLS
# =============================================================================

ASSIGN_TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "assign_task",
        "description": "Assign a task to a specific user.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "The ID of the task to assign"
                },
                "user_id": {
                    "type": "string",
                    "description": "The Discord user ID to assign the task to"
                }
            },
            "required": ["task_id", "user_id"]
        }
    }
}

UNASSIGN_TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "unassign_task",
        "description": "Remove the assignment from a task (unassign from any user).",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "The ID of the task to unassign"
                }
            },
            "required": ["task_id"]
        }
    }
}

GET_USER_TASKS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_user_tasks",
        "description": "Get all tasks assigned to a specific user in the current guild.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The Discord user ID to get tasks for"
                },
                "include_done": {
                    "type": "boolean",
                    "description": "Whether to include completed tasks (default: false)"
                }
            },
            "required": ["user_id"]
        }
    }
}


# =============================================================================
# NOTES TOOLS
# =============================================================================

ADD_PROJECT_NOTE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "add_project_note",
        "description": "Add a note to a project for tracking updates, decisions, or general information.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "The ID of the project to add the note to"
                },
                "content": {
                    "type": "string",
                    "description": "The content of the note"
                }
            },
            "required": ["project_id", "content"]
        }
    }
}

GET_PROJECT_NOTES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_project_notes",
        "description": "Get all notes for a specific project.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "The ID of the project to get notes for"
                }
            },
            "required": ["project_id"]
        }
    }
}

ADD_TASK_NOTE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "add_task_note",
        "description": "Add a note to a task for tracking progress, blockers, or additional context.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "The ID of the task to add the note to"
                },
                "content": {
                    "type": "string",
                    "description": "The content of the note"
                }
            },
            "required": ["task_id", "content"]
        }
    }
}

GET_TASK_NOTES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_task_notes",
        "description": "Get all notes for a specific task.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "The ID of the task to get notes for"
                }
            },
            "required": ["task_id"]
        }
    }
}


# =============================================================================
# GITHUB INTEGRATION TOOLS
# =============================================================================

GITHUB_LIST_FILES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "github_list_files",
        "description": "List files in a GitHub repository at a specific path.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in format 'owner/repo'"
                },
                "path": {
                    "type": "string",
                    "description": "Path within the repository (default: root)"
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name (default: main branch)"
                }
            },
            "required": ["repo"]
        }
    }
}

GITHUB_READ_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "github_read_file",
        "description": "Read the contents of a file from a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in format 'owner/repo'"
                },
                "path": {
                    "type": "string",
                    "description": "Path to the file in the repository"
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name (default: main branch)"
                }
            },
            "required": ["repo", "path"]
        }
    }
}

GITHUB_CREATE_PR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "github_create_pr",
        "description": "Create a pull request in a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in format 'owner/repo'"
                },
                "title": {
                    "type": "string",
                    "description": "Title of the pull request"
                },
                "body": {
                    "type": "string",
                    "description": "Description of the pull request"
                },
                "head": {
                    "type": "string",
                    "description": "The name of the branch where changes are implemented"
                },
                "base": {
                    "type": "string",
                    "description": "The name of the branch to merge into (default: main)"
                }
            },
            "required": ["repo", "title", "head"]
        }
    }
}

GITHUB_LIST_BRANCHES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "github_list_branches",
        "description": "List all branches in a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in format 'owner/repo'"
                }
            },
            "required": ["repo"]
        }
    }
}

GITHUB_UPDATE_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "github_update_file",
        "description": "Update a file in a GitHub repository (creates a commit).",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in format 'owner/repo'"
                },
                "path": {
                    "type": "string",
                    "description": "Path to the file in the repository"
                },
                "content": {
                    "type": "string",
                    "description": "New content for the file"
                },
                "message": {
                    "type": "string",
                    "description": "Commit message"
                },
                "branch": {
                    "type": "string",
                    "description": "Branch to commit to (default: main)"
                }
            },
            "required": ["repo", "path", "content", "message"]
        }
    }
}

GITHUB_LIST_PRS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "github_list_prs",
        "description": "List pull requests in a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in format 'owner/repo'"
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "description": "State of PRs to list (default: open)"
                }
            },
            "required": ["repo"]
        }
    }
}


# =============================================================================
# AGGREGATE SCHEMA LIST
# =============================================================================
# This list is passed to the LLM for function calling.
# Add or remove tools here to control what the bot can do.

TOOLS_SCHEMA: List[Dict[str, Any]] = [
    # Project management
    GET_PROJECTS_SCHEMA,
    CREATE_PROJECT_SCHEMA,
    GET_PROJECT_INFO_SCHEMA,
    ARCHIVE_PROJECT_SCHEMA,
    
    # Task management
    CREATE_TASK_SCHEMA,
    GET_TASKS_SCHEMA,
    TOGGLE_TASK_SCHEMA,
    DELETE_TASK_SCHEMA,
    
    # Task assignment
    ASSIGN_TASK_SCHEMA,
    UNASSIGN_TASK_SCHEMA,
    GET_USER_TASKS_SCHEMA,
    
    # Idea management
    ADD_IDEA_SCHEMA,
    GET_IDEAS_SCHEMA,
    DELETE_IDEA_SCHEMA,
    
    # Notes
    ADD_PROJECT_NOTE_SCHEMA,
    GET_PROJECT_NOTES_SCHEMA,
    ADD_TASK_NOTE_SCHEMA,
    GET_TASK_NOTES_SCHEMA,
    
    # GitHub integration
    GITHUB_LIST_FILES_SCHEMA,
    GITHUB_READ_FILE_SCHEMA,
    GITHUB_CREATE_PR_SCHEMA,
    GITHUB_LIST_BRANCHES_SCHEMA,
    GITHUB_UPDATE_FILE_SCHEMA,
    GITHUB_LIST_PRS_SCHEMA,
]


# =============================================================================
# TOOL REGISTRY
# =============================================================================
# Maps tool names to their schemas for easy lookup.
# Useful for validation and documentation generation.

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    schema["function"]["name"]: schema 
    for schema in TOOLS_SCHEMA
}


def get_tool_schema(tool_name: str) -> Dict[str, Any]:
    """Get the schema for a specific tool by name.
    
    Args:
        tool_name: Name of the tool
        
    Returns:
        Tool schema dict, or None if not found
    """
    return TOOL_REGISTRY.get(tool_name)


def get_tool_names() -> List[str]:
    """Get a list of all available tool names.
    
    Returns:
        List of tool name strings
    """
    return list(TOOL_REGISTRY.keys())
