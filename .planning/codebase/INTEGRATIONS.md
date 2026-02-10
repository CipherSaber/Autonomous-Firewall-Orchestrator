# External Integrations

**Analysis Date:** 2026-02-10

## APIs & External Services

**LLM Inference (Ollama):**
- Ollama - Local LLM inference for natural language to firewall rule translation
  - SDK/Client: `langchain-ollama` (`ChatOllama` class)
  - Connection: `agents/firewall_agent.py` lines 22-33
  - Auth: None (local service, no API key)
  - Env var: `OLLAMA_HOST` (default: `http://localhost:11434`), `OLLAMA_MODEL` (default: `qwen2.5-coder:3b`)
  - Models used:
    - `qwen2.5-coder:3b` - Chat/instruction model for rule generation
    - `nomic-embed-text` - Embedding model for RAG vector similarity
  - LLM parameters: `temperature=0.1`, `num_predict=1024` (set in `agents/firewall_agent.py` line 28-33)

**Ollama Embedding API (Direct HTTP):**
- Ollama `/api/embed` endpoint - Used for document and query embeddings
  - SDK/Client: `httpx` (direct HTTP POST)
  - Connection: `db/vector_store.py` lines 32-37
  - Endpoint: `{OLLAMA_HOST}/api/embed`
  - Payload: `{"model": EMBED_MODEL, "input": texts}`
  - Timeout: 60 seconds
  - Health check: `{OLLAMA_HOST}/api/tags` (GET, 3s timeout) in `db/vector_store.py` line 26

**Ollama Connectivity Pattern:**
- All Ollama calls include graceful fallback when Ollama is unreachable
- Vector store falls back to keyword-based search when embeddings unavailable (`db/vector_store.py` lines 179-181)
- Agent returns explicit error messages when LLM connection fails (`agents/firewall_agent.py` lines 182-187)

## MCP (Model Context Protocol) Server

**FastMCP Server:**
- Purpose: Exposes firewall orchestration tools to LLM clients via MCP protocol
- Implementation: `afo_mcp/server.py`
- Bind: `{MCP_HOST}:{MCP_PORT}` (default: `127.0.0.1:8765`)
- Transport: Managed by FastMCP (WebSocket-based)
- Tools exposed:
  - `get_network_context` - Network interface and ruleset discovery
  - `validate_syntax` - nftables dry-run validation
  - `detect_conflicts` - Rule conflict detection
  - `deploy_policy` - Safe rule deployment with rollback
  - `confirm_rule_deployment` - Finalize deployment (stop heartbeat)
  - `rollback_rule` - Manual rollback

## Data Storage

**Vector Store (Custom JSON-based):**
- Type: Custom file-based vector store (NOT ChromaDB despite some UI references)
- Implementation: `db/vector_store.py`
- Storage file: `.vectorstore/embeddings.json`
- Format: JSON with `{"chunks": [...], "embeddings": [...]}`
- Similarity: Cosine similarity computed in Python (`db/vector_store.py` lines 40-47)
- Chunking: `MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter` (chunk_size=800, overlap=100)
- Source documents: `docs/nftables_reference.md`
- Ingestion CLI: `afo-ingest` or `python -m db.vector_store`
- Persistence: Docker volume `afo-chromadb` mounted at `/app/.chromadb` (legacy name)

**File-based Backups:**
- Purpose: Stores nftables ruleset backups before deployments for rollback
- Location: `/var/lib/afo/backups/` (Docker volume `afo-backups`)
- Format: `backup_{rule_id}_{timestamp}.nft` (plain text nftables ruleset)
- Implementation: `afo_mcp/tools/deployer.py` lines 20-48

**Databases:**
- PostgreSQL - Mentioned in `claude.md` as planned audit store, **NOT implemented**
- ChromaDB - Referenced in UI spinner text (`ui/app.py` line 44), but the actual implementation uses a custom JSON store

**Caching:**
- None (vector store file serves as a persistent cache for embeddings)

## System Integrations

