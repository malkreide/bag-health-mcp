FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

# Bind all interfaces inside the container so the published port is reachable.
# This is an explicit, container-scoped opt-in — the server defaults to
# 127.0.0.1 when MCP_HOST is unset (see server.main()).
ENV MCP_HOST=0.0.0.0

CMD ["python", "-m", "bag_health_mcp.server", "--http", "--port", "8000"]
