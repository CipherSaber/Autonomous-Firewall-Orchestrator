# Roadmap: AFO — AI Firewall Orchestrator

## Overview

AFO evolves from a reactive NLP-to-nftables tool into an autonomous security agent with universal firewall support and a native terminal interface. The roadmap starts by extracting a clean service layer and persistent state from the existing codebase, then delivers the TUI as the primary user-facing interface, then builds the autonomous daemon with safety mechanisms before detection logic, validates the plugin architecture with a second backend, adds threat intelligence enrichment, and finally extends to cloud and appliance firewalls.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Core Foundation** - Service layer, backend abstraction, persistent state, and nftables refactor
- [ ] **Phase 2: TUI Interface** - Keyboard-driven terminal interface with NL chat, rule management, and multi-pane layout
- [ ] **Phase 3: Daemon Foundation + Safety Infrastructure** - Background service skeleton with audit trail and safety guardrails
- [ ] **Phase 4: Autonomous Threat Detection + Response** - Log-based threat detection, pattern matching, and auto-blocking with live TUI dashboard
- [ ] **Phase 5: iptables Backend** - Second backend validates plugin architecture; auto-detection and rule import
- [ ] **Phase 6: Threat Intelligence + Advanced Detection** - External threat feeds, LLM-enhanced analysis, traffic analysis, and reporting
- [ ] **Phase 7: Cloud and Appliance Backends** - OPNsense, pfSense, AWS SG, Azure NSG, GCP Firewall via optional extras

## Phase Details

### Phase 1: Core Foundation
**Goal**: All consumers (TUI, daemon, MCP) interact with firewalls through a single, persistent, backend-agnostic service layer
**Depends on**: Nothing (first phase)
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-06, CORE-07
**Success Criteria** (what must be TRUE):
  1. Firewall operations (list, validate, deploy, rollback) work through FirewallService without consumers knowing which backend is active
  2. All state (deployments, events, audit trail) persists across process restarts via SQLite
  3. Existing nftables functionality (rule generation, validation, conflict detection, deployment, rollback) works identically through the new backend plugin
  4. All existing tests pass without modification to test assertions
  5. All log output uses structured logging with consistent fields (timestamp, level, component, message)
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD
- [ ] 01-03: TBD

### Phase 2: TUI Interface
**Goal**: Users can manage firewalls through a keyboard-driven terminal interface using natural language
**Depends on**: Phase 1
**Requirements**: TUI-01, TUI-02, TUI-03, TUI-04, TUI-05, TUI-06, TUI-07, TUI-08, TUI-10, TUI-11
**Success Criteria** (what must be TRUE):
  1. User can type a natural language request, see a proposed firewall rule, and approve or reject it without leaving the terminal
  2. User can browse, search, and filter current firewall rules in a table view
  3. User can view deployment history showing what was deployed, when, and whether it succeeded
  4. User can navigate the entire interface using keyboard shortcuts alone (no mouse required)
  5. Multiple information streams (chat, rules, status) are visible simultaneously in a multi-pane layout with severity-based color coding
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Daemon Foundation + Safety Infrastructure
**Goal**: A background daemon runs continuously with safety guardrails that prevent it from causing harm, even before it has detection logic
**Depends on**: Phase 1
**Requirements**: AGENT-01, AGENT-06, AGENT-07, AGENT-08
**Success Criteria** (what must be TRUE):
  1. Daemon starts as a systemd service, runs in the background, and survives process restarts
  2. Every action the daemon takes is recorded in an immutable audit trail with timestamp, threat type, evidence, action taken, and confidence level
  3. IPs, CIDR ranges, and hostnames on the allowlist are never blocked regardless of what detection logic reports
  4. Daemon continues operating with pattern-based detection when Ollama is unavailable
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: Autonomous Threat Detection + Response
**Goal**: The daemon detects real threats from infrastructure logs and automatically blocks them with appropriate firewall rules
**Depends on**: Phase 3
**Requirements**: AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-11, AGENT-12, TUI-09
**Success Criteria** (what must be TRUE):
  1. Daemon detects SSH brute force attempts from auth logs and auto-blocks offending IPs at the firewall level
  2. Daemon detects port scans and high connection rates from firewall logs and responds based on configured aggression level (monitor/cautious/aggressive)
  3. Auto-generated blocking rules expire after a configurable TTL based on threat severity
  4. TUI displays a live threat dashboard showing detected threats, blocked IPs, and security events updating in real-time
  5. Daemon correlates signals across multiple log sources to reduce false positives before taking action
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

### Phase 5: iptables Backend
**Goal**: The plugin architecture is proven by a second fully-functional backend, and the system auto-detects which backend to use
**Depends on**: Phase 1
**Requirements**: BACK-01, BACK-02, BACK-03, BACK-04
**Success Criteria** (what must be TRUE):
  1. User can manage firewall rules on an iptables-based system through the same interface used for nftables
  2. System auto-detects whether nft or iptables is available on the host and selects the appropriate backend
  3. User can import existing firewall rules from either nftables or iptables into the abstract PolicyRule model
  4. iptables backend supports the full lifecycle: listing, validation, deployment, and rollback
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

### Phase 6: Threat Intelligence + Advanced Detection
**Goal**: The daemon enriches its detection with external threat feeds and LLM-powered analysis for situations beyond simple pattern matching
**Depends on**: Phase 4
**Requirements**: AGENT-09, AGENT-10, AGENT-13, AGENT-14
**Success Criteria** (what must be TRUE):
  1. Daemon polls external threat intelligence feeds and automatically blocks known-bad IPs before they attack
  2. Daemon uses LLM analysis to classify ambiguous threat situations that pattern matching alone cannot resolve
  3. Network traffic anomalies (unusual volumes, suspicious patterns) are detected and reported
  4. Daemon generates scheduled threat reports summarizing threats detected and actions taken over a configurable period
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

### Phase 7: Cloud and Appliance Backends
**Goal**: Users can manage cloud and appliance firewalls through the same universal interface used for Linux firewalls
**Depends on**: Phase 5
**Requirements**: BACK-05, BACK-06, BACK-07, BACK-08, BACK-09, BACK-10
**Success Criteria** (what must be TRUE):
  1. User can manage OPNsense and pfSense firewall rules through AFO via their REST APIs
  2. User can manage AWS Security Groups, Azure NSGs, and GCP Firewall rules through AFO via their respective SDKs
  3. Cloud backends install as optional extras (e.g., `pip install afo[aws]`) without adding dependencies for users who do not need them
  4. Each backend accurately reports its capabilities, and the interface adapts to what the backend supports
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order. Phases 2, 3, and 5 all depend on Phase 1 but are independent of each other. Phase 4 depends on Phase 3. Phase 6 depends on Phase 4. Phase 7 depends on Phase 5.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Foundation | 0/3 | Not started | - |
| 2. TUI Interface | 0/2 | Not started | - |
| 3. Daemon Foundation + Safety | 0/2 | Not started | - |
| 4. Threat Detection + Response | 0/2 | Not started | - |
| 5. iptables Backend | 0/1 | Not started | - |
| 6. Threat Intel + Advanced | 0/2 | Not started | - |
| 7. Cloud + Appliance Backends | 0/2 | Not started | - |

---
*Roadmap created: 2026-02-10*
*Last updated: 2026-02-10*
