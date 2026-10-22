# Music Minion web image: built from a clean `git archive`, runs as uid 1000.
# Config and secrets are mounted at runtime, never baked in.

# --- Frontend: build the Vite bundle -----------------------------------------
FROM node:24-slim AS frontend
WORKDIR /build

# Manifests first so `npm ci` stays cached until dependencies change. The
# lockfile covers every workspace, so mobile's manifest must be present too.
COPY package.json package-lock.json ./
COPY shared/package.json shared/
COPY web/frontend/package.json web/frontend/
COPY mobile/package.json mobile/
RUN npm ci --workspace web/frontend --no-audit --no-fund

COPY shared/ shared/
COPY web/frontend/ web/frontend/
# vite generates routeTree.gen.ts, which tsc needs, so vite runs first
RUN cd web/frontend && npx vite build && npx tsc -b

# --- Python: resolve the venv ------------------------------------------------
FROM python:3.12-slim AS python-build
COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /usr/local/bin/uv
# git: serato-crate is a git dependency
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ src/
RUN uv sync --frozen --no-dev

# --- Runtime -----------------------------------------------------------------
FROM python:3.12-slim
# ffmpeg: waveforms; curl: compose healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1000 kevin && useradd -u 1000 -g 1000 -m -d /home/kevin kevin

WORKDIR /app
COPY --from=python-build /app/.venv .venv
COPY src/ src/
COPY web/__init__.py web/
COPY web/backend/ web/backend/
COPY --from=frontend /build/web/frontend/dist web/frontend/dist

# Same HOME as the pi host, so ~/Music and ~/.local/share resolve identically
ENV PATH=/app/.venv/bin:$PATH HOME=/home/kevin PYTHONUNBUFFERED=1
USER 1000:1000
EXPOSE 8642

# WS ping flags: uvicorn's default 20s timeout dropped sockets during pi stalls
CMD ["uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8642", \
     "--ws-ping-interval", "25", "--ws-ping-timeout", "120"]
