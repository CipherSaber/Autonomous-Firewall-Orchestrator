# Architecture

**Analysis Date:** 2026-02-10

## Pattern Overview

**Overall:** Layered Hybrid AI Pipeline (Generative AI + Deterministic Verification)

**Key Characteristics:**
- Natural language input is translated to structured firewall rules via LLM (Ollama)
- RAG retrieval augments LLM context with nftables documentation
- Deterministic validation and conflict detection gate all LLM output before deployment
- Human-in-the-loop approval required before any rule reaches the system
- MCP (Model Context Protocol) exposes firewall tools as a server for LLM consumption
- Heartbeat-based auto-rollback provides a safety net after deployment

## Layers

**Presentation Layer (UI):**
- Purpose: Human-in-the-loop dashboard for chat, rule approval, and deployment history
- Location: `ui/app.py`
- Contains: Streamlit app with chat interface, pending rule cards, deployment history
- Depends on: `agents.firewall_agent.chat()`, `db.vector_store.ingest_docs()`, `afo_mcp.tools.deployer.deploy_policy()`
- Used by: End users (browser on port 8501)

**Agent Layer (AI Orchestration):**
- Purpose: Translates natural language to structured FirewallRule objects using LLM + RAG
- Location: `agents/`
- Contains: LangChain agent (`firewall_agent.py`), prompt templates (`prompts.py`), LangChain tool wrappers (`tools.py`)
- Depends on: `db.vector_store.retrieve()`, `afo_mcp.tools.*`, `afo_mcp.models.*`, LangChain + Ollama
- Used by: UI layer via `chat()` and `generate_rule()`

**MCP Server Layer (Tool Interface):**
- Purpose: Exposes firewall operations as MCP tools consumable by LLMs
- Location: `afo_mcp/server.py`
- Contains: FastMCP server with 6 registered tools, each returning Pydantic model dicts
- Depends on: `afo_mcp.tools.*`, `afo_mcp.models.*`
- Used by: External LLM clients via MCP protocol (port 8765)

**Tools Layer (Core Logic):**
- Purpose: Implements all firewall operations: network context, validation, conflict detection, deployment
- Location: `afo_mcp/tools/`
- Contains: `network.py` (system introspection), `validator.py` (nft --check), `conflicts.py` (rule comparison), `deployer.py` (safe deployment with rollback)
- Depends on: `afo_mcp.models.*`, `afo_mcp.security.*`, system commands (`nft`, `ip`, `hostname`)
- Used by: MCP server layer, Agent layer (via direct import), UI layer (deployer)

**Data Models Layer:**
- Purpose: Pydantic models defining all data structures shared across the system
- Location: `afo_mcp/models.py`
- Contains: `NetworkInterface`, `NetworkContext`, `FirewallRule`, `RuleSet`, `ValidationResult`, `ConflictReport`, `DeploymentResult`, and supporting enums
- Depends on: Pydantic
- Used by: All other layers

**Security Layer:**
- Purpose: Input sanitization and validation utilities to prevent shell injection
- Location: `afo_mcp/security.py`
- Contains: `contains_dangerous_chars()`, `sanitize_for_shell()`, `is_valid_interface_name()`, `is_valid_table_name()`, `is_valid_chain_name()`
- Depends on: Python stdlib (`re`)
- Used by: `afo_mcp/tools/validator.py`, `afo_mcp/tools/deployer.py`

**RAG / Vector Store Layer:**
- Purpose: Document ingestion, embedding, and retrieval for nftables reference material
- Location: `db/vector_store.py`
- Contains: Markdown chunking, Ollama embedding, cosine similarity search, keyword fallback
- Depends on: `langchain_text_splitters`, `httpx` (Ollama API), `docs/*.md`
- Used by: Agent layer (`agents/firewall_agent.py`)

## Data Flow

**Rule Generation Flow (primary):**

1. User enters natural language request in Streamlit chat (`ui/app.py` -> `_chat_interface()`)
2. `agents.firewall_agent.chat()` classifies input as rule request or general question via keyword heuristic
3. `generate_rule()` retrieves RAG context from `db.vector_store.retrieve()` (nftables docs)
4. `generate_rule()` gathers network state via `afo_mcp.tools.network.get_network_context()`
5. System prompt is assembled with RAG context + network context + prompt template from `agents/prompts.py`
6. LLM (Ollama via `langchain_ollama.ChatOllama`) generates JSON response
7. JSON is extracted (`_extract_json()`), converted to `FirewallRule` (`_build_firewall_rule()`)
8. `FirewallRule.to_nft_command()` generates nftables CLI syntax
9. Structural validation via `afo_mcp.tools.validator.validate_rule_structure()`
10. Conflict detection via `afo_mcp.tools.conflicts.detect_conflicts()`
11. Result returned to UI with rule, nft command, explanation, validation, conflicts, RAG sources
12. User reviews rule card in "Pending Rules" tab with approve/reject buttons
13. On approval, `afo_mcp.tools.deployer.deploy_policy()` creates backup, deploys via `nft -f`, starts heartbeat
14. User must call `confirm_deployment()` to finalize, or heartbeat auto-rolls back after timeout

**MCP Server Flow (alternative):**

1. External LLM client connects to FastMCP server on port 8765
2. Client calls any of 6 registered tools: `get_network_context`, `validate_syntax`, `detect_conflicts`, `deploy_policy`, `confirm_rule_deployment`, `rollback_rule`
3. Each tool delegates to `afo_mcp/tools/*` implementations
4. Results returned as serialized Pydantic model dicts

