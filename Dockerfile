# Command-center service image (task #27). Ships the FastAPI backend that
# reuses emctl's data layer; when the SPA (task #28) is built, its static bundle
# is dropped at command_center/static and FastAPI serves it alongside the API
# (one image, one deploy -- PRD command-center §3). Infra task #29 owns the
# Cloud Run wiring, ingress lock, and Secret Manager injection of GITHUB_TOKEN
# and the OIDC/session secrets; this Dockerfile is the runnable unit it deploys.
#
# Build context is the repo root:  docker build -t command-center .

# ── frontend build stage (task #28) ────────────────────────────────────────
# Compiles the Vite SPA and emits it into command_center/static, which the
# Python image copies and FastAPI serves. Kept in a separate stage so Node and
# node_modules never reach the runtime image.
FROM node:22-slim AS frontend
# pnpm pinned to match the committed pnpm-lock.yaml, mirroring plant-log's
# Dockerfile. corepack's shim resolves whatever pnpm the ambient version policy
# points at (currently pnpm 11, whose minimumReleaseAge rule rejects freshly
# published transitive deps and fails `pnpm install --frozen-lockfile`); pinning
# the exact version corepack used before that policy landed keeps the frozen
# install deterministic.
RUN npm install -g pnpm@9.15.9
WORKDIR /build/command_center/frontend
# Types are generated from the contract, so the schema must be in place first.
COPY command_center/openapi.json /build/command_center/openapi.json
COPY command_center/frontend/package.json command_center/frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY command_center/frontend/ ./
# vite build writes to ../static -> /build/command_center/static
RUN pnpm build

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so the layer caches until the manifest changes.
# The package + its `web` extra pull FastAPI, uvicorn, httpx, pydantic(-settings),
# and itsdangerous; emctl's own deps (psycopg, alembic, sqlalchemy) come with it.
COPY pyproject.toml ./
COPY emctl/__init__.py ./emctl/__init__.py
RUN pip install ".[web]"

# Application source: the CLI/data layer it reuses, the migrations, and the API.
COPY emctl ./emctl
COPY command_center ./command_center
COPY alembic.ini ./
# Drop in the compiled SPA from the frontend stage. FastAPI mounts it at / when
# command_center/static/index.html exists (command_center/main.py) -- one image,
# one deploy (PRD command-center §3).
COPY --from=frontend /build/command_center/static ./command_center/static
# Reinstall so the console script + package metadata pick up the full source.
RUN pip install --no-deps ".[web]"

# Drop root: the service needs no write access to its own source or the
# install prefix, so run it as an unprivileged account (defence in depth for
# the ingress-locked Cloud Run surface, infra task #29).
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080
# Cloud Run provides $PORT; default to 8080 for local runs.
CMD ["sh", "-c", "uvicorn command_center.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
