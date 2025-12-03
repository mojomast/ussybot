"""
Unit tests for ToolExecutor
Tests get_projects, create_task, add_idea functions
"""

import pytest
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tools import ToolExecutor, TOOLS_SCHEMA
from src.database import Database


class TestToolsSchema:
    """Test that tool schemas are properly defined"""
    
    def test_schema_has_required_tools(self):
        tool_names = [t["function"]["name"] for t in TOOLS_SCHEMA]
        assert "get_projects" in tool_names
        assert "create_task" in tool_names
        assert "add_idea" in tool_names
    
    def test_schema_format(self):
        for tool in TOOLS_SCHEMA:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]
    
    def test_get_projects_schema(self):
        get_projects = next(t for t in TOOLS_SCHEMA if t["function"]["name"] == "get_projects")
        params = get_projects["function"]["parameters"]
        
        assert params["type"] == "object"
        assert "status" in params["properties"]
        assert "enum" in params["properties"]["status"]
    
    def test_create_task_schema(self):
        create_task = next(t for t in TOOLS_SCHEMA if t["function"]["name"] == "create_task")
        params = create_task["function"]["parameters"]
        
        assert "project_id" in params["properties"]
        assert "label" in params["properties"]
        assert "project_id" in params["required"]
        assert "label" in params["required"]
    
    def test_add_idea_schema(self):
        add_idea = next(t for t in TOOLS_SCHEMA if t["function"]["name"] == "add_idea")
        params = add_idea["function"]["parameters"]
        
        assert "title" in params["properties"]
        assert "description" in params["properties"]
        assert "title" in params["required"]


@pytest.fixture
async def db():
    """Create a temporary test database"""
    db_path = "data/test_tools.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    database = Database(db_path)
    await database.init()
    yield database
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
async def executor(db):
    """Create a ToolExecutor with test database"""
    return ToolExecutor(db)


@pytest.fixture
async def test_project(db):
    """Create a test project"""
    project_id = await db.create_project(
        guild_id=123,
        title="Test Project",
        description="A project for testing"
    )
    return project_id


class TestToolExecutorGetProjects:
    """Test get_projects tool"""
    
    @pytest.mark.asyncio
    async def test_get_projects_empty(self, executor, db):
        """Test get_projects with no projects"""
        result = await executor.execute_tool(
            "get_projects",
            {},
            context={"guild_id": 999, "user_id": 1}
        )
        assert "No projects found" in result
    
    @pytest.mark.asyncio
    async def test_get_projects_returns_projects(self, executor, db):
        """Test get_projects returns existing projects"""
        # Create some projects
        await db.create_project(guild_id=123, title="Project A")
        await db.create_project(guild_id=123, title="Project B")
        
        result = await executor.execute_tool(
            "get_projects",
            {},
            context={"guild_id": 123, "user_id": 1}
        )
        
        assert "Project A" in result
        assert "Project B" in result
    
    @pytest.mark.asyncio
    async def test_get_projects_filter_by_status(self, executor, db):
        """Test get_projects with status filter"""
        # Create projects with different statuses
        project_id = await db.create_project(guild_id=123, title="Active Project")
        await db.create_project(guild_id=123, title="Another Active")
        
        # Archive one
        archived_id = await db.create_project(guild_id=123, title="Archived Project")
        await db.archive_project(archived_id)
        
        # Get only active
        result = await executor.execute_tool(
            "get_projects",
            {"status": "active"},
            context={"guild_id": 123, "user_id": 1}
        )
        
        assert "Active Project" in result
        assert "Another Active" in result
        assert "Archived Project" not in result
    
    @pytest.mark.asyncio
    async def test_get_projects_no_guild_context(self, executor):
        """Test get_projects without guild context"""
        result = await executor.execute_tool(
            "get_projects",
            {},
            context={"user_id": 1}  # No guild_id
        )
        assert "Error" in result


