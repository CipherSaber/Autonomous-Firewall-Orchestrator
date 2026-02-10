# Codebase Concerns

**Analysis Date:** 2026-02-10

## Tech Debt

**Empty `/logic` directory -- planned formal verification never implemented:**
- Issue: `claude.md` specifies `/logic` for "Deterministic conflict detection and formal verification scripts." The directory exists but is completely empty. The conflict detection code lives in `afo_mcp/tools/conflicts.py` instead, using regex-based heuristics rather than formal methods. A docstring at line 255 of `afo_mcp/tools/conflicts.py` explicitly states: "In Phase 2, this will be enhanced with Z3 solver for formal verification."
- Files: `/mnt/Projects/AFO/logic/` (empty), `/mnt/Projects/AFO/afo_mcp/tools/conflicts.py`
- Impact: Conflict detection is best-effort regex parsing. It misses complex nftables constructs (sets, maps, ct state, rate limits, named chains with jumps). Shadow detection uses a simplistic field-count heuristic that produces inaccurate results for many real-world rule combinations.
- Fix approach: Implement Z3-based formal verification in `/logic/`. Model nftables rules as SMT constraints and check for satisfiability of conflicting match criteria. Import from `afo_mcp/tools/conflicts.py` as the primary conflict check engine.

**Stale ChromaDB references throughout codebase:**
- Issue: The vector store was replaced with a custom JSON-based implementation in `db/vector_store.py`, but ChromaDB references remain in multiple places.
- Files: `/mnt/Projects/AFO/ui/app.py` (line 44: spinner text says "Ingesting docs into ChromaDB..."), `/mnt/Projects/AFO/docker-compose.yml` (line 51: `afo-chromadb` volume), `/mnt/Projects/AFO/claude.md` (references ChromaDB as the vector memory), `/mnt/Projects/AFO/.env.example` (line 13: comment says "for ChromaDB RAG")
- Impact: Confusing for developers; docker-compose creates an unused volume; misleading UI text.
- Fix approach: Replace all ChromaDB references with "vector store" or "JSON embedding store." Remove `afo-chromadb` volume from `docker-compose.yml`.

**Duplicate RAG retrieval in `generate_rule()`:**
- Issue: `generate_rule()` calls `retrieve()` twice with the same query -- once on line 159 for RAG context (via `_get_rag_context()` which calls `retrieve(query, n_results=5)`) and again on line 160 for `rag_sources` (calling `retrieve(user_input, n_results=3)`). Each call to `retrieve()` checks Ollama reachability and potentially computes embeddings.
- Files: `/mnt/Projects/AFO/agents/firewall_agent.py` (lines 159-160)
- Impact: Double HTTP round-trip to Ollama for embeddings. Unnecessary latency on every rule generation request.
- Fix approach: Call `retrieve()` once, extract both context text and source sections from the single result set.

**Environment variables cached at module import time:**
- Issue: `OLLAMA_HOST` and `OLLAMA_MODEL` are read from `os.environ` at module level in both `agents/firewall_agent.py` (lines 22-23) and `db/vector_store.py` (lines 19-20). The UI sidebar in `ui/app.py` (lines 33, 39) sets `os.environ` at runtime, but the module-level variables have already been cached and will not reflect UI changes.
- Files: `/mnt/Projects/AFO/agents/firewall_agent.py` (lines 22-23), `/mnt/Projects/AFO/db/vector_store.py` (lines 19-20), `/mnt/Projects/AFO/ui/app.py` (lines 33, 39)
- Impact: Changing Ollama host/model in the sidebar has no effect on `db/vector_store.py` calls. The `agents/firewall_agent.py` works partially because `_get_llm()` reads `os.environ` each call, but the module-level constants are unused -- they exist but the function reads env directly. The `db/vector_store.py` module-level vars ARE used by `_ollama_reachable()` and `_embed()`, so those cannot be changed at runtime.
- Fix approach: Read environment variables inside functions rather than at module level, or accept module-level as immutable configuration and remove the sidebar mutation pattern.

