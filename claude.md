# Project: Autonomous Firewall Orchestrator (AFO)
## Role: Senior AI Solution Architect & Cybersecurity Engineer

### 1. System Overview
The AFO is a "Verified Autonomous" system that translates Natural Language (NL) security requirements into executable policies for **OPNsense** and **nftables**. It uses a "Hybrid" approach: Generative AI for intent translation and Deterministic Logic for rule verification.

### 2. Core Tech Stack
- **Orchestration:** LangChain (Agentic RAG with ReAct logic)
- **Model:** Llama 3.1 8B / DeepSeek-Coder-V2 (Local via Ollama)
- **Context Bridge:** Model Context Protocol (MCP) using `fastmcp`
- **Vector Memory:** ChromaDB (for RAG: nftables manuals, API docs, security policies)
- **Audit Store:** PostgreSQL (for state tracking and historical logs)
- **Validation:** Python-based Logic Auditor (Symbolic conflict detection)
- **Environment:** Dockerized Dev Container

### 3. Architecture & Data Flow
1. **Input:** User provides NL intent (e.g., "Block Guest VLAN from DB Server").
2. **Retrieve (RAG):** LangChain queries **ChromaDB** for relevant `nftables` syntax and organization "Golden Rules."
3. **Context (MCP):** Agent queries the **MCP Server** to get live interface names, IPs, and existing rule-set.
4. **Draft:** LLM generates a candidate JSON policy.
5. **Verify:** The **Logic Auditor** runs a conflict-detection algorithm and `nft --check`.
6. **Approval:** Rule is displayed on the **Streamlit** dashboard for human sign-off.
7. **Deploy:** Approved rule is pushed via MCP to the target (OPNsense API or nftables CLI).



### 4. MCP Tool Definitions (Required)
The MCP server must expose the following tools to the LLM:
- `get_network_context()`: Returns interfaces, VLAN tags, and active IP ranges.
- `validate_syntax(command, platform)`: Executes a dry-run validation (e.g., `nft --check`).
- `detect_conflicts(proposed_rule)`: Compares proposed rule against active rule-set for shadowing/redundancy.
- `deploy_policy(rule_id)`: Final execution after human approval.

### 5. Strict Security Guardrails
- **No Direct Execution:** The LLM NEVER executes a command directly. It only "proposes."
- **Deterministic Supremacy:** If the Logic Auditor (Python) disagrees with the LLM, the Auditor wins.
- **Fail-Safe:** Every rule deployment must be accompanied by a temporary "Heartbeat" check; if connectivity to management is lost, the rule must auto-rollback.
- **Data Privacy:** No telemetry or logs are sent to external APIs. All inference is local.

### 6. File Structure Convention
- `/agents`: LangChain logic and prompt templates.
- `/mcp`: MCP server implementation and tool definitions.
- `/logic`: Deterministic conflict detection and formal verification scripts.
- `/db`: Schema for Postgres (Audit) and ChromaDB (Vector) ingestion.
- `/ui`: Streamlit dashboard code.
- `/docs`: RAG source material (man pages, API specs).

### 7. Key Development Rules
- Use **Pydantic** for all data modeling to ensure the LLM follows the schema.
- Follow **Zero-Trust** principles: treat every LLM output as a potential injection/hallucination.
- Prioritize **nftables** for native Linux testing and **OPNsense** for appliance integration.
- Ensure all rule changes are **Atomic** (all or nothing).