# Honeybee AI 🐝

A personalized, local-first AI chat workspace with long-term memory, document analyzer, real-time web sources, and custom vibes. Built on FastAPI, PostgreSQL + pgvector, mem0, and any OpenAI-compatible LLM endpoint.

---

## Features

- **Multi-user auth** — email/password signup & login, bcrypt, JWT sessions.
- **Real chat history in PostgreSQL** — messages are loaded for context every turn, not stuffed as scratch-pad notes.
- **Personal long-term memory** — every user message is distilled into short facts via a compact LLM pass and stored per-user via `mem0`/`pgvector` collection `honeybee_memories`. These facts will appear in future chats too.
- **Document analysis** — attach PDF/DOCX/CSV/XLSX/TXT files in the chat composer; text is extracted, chunked, and vectorized into the separate `honeybee_docs` collection. In the same conversation, queries find the uploaded file's facts, without leaking to a different conversation.
- **Conversation-linked docs** — uploaded file facts are stored knowing the `conversation_id`, so another conversation only sees this conversation's files.
- **Real-time web search** — a small LLM router decides if the message needs live/current data. If it does, DuckDuckGo (`ddgs`) is queried, results are injected as citations into the system prompt, and the returned JSON contains `sources`. The UI renders those sources as numbered links, and `[1]`, `[2]`, etc. inside the reply are clickable.
- **Vibe Maker per user** — one simple text preference on `/vibe` is injected into every LLM call as the primary system style instruction.
- **Polish UI** — same charcoal/emerald India-style theme everywhere. Chat UI renders Markdown-style bold, lists, headings, inline code, code blocks, and a copy button; source links are numbered; loading state shows during document upload.

---

## Stack & Layout

| Layer | Tech |
|---|---|
| API | FastAPI + Python 3.12 |
| DB | PostgreSQL 18, SQLAlchemy 2, Alembic |
| Auth | bcyrpt, PyJWT HS256 |
| Memory | mem0ai + pgvector provider |
| Search | `ddgs` library (DuckDuckGo) + explicit router on system prompt |
| LLM | Groq (free/fast), NVIDIA NIM, or local LM Studio via `.env` |
| Frontend | HTML + Tailwind CSS CDN + Font Awesome |

```
src/
├── frontend/
│   ├── index.html          # landing
│   ├── login.html / signup.html
│   ├── chat.html           # chat, conversations sidebar, context panel, tools
│   ├── projects.html / memories.html / tools.html / files.html / tasks.html / vibe.html
│   └── honeybee favicon/small logo loaded inline on every page
└── system/
    ├── main.py             # routes, auth, chat, conversations, uploads, vibe, health
    ├── database.py         # engine + session
    ├── models.py           # User, Conversation, Message, vibe_prompt field
    ├── auth.py             # bcrypt + JWT
    ├── memory.py           # personal memory via honeybee_memories
    ├── model.py            # ChatOpenAI per provider
    ├── documents.py        # extract + chunk PDFs/docx/csv/xlsx/txt
    ├── config.py           # dotenv loader + defaults
    └── web.py              # ddgs search helpers
alembic/ + alembic.ini       # migrations
.env                         # secrets, git-ignored
```

---

## API routes overview

| Route | Description |
|---|---|
| `GET /` | Landing page |
| `GET /login`, `GET /signup` | Auth pages |
| `GET /chat`, `GET /ai` | Chat UI |
| `GET /projects`, `/memories`, `/tools`, `/files`, `/tasks`, `/vibe` | Section pages |
| `POST /api/auth/signup` | create user + JWT |
| `POST /api/auth/login` | login + JWT |
| `GET /api/auth/me` | current user info |
| `GET/POST /api/conversations` | list / create conversation |
| `GET/DELETE /api/conversations/{id}/messages` | load history / clear |
| `POST /api/ai` | chat turn: history → memory → (optional) web → LLM → save history + memory |
| `POST /api/upload` | upload one document (pdf/docx/csv/xlsx/txt) and vectorize it to `honeybee_docs` |
| `GET /api/memories`, `DELETE /api/memories/{id}`, `DELETE /api/memories` | manage personal memories |
| `GET/PUT /api/users/me/vibe` | get/set vibe prompt |
| `GET /api/health` or `GET /health` | app + provider status |

Important: `/api/upload` must include either an active `conversation_id` to upload into the current chat, or leave it empty so a new conversation-specific document store is created.

---

## Memory & document flow

**Personal facts (`honeybee_memories`)** are saved from every chat message:
```sql
add_memory(
  user_id   = current user,
  messages  = [ user_message ],
  infer=False
)
```
Soon after, `search_memory(user.id, query, conversation_id=conv.id)` finds relevant personal facts plus document facts from the current conversation, and the system prompt is enriched with them.

**Document facts (`honeybee_docs`)** are saved only during upload:
```sql
POST /api/upload
  → documents.extract_facts_for_file('report.pdf', bytes)
  → mem0_add(doc collection=honeybee_docs)
```
They are searchable only inside the same conversation by metadata `conversation_id`.

---

## How the AI is prompted per request

```system
[1]    user's vibe_prompt (if set)
[2]    "Known facts about this user: ..." from honeybee_memories
[3]    "Web search results you should cite: ..." (if web is detected)
[4]    LLM history for this conversation
[5]    user's new message
```

If `vibe_prompt` is set, it replaces the default assistant personality line with exactly what the user typed.

---

## File & web workflow

| User action | Behaviour |
|---|---|
| Upload document | extracts text, chunks it, stores in `honeybee_docs`, saves one user fact into `honeybee_memories` (“Uploaded document: X”) |
| Message in chat | loads conversation history, searches personal + doc matches, then (optional) web search if the LLM router returns `YES` |
| Web results | injected with `[1]`, `[2]` instructions; returned separately in `sources`; UI adds numbered list of links |

---

## setup

```bash
# Arch
sudo pacman -S postgresql pgvector
sudo systemctl enable --now postgresql

uv sync

psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE HoneyBee_ai"
psql -h 127.0.0.1 -U postgres -d HoneyBee_ai -c "CREATE EXTENSION IF NOT EXISTS vector;"

uv run alembic upgrade head
uv run ai
```

## Sample `.env`

```env
DATABASE_URL=postgresql+psycopg://postgres:changeme@127.0.0.1:5432/HoneyBee_ai
JWT_SECRET=replace_me
JWT_ALGORITHM=HS256
JWT_EXPIRE_DAYS=7

HONEYBEE_PROVIDER=groq       # groq | local | nvidia
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_API_KEY=gsk_...
GROQ_MODEL=qwen/qwen3.8-27b

HONEYBEE_MODEL=phi-3.5-mini-instruct
HONEYBEE_MODEL_URL=http://127.0.0.1:1234/v1
HONEYBEE_API_KEY=lm-studio

NVIDIA_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_API_KEY=nvapi-...

HONEYBEE_EMBEDDING_MODEL=text-embedding-embeddinggemma-300m-qat
HONEYBEE_EMBEDDING_DIMS=768
HONEYBEE_EMBEDDING_BASE_URL=http://127.0.0.1:1234/v1
```

`uv run ai` starts the server; frontend-only changes don’t need restart, but `.env` and Python changes do.

---

## Misc

- Old document rows were removed from `honeybee_memories`; new uploads go to `honeybee_docs` directly.
- The vibe page uses `/api/users/me/vibe` GET/PUT. It already shares the same theme as every other page.
