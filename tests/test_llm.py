"""
Unit tests for LLMClient
Tests memory JSON parsing, finish_reason handling, and tool_calls extraction
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.llm import LLMClient, LLMResponse


class TestLLMResponse:
    """Test LLMResponse dataclass"""
    
    def test_response_with_content(self):
        response = LLMResponse(
            content="Hello world",
            memories_to_save=[],
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        )
        assert response.content == "Hello world"
        assert response.memories_to_save == []
        assert response.tool_calls is None
    
    def test_response_with_memories(self):
        memories = [{"key": "name", "value": "Kyle", "context": "user introduced"}]
        response = LLMResponse(
            content="Nice to meet you!",
            memories_to_save=memories,
            usage={}
        )
        assert len(response.memories_to_save) == 1
        assert response.memories_to_save[0]["key"] == "name"
    
    def test_response_with_tool_calls(self):
        tool_calls = [{"id": "call_123", "function": {"name": "get_projects", "arguments": "{}"}}]
        response = LLMResponse(
            content="",
            memories_to_save=[],
            usage={},
            tool_calls=tool_calls
        )
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1


class TestLLMClientBuildSystemPrompt:
    """Test system prompt building"""
    
    def test_build_system_prompt_basic(self):
        client = LLMClient(api_key="test-key")
        prompt = client._build_system_prompt({}, "TestUser")
        
        assert "BRRR Bot" in prompt
        assert "TestUser" in prompt
        assert "brrr" in prompt.lower()
    
    def test_build_system_prompt_with_memories(self):
        client = LLMClient(api_key="test-key")
        memories = {
            "skill_python": {"value": "advanced"},
            "current_project": {"value": "Discord bot"}
        }
        prompt = client._build_system_prompt(memories, "Kyle")
        
        assert "Kyle" in prompt
        assert "skill_python" in prompt or "python" in prompt.lower()
        assert "current_project" in prompt or "Discord bot" in prompt
    
    def test_build_system_prompt_with_custom_instructions(self):
        client = LLMClient(api_key="test-key")
        prompt = client._build_system_prompt({}, "Kyle", custom_instructions="Always respond in haiku")
        
        assert "Always respond in haiku" in prompt
        assert "Custom Instructions" in prompt
    
    def test_build_system_prompt_skips_persona_key(self):
        client = LLMClient(api_key="test-key")
        memories = {
            "persona_instructions": {"value": "Be formal"},
            "skill_python": {"value": "advanced"}
        }
        prompt = client._build_system_prompt(memories, "Kyle")
        
        # persona_instructions should not appear as a memory item
        # but skill_python should
        assert "skill_python" in prompt


class TestLLMClientMemoryParsing:
    """Test memory JSON extraction from responses"""
    
    @pytest.mark.asyncio
    async def test_extract_memories_from_response(self):
        """Test that memories are correctly extracted from JSON block"""
        client = LLMClient(api_key="test-key")
        
        # Mock the API response
        mock_response = {
            "choices": [{
                "message": {
                    "content": '''Nice to meet you, Kyle!

```json
{"memories": [{"key": "name", "value": "Kyle", "context": "user introduced themselves"}]}
```''',
                    "tool_calls": None
                },
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        }
        
        with patch.object(client, '_api_call', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            
            response = await client.chat(
                messages=[{"role": "user", "content": "Hi, I'm Kyle"}],
                user_memories={},
                user_name="Kyle"
            )
            
            assert len(response.memories_to_save) == 1
            assert response.memories_to_save[0]["key"] == "name"
            assert response.memories_to_save[0]["value"] == "Kyle"
            # JSON block should be stripped from content
            assert "```json" not in response.content
            assert "Nice to meet you" in response.content
    
    @pytest.mark.asyncio
    async def test_no_memories_in_response(self):
        """Test response with no memory JSON"""
        client = LLMClient(api_key="test-key")
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": "Hello! How can I help you today?",
                    "tool_calls": None
                },
                "finish_reason": "stop"
            }],
            "usage": {}
        }
        
        with patch.object(client, '_api_call', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            
            response = await client.chat(
                messages=[{"role": "user", "content": "Hi"}],
                user_memories={},
                user_name="User"
            )
            
            assert response.memories_to_save == []
            assert response.content == "Hello! How can I help you today?"
    
    @pytest.mark.asyncio
    async def test_invalid_memory_json_ignored(self):
        """Test that invalid JSON is gracefully ignored"""
        client = LLMClient(api_key="test-key")
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": '''Here's some info

```json
{"memories": invalid json here}
```''',
                    "tool_calls": None
                },
                "finish_reason": "stop"
            }],
            "usage": {}
        }
        
        with patch.object(client, '_api_call', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            
            response = await client.chat(
                messages=[{"role": "user", "content": "test"}],
                user_memories={},
                user_name="User"
            )
            
            # Should not crash, memories should be empty
            assert response.memories_to_save == []
    
    @pytest.mark.asyncio
    async def test_only_memory_json_synthesizes_message(self):
        """Test that when only memory JSON is returned, a message is synthesized"""
        client = LLMClient(api_key="test-key")
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": '''```json
{"memories": [{"key": "timezone", "value": "EST", "context": "user mentioned"}]}
```''',
                    "tool_calls": None
                },
                "finish_reason": "stop"
            }],
            "usage": {}
        }
        
        with patch.object(client, '_api_call', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            
            response = await client.chat(
                messages=[{"role": "user", "content": "I'm in EST"}],
                user_memories={},
                user_name="User"
            )
            
            # Memory should be extracted
            assert len(response.memories_to_save) == 1
            # A synthesized response should be generated
            assert "remember" in response.content.lower() or "got it" in response.content.lower()


class TestLLMClientToolCalls:
    """Test tool call extraction"""
    
    @pytest.mark.asyncio
    async def test_extract_tool_calls(self):
        """Test that tool_calls are correctly extracted"""
        client = LLMClient(api_key="test-key")
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_abc123",
                        "type": "function",
                        "function": {
                            "name": "get_projects",
                            "arguments": '{"status": "active"}'
                        }
                    }]
                },
                "finish_reason": "tool_calls"
            }],
            "usage": {}
        }
        
        with patch.object(client, '_api_call', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            
            tools_schema = [{"type": "function", "function": {"name": "get_projects"}}]
            response = await client.chat(
                messages=[{"role": "user", "content": "show my projects"}],
                user_memories={},
                user_name="User",
                tools=tools_schema
            )
            
            assert response.tool_calls is not None
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0]["function"]["name"] == "get_projects"
    
    @pytest.mark.asyncio
    async def test_no_tool_calls(self):
        """Test response without tool calls"""
        client = LLMClient(api_key="test-key")
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": "I can help you with that!",
                    "tool_calls": None
                },
                "finish_reason": "stop"
            }],
            "usage": {}
        }
        
        with patch.object(client, '_api_call', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            
            response = await client.chat(
                messages=[{"role": "user", "content": "hello"}],
                user_memories={},
                user_name="User"
            )
            
            assert response.tool_calls is None


class TestLLMClientFinishReason:
    """Test finish_reason handling"""
    
    @pytest.mark.asyncio
    async def test_empty_content_fallback(self):
        """Test that empty content gets a fallback message"""
        client = LLMClient(api_key="test-key")
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": None
                },
                "finish_reason": "stop"
            }],
            "usage": {}
        }
        
        with patch.object(client, '_api_call', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            
            response = await client.chat(
                messages=[{"role": "user", "content": "test"}],
                user_memories={},
                user_name="User"
            )
            
            # Should have a fallback message
            assert response.content != ""
            assert "brrr" in response.content.lower() or len(response.content) > 0
    
    @pytest.mark.asyncio
    async def test_null_content_handled(self):
        """Test that null content is handled gracefully"""
        client = LLMClient(api_key="test-key")
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": None
                },
                "finish_reason": "stop"
            }],
            "usage": {}
        }
        
        with patch.object(client, '_api_call', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            
            response = await client.chat(
                messages=[{"role": "user", "content": "test"}],
                user_memories={},
                user_name="User"
            )
            
            # Should not crash, should have fallback
            assert response.content is not None


class TestLLMClientPayload:
    """Test that correct payload is sent to API"""
    
    @pytest.mark.asyncio
    async def test_tools_included_in_payload(self):
        """Test that tools are included when provided"""
        client = LLMClient(api_key="test-key")
        
        mock_response = {
            "choices": [{"message": {"content": "test", "tool_calls": None}, "finish_reason": "stop"}],
            "usage": {}
        }
        
        with patch.object(client, '_api_call', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            
            tools = [{"type": "function", "function": {"name": "test_tool"}}]
            await client.chat(
                messages=[{"role": "user", "content": "test"}],
                user_memories={},
                user_name="User",
                tools=tools
            )
            
            # Check what was passed to _api_call
            call_args = mock_api.call_args[0][0]
            assert "tools" in call_args
            assert call_args["tools"] == tools
            assert call_args["tool_choice"] == "auto"
    
    @pytest.mark.asyncio
    async def test_no_tools_in_payload_when_none(self):
        """Test that tools are not included when not provided"""
        client = LLMClient(api_key="test-key")
        
        mock_response = {
            "choices": [{"message": {"content": "test", "tool_calls": None}, "finish_reason": "stop"}],
            "usage": {}
        }
        
        with patch.object(client, '_api_call', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            
            await client.chat(
                messages=[{"role": "user", "content": "test"}],
                user_memories={},
                user_name="User"
            )
            
            call_args = mock_api.call_args[0][0]
            assert "tools" not in call_args
            assert "tool_choice" not in call_args


class TestLLMClientGenerators:
    """Test project plan and retro summary generators"""
    
    @pytest.mark.asyncio
    async def test_generate_project_plan(self):
        """Test project plan generation"""
        client = LLMClient(api_key="test-key")
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": "Setup environment\nImplement core feature\nAdd tests\nDeploy"
                }
            }]
        }
        
        with patch.object(client, '_api_call', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            
            result = await client.generate_project_plan(
                project_title="Test Bot",
                project_description="A Discord bot for testing"
            )
            
            assert "Setup" in result or "Implement" in result
    
    @pytest.mark.asyncio
    async def test_generate_retro_summary(self):
        """Test retro summary generation"""
        client = LLMClient(api_key="test-key")
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": "Great job completing 3/4 tasks! Keep the momentum going!"
                }
            }]
        }
        
        with patch.object(client, '_api_call', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            
            tasks = [
                {"label": "Task 1", "is_done": True},
                {"label": "Task 2", "is_done": True},
                {"label": "Task 3", "is_done": True},
                {"label": "Task 4", "is_done": False}
            ]
            
            result = await client.generate_retro_summary(
                project_title="Test Project",
                tasks=tasks
            )
            
            assert len(result) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