**`validate_syntax` tool omitted from `ALL_TOOLS`:**
- Issue: `agents/tools.py` defines a `validate_syntax` LangChain tool wrapper (lines 36-57) but does not include it in the `ALL_TOOLS` list (line 109). Only `get_network_context`, `validate_structure`, and `detect_conflicts` are exported.
- Files: `/mnt/Projects/AFO/agents/tools.py` (line 109)
- Impact: Any LangChain agent built with `ALL_TOOLS` cannot call syntax validation. The more powerful `nft --check` validation is inaccessible to the agent; only the lightweight structural check is available.
- Fix approach: Add `validate_syntax` to `ALL_TOOLS`. Consider whether the agent should have access to both validation tools or just one.

**Planned architecture components not implemented:**
- Issue: `claude.md` describes PostgreSQL audit store for state tracking and historical logs, and OPNsense API integration for appliance deployment. Neither exists in the codebase.
- Files: `/mnt/Projects/AFO/claude.md` (lines 12-13, 23)
- Impact: No audit trail for rule changes. No appliance integration -- only nftables CLI deployment is available.
- Fix approach: Implement PostgreSQL audit logging in `/db/` and OPNsense API client. These are substantial new features that should be planned as separate phases.

## Known Bugs

**Chat history drops assistant messages:**
- Symptoms: The `chat()` function in `agents/firewall_agent.py` iterates through conversation history but only adds `HumanMessage` entries (line 277). All assistant responses are silently dropped, so the LLM has no context of its own prior responses.
- Files: `/mnt/Projects/AFO/agents/firewall_agent.py` (lines 274-278)
- Trigger: Any multi-turn chat conversation. The LLM will repeat itself or contradict prior answers because it has no memory of what it said.
- Workaround: None currently.

**`to_nft_command()` generates redundant protocol match:**
- Symptoms: `FirewallRule.to_nft_command()` produces `meta l4proto tcp` AND `tcp dport 22` in the same rule. The `meta l4proto tcp` and `tcp dport` are equivalent protocol assertions -- nftables accepts this but it is redundant.
- Files: `/mnt/Projects/AFO/afo_mcp/models.py` (lines 118-136)
- Trigger: Any rule with both protocol and destination port set. Example output: `add rule inet filter input meta l4proto tcp tcp dport 22 accept`.
- Workaround: Not harmful but produces unnecessarily verbose rules.

**Identical branch in `to_nft_command()` protocol handling:**
- Symptoms: Lines 119-122 of `models.py` have an `if/else` block where both branches produce the exact same output (`meta l4proto {protocol.value}`). This appears to be a copy-paste error where the else branch was meant to handle ICMP differently.
- Files: `/mnt/Projects/AFO/afo_mcp/models.py` (lines 119-122)
- Trigger: Any protocol value.
- Workaround: No functional impact since both branches do the same thing, but indicates incomplete implementation.

## Security Considerations

**No authentication on MCP server or Streamlit UI:**
- Risk: Anyone with network access to ports 8765 (MCP) or 8501 (Streamlit) can generate and deploy firewall rules. While `docker-compose.yml` binds to `127.0.0.1`, the Dockerfile `ENV MCP_HOST=0.0.0.0` and the dev container may expose services more broadly.
- Files: `/mnt/Projects/AFO/afo_mcp/server.py` (line 172), `/mnt/Projects/AFO/Dockerfile` (line 34), `/mnt/Projects/AFO/docker-compose.yml` (lines 9, 40)
- Current mitigation: `docker-compose.yml` port bindings use `127.0.0.1`. Deployment requires `approved=True` flag and `REQUIRE_APPROVAL=1` environment variable.
- Recommendations: Add authentication middleware to the MCP server. Add Streamlit authentication (e.g., `st.experimental_user` or HTTP basic auth). Never bind MCP to `0.0.0.0` in production.

**Incomplete shell injection protection:**
- Risk: `security.py` defines `DANGEROUS_CHARS` as `; | & $ \` \\` but omits single quotes `'`, parentheses `()`, newlines, and redirection operators `> <`. While nftables rules are deployed via `nft -f` (file-based, not shell-executed), the temp file content is not fully sanitized.
- Files: `/mnt/Projects/AFO/afo_mcp/security.py` (line 9), `/mnt/Projects/AFO/afo_mcp/tools/deployer.py` (lines 222-226)
- Current mitigation: Rules are written to a temp file and loaded via `nft -f`, avoiding direct shell command execution. `subprocess.run()` uses list arguments (no `shell=True`).
- Recommendations: While the current approach is reasonably safe due to list-based subprocess calls, expand the character blocklist. Consider validating against an nftables grammar rather than character-level filtering.

