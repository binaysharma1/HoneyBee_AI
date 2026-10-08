FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv

RUN uv sync --frozen

COPY src src
COPY alembic alembic
COPY alembic.ini .
COPY src/frontend src/frontend
COPY README.md .

COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
