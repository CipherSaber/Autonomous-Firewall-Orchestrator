# Codebase Structure

**Analysis Date:** 2026-02-10

## Directory Layout

```
AFO/
├── afo_mcp/                # MCP server + core tools + models (main package)
│   ├── __init__.py          # Package init, re-exports all models
│   ├── models.py            # Pydantic data models (FirewallRule, NetworkContext, etc.)
│   ├── security.py          # Input sanitization / shell injection prevention
│   ├── server.py            # FastMCP server entry point, tool registration
│   └── tools/               # Tool implementations
│       ├── __init__.py      # Re-exports tool functions
│       ├── conflicts.py     # Rule conflict detection (shadow, redundant, contradiction, overlap)
│       ├── deployer.py      # Safe deployment with backup + heartbeat rollback
│       ├── network.py       # System network introspection (ip addr, nft list, hostname)
│       └── validator.py     # nftables syntax validation (nft --check + structural)
├── agents/                  # LangChain agent for NL-to-rule translation
│   ├── __init__.py          # Package init (empty)
│   ├── firewall_agent.py    # Main agent: generate_rule(), chat(), LLM chain
│   ├── prompts.py           # Prompt templates (SYSTEM_PROMPT, RULE_GENERATION_PROMPT)
│   └── tools.py             # LangChain @tool wrappers around afo_mcp tools
├── db/                      # Data layer (vector store for RAG)
│   ├── __init__.py          # Package init (empty)
│   └── vector_store.py      # JSON-backed vector store: ingest, embed, retrieve
├── ui/                      # Streamlit dashboard
│   ├── __init__.py          # Package init (empty)
│   └── app.py               # Full Streamlit app: chat, pending rules, history
├── docs/                    # RAG source material
│   └── nftables_reference.md  # nftables reference guide for RAG ingestion
├── logic/                   # Placeholder for formal verification (empty)
├── tests/                   # Test suite
│   ├── __init__.py          # Package init
│   ├── test_mcp_tools.py    # Phase 1 tests: models, validator, conflicts, security
│   └── test_phase2.py       # Phase 2 tests: agent, JSON extraction, rule building, vector store
├── .devcontainer/           # VS Code dev container configuration
│   ├── devcontainer.json    # Dev container settings
│   ├── docker-compose.yml   # Dev container compose
│   ├── Dockerfile           # Dev container image
│   └── setup.sh             # Dev container setup script
├── .vectorstore/            # Persisted vector store data (generated)
│   └── embeddings.json      # Chunk texts + embeddings
├── .planning/               # GSD planning documents
│   └── codebase/            # Codebase analysis (this file)
├── pyproject.toml           # Project config: deps, scripts, build, lint
├── pytest.ini               # Pytest config (legacy, duplicates pyproject.toml)
├── Dockerfile               # Production container image
├── docker-compose.yml       # Multi-service compose (mcp-server, ui, test, dev)
├── claude.md                # Project spec / architecture guide for AI assistants
├── README.md                # Project readme
├── .env.example             # Example environment variables
└── .gitignore               # Git ignore rules
```

## Directory Purposes

**`afo_mcp/`:**
- Purpose: Core package containing MCP server, all tool implementations, data models, and security utilities
- Contains: Python modules (`.py`), organized with `tools/` subdirectory
- Key files: `server.py` (entry point), `models.py` (shared types), `tools/deployer.py` (deployment logic)

**`afo_mcp/tools/`:**
- Purpose: Individual tool implementations that perform actual firewall operations
- Contains: One module per tool domain (network, validator, conflicts, deployer)
- Key files: `conflicts.py` (349 lines, most complex), `deployer.py` (296 lines, deployment + heartbeat)

**`agents/`:**
- Purpose: LangChain-based AI agent that orchestrates NL-to-rule translation
- Contains: Agent logic, prompt templates, LangChain tool wrappers
- Key files: `firewall_agent.py` (293 lines, main agent logic with generate_rule + chat)

**`db/`:**
- Purpose: RAG vector store for nftables documentation retrieval
- Contains: Single module with ingestion, embedding, and retrieval
- Key files: `vector_store.py` (216 lines, JSON-backed store with Ollama embeddings)

**`ui/`:**
- Purpose: Streamlit web dashboard for human-in-the-loop firewall management
- Contains: Single-file Streamlit app
- Key files: `app.py` (254 lines, full dashboard with chat + approval workflow)

**`docs/`:**
- Purpose: Source material for RAG ingestion (nftables reference documentation)
- Contains: Markdown files that get chunked and embedded
- Key files: `nftables_reference.md` (8.7KB reference guide)

**`logic/`:**
- Purpose: Planned location for formal verification / symbolic conflict detection (currently empty)
- Contains: Nothing yet (placeholder per `claude.md` spec)

**`tests/`:**
- Purpose: Pytest test suite
- Contains: Test modules organized by project phase
- Key files: `test_mcp_tools.py` (320 lines, Phase 1), `test_phase2.py` (192 lines, Phase 2)

**`.vectorstore/`:**
- Purpose: Persisted vector embeddings generated by `db/vector_store.py`
- Contains: `embeddings.json` (generated, not committed ideally)
- Generated: Yes
- Committed: Yes (currently tracked)

**`.devcontainer/`:**
- Purpose: VS Code dev container configuration for consistent development environment
- Contains: Dockerfile, docker-compose, devcontainer.json, setup script
- Generated: No
- Committed: Yes

## Key File Locations

