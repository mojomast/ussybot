# BRRR Bot Handoff – Testing & Setup Guide

This doc summarizes everything needed to start testing the Discord bot based on the changes we just made.

---

## 1. Tech Stack & Entry Point

- **Language**: Python 3.10+
- **Discord lib**: `discord.py` (app commands / slash commands)
- **Async DB**: `aiosqlite` with `src/database.py`
- **LLM backend**: Requesty.ai (OpenAI-compatible API)
- **Model (hardcoded)**: `openai/gpt-5-nano`
- **Entrypoint**: `run.py` → `src.bot.main()`

To run the bot from the project root:

```bash
python run.py
```

---

## 2. Dependencies

From project root:

```bash
pip install -r requirements.txt
```

`requirements.txt` contains:
- `discord.py`
- `aiosqlite`
- `python-dotenv`
- `aiohttp`

---

## 3. Environment Configuration

The bot loads environment variables via `python-dotenv` in `src/bot.py`:

```python
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
REQUESTY_API_KEY = os.getenv('REQUESTY_API_KEY')
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/brrr.db')
LLM_MODEL = 'openai/gpt-5-nano'  # hardcoded for now
```

### 3.1 Required env vars

Create a `.env` file in the project root (do **not** commit it):

```ini
DISCORD_TOKEN=your-discord-bot-token-here
REQUESTY_API_KEY=your-requesty-api-key-here
# Optional (default: data/brrr.db)
# DATABASE_PATH=data/brrr.db
```

> Note: Right now `LLM_MODEL` is hardcoded in `src/bot.py` to `openai/gpt-5-nano` for testing, so no `LLM_MODEL` env var is required.

### 3.2 Security note

- **Never commit** real `DISCORD_TOKEN` or `REQUESTY_API_KEY` to git.
- If you want a committed example, keep real values only in `.env`, and use placeholders in `.env.example`.

---

## 4. Discord Application Setup (recap)

In https://discord.com/developers/applications:

1. **Create application & bot** (if not already).
2. In **Bot** tab:
   - Enable **SERVER MEMBERS INTENT**.
   - Enable **MESSAGE CONTENT INTENT**.
3. Copy bot token → put in `.env` as `DISCORD_TOKEN`.
4. In **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`.
   - Permissions at minimum:
     - View Channels
     - Send Messages
     - Use Application Commands
     - Create Public Threads
     - Send Messages in Threads
5. Invite the bot to your server via the generated URL.

---

## 5. LLM / Requesty Integration

### 5.1 Client

`src/llm.py` defines `LLMClient` talking to Requesty’s OpenAI-compatible endpoint:

- Base URL: `https://router.requesty.ai/v1`
- Uses `Authorization: Bearer {REQUESTY_API_KEY}`
- Methods:
  - `chat(...)` – main conversational endpoint
  - `generate_project_plan(...)` – auto checklist from project title/description
  - `generate_retro_summary(...)` – short weekly retro summaries

We added:
- `_api_call()` helper with timeout + logging + error handling.
- Support for **custom persona instructions** via `custom_instructions` parameter.

### 5.2 Hardwired model

In `src/bot.py`:

```python
LLM_MODEL = 'openai/gpt-5-nano'  # Hardcoded for testing via Requesty
```

This value is passed into `LLMClient` in `BrrrBot.setup_hook`.

To test other models later, you only need to change this string (or wire it back to an env var).

---

## 6. Database

`src/database.py` manages an SQLite DB (default path `data/brrr.db`). Tables:
- `projects`
- `tasks`
- `ideas`
- `guild_config`
- `user_memories`
- `conversation_history`

Recent additions:
- `delete_idea(idea_id)`
- `get_idea(idea_id)`
- `get_task(task_id)`

These support cleaner idea/task deletion and validation.

---

## 7. Cogs & Slash Commands Overview

All cogs are loaded in `BrrrBot.setup_hook`:

```python
await self.load_extension('src.cogs.projects')
await self.load_extension('src.cogs.weekly')
await self.load_extension('src.cogs.ideas')
await self.load_extension('src.cogs.chat')
```

And slash commands are synced:

```python
await self.tree.sync()
```

### 7.1 Global commands in `src/bot.py`

- `/ping` – latency check.
- `/brrr` – status embed (latency, guild count, LLM status, active projects).
- `/help` – overview of all command groups:
  - Project
  - Weekly
  - Ideas
  - Persona
  - Memory
  - Chat/@mention

---

## 8. Projects Cog (`/project`)

Group: `/project` (guild-only).

Key commands:
- `/project start` – modal → creates project; optionally makes a thread.
- `/project status [filter]` – list projects (active/archived/all).
- `/project info <id>` – detailed project view with tasks.
- `/project archive <id>` – archive project + summary embed.

Checklist subcommands under `/project checklist`:
- `add <project_id> <task>` – adds a task.
- `list <project_id>` – shows tasks + interactive toggle buttons.
- `toggle <task_id>` – toggles a task (with validation that it belongs to the guild).
- `remove <task_id>` – **new**: delete a task with confirmation message.

LLM integration:
- After `/project start`, if description is provided and LLM is configured, it will auto-generate up to 10 checklist tasks using `generate_project_plan`.

---

## 9. Ideas Cog (`/idea`)

Group: `/idea` (guild-only).

