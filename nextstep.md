# Next Steps / Handoff

## Purpose
This document tracks the latest development session, including concurrency fixes, unit test scaffolding, and model configuration improvements.

---

## Summary of Latest Changes (December 3, 2025)

### Concurrency & Race Condition Fixes
- **Per-channel message locking** (`src/bot.py`): Added `_channel_locks` dictionary with `asyncio.Lock` per channel to prevent concurrent message processing in the same channel.
- **Global API lock** (`src/llm.py`): Added `_api_lock` to serialize all LLM API calls, ensuring only one request is in-flight at a time.
- **Startup timestamp filtering** (`src/bot.py`): Bot now tracks `_started_at` timestamp (set in `on_ready`) and ignores any messages created before the bot was fully connected. This prevents processing old cached Discord messages on reconnect.

### Model Configuration
- **Default model**: `openai/gpt-5-nano` (configurable via `LLM_MODEL` env var)
- **Increased max_tokens**: Changed from 1000 to 2000 to accommodate gpt-5-nano's reasoning tokens
- **Fallback model**: `openai/gpt-4o-mini` used when primary model returns empty content with `finish_reason=length`

### Unit Test Scaffolding (New Files)
- `tests/mocks/__init__.py` — mocks module init
- `tests/mocks/mock_llm.py` — `MockLLMClient` for deterministic testing without API calls
- `tests/test_llm.py` — tests for LLM memory parsing, tool_calls extraction, finish_reason handling
- `tests/test_tools.py` — tests for `ToolExecutor` (get_projects, create_task, add_idea)
- `tests/test_chat.py` — tests for `Chat.handle_mention` tool loop and conversation handling
- `tests/test_local.py` — updated with logging for debugging

---

## Files Modified
- `src/bot.py` — concurrency locks, startup timestamp, model config via env var
- `src/llm.py` — API lock, increased max_tokens to 2000
- `src/cogs/chat.py` — (unchanged from previous session)
- `tests/test_local.py` — added logging setup

## Files Added
- `tests/mocks/__init__.py`
- `tests/mocks/mock_llm.py`
- `tests/test_llm.py`
- `tests/test_tools.py`
- `tests/test_chat.py`

---

## Environment Variables
- `DISCORD_TOKEN` — required for Discord connection
- `REQUESTY_API_KEY` — required for LLM calls
- `DATABASE_PATH` — optional, defaults to `data/brrr.db`
- `LLM_MODEL` — optional, defaults to `openai/gpt-5-nano`

Example `.env`:
```
DISCORD_TOKEN=your_token_here
REQUESTY_API_KEY=sk-xxxxx
DATABASE_PATH=data/brrr.db
LLM_MODEL=openai/gpt-5-nano
```

---

## How to Run

### Discord Bot
```powershell
python run.py
```

### Local Test Harness (without Discord)
```powershell
python tests/test_local.py
```

### Unit Tests
```powershell
python -m pytest tests/test_llm.py tests/test_tools.py tests/test_chat.py -v
```

---

## Architecture Notes

### Message Processing Flow
1. `on_message` receives Discord message
2. Check: Is message from self? → skip
3. Check: Is message before `_started_at`? → skip (prevents old message processing)
4. Check: Is bot mentioned, replied to, or "brrr" in content? → proceed
5. Acquire per-channel lock (`_channel_locks[channel_id]`)
6. Call `chat_cog.handle_mention(message)`
7. LLM call (with global `_api_lock` to serialize API requests)
8. If tool_calls returned → execute tools → second LLM call with results
9. Release locks, send response

### API Call Serialization
- `LLMClient._api_lock` ensures only one HTTP request to the LLM provider at a time
- Prevents race conditions when multiple channels/users message simultaneously
- Tool-calling flow may make 2 API calls (initial + post-tool), but they're sequential

---

## Known Issues / Caveats
- **gpt-5-nano reasoning tokens**: This model uses "reasoning tokens" internally which consume token budget. The 2000 max_tokens setting accommodates this, but very complex requests may still hit limits.
- **Fallback behavior**: If gpt-5-nano returns empty content with `finish_reason=length`, the code retries with gpt-4o-mini using a shorter prompt.

---

## Recommended Next Steps

### Immediate
1. ✅ ~~Add unit tests~~ (scaffolding complete)
2. Run and validate unit tests with `pytest`
3. Add GitHub Actions CI workflow for automated testing

### Short-term
4. Add more tools to `ToolExecutor` (e.g., `toggle_task`, `get_ideas`, `delete_task`)
5. Implement rate limiting per-user to prevent abuse
6. Add `/model` command to let users switch LLM models

### Medium-term
7. Add per-guild system prompt customization
8. Implement message summarization to keep context tokens bounded
9. Add admin toggle for tool execution per-guild

---

## Quick Commit Suggestion
```powershell
git add -A
git commit -m "Add concurrency locks, startup timestamp filter, unit test scaffolding, and model config"
```