**Entry Points:**
- `afo_mcp/server.py`: MCP server (runs on port 8765)
- `ui/app.py`: Streamlit dashboard (runs on port 8501)
- `db/vector_store.py`: Document ingestion CLI (`afo-ingest` command)

**Configuration:**
- `pyproject.toml`: Dependencies, scripts (`afo-ui`, `afo-ingest`), build system, linting, pytest
- `Dockerfile`: Production container (Python 3.11-slim + nftables + iproute2)
- `docker-compose.yml`: Multi-service setup (mcp-server, ui, test, dev profiles)
- `.env.example`: Environment variable reference (existence noted only)

**Core Logic:**
- `afo_mcp/models.py`: All Pydantic models shared across the system (215 lines)
- `afo_mcp/security.py`: Shell injection prevention utilities (84 lines)
- `afo_mcp/tools/conflicts.py`: Rule conflict detection engine (349 lines)
- `afo_mcp/tools/deployer.py`: Deployment with backup + heartbeat rollback (296 lines)
- `afo_mcp/tools/network.py`: System network introspection via subprocess (186 lines)
- `afo_mcp/tools/validator.py`: nftables syntax validation (169 lines)
- `agents/firewall_agent.py`: LLM chain for NL-to-rule translation (293 lines)
- `agents/prompts.py`: Prompt templates with RAG/network context slots (69 lines)
- `agents/tools.py`: LangChain tool wrappers (109 lines)
- `db/vector_store.py`: JSON vector store with Ollama embeddings + keyword fallback (216 lines)

**Testing:**
- `tests/test_mcp_tools.py`: Models, validator, conflicts, security, integration tests
- `tests/test_phase2.py`: Agent JSON extraction, rule building, prompts, tools, vector store

## Naming Conventions

**Files:**
- `snake_case.py` for all Python modules: `firewall_agent.py`, `vector_store.py`, `test_mcp_tools.py`
- Tool modules named by domain: `network.py`, `validator.py`, `conflicts.py`, `deployer.py`
- Test files prefixed with `test_`: `test_mcp_tools.py`, `test_phase2.py`

**Directories:**
- `snake_case` for Python packages: `afo_mcp`, `afo_mcp/tools`
- Short lowercase names for top-level packages: `agents`, `db`, `ui`, `docs`, `tests`, `logic`

**Classes:**
- `PascalCase` for Pydantic models and dataclasses: `FirewallRule`, `NetworkContext`, `ParsedRule`
- `PascalCase` for test classes prefixed with `Test`: `TestModels`, `TestConflictDetection`
- `PascalCase` for enums: `RuleAction`, `ConflictType`, `DeploymentStatus`, `Protocol`

**Functions:**
- `snake_case` for public functions: `generate_rule()`, `detect_conflicts()`, `deploy_policy()`
- `_snake_case` (leading underscore) for private/internal functions: `_parse_rule()`, `_get_llm()`, `_extract_json()`

**Constants:**
- `UPPER_SNAKE_CASE`: `OLLAMA_HOST`, `BACKUP_DIR`, `ROLLBACK_TIMEOUT`, `DANGEROUS_CHARS`
- `ALL_TOOLS` in `agents/tools.py`

## Where to Add New Code

**New MCP Tool:**
1. Create implementation in `afo_mcp/tools/{tool_name}.py`
2. Add Pydantic models to `afo_mcp/models.py` if needed
3. Export from `afo_mcp/tools/__init__.py`
4. Register as `@mcp.tool()` in `afo_mcp/server.py`
5. Optionally create LangChain wrapper in `agents/tools.py` and add to `ALL_TOOLS`
6. Add tests in `tests/test_mcp_tools.py` or a new test file

**New Agent Capability:**
1. Add logic to `agents/firewall_agent.py` (new function or extend `chat()`/`generate_rule()`)
2. Add prompt templates to `agents/prompts.py`
3. Add tests in `tests/test_phase2.py` or a new test file

**New RAG Document:**
1. Add markdown file to `docs/` directory
2. Run `afo-ingest` to re-chunk and embed
3. Existing `db/vector_store.py` auto-discovers `docs/*.md` files

**New UI Feature:**
1. Add to `ui/app.py` (single-file Streamlit app)
2. Follow pattern of existing functions: `_sidebar()`, `_chat_interface()`, etc.
3. Use Streamlit session state for any new persistent data

**New Validation / Security Check:**
1. Add utility functions to `afo_mcp/security.py`
2. Import and use in the relevant tool module (`validator.py`, `deployer.py`)

**Formal Verification / Logic Auditor:**
1. Planned location is `logic/` directory (currently empty)
2. Per `claude.md` spec: should contain deterministic conflict detection and formal verification scripts
3. Import from `afo_mcp/tools/conflicts.py` or replace its logic

## Special Directories

**`.vectorstore/`:**
- Purpose: Persisted RAG embeddings (JSON file with chunk texts + float vectors)
- Generated: Yes, by `db/vector_store.py` `ingest_docs()`
- Committed: Currently tracked in git (should probably be in `.gitignore`)

**`.devcontainer/`:**
- Purpose: VS Code Remote Containers / GitHub Codespaces configuration
- Generated: No (manually authored)
- Committed: Yes

**`.planning/`:**
- Purpose: GSD planning and analysis documents
- Generated: By analysis tools
- Committed: Yes

**`logic/`:**
- Purpose: Future home for symbolic/formal verification (Z3 solver, etc.)
- Generated: No
- Committed: Yes (empty directory)

---

*Structure analysis: 2026-02-10*
