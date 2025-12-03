# Next Steps / Handoff

## Purpose
This document tracks the latest development session, including new project management features, GitHub integration, task assignment, and notes functionality.

---

## Summary of Latest Changes (December 3, 2025)

### New Project Management Features

#### Task Assignment
- **Task attribution**: Tasks can now be assigned to specific users
- **Database schema**: Added `assigned_to` field to tasks table
- **New tools**: 
  - `assign_task` - Assign a task to a user
  - `unassign_task` - Remove task assignment
  - `get_user_tasks` - Get all tasks assigned to a specific user
- **Methods added**: `assign_task()`, `unassign_task()`, `get_user_tasks()` in database.py

#### Notes System
- **Project notes**: Add notes to projects for tracking decisions, updates, and general information
- **Task notes**: Add notes to tasks for tracking progress, blockers, or additional context
- **Database tables**: 
  - `project_notes` table (id, project_id, author_id, content, created_at)
  - `task_notes` table (id, task_id, author_id, content, created_at)
- **New tools**:
  - `add_project_note` - Add a note to a project
  - `get_project_notes` - Get all notes for a project
  - `add_task_note` - Add a note to a task
  - `get_task_notes` - Get all notes for a task
- **Methods added**: `add_project_note()`, `get_project_notes()`, `add_task_note()`, `get_task_notes()` in database.py

#### GitHub Integration
- **Full GitHub API integration**: Bot can now interact with GitHub repositories
- **New tools**:
  - `github_list_files` - List files in a repository at a specific path
  - `github_read_file` - Read the contents of a file from a repository
  - `github_create_pr` - Create a pull request
  - `github_list_branches` - List all branches in a repository
  - `github_update_file` - Update/create a file in a repository (creates a commit)
  - `github_list_prs` - List pull requests (open, closed, or all)
- **Requirements**: PyGithub library added to requirements.txt
- **Authentication**: Uses GITHUB_TOKEN environment variable

### Previous Features (from earlier session)

#### Concurrency & Race Condition Fixes
- **Per-channel message locking** (`src/bot.py`): Added `_channel_locks` dictionary with `asyncio.Lock` per channel to prevent concurrent message processing in the same channel.
- **Global API lock** (`src/llm.py`): Added `_api_lock` to serialize all LLM API calls, ensuring only one request is in-flight at a time.
- **Startup timestamp filtering** (`src/bot.py`): Bot now tracks `_started_at` timestamp (set in `on_ready`) and ignores any messages created before the bot was fully connected. This prevents processing old cached Discord messages on reconnect.

#### Model Configuration
#### Model Configuration
- **Default model**: `openai/gpt-5-nano` (configurable via `LLM_MODEL` env var)
- **Increased max_tokens**: Changed from 1000 to 2000 to accommodate gpt-5-nano's reasoning tokens
- **Fallback model**: `openai/gpt-4o-mini` used when primary model returns empty content with `finish_reason=length`

---

## Files Modified
- `src/database.py` — Added assigned_to field to tasks, added project_notes and task_notes tables, added all related CRUD methods
- `src/tool_schemas.py` — Added schemas for task assignment, notes, and GitHub integration tools
- `src/tools.py` — Added execution logic for all new tools (task assignment, notes, GitHub operations)
- `requirements.txt` — Added PyGithub>=2.1.0 for GitHub API integration

---

