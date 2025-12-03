# 🚀 BRRR Bot

**The first weekend project from the Ussyverse Discord community!**

BRRR Bot is an AI-powered Discord bot that helps makers ship weekly coding projects fast. It combines project management, idea tracking, and conversational AI to keep you productive and motivated.

🌐 **Learn more about the Ussyverse and join our community:** [https://ussy.host](https://ussy.host)

---

## What is BRRR Bot?

BRRR Bot is a Discord bot that goes **BRRRRRRRR** — fast, efficient, and high-energy! It's designed to help developers and makers:

- **Track weekly projects** with checklists and progress tracking
- **Capture ideas** before they slip away
- **Run retrospectives** to celebrate wins and learn from blockers
- **Chat naturally** with an AI that remembers you

### Key Features

| Feature | Description |
|---------|-------------|
| 📋 **Project Management** | Create, track, and archive projects with task checklists |
| 💡 **Idea Pool** | Capture ideas quickly and turn them into projects when ready |
| 📅 **Weekly Rhythm** | Start weeks, run retros, track progress over time |
| 🧠 **Memory System** | The bot remembers things about you across conversations |
| 🤖 **AI Chat** | Conversational AI powered by LLM (GPT-5, GPT-4o, etc.) |
| 🎭 **Persona System** | Customize how the bot responds to you |
| 🔄 **Bot-to-Bot** | Unlike most bots, BRRR responds to other bots too! |

---

## Refactor & Improvements (Dec 3, 2025) ✅

This release consolidates the bot's system prompts and tool schemas into centralized files and adds several enhancements to tool handling and management, improving maintainability and user experience.

Highlights:

- System prompts are now in `src/prompts.py` for easy customization and future per-guild overrides.
- Tool schemas are moved to `src/tool_schemas.py`. This makes adding and documenting tools simpler.
- New tools available: `create_project`, `get_project_info`, `archive_project`, `get_tasks`, `toggle_task`, `delete_task`, `get_ideas`, and `delete_idea`.
- `create_project` tool enables the bot to create a new project before adding tasks instead of assuming a project exists.
- The Chat handler (`src/cogs/chat.py`) now supports multi-round tool calling, allowing the LLM to call tools recursively (e.g., create project → add tasks in the same user request).
- The LLM client (`src/llm.py`) now delegates prompt construction to `src/prompts.py`, and the generator functions (`generate_project_plan`, `generate_retro_summary`) use the centralized prompts.
- Tool execution logic is centralized in `src/tools.py` via `ToolExecutor`.

Testing and future work:

- Tests for prompt building and tool schema formats were updated and pass. Some integration tests require additional context fixtures and may be updated in a follow-up.
- Consider adding per-guild system prompt customization and more tool actions like toggling task ownership and role-based execution logic.

---

## How It Works

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Discord Server                         │
│                                                             │
│   User: "@brrr create a project for my new API"            │
│                           │                                 │
└───────────────────────────┼─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                       BRRR Bot                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   bot.py    │  │   cogs/     │  │     database.py     │ │
│  │  (events)   │──│  (commands) │──│  (SQLite + aiosqlite)│ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│         │                                    ▲              │
│         ▼                                    │              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                      llm.py                          │   │
│  │         LLM Client (Requesty.ai / OpenAI)           │   │
│  │                                                      │   │
│  │  ┌─────────────┐    ┌──────────────────────────┐   │   │
│  │  │ System      │    │      Tool Calls          │   │   │
│  │  │ Prompt +    │───▶│  • get_projects          │───┼───┘
│  │  │ User Msg    │    │  • create_project        │   │
│  │  └─────────────┘    │  • add_task              │   │
│  │                     │  • add_idea              │   │
│  │                     │  • get_ideas             │   │
│  │                     └──────────────────────────┘   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### LLM Integration with Tool Calls

BRRR Bot uses **function calling** (tool calls) to interact with the database. When you chat with the bot:

1. **Your message** is sent to the LLM with a system prompt and available tools
2. The LLM decides if it needs to **call a tool** (e.g., `get_projects`, `create_project`)
3. If tools are called, the bot **executes them** against the SQLite database
4. Tool results are sent back to the LLM for a **final response**
5. The response is posted to Discord

**Example flow:**
```
User: "brrr what projects do I have?"
  │
  ▼
LLM receives: system prompt + user message + tool schemas
  │
  ▼
LLM returns: tool_call: get_projects(status="active")
  │
  ▼
Bot executes: SELECT * FROM projects WHERE guild_id=? AND status='active'
  │
  ▼
LLM receives: tool results (project list)
  │
  ▼
LLM returns: "You have 2 active projects: 1) Slopbot 2) Weekend API"
  │
  ▼
Bot sends response to Discord
```

### Available Tools

The LLM can use these tools to interact with your data:

| Tool | Description |
|------|-------------|
| `get_projects` | List projects (filter by status) |
| `create_project` | Create a new project |
| `create_task` | Add a task to a project checklist |
| `add_idea` | Save an idea to the idea pool |
| `get_ideas` | List saved ideas |

### Memory System

The bot extracts and remembers information about you during conversations:

- **Skills**: Programming languages, frameworks you know
- **Interests**: Topics you're excited about
- **Current projects**: What you're working on
- **Preferences**: Timezone, preferred name, etc.

Memories persist across sessions and help the bot give more relevant responses.

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/mojomast/ussybiot.git
cd ussybiot
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
```

Required environment variables:
```env
DISCORD_TOKEN=your_discord_bot_token
REQUESTY_API_KEY=your_requesty_api_key
```

Optional:
```env
LLM_MODEL=openai/gpt-5-mini    # Default model
DATABASE_PATH=data/brrr.db      # Database location
```

> ⚠️ **Security Note:** The `.env` file is in `.gitignore` — never commit your API keys!

### 3. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application → Bot
3. Enable these intents:
   - ✅ Message Content Intent
   - ✅ Server Members Intent
4. Copy the bot token to `.env`
5. OAuth2 → URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Permissions: Send Messages, Embed Links, Read Message History, Use Slash Commands
6. Invite the bot to your server

### 4. Run

```bash
python run.py
```

---

## Commands

### 💬 Chat
Talk to the bot by **@mentioning** it, **replying** to its messages, or using `/chat`.

### 📋 Projects
| Command | Description |
|---------|-------------|
| `/project start` | Start a new project (modal) |
| `/project status` | List all projects |
| `/project info <id>` | View project details |
| `/project archive <id>` | Archive a project |
| `/project checklist add` | Add a task |
| `/project checklist list` | View/toggle tasks |
| `/project checklist toggle` | Toggle task completion |
| `/project checklist remove` | Remove a task |

### 📅 Weekly
| Command | Description |
|---------|-------------|
| `/week start` | Post weekly overview |
| `/week retro` | AI-generated retrospective |
| `/week summary` | Quick progress summary |

### 💡 Ideas
| Command | Description |
|---------|-------------|
| `/idea add` | Add idea (modal) |
| `/idea quick <title>` | Quick add idea |
| `/idea list` | Browse all ideas |
| `/idea pick` | Turn idea into project |
| `/idea random` | Get a random idea |
| `/idea delete` | Delete an idea |

### 🧠 Memory
| Command | Description |
|---------|-------------|
| `/memory show` | See what the bot remembers |
| `/memory add <key> <value>` | Manually add a memory |
| `/memory forget <key>` | Remove a memory |
| `/memory clear` | Clear all your memories |

### 🎭 Persona
| Command | Description |
|---------|-------------|
| `/persona set` | Set custom instructions |
| `/persona preset` | Use a preset persona |
| `/persona show` | View current persona |
| `/persona clear` | Reset to default |

### 🔧 Utility
| Command | Description |
|---------|-------------|
| `/ping` | Latency check |
| `/brrr` | Bot status |
| `/help` | Show all commands |

---

## Project Structure

```
potw01/
├── run.py              # Entry point
├── requirements.txt    # Python dependencies
├── .env.example        # Environment template
├── .gitignore          # Git ignore (includes .env, logs/, data/)
│
├── src/
│   ├── bot.py          # Main bot, event handlers, startup
│   ├── database.py     # SQLite database (aiosqlite)
│   ├── llm.py          # LLM client (Requesty.ai/OpenAI)
│   ├── tools.py        # Tool definitions for function calling
│   └── cogs/
│       ├── chat.py     # Chat + memory + persona commands
│       ├── projects.py # Project management commands
│       ├── weekly.py   # Weekly workflow commands
│       └── ideas.py    # Idea pool commands
│
├── data/
│   └── brrr.db         # SQLite database (auto-created)
│
├── logs/               # Log files (timestamped per session)
│
└── tests/
    ├── test_llm.py     # LLM client tests
    ├── test_tools.py   # Tool executor tests
    ├── test_chat.py    # Chat cog tests
    └── mocks/          # Mock objects for testing
```

---

## Database Schema

| Table | Purpose |
|-------|---------|
| `projects` | Project tracking (title, description, status, owners) |
| `tasks` | Project checklists (linked to projects) |
| `ideas` | Idea pool (title, description, tags) |
| `guild_config` | Per-server settings |
| `user_memories` | What the bot remembers about users |
| `conversation_history` | Recent chat history for context |

---

## Development

### Running Tests

```bash
python -m pytest tests/ -v
```

### Logging

Logs are written to `logs/brrr_YYYYMMDD_HHMMSS.log` on each bot startup. DEBUG level goes to file, INFO level to console.

### Contributing

This is a community project from the Ussyverse! Feel free to:
- Report issues
- Suggest features
- Submit PRs

Join the community at [https://ussy.host](https://ussy.host) to discuss ideas and collaborate!

---

## Tech Stack

- **Python 3.10+**
- **discord.py** - Discord API wrapper
- **aiosqlite** - Async SQLite
- **aiohttp** - Async HTTP client
- **Requesty.ai** - LLM API router (supports OpenAI, Anthropic, etc.)

---

## License

MIT — Go make it **BRRRRRRRR**! 🏎️💨

---

<p align="center">
  <i>Built with ❤️ by the Ussyverse community</i><br>
  <a href="https://ussy.host">https://ussy.host</a>
</p>
