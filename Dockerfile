FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

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

CMD ["python", "-m", "bag_health_mcp.server", "--http", "--port", "8000"]
