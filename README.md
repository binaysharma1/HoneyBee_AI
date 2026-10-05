# Honeybee AI 🐝

A personalized, local-first AI chat workspace with long-term memory, built on FastAPI, PostgreSQL + pgvector, mem0, and any OpenAI-compatible model endpoint (local or cloud).

---

## Features

- **Multi-user auth** — email/password signup & login, bcrypt hashing, JWT (HS256) sessions.
- **Real chat history** — full conversation and message rows stored in PostgreSQL, replayed into the LLM.
- **Long-term memory with mem0 + pgvector** — every message is distilled into short facts and stored via mem0 on the same Postgres (embeddings); next messages retrieve the relevant facts before generating.
- **Dedup on insert** — simple containment + difflib + word-overlap similarity checks stop repeat facts ("Hobby: Hiking" vs "Hiking - Hobby").
- **Optional cloud model** — Ollama-style local via LM Studio, or Groq free tier for fast responses; switching via one `.env` variable.
- **Beautiful UI** — landing page, login/signup, chat interface with sidebar Recent Chats, right Context panel, tools drawer, and five app sections (Projects, Memories, Tools, Files, Tasks), all with real backend endpoints and live API wiring.

---

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI |
| DB | PostgreSQL 18, SQLAlchemy 2, Alembic |
| Auth | bcrypt, PyJWT HS256 |
| Memory | mem0ai with pgvector provider |
| LLM | Groq free or local LM Studio |
| Frontend | Tailwind CSS CDN, Font Awesome |

---

## Project layout

```
src/
├── frontend/
│   ├── index.html          # landing
│   ├── login.html / signup.html
│   ├── chat.html           # main workspace
│   └── projects/memories/tools/files/tasks.html
└── system/
    ├── main.py             # routes / ai endpoint / auth / conversations / memories
    ├── database.py         # engine + session
    ├── models.py           # User / Conversation / Message SQLAlchemy models
    ├── auth.py             # hash, jwt, get_current_user
    ├── memory.py           # mem0 client + store + dedup + search + facts
    ├── model.py            # LLM client per provider
    ├── config.py           # dotenv loader + defaults
    └── model.py            # ChatOpenAI factory logic
alembic.ini / alembic/      # migrations pointing at same DB
.env                        # secrets (not committed)
```

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
psql -h 127.0.0.1 -U postgres -d honeybee_ai -c "CREATE EXTENSION vector;"
```

### 3. `.env`
```
DATABASE_URL=postgresql+psycopg://postgres:<your-password>@127.0.0.1:5432/HoneyBee_ai
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

# nvidia (if network is reachable)
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

## How memory works

Every `POST /api/ai` call, in order :

1. Load conversation_id messages from `messages` → chat history
2. `search_memory(user_id, query)` → pgvector rows via cosine similarity + keyword boost
3. Prompt: `system (identity + facts)` + conversation history + user message to LLM provider
4. After the LLM responds, save the exchange in `messages`
5. `add_memory(...)` on that same message
   - extract novel facts with compact LLM pass (`extract_facts`)
   - drop exact/substring/semantic duplicates and junk formatting
   - if still new, store in `honeybee_memories` (pgvector, 768-dim Gemma embeddings)
6. Facts are also returned via `GET /api/memories` and deleted via `DELETE /api/memories/{id}`.

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
