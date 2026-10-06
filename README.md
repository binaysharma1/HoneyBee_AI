# Honeybee AI

A personalized, local-first AI chat workspace with long-term memory, built on FastAPI, PostgreSQL + pgvector, mem0, and any OpenAI-compatible model endpoint (local or cloud).

---

## Features

- **Multi-user auth** — email/password signup & login, bcrypt hashing, JWT (HS256) sessions.
- **Real chat history** — full conversation and message rows stored in PostgreSQL, replayed into the LLM.
- **Long-term memory with mem0 + pgvector** — every message is distilled into short facts and stored via mem0 on the same Postgres (embeddings); next messages retrieve the relevant facts before generating.
- **Dedup on insert** — simple containment + difflib + word-overlap similarity checks stop repeat facts ("Hobby: Hiking" vs "Hiking - Hobby").
- **Optional cloud model** — Groq free tier, NVIDIA NIM, or local via LM Studio; switching via one `.env` variable.
- **Real-time web search with sources** — messages that look current/live are routed through `ddgs` to DuckDuckGo results; sources are returned to the UI and the model is instructed to cite them as `[1]`, `[2]`, and `[3]`.
- **Model-agnostic** — same FastAPI routes work with `.env`-selected providers (`groq`, `nvidia`, `local`).
- **Web workspace** — landing page, login/signup, chat interface with Recent Chats, Context & Inspector panel, tools drawer, and dedicated Projects, Memories, Tools, Files, and Tasks pages.

---

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI |
| DB | PostgreSQL, SQLAlchemy 2, Alembic |
| Auth | bcrypt, PyJWT HS256 |
| Memory | mem0ai with pgvector provider |
| LLM | Groq, NVIDIA NIM, or local LM Studio |
| Search | `ddgs` DuckDuckGo search |
| Frontend | Tailwind CSS CDN, Font Awesome |

---

## Project layout

```
src/
├── frontend/
│   ├── index.html          # landing page
│   ├── login.html          # JWT login
│   ├── signup.html         # account creation
│   ├── chat.html           # main chat workspace
│   └── projects.html / memories.html / tools.html / files.html / tasks.html
└── system/
    ├── main.py             # FastAPI app, pages, auth, chat, conversations, memories
    ├── database.py         # engine + session
    ├── models.py           # User / Conversation / Message SQLAlchemy models
    ├── auth.py             # hash, jwt, get_current_user
    ├── memory.py           # mem0 client + store + dedup + search + facts
    ├── model.py             # OpenAI-compatible LLM client per provider
    ├── config.py           # dotenv loader + defaults
    └── web.py               # DuckDuckGo search and source formatting
alembic.ini / alembic/      # migrations pointing at same DB
pyproject.toml / uv.lock     # package metadata and locked dependencies
.env                        # secrets (not committed)
```

## Web and API surface

`system.main` serves the frontend and exposes the backend used by the pages:

| Route | Purpose |
|---|---|
| `GET /` | Landing page |
| `GET /login`, `GET /signup` | Authentication pages |
| `GET /chat` or `GET /ai` | Chat workspace |
| `GET /projects`, `/memories`, `/tools`, `/files`, `/tasks` | Workspace sections |
| `POST /api/auth/signup` | Create a user and issue a JWT |
| `POST /api/auth/login` | Authenticate and issue a JWT |
| `GET /api/auth/me` | Return the authenticated user |
| `GET /api/conversations` | List the user's conversations |
| `POST /api/conversations` | Create an empty conversation |
| `GET /api/conversations/{id}/messages` | Load conversation history |
| `DELETE /api/conversations/{id}` | Delete a conversation and its messages |
| `POST /api/ai` | Generate a reply, persist the exchange, search memory, and optionally search the web |
| `GET /api/memories` | List stored facts for the authenticated user |
| `DELETE /api/memories/{id}` / `DELETE /api/memories` | Delete one or all stored facts |
| `GET /api/health` or `/health` | Report application and provider status |

