from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import auth, config, memory, web
from .database import Base, engine, get_db
from .models import Conversation, Message, User
from .model import ModelError, _client, ask_messages

app = FastAPI(title="Honeybee AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

PAGES = {
    "index": "index.html",
    "chat": "chat.html",
    "login": "login.html",
    "signup": "signup.html",
    "projects": "projects.html",
    "memories": "memories.html",
    "tools": "tools.html",
    "files": "files.html",
    "tasks": "tasks.html",
}

SECTION_DATA = {
    "projects": {"items": []},
    "tools": {"items": []},
    "files": {"items": []},
    "tasks": {"items": []},
}


class AIRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ConversationOut(BaseModel):
    id: str
    title: str
    updated_at: str


def _page(name: str) -> FileResponse:
    return FileResponse(FRONTEND_DIR / PAGES[name], media_type="text/html")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "provider": config.PROVIDER, "system": "running"}


@app.get("/health", include_in_schema=False)
async def health_alias() -> dict:
    return {"status": "ok", "provider": config.PROVIDER, "system": "running"}


@app.get("/", include_in_schema=False)
async def landing() -> FileResponse:
    return _page("index")


@app.get("/chat", include_in_schema=False)
@app.get("/ai", include_in_schema=False)
async def chat() -> FileResponse:
    return _page("chat")


@app.get("/login", include_in_schema=False)
async def login() -> FileResponse:
    return _page("login")


@app.get("/signup", include_in_schema=False)
async def signup() -> FileResponse:
    return _page("signup")


for _section in SECTION_DATA:

    def _make_page_route(section: str):
        async def route() -> FileResponse:
            return _page(section)
        return route

    def _make_data_route(section: str):
        async def route() -> dict:
            return SECTION_DATA[section]
        return route

    app.get(f"/{_section}", include_in_schema=False)(_make_page_route(_section))
    app.get(f"/api/{_section}")(_make_data_route(_section))


# Auth

@app.get("/memories", include_in_schema=False)
async def memories_page() -> FileResponse:
    return _page("memories")


@app.post("/api/auth/signup")
def signup_api(body: SignupRequest, db: Session = Depends(get_db)) -> dict:
    name = body.name.strip()
    email = body.email.strip().lower()
    if not name or len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Name required and password must be at least 6 characters")
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(name=name, email=email, password_hash=auth.hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": auth.create_token(user.id), "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.post("/api/auth/login")
def login_api(body: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"token": auth.create_token(user.id), "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.get("/api/auth/me")
def me_api(user: User = Depends(auth.get_current_user)) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email}


#  Conversations 

@app.get("/api/conversations")
def list_conversations(user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)) -> dict:
    convs = db.scalars(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    ).all()
    return {"conversations": [
        {"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat()} for c in convs
    ]}


@app.post("/api/conversations")
def create_conversation(user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)) -> dict:
    conv = Conversation(user_id=user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {"id": conv.id, "title": conv.title}


@app.get("/api/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)) -> dict:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"messages": [
        {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
        for m in conv.messages
    ]}


@app.get("/api/memories")
def list_memories_api(user: User = Depends(auth.get_current_user)) -> dict:
    return {"items": [
        {"id": m["id"], "name": (m["data"] or "").split(":")[0] if m["data"] else "Memory",
         "detail": m["data"], "badge": "Saved", "badge_class": "border-emerald-900/40 text-emeraldAccent"}
        for m in memory.list_memories(user.id)
    ]}


@app.delete("/api/memories/{memory_id}")
def delete_memory_api(memory_id: str, user: User = Depends(auth.get_current_user)) -> dict:
    if not memory.delete_memory(user.id, memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}


@app.delete("/api/memories")
def clear_memories_api(user: User = Depends(auth.get_current_user)) -> dict:
    memory.clear_memories(user.id)
    return {"ok": True}


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)) -> dict:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)  # messages cascade-delete via relationship cascade
    db.commit()
    return {"ok": True}


#  AI

async def _needs_web_search(message: str) -> bool:
    """Use the LLM as a router to decide if this question needs live web data."""
    prompt = (
        "Does this user message specifically want us to search the web for current/live information (e.g. news, latest, today, price, weather, real-time data) or named web resources?\n"
        "Simple explainers, creative writing, code, or normal general knowledge do NOT need the web.\n"
        "Reply with one word: YES or NO.\n\nMessage: " + message
    )
    try:
        response = await ask_messages([
            {"role": "system", "content": "You are a routing assistant that answers with exactly one word: YES or NO."},
            {"role": "user", "content": prompt},
        ])
        return response.strip().lower().startswith("yes")
    except ModelError:
        # Fallback: search only on explicit hints if the router fails
        return any(k in message.lower() for k in ("search", "google", "web", "news", "latest", "today", "weather", "price"))


@app.post("/api/ai")
async def ai_response(
    request: AIRequest,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if request.conversation_id:
        conv = db.get(Conversation, request.conversation_id)
        if conv is None or conv.user_id != user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = Conversation(user_id=user.id, title=message[:60])
        db.add(conv)
        db.commit()
        db.refresh(conv)

    history = [{"role": m.role, "content": m.content} for m in conv.messages]
    memories = memory.search_memory(user.id, message)

    needs_web = await _needs_web_search(message)
    web_results = web.search_web(message, limit=3) if needs_web else []
    web_context = web.format_web_context(web_results) if web_results else ""

    llm_messages = list(history)
    system_parts = ["You are Honeybee, a personalized AI assistant. You remember details the user shares across sessions and use them to give helpful, contextual answers. Keep answers concise and friendly."]
    if memories:
        system_parts.append("Known facts about this user:\n- " + "\n- ".join(memories))
    if web_context:
        system_parts.append("Web search results you should cite:\n" + web_context + "\n\nWhen you reference web results, use [1], [2], [3] style references.")
    llm_messages.insert(0, {"role": "system", "content": "\n\n".join(system_parts)})
    llm_messages.append({"role": "user", "content": message})

    try:
        reply = await ask_messages(llm_messages)
    except ModelError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    db.add(Message(conversation_id=conv.id, role="user", content=message))
    db.add(Message(conversation_id=conv.id, role="assistant", content=reply))
    if conv.title == "New conversation":
        conv.title = message[:60]
    db.commit()

    await memory.add_memory(user.id, message)

    return {
        "response": reply,
        "conversation_id": conv.id,
        "memories_used": memories,
        "sources": web_results,
    }


@app.get("/api/ai")
async def ai_response_legacy(message: str = Query(min_length=1)) -> dict:
    raise HTTPException(status_code=410, detail="Legacy endpoint removed. Use POST /api/ai with auth.")


def run() -> None:
    import uvicorn

    Base.metadata.create_all(bind=engine)
    uvicorn.run("system.main:app", host="127.0.0.1", port=8000, reload=True)
