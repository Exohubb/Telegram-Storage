<div align="center">

# ☁️ Airo Storage Bot

**Your personal cloud storage, powered by Telegram.**  
Store, organize, and retrieve any file — zero server storage, zero cost.

[![Telegram Bot](https://img.shields.io/badge/Telegram-@tgstorage__airo__bot-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/tgstorage_airo_bot)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![Render](https://img.shields.io/badge/Deployed_on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://render.com)

</div>

---

## What is this?

Airo Storage Bot turns a private Telegram channel into your personal cloud drive. Upload any file through the bot — documents, images, videos, audio — and access them anytime, from anywhere.

**The server never touches your file bytes.** Files are forwarded directly to your private vault channel via Telegram's `copyMessage` API. The backend stores only metadata.

### Try it now → [@tgstorage_airo_bot](https://t.me/tgstorage_airo_bot)

---

## Architecture

```
User ──► Bot ──► Your Private Vault Channel (Telegram)
                        │
                 Supabase PostgreSQL
                 (metadata only — no file bytes)
```

| Layer | Technology | Role |
|---|---|---|
| Interface | python-telegram-bot v21 | Commands, inline keyboards, state machine |
| API | FastAPI + uvicorn | Webhook receiver, health check |
| Storage | Telegram private channel | Blob storage (per user) |
| Database | Supabase PostgreSQL | File metadata, folders, tags |
| Hosting | Render (free tier) | Production deployment |

---

## Features

- 📁 **Folder organization** — create, rename, delete folders
- ⬆️ **File upload** — documents, images, video, audio, voice, stickers
- 🔍 **Search** — by name, file type, or tag
- ⭐ **Favorites** — star important files
- 🕘 **Recent files** — quick access to last 20 uploads
- 🗑 **Trash** — soft delete with restore, 30-day retention
- 🏷 **Tags** — add/remove tags, search by tag
- ⚙️ **Settings** — upload behavior, notifications, page size
- 🔧 **Setup wizard** — guided vault channel onboarding
- 🔒 **Per-user vault** — every user has their own private channel
- 👑 **Admin panel** — stats, user management

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Home dashboard |
| `/setup` | Vault setup wizard (required first) |
| `/upload` | Start an upload session |
| `/folders` | Browse folders |
| `/files` | Browse all files |
| `/search` | Search files |
| `/favorites` | Starred files |
| `/recent` | Recently uploaded |
| `/trash` | Deleted files |
| `/settings` | Bot settings |
| `/help` | Usage guide |

---

## Self-Hosting

### Prerequisites

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A [Supabase](https://supabase.com) project (free tier works)
- A [Render](https://render.com) account (free tier works)

### 1. Clone & install

```bash
git clone https://github.com/your-username/telegram-bot.git
cd telegram-bot
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `BOT_WEBHOOK_SECRET` | Random secret — `openssl rand -hex 32` |
| `DATABASE_URL` | Supabase connection string (`postgresql+asyncpg://...`) |
| `WEBHOOK_BASE_URL` | Your Render URL e.g. `https://my-bot.onrender.com` |
| `ADMIN_USER_IDS` | Comma-separated Telegram user IDs for admin access |

### 3. Set up the database

Run this in your Supabase SQL Editor:

```sql
-- Users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL UNIQUE,
    first_name VARCHAR(128) NOT NULL,
    last_name VARCHAR(128),
    username VARCHAR(128),
    is_admin BOOLEAN NOT NULL DEFAULT false,
    is_banned BOOLEAN NOT NULL DEFAULT false,
    state VARCHAR(32) NOT NULL DEFAULT 'idle',
    state_data TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Folders
CREATE TABLE folders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL,
    parent_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Files
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    label VARCHAR(256) NOT NULL,
    original_filename VARCHAR(256),
    extension VARCHAR(32),
    mime_type VARCHAR(128),
    file_size BIGINT,
    file_type VARCHAR(32) NOT NULL DEFAULT 'other',
    caption TEXT,
    source_chat_id BIGINT,
    source_message_id BIGINT,
    telegram_file_id VARCHAR(256),
    telegram_file_unique_id VARCHAR(128),
    vault_chat_id BIGINT,
    vault_message_id BIGINT,
    is_favorite BOOLEAN NOT NULL DEFAULT false,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- File tags
CREATE TABLE file_tags (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    tag VARCHAR(32) NOT NULL,
    UNIQUE(file_id, tag)
);

-- Upload sessions
CREATE TABLE upload_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- User settings
CREATE TABLE user_settings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    upload_behavior VARCHAR(16) NOT NULL DEFAULT 'ask',
    notifications_enabled BOOLEAN NOT NULL DEFAULT true,
    setup_completed BOOLEAN NOT NULL DEFAULT false,
    vault_channel_id BIGINT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Audit log
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    entity_type VARCHAR(32),
    entity_id INTEGER,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Operation failures
CREATE TABLE operation_failures (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    operation VARCHAR(64) NOT NULL,
    error_code VARCHAR(64),
    error_message TEXT,
    resolved BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Webhook idempotency
CREATE TABLE processed_updates (
    update_id BIGINT PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4. Run locally (polling mode)

No ngrok needed — polling mode works out of the box:

```bash
python run_polling.py
```

### 5. Deploy to Render

1. Push to GitHub
2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo
3. Render auto-detects `render.yaml`
4. Add your environment variables in the Render dashboard
5. Deploy — the webhook registers automatically on startup

---

## Project Structure

```
telegram-bot/
├── main.py                          # Entry point (webhook mode)
├── run_polling.py                   # Local dev runner (polling mode)
├── render.yaml                      # Render deployment config
├── requirements.txt
└── src/
    ├── api/
    │   ├── app.py                   # FastAPI factory + lifespan
    │   ├── webhook/router.py        # Telegram webhook endpoint
    │   └── health/router.py         # Health check
    ├── bot/
    │   ├── app.py                   # PTB Application + command registration
    │   ├── container.py             # Dependency injection container
    │   ├── callbacks/__init__.py    # All inline button handlers
    │   ├── formatters/__init__.py   # Message text builders
    │   ├── handlers/
    │   │   ├── commands.py          # /start, /upload, /search, etc.
    │   │   └── messages.py          # File uploads + state-based text input
    │   ├── keyboards/__init__.py    # Inline keyboard builders
    │   └── middleware/__init__.py   # User resolution + error handling
    ├── core/
    │   ├── config/settings.py       # Pydantic settings
    │   ├── constants/__init__.py    # Enums, callback prefixes, icons
    │   ├── errors/__init__.py       # Typed error hierarchy
    │   └── logging/__init__.py      # Structlog JSON logging
    ├── db/
    │   ├── engine.py                # Async SQLAlchemy engine
    │   ├── models/__init__.py       # ORM models
    │   └── repositories/            # Data access layer
    └── services/
        ├── files/file_service.py    # Upload, retrieve, delete, tags
        ├── folders/folder_service.py
        ├── search/search_service.py
        ├── storage/storage_service.py  # Vault channel operations
        └── users/user_service.py
```

---

## How the vault works

Each user sets up their own private Telegram channel as their personal vault:

1. User runs `/setup` and follows the 3-step wizard
2. They create a private channel, add the bot as admin, and paste the channel ID
3. The bot verifies access and saves the channel ID to their account
4. All uploads go to **their** channel — completely isolated from other users
5. File retrieval uses `copyMessage` — no bytes pass through the server

---

## Free-tier notes

- Single uvicorn worker to stay within Render's 512MB RAM limit
- No Redis — session state in PostgreSQL
- Render free tier spins down after 15 min inactivity — first request after idle is slow (~30s), Telegram retries automatically
- Supabase free tier: 60 connection limit — pool size of 5 is safe
- Idempotency table prevents duplicate processing on webhook retries

---

## License

MIT