**Sidebar environment mutation is a security smell:**
- Risk: `ui/app.py` allows users to set `OLLAMA_HOST` via sidebar text input, which is then written to `os.environ`. A malicious or confused user could point this to an attacker-controlled endpoint that mimics Ollama responses, causing the system to generate and propose rules based on attacker-controlled LLM output.
- Files: `/mnt/Projects/AFO/ui/app.py` (lines 35-39)
- Current mitigation: The human-in-the-loop approval step means rules still require manual approval before deployment.
- Recommendations: Validate `OLLAMA_HOST` input (URL format, allowed hosts). Consider making it read-only in production.

**LLM output not validated for injection in comments:**
- Risk: The LLM generates a `comment` field that is embedded directly into the nftables command string via `comment "{self.comment}"`. If the LLM produces a comment containing double quotes, the nft command could be malformed or exploited. The security check in `deployer.py` would catch `$` and backticks but double quotes in comments could break parsing.
- Files: `/mnt/Projects/AFO/afo_mcp/models.py` (line 139), `/mnt/Projects/AFO/agents/firewall_agent.py` (line 134)
- Current mitigation: Pydantic model does not constrain comment field content. The structural validator only checks for unbalanced quotes across the entire command.
- Recommendations: Sanitize or escape the `comment` field in `FirewallRule.to_nft_command()`. Strip or replace double quotes in comments.

**Silent exception swallowing in critical paths:**
- Risk: Multiple critical code paths catch `Exception` and silently pass or return `None`, hiding potential security-relevant errors.
- Files: `/mnt/Projects/AFO/agents/firewall_agent.py` (line 137: `_build_firewall_rule` catches all exceptions and returns `None`), `/mnt/Projects/AFO/db/vector_store.py` (lines 168-171: `retrieve()` swallows ingestion errors), `/mnt/Projects/AFO/ui/app.py` (lines 237-238: auto-ingest swallows all errors), `/mnt/Projects/AFO/afo_mcp/tools/deployer.py` (line 102: heartbeat monitor swallows exceptions during rollback decision)
- Current mitigation: None. No logging framework is configured.
- Recommendations: Add structured logging throughout. At minimum, log exception tracebacks in catch blocks. Never silently swallow exceptions in security-critical paths like `_build_firewall_rule` and heartbeat monitoring.

## Performance Bottlenecks

**Ollama reachability check on every retrieval:**
- Problem: `retrieve()` calls `_ollama_reachable()` on every invocation, which makes an HTTP GET to Ollama with a 3-second timeout. In `generate_rule()`, this is called twice (via `_get_rag_context()` on line 159 and directly on line 160).
- Files: `/mnt/Projects/AFO/db/vector_store.py` (lines 23-29, 180)
- Cause: No caching of reachability status. Each call performs a fresh HTTP request.
- Improvement path: Cache reachability result with a short TTL (e.g., 30 seconds). Or check once at startup and assume stable connectivity.

**Pure Python cosine similarity for vector search:**
- Problem: `_cosine_similarity()` computes dot product and norms using Python `sum()` and `zip()` over potentially large float lists. The `embeddings.json` store is ~363KB and loaded entirely into memory.
- Files: `/mnt/Projects/AFO/db/vector_store.py` (lines 40-47, 188-193)
- Cause: No use of NumPy or other vectorized math libraries.
- Improvement path: Use NumPy for vectorized cosine similarity. For larger document sets, consider FAISS or a proper vector database. Current document size is small enough that this is not blocking, but will not scale.

**New LLM client created on every request:**
- Problem: `_get_llm()` creates a new `ChatOllama` instance on every call. Both `generate_rule()` and `chat()` call it, meaning each user interaction creates a fresh client with no connection pooling.
- Files: `/mnt/Projects/AFO/agents/firewall_agent.py` (lines 26-33, 156, 245)
- Cause: No singleton or caching pattern for the LLM client.
- Improvement path: Use a module-level cached instance or a factory with `functools.lru_cache`. The ChatOllama client may already handle connection pooling internally, so profile before optimizing.

## Fragile Areas

