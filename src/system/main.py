from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from .model import ModelError, ask_model

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
    "memories": {"items": []},
    "tools": {"items": []},
    "files": {"items": []},
    "tasks": {"items": []},
}


class AIRequest(BaseModel):
    message: str


def _page(name: str) -> FileResponse:
    return FileResponse(FRONTEND_DIR / PAGES[name], media_type="text/html")


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


@app.post("/api/ai")
async def ai_response(request: AIRequest) -> dict[str, str]:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        return {"response": await ask_model(message)}
    except ModelError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/ai")
async def ai_response_legacy(message: str = Query(min_length=1)) -> dict[str, str]:
    return await ai_response(AIRequest(message=message))


def run() -> None:
    import uvicorn

    uvicorn.run("system.main:app", host="127.0.0.1", port=8000, reload=True)
