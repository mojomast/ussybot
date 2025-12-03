"""
BRRR Bot - LLM Integration via Requesty.ai
Uses OpenAI-compatible API for inference
"""

import aiohttp
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger('brrr.llm')
logger.setLevel(logging.DEBUG)


@dataclass
class LLMResponse:
    content: str
    memories_to_save: List[Dict[str, str]]  # [{key, value, context}]
    usage: Dict[str, int]
    tool_calls: Optional[List[Dict]] = None


class LLMClient:
    """Requesty.ai LLM client - OpenAI compatible API"""
    
    BASE_URL = "https://router.requesty.ai/v1"
    
    def __init__(self, api_key: str, model: str = "openai/gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.session: Optional[aiohttp.ClientSession] = None
        # Global lock to ensure only one API call at a time
        self._api_lock = asyncio.Lock()
    
    async def ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _api_call(self, payload: dict) -> dict:
        """Make an API call with proper error handling and timeout.
        
        Uses a lock to ensure only one API call happens at a time,
        preventing concurrent requests that could cause duplicate responses.
        """
        await self.ensure_session()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Verbose logging: Log the full request payload
        logger.debug("=" * 60)
        logger.debug("LLM API REQUEST")
        logger.debug("=" * 60)
        logger.debug(f"Model: {payload.get('model')}")
        logger.debug(f"Temperature: {payload.get('temperature')}")
        logger.debug(f"Max tokens: {payload.get('max_tokens')}")
        logger.debug(f"Tools enabled: {bool(payload.get('tools'))}")
        
        # Log each message in the conversation
        messages = payload.get('messages', [])
        logger.debug(f"Message count: {len(messages)}")
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            # Truncate long messages for readability
            content_preview = content[:500] + '...' if len(content) > 500 else content
            logger.debug(f"  [{i}] {role}: {content_preview}")
            if msg.get('tool_calls'):
                logger.debug(f"      tool_calls: {json.dumps(msg['tool_calls'])[:300]}")
            if msg.get('tool_call_id'):
                logger.debug(f"      tool_call_id: {msg['tool_call_id']}, name: {msg.get('name')}")
        
        logger.debug("-" * 60)
        
        # Use lock to serialize API calls
        async with self._api_lock:
            try:
                async with self.session.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"LLM API error {response.status}: {error_text}")
                        raise Exception(f"LLM API error {response.status}: {error_text}")
                    
                    result = await response.json()
                    
                    # Verbose logging: Log the full response
                    logger.debug("=" * 60)
                    logger.debug("LLM API RESPONSE")
                    logger.debug("=" * 60)
                    logger.debug(f"Response ID: {result.get('id')}")
                    logger.debug(f"Model: {result.get('model')}")
                    
                    # Log usage stats
                    usage = result.get('usage', {})
                    logger.debug(f"Usage - prompt_tokens: {usage.get('prompt_tokens')}, "
                                f"completion_tokens: {usage.get('completion_tokens')}, "
                                f"total_tokens: {usage.get('total_tokens')}")
                    
                    # Log each choice
                    choices = result.get('choices', [])
                    for i, choice in enumerate(choices):
                        logger.debug(f"Choice [{i}]:")
                        logger.debug(f"  finish_reason: {choice.get('finish_reason')}")
                        msg = choice.get('message', {})
                        content = msg.get('content', '')
                        content_preview = content[:500] + '...' if len(str(content)) > 500 else content
                        logger.debug(f"  role: {msg.get('role')}")
                        logger.debug(f"  content: {content_preview}")
                        if msg.get('tool_calls'):
                            logger.debug(f"  tool_calls: {json.dumps(msg['tool_calls'])}")
                    
                    logger.debug("=" * 60)
                    
                    return result
            except aiohttp.ClientError as e:
                logger.error(f"Network error calling LLM API: {e}")
                raise Exception(f"Network error: {e}")
            except asyncio.TimeoutError:
                logger.error("LLM API request timed out")
                raise Exception("Request timed out")
    
    def _build_system_prompt(
        self,
        user_memories: Dict[str, Any],
        user_name: str,
        custom_instructions: str = None
    ) -> str:
        """Build the system prompt with user memories and custom instructions"""
        
        memory_context = ""
        if user_memories:
            memory_lines = []
            for key, data in user_memories.items():
                # Skip persona key - it's handled separately
                if key == "persona_instructions":
                    continue
                if isinstance(data, dict):
                    memory_lines.append(f"- {key}: {data.get('value', data)}")
                else:
                    memory_lines.append(f"- {key}: {data}")
            if memory_lines:
                memory_context = f"\n\n**What I remember about {user_name}:**\n" + "\n".join(memory_lines)
        
        # Build custom instructions section
        custom_section = ""
        if custom_instructions:
            custom_section = f"""

**User's Custom Instructions (IMPORTANT - follow these closely):**
{custom_instructions}
"""
        
        return f"""You are BRRR Bot, an energetic and helpful assistant for the BRRR Discord server focused on weekly coding projects.

**Your personality:**
- You go brrrrrrrrr (fast, efficient, high-energy)
- You're enthusiastic about coding projects and helping people build cool stuff
- You keep responses concise but helpful
- You use occasional "brrr" sounds when excited
- You're supportive and encourage people to ship their projects

**Your capabilities:**
- Help plan and manage weekly coding projects
- Answer coding questions
- Remember things about users to personalize interactions
- Provide encouragement and motivation

**Discord commands & features (very important):**
- You are a Discord bot with many slash commands. When users ask what you can do, how you help, or whether you have commands, you MUST mention these explicitly and suggest using `/help` for details.
- Global utility commands:
  - `/ping`  latency check.
  - `/brrr`  bot status (LLM, guilds, active projects).
  - `/help`  overview of all commands.
- Project workflow (`/project` group):
  - `/project start`  start a new project (modal).
  - `/project status` / `/project info` / `/project archive`.
  - `/project checklist add|list|toggle|remove`  manage project tasks.
- Weekly workflow (`/week` group):
  - `/week start`  weekly overview.
  - `/week retro`  run retrospectives (uses the LLM when available).
  - `/week summary`  quick project stats.
- Idea workflow (`/idea` group):
  - `/idea add`, `/idea quick`, `/idea list`, `/idea pick`, `/idea random`, `/idea delete`.
- Memory & persona (`/memory` and `/persona` groups):
  - `/memory show|add|forget|clear` to inspect and adjust what you remember.
  - `/persona set|preset|show|clear` to customize how you respond to each user.
- Direct chat:
  - Users can @mention you in a channel, reply to your messages, or use `/chat` for a direct LLM response.

When a user seems to need structured help (projects, weeks, ideas, memories, persona), gently point them to the relevant slash commands as well as answering conversationally.
{custom_section}
**Memory System:**
You can remember things about users. When you learn something worth remembering about a user (their preferences, skills, current projects, interests, timezone, etc.), you should include it in your response using this JSON format at the END of your message:

```json
{{"memories": [{{"key": "skill_python", "value": "advanced", "context": "mentioned they've been coding Python for 5 years"}}]}}
```

Memory keys should be descriptive like: current_project, skill_<language>, interest_<topic>, timezone, preferred_name, etc.
Only save memories that would be useful for future interactions. Don't save trivial or temporary information.
{memory_context}

**Current context:**
You're chatting with {user_name}.

Remember: You're here to help make weekly projects go BRRRRR! 🚀"""

    async def chat(
        self,
        messages: List[Dict[str, str]],
        user_memories: Dict[str, Any] = None,
        user_name: str = "User",
        custom_instructions: str = None,
        temperature: float = 0.7,
        max_tokens: int = 12000,
        tools: Optional[List[Dict]] = None
    ) -> LLMResponse:
        """Send a chat completion request"""
        
        system_prompt = self._build_system_prompt(user_memories or {}, user_name, custom_instructions)
        
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        data = await self._api_call(payload)
        
        # Safely extract message content and finish_reason
        choices = data.get("choices") or [{}]
        if not isinstance(choices, list):
            choices = [choices]
        first_choice = choices[0] or {}
        finish_reason = first_choice.get("finish_reason")
        message_data = first_choice.get("message", {})
        content = message_data.get("content", "")
        tool_calls = message_data.get("tool_calls")
        
        if content is None:
            content = ""
        usage = data.get("usage", {})
        
        # Extract memories from response
        memories_to_save = []
        clean_content = content or ""
        
        # Look for JSON memory block at the end
        if "```json" in clean_content and '"memories"' in clean_content:
            try:
                json_start = clean_content.rfind("```json")
                json_end = clean_content.rfind("```", json_start + 7)
                if json_start != -1 and json_end != -1:
                    json_str = clean_content[json_start + 7:json_end].strip()
                    memory_data = json.loads(json_str)
                    if "memories" in memory_data:
                        memories_to_save = memory_data["memories"]
                    # Remove the JSON block from the displayed content
                    clean_content = clean_content[:json_start].strip()
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                pass  # No valid memory JSON found

        # If the model only sent memory JSON with no visible text,
        # synthesize a simple acknowledgement so chat stays natural.
        if not clean_content.strip() and memories_to_save:
            try:
                keys = [m.get("key") for m in memories_to_save if isinstance(m, dict) and m.get("key")]
                if keys:
                    key_list = ", ".join(keys[:5])
                    clean_content = f"Got it, I'll remember that ({key_list})."
                else:
                    clean_content = "Got it, I'll remember that."
            except Exception:
                clean_content = "Got it, I'll remember that."
        
        # If we hit the length limit and got no content back, try a smaller, single-turn retry
        if not clean_content.strip() and finish_reason == "length":
            try:
                logger.debug("Empty content with finish_reason=length; retrying with shorter, single-turn prompt")
                # Find the last user message
                last_user_msg = None
                for m in reversed(messages):
                    if m.get("role") == "user":
                        last_user_msg = m
                        break
                if last_user_msg is not None:
                    # Use a more stable fallback model for the retry while
                    # keeping the primary model (e.g., openai/gpt-5-nano) for
                    # normal calls.
                    retry_model = "openai/gpt-4o-mini"
                    logger.debug(f"Retrying with fallback model: {retry_model}")
                    retry_payload = {
                        "model": retry_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            last_user_msg,
                        ],
                        "temperature": temperature,
                        "max_tokens": min(max_tokens, 256),
                    }
                    retry_data = await self._api_call(retry_payload)
                    try:
                        logger.debug(f"Retry raw LLM response: {json.dumps(retry_data)[:1000]}")
                    except Exception:
                        logger.debug("Retry LLM response could not be serialized to JSON for logging")
                    retry_choices = retry_data.get("choices") or [{}]
                    if not isinstance(retry_choices, list):
                        retry_choices = [retry_choices]
                    retry_first = retry_choices[0] or {}
                    retry_content = (
                        retry_first.get("message", {})
                        .get("content", "")
                    ) or ""
                    if retry_content.strip():
                        clean_content = retry_content.strip()
                        usage = retry_data.get("usage", usage)
            except Exception as e:
                logger.error(f"Error during LLM retry after empty length-limited response: {e}")

        # Absolute last resort: never return an empty string
        if not clean_content.strip():
            clean_content = "brrr... I didn't quite get that. Try asking in another way?"
        
        return LLMResponse(
            content=clean_content,
            memories_to_save=memories_to_save,
            usage=usage,
            tool_calls=tool_calls
        )
    
    async def generate_project_plan(
        self,
        project_title: str,
        project_description: str,
        user_context: str = ""
    ) -> str:
        """Generate a project plan/checklist"""
        
        prompt = f"""Generate a concise project checklist for:

**Project:** {project_title}
**Description:** {project_description}
{f"**Context:** {user_context}" if user_context else ""}

Create 5-10 actionable tasks that break down this project into manageable steps.
Format each task as a simple one-line item.
Focus on the most important tasks to ship an MVP.

Respond with ONLY the task list, one task per line, no numbering or bullets."""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a project planning assistant. Be concise and practical."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "max_tokens": 500
        }
        
        data = await self._api_call(payload)
        return data["choices"][0]["message"]["content"]
    
    async def generate_retro_summary(self, project_title: str, tasks: List[Dict]) -> str:
        """Generate a retrospective summary"""
        
        completed = [t for t in tasks if t.get('is_done')]
        incomplete = [t for t in tasks if not t.get('is_done')]
        
        prompt = f"""Generate a brief retro summary for this week's project:

**Project:** {project_title}
**Completed tasks:** {len(completed)}/{len(tasks)}
**Done:** {', '.join(t['label'] for t in completed) if completed else 'None'}
**Not done:** {', '.join(t['label'] for t in incomplete) if incomplete else 'All done!'}

Write a 2-3 sentence summary celebrating wins and noting what to carry forward.
Be encouraging and positive!"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are BRRR Bot, celebrating weekly project progress. Be enthusiastic!"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 200
        }
        
        data = await self._api_call(payload)
        return data["choices"][0]["message"]["content"]