**Chat intent detection via keyword matching:**
- Files: `/mnt/Projects/AFO/agents/firewall_agent.py` (lines 248-255)
- Why fragile: The `chat()` function determines whether user input is a rule request or a general question using a list of 24 keywords. Common words like "port", "network", "ssh", "ping", "rule" trigger rule generation mode even for informational questions. For example, "What is a port?" or "Explain how NAT works" would be classified as rule requests and sent to `generate_rule()`, which would attempt to parse an nftables rule from the LLM's explanatory response and fail.
- Safe modification: Replace keyword heuristic with an LLM-based intent classifier (a short classification prompt) or use a two-step approach where the main prompt handles both tasks.
- Test coverage: No tests exist for the `chat()` function or intent detection.

**JSON extraction from LLM responses:**
- Files: `/mnt/Projects/AFO/agents/firewall_agent.py` (lines 78-95)
- Why fragile: `_extract_json()` finds the first `{` and last `}` in the text to extract JSON. This fails when the LLM produces multiple JSON objects, nested structures with errors, or explanatory text containing curly braces (e.g., Python code examples). The regex for code block extraction also assumes a single code block.
- Safe modification: Use a more robust JSON extraction approach -- try parsing from each `{` position, or use a library like `json-repair`. Add unit tests for edge cases (nested JSON, multiple objects, partial JSON).
- Test coverage: Tests exist in `tests/test_phase2.py` for basic cases but not for edge cases like nested JSON or multiple JSON blocks.

**Conflict detection regex parsing:**
- Files: `/mnt/Projects/AFO/afo_mcp/tools/conflicts.py` (lines 28-94)
- Why fragile: `_parse_rule()` uses individual regex patterns to extract rule components. It does not handle: nftables sets (`{ 80, 443 }`), anonymous sets in match expressions, `ct state` expressions, `limit rate` expressions, `meta` expressions beyond `l4proto`, counter/log statements with arguments, or chain type/policy/priority declarations within ruleset listings. Any rule using these constructs will be partially or incorrectly parsed.
- Safe modification: Build a proper nftables rule parser using a grammar-based approach (e.g., Lark or PLY). Add comprehensive test cases for real-world rulesets.
- Test coverage: Basic parsing tests exist in `tests/test_mcp_tools.py`. No tests for complex nftables syntax (sets, ct state, rate limiting, NAT rules).

**Heartbeat monitor thread lifecycle:**
- Files: `/mnt/Projects/AFO/afo_mcp/tools/deployer.py` (lines 16-17, 74-108, 110-123)
- Why fragile: The heartbeat system uses global dictionaries (`_active_heartbeats`, `_heartbeat_threads`) to track daemon threads. If `confirm_deployment()` is never called and the thread exits naturally after timeout, the entries in `_active_heartbeats` and `_heartbeat_threads` are never cleaned up, causing a memory leak. Thread cleanup in `confirm_deployment()` uses `join(timeout=2)` but does not verify the thread actually stopped. If multiple deployments use the same `rule_id`, earlier heartbeat entries are silently overwritten.
- Safe modification: Add cleanup logic in the heartbeat thread itself when it exits. Use a lock around dictionary mutations. Validate `rule_id` uniqueness before deployment.
- Test coverage: No tests exist for the deployer module.

## Scaling Limits

**JSON-based vector store loaded entirely into memory:**
- Current capacity: The `embeddings.json` file is ~363KB with embeddings from a single reference document (`docs/nftables_reference.md`). This is easily handled in memory.
- Limit: With more reference documents, the JSON file will grow linearly. At ~100 documents, the file could reach tens of MB. `_cosine_similarity()` is O(n*d) per query where n=chunks and d=embedding dimensions. With thousands of chunks, retrieval latency will become noticeable.
- Scaling path: Migrate to a proper vector database (ChromaDB, FAISS, Qdrant). The current interface (`ingest_docs()`, `retrieve()`) provides a clean abstraction for swapping implementations.

**Global thread dictionary for heartbeat monitors:**
- Current capacity: One or two concurrent deployments.
- Limit: Thread entries are never cleaned up after natural expiration. After many deployments, `_active_heartbeats` and `_heartbeat_threads` dicts grow without bound. Each entry holds a `threading.Event` and a `threading.Thread` reference.
- Scaling path: Add a cleanup mechanism -- either a periodic sweep or cleanup within the thread function itself. Consider using `asyncio` instead of threading for the heartbeat monitor.

## Dependencies at Risk

