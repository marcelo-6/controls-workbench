FROM python:3.14-slim

WORKDIR /app

# Install uv (best practice is copying the binary from Astral's image)
# Pin the version if you want fully reproducible builds.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Make sure we install only the base (runtime) dependencies:
# - --no-default-groups prevents installing tool.uv.default-groups (e.g., lint/test)
# - --no-dev excludes the dev group (alias of --no-group dev)
ENV UV_NO_DEFAULT_GROUPS=true \
    UV_NO_DEV=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy lock + project metadata first for Docker layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (creates /app/.venv)
RUN uv sync --locked --no-install-project

# Now copy the application code
COPY app ./app

# Sync again to install the project (editable by default; OK for containers)
RUN uv sync --locked --no-default-groups --no-dev

# Make venv executables (uvicorn, huey_consumer.py) available on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Default command (compose can override if desired)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