**nftables (Linux Firewall):**
- Purpose: Core firewall management - the primary target of generated rules
- Interface: `subprocess` calls to `nft` CLI binary
- Operations:
  - `nft list ruleset` - Read current firewall rules (`afo_mcp/tools/network.py` line 139-144, `afo_mcp/tools/deployer.py` line 33-37)
  - `nft --check -f {file}` - Dry-run syntax validation (`afo_mcp/tools/validator.py` line 53-58)
  - `nft -f {file}` - Apply rules from file (`afo_mcp/tools/deployer.py` line 230-235)
  - `nft flush ruleset` - Clear all rules before restore (`afo_mcp/tools/deployer.py` line 58-62)
- Security: Shell injection prevention via `afo_mcp/security.py` (`contains_dangerous_chars`)
- Requires: `NET_ADMIN` capability or root privileges
- Timeout: 10s for reads, 30s for deploys

**iproute2 (Network Interface Discovery):**
- Purpose: Discover network interfaces, IPs, MACs, VLANs, and link state
- Interface: `subprocess` calls to `ip` CLI binary
- Operations:
  - `ip -o addr show` - List all interface addresses (`afo_mcp/tools/network.py` line 38-43)
  - `ip -o link show` - List link info (MAC, MTU, state) (`afo_mcp/tools/network.py` line 48-53)
- Supplemented by: `/proc/net/dev` parsing for RX/TX byte statistics (`afo_mcp/tools/network.py` lines 10-30)

**hostname:**
- Purpose: Get system hostname for rule metadata
- Interface: `subprocess` call to `hostname` command (`afo_mcp/tools/network.py` lines 156-167)

## Authentication & Identity

**Auth Provider:**
- None - No authentication layer implemented
- MCP server binds to `127.0.0.1` by default (localhost-only access)
- Docker Compose restricts port exposure to `127.0.0.1` for security
- Human approval required for rule deployment (`REQUIRE_APPROVAL=1` env var)

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, etc.)

**Logs:**
- `print()` statements for server startup messages (`afo_mcp/server.py` lines 175-182)
- No structured logging framework

**Heartbeat Monitor:**
- Custom implementation in `afo_mcp/tools/deployer.py` lines 74-108
- Background thread monitors deployed rules
- Auto-rollback on timeout (configurable via `ROLLBACK_TIMEOUT`)
- In-memory state tracking via global dicts (`_active_heartbeats`, `_heartbeat_threads`)

## CI/CD & Deployment

**Hosting:**
- Self-hosted Docker containers (no cloud deployment configured)
- Docker Compose for orchestration

**CI Pipeline:**
- None detected (no `.github/workflows/`, `.gitlab-ci.yml`, or similar)

**Container Registry:**
- None configured (builds from local Dockerfile)

## Environment Configuration

**Required env vars (for full functionality):**
- `OLLAMA_HOST` - Ollama API endpoint (must be reachable)
- `OLLAMA_MODEL` - Chat model name (must be pulled in Ollama)
- `EMBED_MODEL` - Embedding model name (must be pulled in Ollama)

**Optional env vars (have defaults):**
- `MCP_HOST` - Server bind address (default: `127.0.0.1`)
- `MCP_PORT` - Server port (default: `8765`)
- `REQUIRE_APPROVAL` - Approval gate (default: `1`)
- `ROLLBACK_TIMEOUT` - Heartbeat timeout seconds (default: `30`)

**Env file:**
- `.env.example` - Template with all variables and defaults
- `.env` - Actual config (gitignored)

## Webhooks & Callbacks

**Incoming:**
- None (MCP protocol handles tool invocations, not HTTP webhooks)

**Outgoing:**
- None

## Planned but Not Implemented

Based on `claude.md` (project design document), the following integrations are planned but not yet in the codebase:

- **OPNsense API** - Firewall appliance integration (mentioned in `claude.md` section 3, step 7)
- **PostgreSQL** - Audit store for state tracking and historical logs (mentioned in `claude.md` section 2)
- **Z3 Solver** - Formal verification for conflict detection (mentioned in `afo_mcp/tools/conflicts.py` line 255)
- **ChromaDB** - Was planned as vector store; replaced with custom JSON-based implementation

---

*Integration audit: 2026-02-10*
