FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /usr/local/bin/uv

FROM base AS deps

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

FROM deps AS runtime

COPY api ./api
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY prompts ./prompts
COPY README.md ./
RUN uv sync --frozen --no-dev

COPY api/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
