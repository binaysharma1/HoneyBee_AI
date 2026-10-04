from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .model import ModelError, ask_model

app = FastAPI(title="Honeybee AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
FRONTEND_PATH = Path(__file__).resolve().parent.parent / "frontend" / "honeybee_ai.html"


class AIRequest(BaseModel):
    message: str


@app.get("/ai", include_in_schema=False)
async def frontend() -> FileResponse:
    return FileResponse(FRONTEND_PATH, media_type="text/html")


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
