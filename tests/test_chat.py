"""
Unit tests for Chat Cog
Tests handle_mention tool loop and conversation handling
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.cogs.chat import Chat
from src.database import Database
from tests.mocks.mock_llm import MockLLMClient, MockResponse


@pytest.fixture
async def db():
    """Create a temporary test database"""
    db_path = "data/test_chat.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    database = Database(db_path)
    await database.init()
    yield database
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def mock_llm():
    """Create a mock LLM client"""
    return MockLLMClient()


@pytest.fixture
def mock_bot(db, mock_llm):
    """Create a mock bot with db and llm"""
    bot = MagicMock()
    bot.db = db
    bot.llm = mock_llm
    bot.user = MagicMock()
    bot.user.id = 12345
    bot.user.avatar = MagicMock()
    bot.user.avatar.url = "http://example.com/avatar.png"
    return bot


@pytest.fixture
def chat_cog(mock_bot):
    """Create a Chat cog instance"""
    return Chat(mock_bot)


def create_mock_message(content: str, author_id: int = 999, guild_id: int = 123, channel_id: int = 456):
    """Helper to create a mock Discord message"""
    message = AsyncMock()
    message.content = content
    message.author.id = author_id
    message.author.display_name = "TestUser"
    message.author.bot = False
    message.guild.id = guild_id
    message.channel.id = channel_id
    message.mentions = []
    
    # Mock channel.typing context manager
    typing_cm = MagicMock()
    typing_cm.__aenter__ = AsyncMock(return_value=None)
    typing_cm.__aexit__ = AsyncMock(return_value=None)
    message.channel.typing = MagicMock(return_value=typing_cm)
    
    # Track replies
    message.replies = []
    async def mock_reply(content, mention_author=False):
        message.replies.append(content)
    message.reply = mock_reply
    
    # Track channel sends
    message.channel.sends = []
    async def mock_send(content):
        message.channel.sends.append(content)
    message.channel.send = mock_send
    
    return message


class TestChatCogBasic:
    """Basic Chat cog tests"""
    
    @pytest.mark.asyncio
    async def test_handle_mention_simple_response(self, chat_cog, mock_llm):
        """Test simple mention handling"""
        mock_llm.set_response("Hello! How can I help? brrr!")
        
        message = create_mock_message("Hello bot!")
        await chat_cog.handle_mention(message)
        
        assert len(message.replies) == 1
        assert "Hello!" in message.replies[0]
    
    @pytest.mark.asyncio
    async def test_handle_mention_saves_conversation(self, chat_cog, mock_llm, db):
        """Test that conversation is saved to history"""
        mock_llm.set_response("Nice to meet you!")
        
        message = create_mock_message("Hi there!")
        await chat_cog.handle_mention(message)
        
        # Check conversation was saved
        history = await db.get_recent_messages(
            user_id=999,
            guild_id=123,
            channel_id=456,
            limit=10
        )
        
        assert len(history) == 2  # User message + assistant response
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
    
    @pytest.mark.asyncio
    async def test_handle_mention_saves_memories(self, chat_cog, mock_llm, db):
        """Test that memories from LLM response are saved"""
        mock_llm.set_response(
            "Got it, I'll remember that!",
            memories=[{"key": "favorite_color", "value": "blue", "context": "user mentioned"}]
        )
        
        message = create_mock_message("My favorite color is blue")
        await chat_cog.handle_mention(message)
        
        # Check memory was saved
        memories = await db.get_all_memories(user_id=999, guild_id=123)
        assert "favorite_color" in memories
        assert memories["favorite_color"]["value"] == "blue"
    
    @pytest.mark.asyncio
    async def test_handle_mention_no_llm(self, chat_cog, mock_bot):
        """Test that nothing happens when LLM is not available"""
        mock_bot.llm = None
        
        message = create_mock_message("Hello!")
        await chat_cog.handle_mention(message)
        
        assert len(message.replies) == 0
    
    @pytest.mark.asyncio
    async def test_handle_mention_strips_bot_mention(self, chat_cog, mock_llm):
        """Test that bot mentions are stripped from content"""
        mock_llm.set_response("Hello!")
        
        message = create_mock_message("<@12345> hello bot")
        # Add the bot as a mention
        bot_mention = MagicMock()
        bot_mention.id = 12345
        message.mentions = [bot_mention]
        
        await chat_cog.handle_mention(message)
        
        # Check what was sent to LLM
        call_history = mock_llm.get_call_history()
        assert len(call_history) == 1
        # The last message should have the mention stripped
        messages = call_history[0]["messages"]
        last_user_msg = [m for m in messages if m["role"] == "user"][-1]
        assert "<@12345>" not in last_user_msg["content"]


class TestChatCogToolHandling:
    """Test tool calling integration"""
    
    @pytest.mark.asyncio
    async def test_tool_call_flow(self, chat_cog, mock_llm, db):
        """Test complete tool call flow"""
        # Create a project first
        project_id = await db.create_project(guild_id=123, title="Test Project")
        
        # Queue responses: first with tool call, then with final response
        mock_llm.queue_responses([
            MockResponse(
                content="",
                tool_calls=[{
                    "id": "call_123",
                    "function": {
                        "name": "get_projects",
                        "arguments": "{}"
                    }
                }]
            ),
            MockResponse(
                content="I found your project: Test Project!"
            )
        ])
        
        message = create_mock_message("show my projects")
        await chat_cog.handle_mention(message)
        
        # Should have called LLM twice
        assert len(mock_llm.get_call_history()) == 2
        
        # Final reply should include project info
        assert len(message.replies) == 1
        assert "Test Project" in message.replies[0]
    
    @pytest.mark.asyncio
    async def test_tool_call_create_task(self, chat_cog, mock_llm, db):
        """Test create_task tool execution"""
        project_id = await db.create_project(guild_id=123, title="Dev Project")
        
        mock_llm.queue_responses([
            MockResponse(
                content="",
                tool_calls=[{
                    "id": "call_456",
                    "function": {
                        "name": "create_task",
                        "arguments": f'{{"project_id": {project_id}, "label": "Write tests"}}'
                    }
                }]
            ),
            MockResponse(
                content="I've created the task 'Write tests' for you!"
            )
        ])
        
        message = create_mock_message(f"add task 'Write tests' to project {project_id}")
        await chat_cog.handle_mention(message)
        
        # Verify task was created
        tasks = await db.get_project_tasks(project_id)
        assert len(tasks) == 1
        assert tasks[0]["label"] == "Write tests"
    
    @pytest.mark.asyncio
    async def test_tool_call_add_idea(self, chat_cog, mock_llm, db):
        """Test add_idea tool execution"""
        mock_llm.queue_responses([
            MockResponse(
                content="",
                tool_calls=[{
                    "id": "call_789",
                    "function": {
                        "name": "add_idea",
                        "arguments": '{"title": "Build a CLI tool", "description": "A command line utility"}'
                    }
                }]
            ),
            MockResponse(
                content="I've added your idea: Build a CLI tool!"
            )
        ])
        
        message = create_mock_message("I have an idea for a CLI tool")
        await chat_cog.handle_mention(message)
        
        # Verify idea was created
        ideas = await db.get_guild_ideas(123)
        assert len(ideas) == 1
        assert ideas[0]["title"] == "Build a CLI tool"
    
    @pytest.mark.asyncio
    async def test_tool_result_passed_to_llm(self, chat_cog, mock_llm, db):
        """Test that tool results are passed back to LLM"""
        await db.create_project(guild_id=123, title="Project Alpha")
        await db.create_project(guild_id=123, title="Project Beta")
        
        mock_llm.queue_responses([
            MockResponse(
                content="",
                tool_calls=[{
                    "id": "call_list",
                    "function": {
                        "name": "get_projects",
                        "arguments": "{}"
                    }
                }]
            ),
            MockResponse(
                content="You have 2 projects: Alpha and Beta"
            )
        ])
        
        message = create_mock_message("what projects do I have?")
        await chat_cog.handle_mention(message)
        
        # Check the second LLM call had tool result
        call_history = mock_llm.get_call_history()
        assert len(call_history) == 2
        
        second_call = call_history[1]
        messages = second_call["messages"]
        
        # Should have a tool message with results
        tool_messages = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_messages) == 1
        assert "Project Alpha" in tool_messages[0]["content"]
        assert "Project Beta" in tool_messages[0]["content"]


class TestChatCogLongResponses:
    """Test handling of long responses"""
    
    @pytest.mark.asyncio
    async def test_long_response_split(self, chat_cog, mock_llm):
        """Test that long responses are split into chunks"""
        # Create a response longer than 2000 characters
        long_content = "brrr! " * 500  # ~3000 characters
        mock_llm.set_response(long_content)
        
        message = create_mock_message("give me a long response")
        await chat_cog.handle_mention(message)
        
        # Should have multiple messages
        total_messages = len(message.replies) + len(message.channel.sends)
        assert total_messages >= 2


class TestChatCogEmptyResponses:
    """Test handling of empty responses"""
    
    @pytest.mark.asyncio
    async def test_empty_response_fallback(self, chat_cog, mock_llm):
        """Test that empty responses get a fallback"""
        mock_llm.set_response("")
        
        message = create_mock_message("test")
        await chat_cog.handle_mention(message)
        
        # Should have a fallback response
        assert len(message.replies) == 1
        # The fallback message from chat.py
        assert "blank" in message.replies[0].lower() or "brrr" in message.replies[0].lower()


class TestChatCogErrorHandling:
    """Test error handling"""
    
    @pytest.mark.asyncio
    async def test_llm_error_handled(self, chat_cog, mock_bot):
        """Test that LLM errors are handled gracefully"""
        # Make LLM raise an exception
        async def raise_error(*args, **kwargs):
            raise Exception("API Error")
        
        mock_bot.llm.chat = raise_error
        
        message = create_mock_message("hello")
        await chat_cog.handle_mention(message)
        
        # Should have an error message reply
        assert len(message.replies) == 1
        assert "wrong" in message.replies[0].lower() or "error" in message.replies[0].lower()


class TestChatCogContext:
    """Test context handling"""
    
    @pytest.mark.asyncio
    async def test_conversation_history_included(self, chat_cog, mock_llm, db):
        """Test that conversation history is included in context"""
        # Add some history
        await db.add_message(999, 123, 456, "user", "Previous message")
        await db.add_message(999, 123, 456, "assistant", "Previous response")
        
        mock_llm.set_response("Hello!")
        
        message = create_mock_message("new message")
        await chat_cog.handle_mention(message)
        
        # Check that history was included
        call_history = mock_llm.get_call_history()
        messages = call_history[0]["messages"]
        
        # Should have history + new message
        assert len(messages) >= 3
        contents = [m["content"] for m in messages]
        assert "Previous message" in contents
        assert "Previous response" in contents
    
    @pytest.mark.asyncio
    async def test_user_memories_passed_to_llm(self, chat_cog, mock_llm, db):
        """Test that user memories are passed to LLM"""
        # Add some memories
        await db.set_memory(999, 123, "skill_python", "advanced", "from previous chat")
        
        mock_llm.set_response("Hello!")
        
        message = create_mock_message("hi")
        await chat_cog.handle_mention(message)
        
        # Check that memories were passed
        call_history = mock_llm.get_call_history()
        user_memories = call_history[0]["user_memories"]
        
        assert "skill_python" in user_memories
    
    @pytest.mark.asyncio
    async def test_custom_instructions_from_persona(self, chat_cog, mock_llm, db):
        """Test that persona instructions are passed as custom instructions"""
        # Set persona
        await db.set_memory(999, 123, "persona_instructions", "Always be formal", "user set")
        
        mock_llm.set_response("Hello!")
        
        message = create_mock_message("hi")
        await chat_cog.handle_mention(message)
        
        # Check custom instructions were passed
        call_history = mock_llm.get_call_history()
        custom_instructions = call_history[0]["custom_instructions"]
        
        assert custom_instructions == "Always be formal"


class TestChatCogBotMessages:
    """Test handling of messages from other bots"""
    
    @pytest.mark.asyncio
    async def test_bot_message_flagged(self, chat_cog, mock_llm):
        """Test that messages from bots are flagged in content"""
        mock_llm.set_response("Hello bot friend!")
        
        message = create_mock_message("Hello!")
        message.author.bot = True
        message.author.display_name = "OtherBot"
        
        await chat_cog.handle_mention(message)
        
        # Check that bot flag was included
        call_history = mock_llm.get_call_history()
        messages = call_history[0]["messages"]
        last_user_msg = [m for m in messages if m["role"] == "user"][-1]
        
        assert "another bot" in last_user_msg["content"].lower() or "OtherBot" in last_user_msg["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
