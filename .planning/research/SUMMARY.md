# Project Research Summary

**Project:** AFO -- Autonomous Firewall Orchestrator
**Domain:** AI-powered security infrastructure (firewall management, autonomous threat response, terminal-native interface)
**Researched:** 2026-02-10
**Confidence:** MEDIUM

## Executive Summary

AFO is an AI-powered firewall orchestration platform that combines natural language rule generation via local LLMs, a universal plugin architecture for multiple firewall backends, and an autonomous security daemon for 24/7 threat monitoring and response. This is a mature problem domain -- firewall management, log-based threat detection, and plugin architectures all have decades of battle-tested patterns. The recommended approach builds on the existing LangChain + Ollama + nftables codebase by extracting a clean service layer, implementing a backend abstraction (ABC + registry), adding a Textual-based TUI, and running an asyncio-based monitoring daemon. The existing nftables implementation becomes the first plugin; iptables validates the abstraction; cloud and appliance backends follow once the architecture is proven.

The most dangerous risks are all consequences of autonomous operation. An automated system that modifies firewall rules can lock operators out of their own infrastructure, create self-amplifying blocking cascades, or deploy hallucinated rules that open security holes instead of closing them. These are not edge cases -- they are the documented failure modes of every IDS/IPS/SOAR system that has gone before AFO. The research is unambiguous: safety mechanisms (never-block lists, circuit breakers, management-plane protection, deterministic rule templates for auto-response) must be built BEFORE the autonomous detection logic, not after. The daemon should use the LLM only for threat classification, never for autonomous rule syntax generation.

The plugin architecture presents a well-known design tension: too much abstraction cripples the nftables backend's expressiveness, while too little leaks nftables semantics into the universal interface. The resolution is a tiered interface -- a universal core (block IP, allow port, list rules) plus backend-specific capability negotiation. The existing `FirewallRule` model is deeply nftables-specific and must be supplemented (not replaced) with a backend-agnostic policy model. SQLite replaces all in-memory state to enable daemon-TUI communication and survive process restarts. Textual is the clear TUI framework choice given that Rich is already a dependency.

## Key Findings

### Recommended Stack

The stack extends the existing Python/LangChain/Ollama foundation with five new areas: TUI framework, plugin system, async daemon, threat intelligence, and persistent state. Most core dependencies are already installed or are stdlib.

**Core technologies:**
- **Textual** (TUI framework): Built on Rich (already installed at 14.3.2), async-native, CSS-like styling, comprehensive widget library. The only serious Python TUI framework with a component model. No viable alternatives.
- **Python ABCs + importlib.metadata** (plugin system): Standard library. ABC defines the `FirewallBackend` interface; entry points handle discovery. Simpler and more appropriate than pluggy (hook-based, wrong pattern) or stevedore (heavy, declining).
- **asyncio** (daemon runtime): Stdlib. Unifies the entire runtime: Textual uses asyncio, LangChain supports async (`ainvoke`), httpx supports async. The existing threading in `deployer.py` should migrate to asyncio tasks.
- **SQLite** (persistent state): Replaces scattered in-memory state (Streamlit session_state, deployer heartbeat dicts). Enables daemon-TUI shared state, survives restarts, no server dependency.
- **watchdog 6.0.0** (log monitoring): Already installed. inotify-based file watching for log tailing with rotation awareness.
- **structlog** (structured logging): Replaces all `print()` statements. JSON output for daemon, colored output for TUI, contextual field binding. Non-negotiable for a security tool.
- **scapy** (packet analysis): Gold standard for Python packet manipulation. `AsyncSniffer` for daemon integration. Use for deep inspection, not high-volume monitoring.

**Critical version items:** Textual, scapy, and structlog versions need live PyPI verification before pinning. stix2 may still be at 2.x, not 3.x. The systemd journal Python bindings ecosystem is fragmented (systemd-python vs. cysystemd vs. pystemd).

### Expected Features

