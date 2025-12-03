"""
Mock LLM Client for deterministic testing
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from src.llm import LLMResponse


@dataclass
class MockResponse:
    """Configuration for a mock LLM response"""
    content: str = "Hello! I'm a mock response."
    memories: List[Dict[str, str]] = field(default_factory=list)
    tool_calls: Optional[List[Dict]] = None
    finish_reason: str = "stop"
    usage: Dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})


class MockLLMClient:
    """
    Mock LLM client for testing without making real API calls.
    
    Usage:
        client = MockLLMClient()
        
        # Set a simple response
        client.set_response("Hello!")
        
        # Set a response with memories
        client.set_response("Got it!", memories=[{"key": "name", "value": "Kyle", "context": "user introduced themselves"}])
        
        # Set a response with tool calls
        client.set_response("", tool_calls=[{
            "id": "call_123",
            "function": {"name": "get_projects", "arguments": "{}"}
        }])
        
        # Queue multiple responses
        client.queue_responses([
            MockResponse(content="First response"),
            MockResponse(content="Second response")
        ])
    """
    
    def __init__(self, api_key: str = "mock-key", model: str = "mock/model"):
        self.api_key = api_key
        self.model = model
        self._response_queue: List[MockResponse] = []
        self._default_response = MockResponse()
        self._call_history: List[Dict[str, Any]] = []
        self.session = None  # For compatibility with real client
    
    async def ensure_session(self):
        """No-op for mock"""
        pass
    
    async def close(self):
        """No-op for mock"""
        pass
    
    def set_response(
        self,
        content: str,
        memories: List[Dict[str, str]] = None,
        tool_calls: Optional[List[Dict]] = None,
        finish_reason: str = "stop"
    ):
        """Set a single response that will be returned for all calls"""
        self._default_response = MockResponse(
            content=content,
            memories=memories or [],
            tool_calls=tool_calls,
            finish_reason=finish_reason
        )
        self._response_queue = []
    
    def queue_responses(self, responses: List[MockResponse]):
        """Queue multiple responses to be returned in order"""
        self._response_queue = list(responses)
    
    def get_call_history(self) -> List[Dict[str, Any]]:
        """Get history of all calls made to the mock client"""
        return self._call_history
    
    def clear_history(self):
        """Clear call history"""
        self._call_history = []
    
    async def chat(
        self,
        user_message: str,
        user_memories: Dict[str, Any] = None,
        user_name: str = "User",
        custom_instructions: str = None,
        conversation_context: List[Dict[str, str]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict]] = None
    ) -> LLMResponse:
        """Mock chat method that returns configured responses"""
        
        # Record the call
        self._call_history.append({
            "user_message": user_message,
            "user_memories": user_memories,
            "user_name": user_name,
            "custom_instructions": custom_instructions,
            "conversation_context": conversation_context,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools
        })
        
        # Get response
        if self._response_queue:
            mock_resp = self._response_queue.pop(0)
        else:
            mock_resp = self._default_response
        
        return LLMResponse(
            content=mock_resp.content,
            memories_to_save=mock_resp.memories,
            usage=mock_resp.usage,
            tool_calls=mock_resp.tool_calls
        )
    
    async def chat_with_tool_results(
        self,
        user_message: str,
        assistant_tool_calls: List[Dict],
        tool_results: List[Dict],
        user_memories: Dict[str, Any] = None,
        user_name: str = "User",
        custom_instructions: str = None,
        conversation_context: List[Dict[str, str]] = None,
        temperature: float = 0.7,
        max_tokens: int = 12000,
        tools: Optional[List[Dict]] = None
    ) -> LLMResponse:
        """Mock chat with tool results method"""
        
        # Record the call
        self._call_history.append({
            "method": "chat_with_tool_results",
            "user_message": user_message,
            "assistant_tool_calls": assistant_tool_calls,
            "tool_results": tool_results,
            "user_memories": user_memories,
            "user_name": user_name,
            "custom_instructions": custom_instructions,
            "conversation_context": conversation_context,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools
        })
        
        # Get response
        if self._response_queue:
            mock_resp = self._response_queue.pop(0)
        else:
            mock_resp = self._default_response
        
        return LLMResponse(
            content=mock_resp.content,
            memories_to_save=mock_resp.memories,
            usage=mock_resp.usage,
            tool_calls=mock_resp.tool_calls
        )
    
    async def generate_project_plan(
        self,
        project_title: str,
        project_description: str,
        user_context: str = ""
    ) -> str:
        """Mock project plan generation"""
        self._call_history.append({
            "method": "generate_project_plan",
            "project_title": project_title,
            "project_description": project_description,
            "user_context": user_context
        })
        return "Task 1: Setup project\nTask 2: Implement feature\nTask 3: Test\nTask 4: Deploy"
    
    async def generate_retro_summary(self, project_title: str, tasks: List[Dict]) -> str:
        """Mock retro summary generation"""
        self._call_history.append({
            "method": "generate_retro_summary",
            "project_title": project_title,
            "tasks": tasks
        })
        completed = len([t for t in tasks if t.get('is_done')])
        return f"Great progress on {project_title}! Completed {completed}/{len(tasks)} tasks. Keep up the momentum! 🚀"
