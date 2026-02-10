# Technology Stack

**Analysis Date:** 2026-02-10

## Languages

**Primary:**
- Python >=3.11 - All application code (`afo_mcp/`, `agents/`, `db/`, `ui/`)

**Secondary:**
- Bash - Dev container setup script (`.devcontainer/setup.sh`)
- Markdown - RAG source documentation (`docs/nftables_reference.md`)

## Runtime

**Environment:**
- Python 3.11 (Docker image: `python:3.11-slim`)
- Linux (requires `nftables` and `iproute2` system packages)

**Package Manager:**
- pip / uv (uv used in Docker for faster installs: `uv pip install --system`)
- Lockfile: **missing** - no `uv.lock`, `requirements.lock`, or `requirements.txt` committed

**Build System:**
- hatchling (`pyproject.toml` `[build-system]`)
- Packages included in wheel: `afo_mcp`, `agents`, `db`, `ui` (configured in `[tool.hatch.build.targets.wheel]`)

## Frameworks

**Core:**
- FastMCP >=0.4.0 - MCP (Model Context Protocol) server exposing firewall tools to LLMs (`afo_mcp/server.py`)
- LangChain >=0.3.0 - Agent orchestration, prompt chaining, tool wrappers (`agents/firewall_agent.py`, `agents/tools.py`)
- LangChain-Ollama >=0.2.0 - ChatOllama LLM integration (`agents/firewall_agent.py`)
- Pydantic >=2.0 - Data models and validation for all MCP tool inputs/outputs (`afo_mcp/models.py`)
- Streamlit >=1.38.0 - Web dashboard UI (`ui/app.py`)

**Testing:**
- pytest >=8.0 - Test runner (`tests/`)
- pytest-asyncio >=0.23 - Async test support (configured: `asyncio_mode = "auto"` in `pyproject.toml`)

**Linting/Formatting:**
- ruff >=0.4 - Linting and formatting (`pyproject.toml` `[tool.ruff]`)

## Key Dependencies

**Critical:**
- `fastmcp` >=0.4.0 - Core protocol server; the MCP server is the backbone of the architecture (`afo_mcp/server.py`)
- `langchain` >=0.3.0 - Agent logic, prompt templates, output parsing (`agents/`)
- `langchain-ollama` >=0.2.0 - LLM inference via local Ollama instance (`agents/firewall_agent.py`)
- `langchain-text-splitters` >=0.3.0 - Document chunking for RAG ingestion (`db/vector_store.py`)
- `pydantic` >=2.0 - Schema enforcement for all data models (`afo_mcp/models.py`)
- `streamlit` >=1.38.0 - Human-in-the-loop approval dashboard (`ui/app.py`)

**Infrastructure:**
- `httpx` >=0.27.0 - HTTP client for Ollama embedding API calls (`db/vector_store.py`)
- `python-dotenv` >=1.0.0 - Environment variable loading from `.env` files (`afo_mcp/server.py`)

**System Dependencies (non-Python):**
- `nftables` - Linux firewall framework; invoked via `subprocess` (`nft` CLI) for rule validation, listing, and deployment
- `iproute2` - Network utilities; `ip addr show` and `ip link show` invoked via `subprocess` for network context

## Configuration

**Environment Variables:**
- `MCP_HOST` - MCP server bind address (default: `127.0.0.1`)
- `MCP_PORT` - MCP server port (default: `8765`)
- `OLLAMA_HOST` - Ollama API URL (default: `http://localhost:11434`)
- `OLLAMA_MODEL` - LLM model name (default: `qwen2.5-coder:3b`)
- `EMBED_MODEL` - Embedding model for RAG (default: `nomic-embed-text`)
- `REQUIRE_APPROVAL` - Require explicit approval for deployments, `1`=enabled (default: `1`)
- `ROLLBACK_TIMEOUT` - Auto-rollback timeout in seconds (default: `30`)
- Configured via `.env` file (loaded by `python-dotenv`) or Docker environment
- Template: `.env.example`

**Build/Project:**
- `pyproject.toml` - All project metadata, dependencies, tool config, scripts, and build settings
- `pytest.ini` - Custom pytest markers (`integration`)

**Entry Points (defined in `pyproject.toml` `[project.scripts]`):**
- `afo-ui` -> `ui.app:main` (Streamlit dashboard)
- `afo-ingest` -> `db.vector_store:ingest_docs_cli` (RAG document ingestion)
- MCP server run: `python -m afo_mcp.server` (direct module execution)

## Docker

**Production Dockerfile:** `Dockerfile`
- Base: `python:3.11-slim`
- Non-root user `afo` for runtime
- Healthcheck on MCP port (TCP socket check)
- Exposes ports: `8765` (MCP), `8501` (Streamlit)
- Default CMD: `python -m afo_mcp.server`

**Docker Compose:** `docker-compose.yml`
- `mcp-server` - MCP server on `127.0.0.1:8765`
- `ui` - Streamlit on `127.0.0.1:8501` (depends on `mcp-server`)
- `test` - Test runner (profile: `test`)
- `dev` - Dev shell with `NET_ADMIN` capability (profile: `dev`)
- Named volumes: `afo-backups`, `afo-chromadb`
- Internal bridge network: `afo-network`

**Dev Container:** `.devcontainer/`
- Separate `Dockerfile` and `docker-compose.yml` for VS Code dev containers
- Adds `curl`, `git` to base image
- Mounts full project as workspace
- `NET_ADMIN` capability enabled for nftables testing
- Post-create script: `.devcontainer/setup.sh` (installs deps, checks Ollama, ingests docs)

## Platform Requirements

**Development:**
- Python 3.11+
- Docker and Docker Compose (recommended)
- Ollama running on host with models: `qwen2.5-coder:3b` (LLM), `nomic-embed-text` (embeddings)
- Linux recommended (nftables is Linux-only); macOS/Windows work for agent/UI dev without firewall features

**Production:**
- Linux host with nftables installed
- `NET_ADMIN` capability (or root) for firewall rule management
- Ollama instance accessible at configured `OLLAMA_HOST`
- Docker deployment (containerized)

---

*Stack analysis: 2026-02-10*