**Must have (table stakes):**
- TUI with NL chat prompt, rule display, approve/reject workflow, keyboard shortcuts, multi-pane layout
- Abstract rule model (vendor-neutral `PolicyRule`) and plugin/backend interface
- nftables backend refactored as first plugin (preserve all existing behavior)
- iptables backend (validates the plugin architecture)
- Import existing rules from live firewalls
- Backend auto-detection on first run
- Daemon with auth log monitoring and pattern-based auto-blocking (fail2ban-level functionality)
- Configurable aggression levels (monitor / cautious / aggressive)
- Action audit trail (every autonomous action logged with evidence and reasoning)
- Whitelist/allowlist (non-negotiable for preventing false-positive blocking)
- Graceful degradation when Ollama is unavailable (rule-based detection continues)

**Should have (differentiators):**
- Live threat dashboard in TUI (streaming daemon events)
- Inline rule explanation via LLM ("explain this rule in plain English")
- Threat intelligence feed integration (abuse.ch, Spamhaus, AlienVault OTX)
- Auto-expiring blocks with LLM-suggested durations
- LLM-enhanced threat analysis for ambiguous situations
- Context-aware hardening suggestions post-incident
- Scheduled threat reports (daily/weekly summaries)

**Defer to v2+:**
- Cloud firewall backends (AWS SG, Azure NSG, GCP) -- high complexity, SDK auth handling
- Firewall appliance backends (OPNsense, pfSense) -- REST API complexity, CSRF handling
- Network traffic analysis (pcap/netflow) -- requires privileged access, heavy implementation
- Multi-source correlation engine -- needs multiple data sources operational first
- Multi-host deployment -- transforms from tool to orchestrator, major scope increase
- Rule migration between backends -- requires mature abstract model
- Collaborative intelligence (CrowdSec-style) -- conflicts with privacy-first ethos

**Anti-features (explicitly do NOT build):**
- Cloud LLM API support (violates core privacy guarantee)
- Web dashboard replacement (TUI is primary; Streamlit is legacy, not invested in)
- Full IDS/IPS reimplementation (integrate with Suricata/Snort, do not replace)
- SIEM functionality (consume logs, do not store/index them)
- Custom scripting language (NL is the scripting language)

### Architecture Approach

The architecture introduces a service layer (Facade pattern) between all consumers (TUI, Streamlit, daemon, MCP server) and the existing agent/tool code. This eliminates duplicated orchestration logic and enables shared persistent state. The plugin system uses an ABC-defined `FirewallBackend` interface with an explicit registry (not entry_points, since all backends are in-repo). The daemon is an asyncio supervisor managing pluggable `DataSource` monitors that produce typed `SecurityEvent` objects fed through a threat analysis pipeline. TUI and daemon communicate via shared SQLite state (polling or reactive updates), not direct IPC.

**Major components:**
1. **Service Layer** (`core/service.py`) -- Unified API for rule generation, validation, deployment, and state management. All consumers go through this.
2. **Backend System** (`core/backends/`) -- ABC interface + registry + implementations (nftables extracted from existing tools, iptables new).
3. **State Store** (`core/state.py`) -- SQLite persistence for proposals, deployments, events, daemon state. Replaces all in-memory state.
4. **Daemon Supervisor** (`daemon/supervisor.py`) -- asyncio event loop managing data source tasks, threat analysis, and autonomous response with configurable autonomy levels.
5. **Data Sources** (`daemon/sources/`) -- Pluggable monitors (syslog, auth.log, firewall logs, threat feeds) implementing a `DataSource` ABC.
6. **Textual TUI** (`tui/`) -- Screens for chat, dashboard, rule browser. Workers for non-blocking LLM calls. Reads shared state from SQLite.

### Critical Pitfalls

1. **Autonomous rule feedback loops** -- The daemon's own blocking actions generate log events that trigger further blocks, cascading to network outage. Prevent with: never-block list (hardcoded infrastructure IPs), circuit breaker (halt after N rules in M minutes), action attribution (filter events caused by daemon's own actions), rate limiting on rule creation.

2. **LLM hallucinating rules in autonomous mode** -- Without human review, the LLM may generate rules that open ports, block wrong IPs, or use overly broad match criteria. Prevent with: deterministic rule templates for auto-response (LLM classifies threats, templates generate rules), action-restricted mode (daemon can only create `drop` rules, never `accept`), mandatory validation before deployment.

