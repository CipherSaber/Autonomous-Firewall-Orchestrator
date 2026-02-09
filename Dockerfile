FROM python:3.11-slim

# Install system dependencies for nftables
RUN apt-get update && apt-get install -y --no-install-recommends \
    nftables \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for development
RUN useradd -m -s /bin/bash afo

# Set working directory
WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv

# Copy project files
COPY pyproject.toml README.md ./
COPY afo_mcp/ afo_mcp/
COPY tests/ tests/

# Install dependencies
RUN uv pip install --system -e ".[dev]"

# Create backup directory
RUN mkdir -p /var/lib/afo/backups && chown afo:afo /var/lib/afo/backups

# Default environment
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8765
ENV REQUIRE_APPROVAL=1
ENV ROLLBACK_TIMEOUT=30

# Expose MCP port
EXPOSE 8765

# Run as root for nftables access (required for firewall operations)
# In production, use capabilities instead: CAP_NET_ADMIN
USER root

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 8765)); s.close()"

# Default command
CMD ["python", "-m", "afo_mcp.server"]