The Projects, Tools, Files, and Tasks data endpoints currently return the empty `SECTION_DATA` shape from `main.py`. Their pages and AI query controls are wired into the workspace, but persistent CRUD for those sections is not implemented yet.

## Setup (Arch)

### 1. Dependencies
```
sudo pacman -S postgresql pgvector
postgresql -D /var/lib/postgres/data initdb   # usually a systemd service
sudo systemctl enable --now postgresql

uv sync
```

### 2. Create the honeybee database
```
psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE honeybee_ai"
psql -h 127.0.0.1 -U postgres -d honeybee_ai -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 3. `.env`
```
DATABASE_URL=postgresql+psycopg://postgres:<your-password>@127.0.0.1:5432/honeybee_ai
JWT_SECRET=009e2...   # or any strong random string
JWT_ALGORITHM=HS256
JWT_EXPIRE_DAYS=7

HONEYBEE_PROVIDER=groq   # groq | local | nvidia

# groq
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_API_KEY=gsk_...
GROQ_MODEL=qwen/qwen3.8-27b

# local (LM Studio)
HONEYBEE_MODEL=phi-3.5-mini-instruct
HONEYBEE_MODEL_URL=http://127.0.0.1:1234/v1
HONEYBEE_API_KEY=lm-studio

# nvidia (if network access is available)
NVIDIA_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_API_KEY=nvapi-...

# Embeddings (reuse local server for now)
HONEYBEE_EMBEDDING_MODEL=text-embedding-embeddinggemma-300m-qat
HONEYBEE_EMBEDDING_DIMS=768
HONEYBEE_EMBEDDING_BASE_URL=http://127.0.0.1:1234/v1
```

### 4. Migrations
```
uv run alembic revision --autogenerate -m "initial"
uv run alembic upgrade head
```

### 5. Run
```
uv run ai
```
Open `http://127.0.0.1:8000` in browser. Signup first; `/chat` then shows the workspace, with pgvector facts carrying over across new conversations.

---

## How chat and memory work

Every `POST /api/ai` call, in order :

1. Load conversation_id messages from `messages` → chat history
2. `search_memory(user_id, query)` → mem0/pgvector rows via similarity plus a keyword boost
3. Prompt: `system (identity + facts)` + conversation history + user message to LLM provider
4. `_needs_web_search(...)` decides whether the request needs live data; `web.search_web(...)` fetches up to three DuckDuckGo results when needed
5. After the LLM responds, save the exchange in `messages`
6. `add_memory(...)` on the user's message
   - extract novel facts with compact LLM pass (`extract_facts`)
   - drop exact/substring/semantic duplicates and junk formatting
   - if still new, store in `honeybee_memories` (pgvector, 768-dim Gemma embeddings)
7. Facts are also returned via `GET /api/memories` and deleted via `DELETE /api/memories/{id}`.

If mem0 or pgvector cannot initialize, `memory.py` logs the failure and chat continues without long-term memory.

## Recent development

The current `main` history includes these milestones:

- `d258409` — added web search integration, NVIDIA provider support, frontend maintenance, and locked dependencies.
- `8ccadb8` — expanded the README and documented the database-backed AI workspace.
- `75537f5` — fixed model and memory integration, including provider configuration and fact deduplication.
- `77110de` — added authentication, SQLAlchemy persistence, Alembic migrations, and the database models.
- `0d27b5a` — connected the frontend pages to backend routes and replaced the original frontend entry point.

## Dev commands

| command | purpose |
|---|---|
| `uv run ai` | FastAPI + uvicorn |
| `uv run alembic upgrade head` | apply schema migrations |
| `uv run alembic revision --autogenerate` | new migration |
| `curl -X POST .../api/ai -H 'Authorization: Bearer ...'` | manual chat |

### Notes

- If you switch providers, **restart the server** — uvicorn only watches `.py` files, not `.env`.
- `.env` is gitignored; keep all private keys out of GitHub.