3. **Plugin abstraction leaking nftables semantics** -- Designing the interface from nftables' perspective makes it unusable for AWS SGs (stateful-only, no deny) or OPNsense (last-match-wins). Prevent with: design from the intersection of all backends, capability negotiation per plugin, tiered interface (universal core + backend-specific extensions).

4. **Losing management access** -- Daemon deploys a rule blocking SSH or the management path. Current heartbeat checks outbound connectivity, not management-plane reachability. Prevent with: persistent high-priority management allow rule, pre-deployment management IP check, canary connection test after every autonomous deployment.

5. **Log processing overwhelm during attacks** -- During a DDoS, log volume spikes 100-1000x. Sending every event to the LLM causes OOM/queue backup. Prevent with: two-tier analysis (fast regex for known patterns, LLM only for ambiguous events), sampling and aggregation during high-volume periods, bounded queues with backpressure.

## Implications for Roadmap

Based on combined research findings, the following phase structure reflects dependency chains, safety-first ordering, and architectural prerequisites.

### Phase 1: Core Foundation (State Store + Backend ABC + Service Layer)

**Rationale:** Everything depends on this. The state store enables persistent shared state. The backend ABC defines the plugin contract. The service layer eliminates duplicated orchestration across consumers. Without this phase, every subsequent phase builds on a fragile foundation.
**Delivers:** Persistent SQLite state store, `FirewallBackend` ABC and registry, `FirewallService` facade, nftables backend extracted from existing tools, existing tools refactored to delegate through backend, existing tests continue passing.
**Addresses features:** Plugin/backend interface, abstract rule model foundation, nftables behavior preservation.
**Avoids pitfalls:** Pitfall 14 (dual codepath -- service layer prevents it), Pitfall 6 (shared state -- SQLite resolves it), Pitfall 4 (management access -- backend abstraction enables management-plane checks).

### Phase 2: TUI Interface

**Rationale:** The TUI is the new primary interface and the project's most visible deliverable. It depends on the service layer (Phase 1) but is independent of the daemon. Building it early validates the service layer design and delivers user-facing value.
**Delivers:** Textual application with chat screen (NL input, streaming LLM responses), rule browser (list, search, filter), approve/reject workflow, keyboard shortcuts, multi-pane layout, deployment history view.
**Addresses features:** All TUI table-stakes features (chat prompt, rule listing, approval workflow, keyboard shortcuts, color-coded severity, multi-pane layout, error messages).
**Avoids pitfalls:** Pitfall 10 (blocking event loop -- use Workers for all I/O from day one), Pitfall 14 (dual codepath -- TUI uses service layer, no direct tool calls).
**Stack:** Textual, Rich (already installed).

### Phase 3: Safety Infrastructure + Daemon Foundation

**Rationale:** The pitfalls research is emphatic: build safety mechanisms BEFORE autonomous logic. This phase creates the audit system, never-block list, circuit breaker, and daemon skeleton -- all prerequisites for threat detection. Building audit logging now means every subsequent feature is automatically auditable.
**Delivers:** Structured logging (structlog replacing all print()), immutable audit log, `DataSource` ABC, daemon supervisor skeleton (asyncio), never-block list configuration, circuit breaker, rate limiting on rule creation, management-plane protection rules, systemd service unit, signal handling, health check endpoint.
**Addresses features:** Action audit trail, whitelist/allowlist, daemon mode (background service), graceful degradation.
**Avoids pitfalls:** Pitfall 12 (inadequate audit -- built first), Pitfall 1 (feedback loops -- circuit breaker + never-block list), Pitfall 4 (management lockout -- management-plane rules), Pitfall 11 (daemon lifecycle -- systemd + signals from the start).

### Phase 4: Autonomous Threat Detection + Response

**Rationale:** With the daemon skeleton and safety infrastructure in place, add actual threat detection. Start with the simplest, highest-value data source (auth logs for SSH brute force detection) and expand. This is the phase where AFO surpasses fail2ban.
**Delivers:** Auth log data source (syslog/journald parser), pattern-based threat detection (brute force, port scan), deterministic auto-blocking with templates, configurable aggression levels, firewall log ingestion, TUI daemon dashboard integration (live events, pending approvals), auto-expiring blocks.
**Addresses features:** Auth log monitoring, pattern-based threat detection, automated blocking, configurable aggression, live threat dashboard, auto-expiring blocks.
**Avoids pitfalls:** Pitfall 2 (LLM hallucination -- deterministic templates for auto-response, LLM only for classification), Pitfall 5 (log overwhelm -- two-tier analysis from the start), Pitfall 15 (aggressive defaults -- conservative thresholds, learning mode).

