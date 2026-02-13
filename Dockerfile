FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck, git for pip git deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock README.md ./

# Copy source code
COPY src/ src/
COPY web/ web/

# Copy config (for library paths)
COPY config.toml ./

# Install dependencies
RUN uv sync --frozen

# Expose backend port
EXPOSE 8642

# Run uvicorn (no --reload in production)
CMD ["uv", "run", "uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8642"]
