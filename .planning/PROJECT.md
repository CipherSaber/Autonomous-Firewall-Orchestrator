# AFO — AI Firewall Orchestrator

## What This Is

An autonomous AI-powered firewall orchestrator that translates natural language commands into firewall rules, monitors infrastructure for threats, and automatically responds — all through a rich terminal interface. It supports universal firewall backends via a plugin architecture and runs as both a background daemon (autonomous monitoring) and an interactive TUI (manual commands and status).

## Core Value

Natural language control of firewalls with autonomous threat detection and response — you tell it what to do in plain English, and it also watches your back when you're not looking.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Natural language → nftables rule generation via local LLM (Ollama + LangChain) — existing
- ✓ RAG retrieval augmenting LLM context with nftables documentation — existing
- ✓ Structural rule validation and nft --check syntax validation — existing
- ✓ Conflict detection between proposed and existing rules — existing
- ✓ Safe deployment with backup and heartbeat auto-rollback — existing
- ✓ MCP server exposing firewall tools for external LLM clients — existing
- ✓ Streamlit web dashboard with chat interface and rule approval workflow — existing
- ✓ Input sanitization and shell injection prevention — existing
- ✓ Pydantic data models for all firewall structures — existing
- ✓ Docker and dev container setup — existing

### Active

<!-- Current scope. Building toward these. -->

- [ ] TUI interface with chat-style prompt for issuing commands and viewing status
- [ ] Background daemon mode for autonomous 24/7 monitoring
- [ ] Universal firewall backend plugin architecture (nftables, iptables, cloud firewalls, appliances)
- [ ] Firewall log ingestion and analysis for threat detection
- [ ] Network traffic analysis (netflow/pcap) for anomaly detection
- [ ] Threat intelligence feed integration (known bad IPs, CVEs)
- [ ] System log analysis (syslog, auth logs) for security events
- [ ] Autonomous threat detection combining all data sources
- [ ] Autonomous response — auto-block detected threats with appropriate firewall rules
- [ ] Action reporting — daemon reports what it detected and what it did
- [ ] TUI dashboard showing daemon status, recent actions, and active threats

### Out of Scope

- Mobile app — terminal-first tool, mobile doesn't fit the use case
- Cloud-hosted SaaS — this runs on your infrastructure, your data stays local
- Cloud LLM APIs — local/self-hosted LLM only for privacy and security
- GUI/web replacement for TUI — Streamlit exists for legacy, TUI is the primary interface going forward

## Context

AFO started as a proof-of-concept NLP-to-nftables pipeline with a Streamlit UI. The existing codebase handles the core rule generation flow: user types a request, LLM generates a rule, system validates and checks for conflicts, user approves, system deploys with rollback safety.

The next evolution transforms AFO from a reactive tool (user asks, system does) into an autonomous security agent (system watches, detects, acts, reports) with universal firewall support and a native terminal interface.

**Existing architecture layers:**
- Presentation: Streamlit (to be supplemented by TUI)
- Agent: LangChain + Ollama
- MCP Server: FastMCP exposing 6 tools
- Tools: network context, validation, conflict detection, deployment
- Data Models: Pydantic
- RAG: Custom vector store with Ollama embeddings
- Security: Input sanitization

**Tech stack:** Python 3.11+, LangChain, Ollama (qwen2.5-coder:3b), FastMCP, Pydantic, Docker

## Constraints

- **Privacy**: All AI inference must run locally — no cloud LLM APIs. Ollama or equivalent self-hosted models only.
- **Firewall runtime**: Linux required for actual firewall operations. NET_ADMIN capability needed.
- **Safety**: Human-in-the-loop approval must remain available. Autonomous mode should have configurable aggression levels and always log actions.
- **Compatibility**: Must preserve existing MCP server interface for backward compatibility.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Local LLM only (Ollama) | Security tool must not leak firewall configs to cloud APIs | — Pending |
| TUI as primary interface | Target audience lives in terminals; richer than CLI, lighter than web | — Pending |
| Plugin architecture for firewalls | "Universal" means extensible, not monolithic support for every firewall | — Pending |
| Daemon + TUI dual mode | Autonomous monitoring needs to run 24/7; TUI is for human interaction | — Pending |

---
*Last updated: 2026-02-10 after initialization*
