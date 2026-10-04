## Honeybee AI

FastAPI gateway for an OpenAI-compatible local model running on port `1234`.

Install dependencies and start the API:

```bash
uv sync
uv run ai
```

Open `http://127.0.0.1:8000/ai` in a browser after starting the API. The page sends messages to `POST /api/ai`. Configure the model with `HONEYBEE_MODEL_URL`, `HONEYBEE_MODEL`, and `HONEYBEE_API_KEY`.