## Environment Variables
- `DISCORD_TOKEN` — required for Discord connection
- `REQUESTY_API_KEY` — required for LLM calls
- `DATABASE_PATH` — optional, defaults to `data/brrr.db`
- `LLM_MODEL` — optional, defaults to `openai/gpt-5-nano`
- `GITHUB_TOKEN` — **NEW**, optional, required for GitHub integration features (get from https://github.com/settings/tokens)

Example `.env`:
```
DISCORD_TOKEN=your_token_here
REQUESTY_API_KEY=sk-xxxxx
DATABASE_PATH=data/brrr.db
LLM_MODEL=openai/gpt-5-nano
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxx
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

### Install New Dependencies
```powershell
pip install -r requirements.txt
```

---

## New Tool Usage Examples

### Task Assignment
```
User: "@brrr assign task 5 to @alice"
Bot: [calls assign_task with task_id=5, user_id=alice's Discord ID]

User: "@brrr show me all tasks assigned to me"
Bot: [calls get_user_tasks with the user's Discord ID]

User: "@brrr unassign task 5"
Bot: [calls unassign_task with task_id=5]
```

### Notes
```
User: "@brrr add a note to project 3: We decided to use React instead of Vue"
Bot: [calls add_project_note with project_id=3, content="We decided to use React instead of Vue"]

User: "@brrr show me notes for task 7"
Bot: [calls get_task_notes with task_id=7]

User: "@brrr add a note to task 12: Blocked by API rate limit, waiting for approval"
Bot: [calls add_task_note with task_id=12, content="..."]
```

### GitHub Integration
```
User: "@brrr list files in owner/repo at docs/"
Bot: [calls github_list_files with repo="owner/repo", path="docs/"]

User: "@brrr read README.md from owner/repo"
Bot: [calls github_read_file with repo="owner/repo", path="README.md"]

User: "@brrr create a PR in owner/repo from feature-branch to main titled 'Add new feature'"
Bot: [calls github_create_pr]

User: "@brrr update the docs in owner/repo, change docs/api.md to include the new endpoint"
Bot: [calls github_update_file with appropriate parameters]

User: "@brrr show me open PRs in owner/repo"
Bot: [calls github_list_prs with repo="owner/repo", state="open"]
```

---

## Architecture Notes

### Database Schema Updates
The database now supports:
1. **Task assignments** via `assigned_to` field (user_id)
2. **Project notes** via dedicated `project_notes` table
3. **Task notes** via dedicated `task_notes` table

### Tool System
- All tool schemas centralized in `src/tool_schemas.py`
- Tool execution logic in `src/tools.py`
- GitHub tools use PyGithub library for API interaction
- All tools include proper error handling and user-friendly responses

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

---

## Known Issues / Caveats
- **GitHub token security**: Make sure GITHUB_TOKEN is kept secure and not committed to version control
- **GitHub API rate limits**: Be aware of GitHub API rate limits (typically 5,000 requests/hour for authenticated requests)
- **File size limits**: GitHub file reading is truncated at 4000 characters to prevent context overflow
- **gpt-5-nano reasoning tokens**: This model uses "reasoning tokens" internally which consume token budget. The 2000 max_tokens setting accommodates this, but very complex requests may still hit limits.

---

## Recommended Next Steps

### Immediate
1. ✅ ~~Add task assignment features~~ (complete)
2. ✅ ~~Add notes system~~ (complete)
3. ✅ ~~Add GitHub integration~~ (complete)
4. Test new features with real Discord interactions
5. Update unit tests to cover new functionality

### Short-term
6. Add GitHub webhook integration for automatic updates
7. Add project templates with pre-defined task structures
8. Implement task dependencies (task X blocks task Y)
9. Add task deadlines and reminders
10. Create slash commands for common operations (e.g., `/task assign`)

### Medium-term
11. Add visualization for project progress (charts, graphs)
12. Implement sprint planning features
13. Add time tracking for tasks
14. Create project analytics and reports
15. Add integration with other services (Jira, Trello, etc.)

---

## Quick Commit Suggestion
```powershell
git add -A
git commit -m "Add task assignment, notes system, and GitHub integration

- Add assigned_to field to tasks table for user attribution
- Add project_notes and task_notes tables with full CRUD operations
- Add 6 new GitHub integration tools (list files, read file, create PR, etc.)
- Add PyGithub dependency for GitHub API access
- Update tool schemas and execution logic for all new features"
```
