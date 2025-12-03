# BRRR Bot MVP Plan

## 1. Core MVP Goal

- **Bot connects to Discord and joins your server.**
- **Basic workflow commands work without relying on LLM:**
  - `/ping`
  - `/brrr`
  - `/help`
  - `/project start | status | info | archive | checklist add|list|toggle`
  - `/idea add | quick | list | pick | random`
  - `/week start | retro | summary`

LLM (`REQUESTY_API_KEY`) is optional and can be added later.

---

## 2. Local Setup

- [ ] Install Python dependencies (from project root)
  - `pip install discord.py python-dotenv aiosqlite aiohttp`

- [ ] Create a `.env` file in project root

  ```ini
  DISCORD_TOKEN=your-bot-token-here

  # Optional for later:
  # REQUESTY_API_KEY=your-requesty-key
  # LLM_MODEL=openai/gpt-4o-mini
  # DATABASE_PATH=data/brrr.db
  ```

- [ ] Verify the `run.py` entrypoint

  - File: `run.py`
  - Should contain:

    ```python
    from src.bot import main

    if __name__ == '__main__':
        main()
    ```

  - This already exists; just confirm you’ll run `python run.py` from the project root.

---

## 3. Discord Developer Portal Setup

- [ ] Create a Discord application & bot (if not already)
  - Go to https://discord.com/developers/applications.
  - Create Application → Bot tab → Add Bot.

- [ ] Enable required intents
  - In the **Bot** tab:
    - **SERVER MEMBERS INTENT** → enable.
    - **MESSAGE CONTENT INTENT** → enable.
    - (Presence not required.)

- [ ] Copy the bot token
  - In the **Bot** tab, click “Reset Token” or “Copy”.
  - Paste into your `.env` as `DISCORD_TOKEN`.

- [ ] Generate an invite URL
  - Go to **OAuth2 → URL Generator**:
    - Scopes:
      - `bot`
      - `applications.commands`
    - Bot permissions (minimum):
      - View Channels
      - Send Messages
      - Use Application Commands
      - Create Public Threads (if you want project threads)
      - Send Messages in Threads
  - Copy the generated URL.

- [ ] Invite the bot to your server
  - Open the invite URL in a browser.
  - Select your server → Authorize.

---

## 4. First Run

- [ ] Start the bot

  - From project root:

    ```bash
    python run.py
    ```

- [ ] Watch console output
  - Expect logs like:
    - `Database initialized`
    - `All cogs loaded`
    - `Commands synced`
    - `BRRR Bot is online! Logged in as ...`

---

## 5. MVP Command Smoke Test (in Discord)

Once the bot shows as **online** in your server:

- [ ] `/ping`
  - Should respond with `Pong` + latency.

- [ ] `/brrr`
  - Should show:
    - Latency
    - Guild count
    - LLM: likely “Disabled” (until you set `REQUESTY_API_KEY`).
    - Active projects count (0 at first).

- [ ] `/project` commands
  - [ ] `/project start`
    - Modal pops up → fill title/description.
    - Expect:
      - Project embed in the channel.
      - Maybe a new thread if channel type is text.
  - [ ] `/project status`
    - Should list your new project with progress.
  - [ ] `/project info <id>`
    - Should show detailed info for that project.
  - [ ] `/project checklist add <id> <task>`
    - Adds a task.
  - [ ] `/project checklist list <id>`
    - Shows tasks and buttons to toggle.
  - [ ] `/project archive <id>`
    - Marks project archived and shows summary.

- [ ] `/idea` commands
  - [ ] `/idea quick "test idea"`
  - [ ] `/idea list`
    - Should show the idea.
  - [ ] `/idea pick`
    - Dropdown appears; selecting creates a project and marks idea used.
  - [ ] `/idea random`
    - Should pick from unused ideas.

- [ ] `/week` commands
  - [ ] `/week start`
    - Weekly overview embed + “Start New Project” button.
  - [ ] `/week summary`
    - Shows active project count and task completion.
  - [ ] `/week retro`
    - With at least one active project, should post retro summary embeds.
    - If no LLM key, it just skips the AI summary part.

---

## 6. After MVP Is Stable

When all the above works reliably:

- **Next steps (later):**
  - Add `REQUESTY_API_KEY` to `.env`.
  - Test:
    - Auto-generated checklists in `/project start`.
    - AI summaries in `/week retro`.
    - `/chat` command and @mention chat.
    - `/memory` commands.
