# Use the official uv image (Python 3.12 + uv preinstalled).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy the server.
COPY server.py ./

# Tell uv to install packages into the system Python (no virtualenv needed
# inside a container). This makes the fastmcp CLI available in PATH.
ENV UV_SYSTEM_PYTHON=1

# Install the dependency declared in the PEP 723 inline metadata.
RUN uv pip install fastmcp

# The MCP server listens over HTTP so it can run as a long-lived service.
EXPOSE 8000

# FastMCP CLI runs the server with HTTP transport on all interfaces.
# The server.py uses stdio by default; the CLI overrides the transport here.
CMD ["fastmcp", "run", "server.py", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