Commands:
- `/idea add` – modal with title/description/tags.
- `/idea quick <title>` – fast add.
- `/idea list [show_used]` – list ideas, show status (available/used).
- `/idea pick` – dropdown to convert an idea to a project (uses `ProjectModal`).
- `/idea random` – random unused idea.
- `/idea delete <id>` – delete an idea:
  - Validates idea exists & belongs to guild.
  - Only author or admin can delete.
  - Uses new `db.get_idea` + `db.delete_idea` helpers.

---

## 10. Weekly Cog (`/week`)

Group: `/week` (guild-only).

Commands:
- `/week start` – weekly overview embed:
  - Shows active projects with task progress.
  - Shows idea backlog summary.
  - Includes **Start Project** button.
- `/week retro` – runs retrospective:
  - Main summary embed.
  - One embed per active project.
  - If LLM configured, `generate_retro_summary` is called per project.
- `/week summary` – high-level stats: active projects, tasks done, completion rate.

**Important fix:**
- The **Start New Project** button now actually creates a project using the same logic as `/project start`.

---

## 11. Chat Cog – Conversation, Memory & Persona

### 11.1 Chat behavior

Two ways to chat:
- **@mention the bot** in a channel.
- Use `/chat message:"..."` (guild-only).

Flow:
1. Fetch user memories + recent conversation history from DB.
2. Extract any `persona_instructions` from memories.
3. Build message list and send to `LLMClient.chat(...)` with:
   - `messages`
   - `user_memories`
   - `user_name`
   - `custom_instructions` (the persona text)
4. Save user and assistant messages to `conversation_history`.
5. Save any new memories emitted by the LLM according to the documented JSON format.

### 11.2 Memory commands (`/memory`)

Group: `/memory` (guild-only).

- `/memory show` – shows what the bot remembers about you.
- `/memory forget <key>` – delete one memory.
- `/memory clear` – interactive confirmation → clear all your memories.
- `/memory add <key> <value>` – manually add a memory.

### 11.3 Persona commands (`/persona`)

**New feature**: lets users tweak the bot’s orientation/direction via prompting.

Group: `/persona` (guild-only).

- `/persona set`
  - Opens a modal where the user can write **custom instructions** (e.g. “be concise”, “explain like I’m a beginner”, “be very hype”).
  - Saved under memory key `persona_instructions` with context.
- `/persona show`
  - Displays the current persona text.
- `/persona clear`
  - Deletes `persona_instructions`; bot returns to default behavior.
- `/persona preset`
  - Provides predefined styles:
    - `concise`
    - `detailed`
    - `beginner`
    - `technical`
    - `hype`
    - `calm`
  - Stores a preset blurb into `persona_instructions`.

Implementation details:
- `LLMClient._build_system_prompt(...)` now accepts a `custom_instructions` string.
- It:
  - Skips `persona_instructions` in the memory list (to avoid duplication).
  - Injects `custom_instructions` into the system prompt under a prominent section.
- Both mention-based chat and `/chat` pass this `custom_instructions` value into `LLMClient.chat(...)`.

Result: the bot’s behavior is **per-user, per-guild** tunable purely via prompting, without changing code.

---

## 12. What to Test First

Once `.env` is set and dependencies installed:

1. **Run the bot**
   ```bash
   python run.py
   ```
   Watch logs for:
   - `Database initialized`
   - `All cogs loaded`
   - `Commands synced`
   - `BRRR Bot is online! Logged in as ...`

2. **In Discord (same server where you invited the bot)**

   - `/ping` → should respond with `Pong` + latency.
   - `/brrr` → status embed, LLM should show as **Active** when `REQUESTY_API_KEY` is set.
   - `/help` → confirm all command sections render, including **Persona Commands**.

3. **Persona behavior**

   - Run `/persona preset` and pick e.g. **Concise**.
   - Use `/chat` or @mention and confirm responses are short and direct.
   - Switch to **Detailed** and verify longer explanations.
   - Use `/persona set` to write your own style and confirm it takes effect.

4. **Projects / Weekly flow**

   - `/project start` → create a project; check thread creation and auto-tasks (if description + LLM).
   - `/project checklist add` / `list` / `toggle` / `remove`.
   - `/week start` → weekly overview + **Start New Project** button.
   - Click **Start New Project** and confirm a project is created.
   - `/week retro` → see retro summaries; if LLM is configured, check AI summaries section.

5. **Ideas flow**

   - `/idea add` or `/idea quick` → create idea.
   - `/idea list` → confirm idea appears.
   - `/idea pick` → convert idea into project & mark it used.
   - `/idea delete <id>` → ensure only author/admin can delete.

6. **Memory flow**

   - Chat a bit so the bot learns something.
   - `/memory show` → confirm it appears.
   - `/memory forget <key>` or `/memory clear` → verify deletion.

---

## 13. Future: Fine-Tunable Models

Right now, the only hardwired piece is the model name:

```python
LLM_MODEL = 'openai/gpt-5-nano'
```

To move toward **fine-tunable / per-model configuration** later, some options:

- Use `LLM_MODEL` from env again and set per-environment model names (e.g. fine-tuned variants).
- Add a small table in DB (or reuse `guild_config` / `user_memories`) to store preferred model per guild or per user.
- Add a `/model` command that updates that preference.
- Pass that chosen model into `LLMClient` instead of the hardcoded one.

The rest of the code (LLM client, chat cog, etc.) is already structured so that swapping the model string is localized and straightforward.

---

This should be everything you need to spin the bot up and start exercising all the flows we just wired up.
