FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy all source files first (needed for uv sync to build local package)
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY web/backend/ ./web/backend/

# Create empty README.md if referenced by pyproject.toml
RUN touch README.md

# Install dependencies
RUN uv sync --frozen --no-dev

# Set Python path
ENV PYTHONPATH=/app/src:/app

# Expose port
EXPOSE 8000

# Run the backend
CMD ["uv", "run", "uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