### Phase 5: Second Backend (iptables) + Multi-Backend Validation

**Rationale:** The iptables backend validates the plugin architecture. If iptables works cleanly through the same interface as nftables, the abstraction is proven. This phase also addresses the iptables/nftables coexistence problem.
**Delivers:** iptables backend implementation, backend auto-detection, import existing rules (nftables + iptables), iptables-nft vs. iptables-legacy detection, mutual exclusion enforcement.
**Addresses features:** iptables backend, backend auto-detection, import existing rules.
**Avoids pitfalls:** Pitfall 3 (leaky abstraction -- second backend reveals abstraction flaws), Pitfall 7 (too thin -- iptables has similar expressiveness to nftables, tests tiered interface), Pitfall 13 (iptables/nftables coexistence -- detect and warn), Pitfall 9 (flush-and-replace -- implement atomic replacement in nftables backend).

### Phase 6: Threat Intelligence + Advanced Detection

**Rationale:** With solid detection and response infrastructure, add external threat feeds and LLM-enhanced analysis. These are additive features that increase detection quality without changing the core architecture.
**Delivers:** Threat feed polling (abuse.ch, Spamhaus, AlienVault OTX via httpx), IP reputation cache, feed quality scoring, time-bounded blocks from threat intel, LLM-enhanced threat analysis for ambiguous events, inline rule explanation in TUI, context-aware hardening suggestions, scheduled threat reports.
**Addresses features:** Threat intel feed integration, LLM-enhanced threat analysis, inline rule explanation, context-aware suggestions, scheduled reports.
**Avoids pitfalls:** Pitfall 8 (feed poisoning -- quality scoring + cross-reference + time-bounded blocks).

### Phase 7: Cloud and Appliance Backends

**Rationale:** Deferred until the plugin architecture is validated with two Linux firewall backends. Cloud and appliance backends have fundamentally different semantics (stateful-only, REST APIs, different evaluation orders) that stress-test the abstraction.
**Delivers:** OPNsense/pfSense REST API backend, AWS Security Groups backend, Azure NSG backend, GCP Firewall backend, capability negotiation system, cloud SDK optional dependencies.
**Addresses features:** Cloud firewall backends, firewall appliance backends, capability-based feature exposure.
**Avoids pitfalls:** Pitfall 3 (leaky abstraction -- capability negotiation resolves semantic mismatches).

### Phase Ordering Rationale

- **Foundation first (Phase 1):** The service layer and state store are load-bearing infrastructure. Every subsequent phase depends on them. Building them first prevents the rework that would come from adding them later.
- **TUI before daemon (Phase 2 before 3-4):** The TUI delivers immediate user-facing value and validates the service layer design without the complexity of autonomous operation. It is also lower risk (no security consequences from a TUI bug).
- **Safety before autonomy (Phase 3 before 4):** The pitfalls research is unambiguous. Every autonomous security system that shipped without safety mechanisms caused outages. Audit logging, never-block lists, and circuit breakers are prerequisites, not enhancements.
- **Second backend after daemon (Phase 5 after 4):** The daemon needs only nftables initially. The iptables backend validates the abstraction but is not on the critical path for core value delivery.
- **Threat intel and cloud backends last (Phases 6-7):** These are high-complexity, additive features. They depend on a stable core and validated abstraction. Shipping them prematurely risks rework.

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 2 (TUI):** Textual widget capabilities, CSS layout patterns, and Worker API details should be verified against current Textual documentation. Snapshot testing tooling (`pytest-textual-snapshot`) needs package name verification.
- **Phase 4 (Threat Detection):** Auth log format parsing for different distros (Debian vs. RHEL vs. Arch). systemd journal access libraries need evaluation (systemd-python vs. cysystemd vs. pystemd). Detection threshold tuning requires empirical testing.
- **Phase 7 (Cloud Backends):** Cloud SDK versions need live verification. AWS SG, Azure NSG, and GCP Firewall API semantics need detailed mapping against the abstract interface. Authentication handling per provider is complex.

