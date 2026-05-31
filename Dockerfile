# syntax=docker/dockerfile:1

# --- Build stage: produce a wheel; build tooling stays out of the final image.
FROM python:3.12-slim AS builder

WORKDIR /build

# Only the files needed to build the wheel.
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Build a wheel for the package (no deps here; they are resolved in the final
# stage so pip can cache and the build layer stays small).
RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /dist

# --- Final stage: a clean runtime image with only the installed package.
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install the built wheel plus its runtime dependencies — no source tree, no
# editable install, no build backend in the final image.
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl \
    && rm -f /tmp/*.whl

EXPOSE 8000

# Bind all interfaces inside the container so the published port is reachable.
# This is an explicit, container-scoped opt-in — the server defaults to
# 127.0.0.1 when MCP_HOST is unset (see server.main()).
ENV MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

# Liveness: the published port accepts TCP connections.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import os,socket; socket.create_connection(('127.0.0.1', int(os.environ.get('MCP_PORT','8000'))), timeout=4).close()"]

# Drop privileges: run as a non-root user with minimal rights.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# Use the installed console script (no source tree / module path needed).
CMD ["bag-health-mcp", "--http", "--port", "8000"]
