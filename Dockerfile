# --- Frontend: build the SvelteKit SPA as static files ---
FROM node:24-slim AS frontend
WORKDIR /frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# --- Backend: FastAPI + built SPA ---
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    APPLIFY_STATIC_DIR=/app/static \
    APPLIFY_DATA_DIR=/data/files
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY --from=frontend /frontend/build /app/static
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn applify.main:app --host 0.0.0.0 --port 8000"]