**State Management:**
- Chat history: Streamlit `session_state.messages` (in-memory, per-session)
- Pending rules: Streamlit `session_state.pending_rules` (in-memory, per-session)
- Deployed rules: Streamlit `session_state.deployed_rules` (in-memory, per-session)
- Heartbeat state: Module-level dicts `_active_heartbeats` / `_heartbeat_threads` in `afo_mcp/tools/deployer.py` (in-memory, per-process)
- Vector store: JSON file at `.vectorstore/embeddings.json` (persisted to disk)
- Rule backups: Files at `/var/lib/afo/backups/backup_{rule_id}_{timestamp}.nft`

## Key Abstractions

**FirewallRule (Pydantic model):**
- Purpose: Structured representation of an nftables firewall rule with all match criteria and actions
- Definition: `afo_mcp/models.py` lines 74-146
- Pattern: Pydantic BaseModel with `to_nft_command()` method for serialization to nftables CLI syntax
- Used by: `agents/firewall_agent.py` (build from LLM JSON), tests

**NetworkContext (Pydantic model):**
- Purpose: Snapshot of system network state (interfaces, active ruleset, hostname)
- Definition: `afo_mcp/models.py` lines 31-41
- Pattern: Aggregates `NetworkInterface` list with system metadata
- Used by: `afo_mcp/tools/network.py`, `agents/firewall_agent.py`

**DeploymentResult (Pydantic model):**
- Purpose: Outcome of a deployment operation including status, backup path, heartbeat state
- Definition: `afo_mcp/models.py` lines 204-215
- Pattern: Result type with `DeploymentStatus` enum for state machine tracking
- Used by: `afo_mcp/tools/deployer.py`, `afo_mcp/server.py`, `ui/app.py`

**ParsedRule (dataclass):**
- Purpose: Intermediate representation for conflict detection rule comparison
- Definition: `afo_mcp/tools/conflicts.py` lines 11-25
- Pattern: Simple dataclass with extracted match fields (saddr, daddr, sport, dport, action, etc.)
- Used by: `afo_mcp/tools/conflicts.py` internal functions only

**MCP Tool Registration:**
- Purpose: Expose Python functions as tools callable by LLMs via MCP protocol
- Pattern: `@mcp.tool()` decorator on thin wrapper functions in `afo_mcp/server.py`
- Each tool delegates to implementation in `afo_mcp/tools/`, receives typed args, returns `dict`

## Entry Points

**MCP Server:**
- Location: `afo_mcp/server.py` -> `main()`
- Triggers: `python -m afo_mcp.server` or Docker CMD
- Responsibilities: Starts FastMCP server on configurable host/port, registers 6 tools

**Streamlit UI:**
- Location: `ui/app.py` -> `main()`
- Triggers: `streamlit run ui/app.py` or `afo-ui` CLI command (from pyproject.toml scripts)
- Responsibilities: Renders dashboard, handles chat, manages rule approval workflow

**Document Ingestion CLI:**
- Location: `db/vector_store.py` -> `ingest_docs_cli()`
- Triggers: `afo-ingest` CLI command (from pyproject.toml scripts) or `python -m db.vector_store`
- Responsibilities: Reads `docs/*.md`, chunks via LangChain splitters, embeds via Ollama, saves to `.vectorstore/embeddings.json`

## Error Handling

**Strategy:** Defensive returns with graceful degradation; no exceptions propagated to end users

**Patterns:**
- **Tool functions** return result models with `success: bool` and `error: str | None` fields (e.g., `DeploymentResult`, `ValidationResult`) rather than raising exceptions
- **Subprocess calls** are wrapped in try/except for `TimeoutExpired`, `FileNotFoundError`, `PermissionError` with descriptive error messages
- **LLM failures** caught in `agents/firewall_agent.py` with fallback error dicts: `{"success": False, "error": "..."}`
- **RAG retrieval** falls back from embedding-based search to keyword search when Ollama is unavailable (`db/vector_store.py`)
- **Auto-ingestion** on first UI load wrapped in bare `except Exception: pass` (`ui/app.py` line 237)
- **Heartbeat monitor** catches all exceptions during health check and triggers rollback (`afo_mcp/tools/deployer.py` line 102)

## Cross-Cutting Concerns

**Logging:** No structured logging framework. Uses `print()` statements in `afo_mcp/server.py` for startup info. No runtime logging in tools or agent.

**Validation:**
- Input sanitization via `afo_mcp/security.py` (shell injection prevention) used in validator and deployer
- Pydantic model validation on all data structures via `afo_mcp/models.py`
- Structural rule validation via `afo_mcp/tools/validator.validate_rule_structure()` (lightweight, no root)
- Full nft --check validation via `afo_mcp/tools/validator.validate_syntax()` (requires nftables + potentially root)

**Authentication:** None. MCP server binds to localhost only (127.0.0.1:8765 in docker-compose). Streamlit binds to localhost (127.0.0.1:8501). No auth layer.

**Configuration:** Environment variables loaded via `python-dotenv` in `afo_mcp/server.py`. Key vars: `MCP_HOST`, `MCP_PORT`, `REQUIRE_APPROVAL`, `ROLLBACK_TIMEOUT`, `OLLAMA_HOST`, `OLLAMA_MODEL`, `EMBED_MODEL`.

---

*Architecture analysis: 2026-02-10*