**Phases with standard patterns (skip deep research):**
- **Phase 1 (Foundation):** ABC patterns, SQLite, service layer/Facade -- all well-documented, established Python patterns. HIGH confidence.
- **Phase 3 (Safety + Daemon Foundation):** asyncio supervisor, structured logging, systemd service units -- thoroughly documented. HIGH confidence.
- **Phase 5 (iptables Backend):** iptables CLI is stable and exhaustively documented. The main concern (coexistence with nftables) is covered in pitfalls research. HIGH confidence.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Core libraries (Rich, watchdog, Pydantic, httpx) verified from installed packages (HIGH). New dependencies (Textual, scapy, structlog) from training data (MEDIUM). Cloud SDK versions unverified (LOW). |
| Features | MEDIUM | Domain patterns are mature and stable (fail2ban since 2004, nftables since 2014). Feature expectations well-understood from competitive analysis. Specific library capabilities unverified against current versions. |
| Architecture | MEDIUM-HIGH | Patterns (ABC, Facade, asyncio supervisor, SQLite state) are well-established and version-independent. Component boundaries derived from direct codebase analysis. Textual-specific patterns need current docs verification. |
| Pitfalls | MEDIUM-HIGH | Failure modes drawn from well-documented IDS/IPS/SOAR literature and direct codebase analysis. nftables-specific pitfalls (flush-and-replace) from kernel documentation. Textual-specific pitfalls at MEDIUM confidence. |

**Overall confidence:** MEDIUM

### Gaps to Address

- **Textual version and API verification:** Training data may not reflect current Textual API (rapid development pace). Verify widget availability, Worker API, and CSS layout capabilities before Phase 2 planning.
- **systemd journal library selection:** The Python systemd bindings ecosystem is fragmented. Evaluate `cysystemd`, `pystemd`, and `systemd-python` for Phase 4.
- **stix2 library version:** May still be at 2.x, not the 3.x assumed in STACK.md. Verify before Phase 6 planning.
- **nftables atomic replacement:** The fix for Pitfall 9 (flush-and-replace race) should be validated against the current `deployer.py` implementation early, ideally during Phase 1.
- **Ollama async support:** LangChain-Ollama's async capabilities (`ainvoke`, `astream`) need verification. If async is not supported, all LLM calls in the daemon must use `asyncio.to_thread()`.
- **Python 3.14 compatibility:** Several new dependencies (scapy, dpkt) may not have Python 3.14 wheels yet. Test compatibility before adding to `pyproject.toml`.

## Sources

### Primary (HIGH confidence)
- Installed package metadata in `/mnt/Projects/AFO/.venv/lib/python3.14/site-packages/` -- Rich 14.3.2, pluggy 1.6.0, watchdog 6.0.0, Pydantic 2.12.5, pydantic-settings 2.12.0, httpx 0.28.1, FastMCP 2.14.5
- Direct codebase analysis: `afo_mcp/tools/deployer.py`, `afo_mcp/models.py`, `afo_mcp/security.py`, `agents/firewall_agent.py`, `ui/app.py`
- Existing planning docs: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STACK.md`, `.planning/codebase/INTEGRATIONS.md`, `.planning/codebase/CONCERNS.md`
- Project definition: `.planning/PROJECT.md`, `claude.md`

### Secondary (MEDIUM confidence)
- Training data on Textual framework architecture and widget library
- Training data on IDS/IPS/SOAR failure modes (Snort, Suricata, TheHive/Cortex post-mortems)
- Training data on firewall management best practices (CIS Benchmarks, NIST 800-41)
- Training data on Python plugin architecture patterns (ABC, strategy pattern, entry points)
- Training data on asyncio supervisor and daemon patterns

### Tertiary (LOW confidence)
- Textual, scapy, structlog specific version numbers -- need PyPI verification
- Cloud SDK versions (boto3, azure-mgmt-network, google-cloud-compute) -- need verification
- stix2 and taxii2-client version status -- may be outdated
- systemd Python bindings package landscape -- fragmented, needs evaluation

---
*Research completed: 2026-02-10*
*Ready for roadmap: yes*