**`fastmcp>=0.4.0`:**
- Risk: FastMCP is a relatively new library for Model Context Protocol. The API surface may change significantly between minor versions. The codebase pins `>=0.4.0` without an upper bound.
- Impact: A breaking API change in a new fastmcp release could break the MCP server.
- Migration plan: Pin to a specific version range (e.g., `>=0.4.0,<1.0`). The MCP tool definitions in `afo_mcp/server.py` are the only integration point.

**Hard dependency on Ollama for LLM and embeddings:**
- Risk: The entire system requires a running Ollama instance. There is no abstraction layer for LLM providers. If the team wants to use OpenAI, Anthropic, or another provider, every LLM call site needs modification.
- Impact: Deployment environments must have Ollama installed and running with specific models (`qwen2.5-coder:3b`, `nomic-embed-text`). No fallback LLM provider.
- Migration plan: Abstract LLM calls behind an interface. LangChain already supports multiple providers, so the `_get_llm()` function could be extended to support different backends based on configuration.

## Missing Critical Features

**No audit logging:**
- Problem: No record of which rules were proposed, approved, deployed, or rolled back. The `claude.md` architecture specifies PostgreSQL audit store but none exists.
- Blocks: Compliance requirements, incident investigation, change tracking. Cannot answer "who approved what rule and when."

**No connection tracking or stateful rule generation:**
- Problem: The `FirewallRule` model has no field for connection tracking state (`ct state established,related`). The LLM prompt and model schema cannot express stateful filtering rules, which are a fundamental best practice per the reference documentation.
- Blocks: Generating production-quality firewalls. Without `ct state` rules, generated rulesets cannot properly handle return traffic for established connections.

**No support for nftables sets, maps, or named objects:**
- Problem: The `FirewallRule` model only supports single-value match criteria. Cannot express port sets (`{ 80, 443 }`), address sets, named sets, or verdict maps.
- Blocks: Generating efficient, real-world firewall configurations. Every port/address combination requires a separate rule.

## Test Coverage Gaps

**No tests for deployment lifecycle:**
- What's not tested: `deploy_policy()`, `_create_backup()`, `_restore_backup()`, `_heartbeat_monitor()`, `confirm_deployment()`, `rollback_deployment()`.
- Files: `/mnt/Projects/AFO/afo_mcp/tools/deployer.py`
- Risk: The most safety-critical code in the system (actual firewall modification with rollback) has zero test coverage. Bugs in backup/restore or heartbeat timing could leave firewalls in inconsistent states.
- Priority: High

**No tests for network context gathering:**
- What's not tested: `_parse_ip_addr()`, `_parse_proc_net_dev()`, `_get_active_ruleset()`, `get_network_context()` (integration test exists but is skipped by default).
- Files: `/mnt/Projects/AFO/afo_mcp/tools/network.py`
- Risk: Parsing of `ip addr` and `ip link` output is regex-based. Unusual interface names or output formats could cause silent failures. The conflict detector depends on correct ruleset parsing.
- Priority: Medium

**No tests for Streamlit UI:**
- What's not tested: `_deploy_rule()`, `_display_rule_card()`, `_chat_interface()`, `_sidebar()`, session state management.
- Files: `/mnt/Projects/AFO/ui/app.py`
- Risk: UI-level bugs (e.g., incorrect index in `pending_rules.pop()`, session state corruption) would not be caught.
- Priority: Low (UI testing is complex, but `_deploy_rule` logic should be tested)

**No tests for `generate_rule()` or `chat()` end-to-end:**
- What's not tested: Full pipeline from user input through RAG retrieval, LLM invocation, JSON extraction, rule building, validation, and conflict detection. Component tests exist for individual pieces but no integration test for the complete flow.
- Files: `/mnt/Projects/AFO/agents/firewall_agent.py`
- Risk: Integration issues between components (e.g., LLM output format not matching expected JSON schema) would not be caught.
- Priority: Medium

**No tests for MCP server tool registration:**
- What's not tested: Whether FastMCP correctly exposes all tools, parameter validation at the MCP protocol level, serialization of Pydantic models in MCP responses.
- Files: `/mnt/Projects/AFO/afo_mcp/server.py`
- Risk: MCP tools could silently fail to register or serialize incorrectly. Since this is the primary external interface, this is a significant gap.
- Priority: Medium

---

*Concerns audit: 2026-02-10*
