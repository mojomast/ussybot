"""
BRRR Bot - Database Models
SQLite database with aiosqlite for async operations
"""

import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


class Database:
    def __init__(self, db_path: str = "data/brrr.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
    async def init(self):
        """Initialize database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Projects table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    owners TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'active',
                    thread_id INTEGER,
                    created_at TEXT NOT NULL,
                    archived_at TEXT,
                    tags TEXT DEFAULT '[]',
                    template TEXT
                )
            """)
            
            # Tasks table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    is_done INTEGER DEFAULT 0,
                    created_by INTEGER,
                    assigned_to INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)
            
            # Ideas table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    tags TEXT DEFAULT '[]',
                    used_project_id INTEGER,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Guild config table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id INTEGER PRIMARY KEY,
                    projects_channel_id INTEGER,
                    admin_roles TEXT DEFAULT '[]',
                    thread_mode TEXT DEFAULT 'auto'
                )
            """)
            
            # User memories table - stores info about each user for the bot to remember
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    context TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, guild_id, memory_key)
                )
            """)
            
            # Conversation history for context
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Project notes table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS project_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)
            
            # Task notes table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS task_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            """)
            
            await db.commit()
    
    # ============ PROJECT METHODS ============
    
    async def create_project(self, guild_id: int, title: str, description: str = None,
                            owners: List[int] = None, thread_id: int = None,
                            tags: List[str] = None, template: str = None) -> int:
        """Create a new project and return its ID"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO projects (guild_id, title, description, owners, thread_id, tags, template, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                guild_id, title, description,
                json.dumps(owners or []),
                thread_id,
                json.dumps(tags or []),
                template,
                datetime.utcnow().isoformat()
            ))
            await db.commit()
            return cursor.lastrowid
    
    async def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Get a project by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = await cursor.fetchone()
            if row:
                return self._row_to_project(row)
            return None
    
    async def get_guild_projects(self, guild_id: int, status: str = None) -> List[Dict[str, Any]]:
        """Get all projects for a guild, optionally filtered by status"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                cursor = await db.execute(
                    "SELECT * FROM projects WHERE guild_id = ? AND status = ? ORDER BY created_at DESC",
                    (guild_id, status)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM projects WHERE guild_id = ? ORDER BY created_at DESC",
                    (guild_id,)
                )
            rows = await cursor.fetchall()
            return [self._row_to_project(row) for row in rows]
    
    async def update_project(self, project_id: int, **kwargs) -> bool:
        """Update project fields"""
        if not kwargs:
            return False
        
        # Handle JSON fields
        for key in ['owners', 'tags']:
            if key in kwargs and isinstance(kwargs[key], list):
                kwargs[key] = json.dumps(kwargs[key])
        
        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [project_id]
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", values)
            await db.commit()
            return True
    
    async def archive_project(self, project_id: int) -> bool:
        """Archive a project"""
        return await self.update_project(
            project_id,
            status='archived',
            archived_at=datetime.utcnow().isoformat()
        )
    
    def _row_to_project(self, row) -> Dict[str, Any]:
        """Convert a database row to a project dict"""
        return {
            'id': row['id'],
            'guild_id': row['guild_id'],
            'title': row['title'],
            'description': row['description'],
            'owners': json.loads(row['owners']),
            'status': row['status'],
            'thread_id': row['thread_id'],
            'created_at': row['created_at'],
            'archived_at': row['archived_at'],
            'tags': json.loads(row['tags']),
            'template': row['template']
        }
    
    # ============ TASK METHODS ============
    
    async def create_task(self, project_id: int, label: str, created_by: int = None, assigned_to: int = None) -> int:
        """Create a new task"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO tasks (project_id, label, created_by, assigned_to, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (project_id, label, created_by, assigned_to, datetime.utcnow().isoformat()))
            await db.commit()
            return cursor.lastrowid
    
    async def get_project_tasks(self, project_id: int) -> List[Dict[str, Any]]:
        """Get all tasks for a project"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at",
                (project_id,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get a single task by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def toggle_task(self, task_id: int) -> bool:
        """Toggle task completion status"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET is_done = NOT is_done WHERE id = ?",
                (task_id,)
            )
            await db.commit()
            return True
    
    async def delete_task(self, task_id: int) -> bool:
        """Delete a task"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            await db.commit()
            return True
    
    async def assign_task(self, task_id: int, user_id: int) -> bool:
        """Assign a task to a user"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET assigned_to = ? WHERE id = ?",
                (user_id, task_id)
            )
            await db.commit()
            return True
    
    async def unassign_task(self, task_id: int) -> bool:
        """Unassign a task from any user"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET assigned_to = NULL WHERE id = ?",
                (task_id,)
            )
            await db.commit()
            return True
    
    async def get_user_tasks(self, guild_id: int, user_id: int, include_done: bool = False) -> List[Dict[str, Any]]:
        """Get all tasks assigned to a user in a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if include_done:
                cursor = await db.execute("""
                    SELECT tasks.* FROM tasks
                    JOIN projects ON tasks.project_id = projects.id
                    WHERE projects.guild_id = ? AND tasks.assigned_to = ?
                    ORDER BY tasks.created_at DESC
                """, (guild_id, user_id))
            else:
                cursor = await db.execute("""
                    SELECT tasks.* FROM tasks
                    JOIN projects ON tasks.project_id = projects.id
                    WHERE projects.guild_id = ? AND tasks.assigned_to = ? AND tasks.is_done = 0
                    ORDER BY tasks.created_at DESC
                """, (guild_id, user_id))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # ============ IDEA METHODS ============
    
    async def create_idea(self, guild_id: int, author_id: int, title: str,
                         description: str = None, tags: List[str] = None) -> int:
        """Create a new idea"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO ideas (guild_id, author_id, title, description, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                guild_id, author_id, title, description,
                json.dumps(tags or []),
                datetime.utcnow().isoformat()
            ))
            await db.commit()
            return cursor.lastrowid
    
    async def get_guild_ideas(self, guild_id: int, unused_only: bool = False) -> List[Dict[str, Any]]:
        """Get ideas for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if unused_only:
                cursor = await db.execute(
                    "SELECT * FROM ideas WHERE guild_id = ? AND used_project_id IS NULL ORDER BY created_at DESC",
                    (guild_id,)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM ideas WHERE guild_id = ? ORDER BY created_at DESC",
                    (guild_id,)
                )
            rows = await cursor.fetchall()
            return [{**dict(row), 'tags': json.loads(row['tags'])} for row in rows]
    
    async def mark_idea_used(self, idea_id: int, project_id: int) -> bool:
        """Mark an idea as used by a project"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE ideas SET used_project_id = ? WHERE id = ?",
                (project_id, idea_id)
            )
            await db.commit()
            return True
    
    async def delete_idea(self, idea_id: int) -> bool:
        """Delete an idea from the pool"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
            await db.commit()
            return True
    
    async def get_idea(self, idea_id: int) -> Optional[Dict[str, Any]]:
        """Get a single idea by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,))
            row = await cursor.fetchone()
            if row:
                return {**dict(row), 'tags': json.loads(row['tags'])}
            return None
    
    # ============ GUILD CONFIG METHODS ============
    
    async def get_guild_config(self, guild_id: int) -> Dict[str, Any]:
        """Get guild configuration, creating default if not exists"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM guild_config WHERE guild_id = ?",
                (guild_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    'guild_id': row['guild_id'],
                    'projects_channel_id': row['projects_channel_id'],
                    'admin_roles': json.loads(row['admin_roles']),
                    'thread_mode': row['thread_mode']
                }
            # Create default config
            await db.execute(
                "INSERT INTO guild_config (guild_id) VALUES (?)",
                (guild_id,)
            )
            await db.commit()
            return {
                'guild_id': guild_id,
                'projects_channel_id': None,
                'admin_roles': [],
                'thread_mode': 'auto'
            }
    
    async def update_guild_config(self, guild_id: int, **kwargs) -> bool:
        """Update guild configuration"""
        if 'admin_roles' in kwargs and isinstance(kwargs['admin_roles'], list):
            kwargs['admin_roles'] = json.dumps(kwargs['admin_roles'])
        
        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [guild_id]
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE guild_config SET {set_clause} WHERE guild_id = ?", values)
            await db.commit()
            return True
    
    # ============ USER MEMORY METHODS ============
    
    async def set_memory(self, user_id: int, guild_id: int, key: str, value: str,
                        context: str = None) -> bool:
        """Set or update a memory for a user"""
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO user_memories (user_id, guild_id, memory_key, memory_value, context, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id, memory_key) DO UPDATE SET
                    memory_value = excluded.memory_value,
                    context = excluded.context,
                    updated_at = excluded.updated_at
            """, (user_id, guild_id, key, value, context, now, now))
            await db.commit()
            return True
    
    async def get_memory(self, user_id: int, guild_id: int, key: str) -> Optional[str]:
        """Get a specific memory for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT memory_value FROM user_memories WHERE user_id = ? AND guild_id = ? AND memory_key = ?",
                (user_id, guild_id, key)
            )
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def get_all_memories(self, user_id: int, guild_id: int) -> Dict[str, str]:
        """Get all memories for a user in a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT memory_key, memory_value, context, updated_at FROM user_memories WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            rows = await cursor.fetchall()
            return {row['memory_key']: {
                'value': row['memory_value'],
                'context': row['context'],
                'updated_at': row['updated_at']
            } for row in rows}
    
    async def delete_memory(self, user_id: int, guild_id: int, key: str) -> bool:
        """Delete a specific memory"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM user_memories WHERE user_id = ? AND guild_id = ? AND memory_key = ?",
                (user_id, guild_id, key)
            )
            await db.commit()
            return True
    
    async def clear_user_memories(self, user_id: int, guild_id: int) -> bool:
        """Clear all memories for a user in a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM user_memories WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            await db.commit()
            return True
    
    # ============ CONVERSATION HISTORY METHODS ============
    
    async def add_message(self, user_id: int, guild_id: int, channel_id: int,
                         role: str, content: str) -> int:
        """Add a message to conversation history"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO conversation_history (user_id, guild_id, channel_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, guild_id, channel_id, role, content, datetime.utcnow().isoformat()))
            await db.commit()
            return cursor.lastrowid
    
    async def get_recent_messages(self, user_id: int, guild_id: int, channel_id: int,
                                  limit: int = 20) -> List[Dict[str, str]]:
        """Get recent conversation history for context"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT role, content FROM conversation_history
                WHERE user_id = ? AND guild_id = ? AND channel_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, guild_id, channel_id, limit))
            rows = await cursor.fetchall()
            # Reverse to get chronological order
            return [{'role': row['role'], 'content': row['content']} for row in reversed(rows)]
    
    async def prune_old_messages(self, days: int = 7) -> int:
        """Delete conversation history older than specified days"""
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM conversation_history WHERE created_at < ?",
                (cutoff,)
            )
            await db.commit()
            return cursor.rowcount

    async def clear_conversation_history(self, user_id: int = None, guild_id: int = None, 
                                         channel_id: int = None) -> int:
        """Clear conversation history with optional filters.
        
        If no filters provided, clears ALL conversation history.
        """
        async with aiosqlite.connect(self.db_path) as db:
            conditions = []
            params = []
            
            if user_id is not None:
                conditions.append("user_id = ?")
                params.append(user_id)
            if guild_id is not None:
                conditions.append("guild_id = ?")
                params.append(guild_id)
            if channel_id is not None:
                conditions.append("channel_id = ?")
                params.append(channel_id)
            
            if conditions:
                query = f"DELETE FROM conversation_history WHERE {' AND '.join(conditions)}"
            else:
                query = "DELETE FROM conversation_history"
            
            cursor = await db.execute(query, tuple(params))
            await db.commit()
            return cursor.rowcount
    
    # ============ NOTES METHODS ============
    
    async def add_project_note(self, project_id: int, author_id: int, content: str) -> int:
        """Add a note to a project"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO project_notes (project_id, author_id, content, created_at)
                VALUES (?, ?, ?, ?)
            """, (project_id, author_id, content, datetime.utcnow().isoformat()))
            await db.commit()
            return cursor.lastrowid
    
    async def get_project_notes(self, project_id: int) -> List[Dict[str, Any]]:
        """Get all notes for a project"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM project_notes WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def delete_project_note(self, note_id: int) -> bool:
        """Delete a project note"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM project_notes WHERE id = ?", (note_id,))
            await db.commit()
            return True
    
    async def add_task_note(self, task_id: int, author_id: int, content: str) -> int:
        """Add a note to a task"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO task_notes (task_id, author_id, content, created_at)
                VALUES (?, ?, ?, ?)
            """, (task_id, author_id, content, datetime.utcnow().isoformat()))
            await db.commit()
            return cursor.lastrowid
    
    async def get_task_notes(self, task_id: int) -> List[Dict[str, Any]]:
        """Get all notes for a task"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM task_notes WHERE task_id = ? ORDER BY created_at DESC",
                (task_id,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def delete_task_note(self, note_id: int) -> bool:
        """Delete a task note"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM task_notes WHERE id = ?", (note_id,))
            await db.commit()
            return True