class TestToolExecutorCreateTask:
    """Test create_task tool"""
    
    @pytest.mark.asyncio
    async def test_create_task_success(self, executor, db, test_project):
        """Test successful task creation"""
        result = await executor.execute_tool(
            "create_task",
            {"project_id": test_project, "label": "Test Task"},
            context={"guild_id": 123, "user_id": 1}
        )
        
        assert "successfully" in result.lower() or "created" in result.lower()
        
        # Verify task was created
        tasks = await db.get_project_tasks(test_project)
        assert len(tasks) == 1
        assert tasks[0]["label"] == "Test Task"
    
    @pytest.mark.asyncio
    async def test_create_task_missing_project_id(self, executor):
        """Test create_task without project_id"""
        result = await executor.execute_tool(
            "create_task",
            {"label": "Test Task"},  # No project_id
            context={"guild_id": 123, "user_id": 1}
        )
        assert "Error" in result
    
    @pytest.mark.asyncio
    async def test_create_task_missing_label(self, executor, test_project):
        """Test create_task without label"""
        result = await executor.execute_tool(
            "create_task",
            {"project_id": test_project},  # No label
            context={"guild_id": 123, "user_id": 1}
        )
        assert "Error" in result
    
    @pytest.mark.asyncio
    async def test_create_task_invalid_project(self, executor):
        """Test create_task with non-existent project"""
        result = await executor.execute_tool(
            "create_task",
            {"project_id": 99999, "label": "Test Task"},
            context={"guild_id": 123, "user_id": 1}
        )
        assert "Error" in result or "not found" in result.lower()
    
    @pytest.mark.asyncio
    async def test_create_task_stores_user_id(self, executor, db, test_project):
        """Test that task stores creator user_id"""
        await executor.execute_tool(
            "create_task",
            {"project_id": test_project, "label": "User Task"},
            context={"guild_id": 123, "user_id": 456}
        )
        
        tasks = await db.get_project_tasks(test_project)
        assert tasks[0]["created_by"] == 456


class TestToolExecutorAddIdea:
    """Test add_idea tool"""
    
    @pytest.mark.asyncio
    async def test_add_idea_success(self, executor, db):
        """Test successful idea creation"""
        result = await executor.execute_tool(
            "add_idea",
            {"title": "Great Idea"},
            context={"guild_id": 123, "user_id": 1}
        )
        
        assert "added" in result.lower() or "success" in result.lower()
        
        # Verify idea was created
        ideas = await db.get_guild_ideas(123)
        assert len(ideas) == 1
        assert ideas[0]["title"] == "Great Idea"
    
    @pytest.mark.asyncio
    async def test_add_idea_with_description(self, executor, db):
        """Test idea creation with description"""
        result = await executor.execute_tool(
            "add_idea",
            {"title": "Another Idea", "description": "This is a detailed description"},
            context={"guild_id": 123, "user_id": 1}
        )
        
        ideas = await db.get_guild_ideas(123)
        assert ideas[0]["description"] == "This is a detailed description"
    
    @pytest.mark.asyncio
    async def test_add_idea_no_guild_context(self, executor):
        """Test add_idea without guild context"""
        result = await executor.execute_tool(
            "add_idea",
            {"title": "Test Idea"},
            context={"user_id": 1}  # No guild_id
        )
        assert "Error" in result
    
    @pytest.mark.asyncio
    async def test_add_idea_stores_user_id(self, executor, db):
        """Test that idea stores author user_id"""
        await executor.execute_tool(
            "add_idea",
            {"title": "User Idea"},
            context={"guild_id": 123, "user_id": 789}
        )
        
        ideas = await db.get_guild_ideas(123)
        assert ideas[0]["author_id"] == 789


class TestToolExecutorUnknownTool:
    """Test handling of unknown tools"""
    
    @pytest.mark.asyncio
    async def test_unknown_tool(self, executor):
        """Test that unknown tools return an error"""
        result = await executor.execute_tool(
            "nonexistent_tool",
            {},
            context={"guild_id": 123, "user_id": 1}
        )
        assert "Error" in result or "Unknown" in result


class TestToolExecutorErrorHandling:
    """Test error handling in tool execution"""
    
    @pytest.mark.asyncio
    async def test_exception_handling(self, executor, db):
        """Test that exceptions are caught and returned as errors"""
        # Manually break the db connection to cause an error
        original_path = db.db_path
        db.db_path = "/nonexistent/path/db.db"
        
        result = await executor.execute_tool(
            "get_projects",
            {},
            context={"guild_id": 123, "user_id": 1}
        )
        
        # Restore
        db.db_path = original_path
        
        # Should return error message, not raise exception
        assert "Error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
