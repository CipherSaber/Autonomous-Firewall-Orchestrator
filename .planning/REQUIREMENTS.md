# Requirements: AFO — AI Firewall Orchestrator

**Defined:** 2026-02-10
**Core Value:** Natural language control of firewalls with autonomous threat detection and response

## v1 Requirements

Requirements for the next milestone. Each maps to roadmap phases.

### Core Foundation

- [ ] **CORE-01**: System uses SQLite for persistent state (deployments, events, audit trail) replacing in-memory session state
- [ ] **CORE-02**: Abstract `FirewallBackend` ABC defines interface all backends implement (`list_rules`, `validate_rule`, `deploy_rule`, `rollback`, `get_status`)
- [ ] **CORE-03**: Vendor-neutral `PolicyRule` model represents firewall intent independent of backend syntax
- [ ] **CORE-04**: Service layer facade (`FirewallService`) sits between all consumers (TUI, daemon, MCP) and business logic
- [ ] **CORE-05**: Existing nftables logic refactored into `NftablesBackend` plugin implementing the backend ABC
- [ ] **CORE-06**: All existing tests continue passing after refactor
- [ ] **CORE-07**: Structured logging via structlog replaces print() statements throughout codebase

### TUI Interface

- [ ] **TUI-01**: User can type natural language commands in a chat prompt and receive firewall rule proposals
- [ ] **TUI-02**: User can view current firewall rules in a filterable, searchable table
- [ ] **TUI-03**: User can approve or reject proposed rules via keyboard shortcuts
- [ ] **TUI-04**: User can view deployment history (what was deployed, when, success/failure)
- [ ] **TUI-05**: TUI supports keyboard-driven navigation without requiring mouse
- [ ] **TUI-06**: Rules, alerts, and status are color-coded by severity (red/yellow/green)
- [ ] **TUI-07**: TUI displays multiple information streams in a multi-pane layout (chat, rules, alerts, status)
- [ ] **TUI-08**: Error messages are clear and actionable; help command shows available actions
- [ ] **TUI-09**: Live threat dashboard shows detected threats, blocked IPs, and security events in real-time
- [ ] **TUI-10**: User can request an LLM-generated plain-English explanation of any displayed rule
- [ ] **TUI-11**: User can build rules via a step-by-step interactive form (source IP, dest port, protocol, action)

### Universal Firewall Backends

- [ ] **BACK-01**: System auto-detects available firewall backend on the host (nft, iptables, cloud CLI)
- [ ] **BACK-02**: User can import existing firewall rules from any supported backend into the abstract model
- [ ] **BACK-03**: iptables backend translates PolicyRule to iptables/iptables-restore commands
- [ ] **BACK-04**: iptables backend supports rule listing, validation, deployment, and rollback
- [ ] **BACK-05**: OPNsense backend manages firewall rules via REST API
- [ ] **BACK-06**: pfSense backend manages firewall rules via REST API
- [ ] **BACK-07**: AWS Security Groups backend manages ingress/egress rules via boto3
- [ ] **BACK-08**: Azure NSG backend manages network security group rules via azure-mgmt-network
- [ ] **BACK-09**: GCP Firewall backend manages firewall rules via google-cloud-compute SDK
- [ ] **BACK-10**: Cloud backends are optional dependencies installable via extras (`pip install afo[aws]`)

### Autonomous Security Agent

- [ ] **AGENT-01**: Daemon runs as a background service (systemd unit) monitoring infrastructure 24/7
- [ ] **AGENT-02**: Daemon ingests and parses firewall logs (nftables log targets, iptables LOG rules)
- [ ] **AGENT-03**: Daemon monitors auth logs (sshd failures, sudo abuse, PAM messages) for brute force detection
- [ ] **AGENT-04**: Daemon detects known attack patterns: brute force, port scans, high connection rates
- [ ] **AGENT-05**: Daemon auto-blocks detected threats with configurable aggression levels (monitor/cautious/aggressive)
- [ ] **AGENT-06**: Every autonomous action is logged in a persistent audit trail (timestamp, threat, evidence, action, confidence)
- [ ] **AGENT-07**: User can configure an allowlist of IPs, CIDR ranges, and hostnames exempt from auto-blocking
- [ ] **AGENT-08**: Daemon continues pattern-based detection when Ollama is unavailable (graceful degradation)
- [ ] **AGENT-09**: Daemon uses LLM to analyze ambiguous threat situations beyond pattern matching
- [ ] **AGENT-10**: Daemon polls threat intelligence feeds (abuse.ch, Spamhaus, AlienVault OTX) for known-bad IPs
- [ ] **AGENT-11**: Daemon correlates signals across data sources (auth + firewall + traffic) to reduce false positives
- [ ] **AGENT-12**: Auto-blocking rules expire after a configurable TTL (duration based on threat severity)
- [ ] **AGENT-13**: Daemon captures and analyzes network traffic (pcap/netflow) for anomaly detection
- [ ] **AGENT-14**: Daemon generates scheduled threat reports (daily/weekly summary of threats and actions)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Multi-Host Orchestration

- **MULTI-01**: User can deploy the same policy across multiple hosts simultaneously
- **MULTI-02**: System tracks per-host deployment status

### Advanced Features

- **ADV-01**: User can migrate rules between firewall backends (e.g., iptables -> nftables)
- **ADV-02**: User can apply predefined policy templates (web server, database server, bastion host)
- **ADV-03**: System suggests related hardening rules after blocking a threat (context-aware suggestions)
- **ADV-04**: System detects cross-host policy inconsistencies (topology-aware conflict detection)

### Collaborative Intelligence

- **COLLAB-01**: Opt-in anonymous threat data sharing between AFO instances

## Out of Scope

| Feature | Reason |
|---------|--------|
| Cloud LLM API support | Core privacy guarantee — firewall configs must never leave the host |
| Web UI replacement | TUI is primary interface; Streamlit exists for legacy, no investment in web parity |
| Full IDS/IPS (deep packet inspection) | Integrate with Suricata/Snort rather than reimplementing |
| SIEM functionality | Consume logs for detection, don't store/index long-term. Use existing SIEMs |
| Mobile app | TUI works over SSH from any device |
| User management / multi-tenancy | Single-operator model. Use OS-level permissions |
| Custom scripting language | Natural language IS the scripting language |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 | Pending |
| CORE-02 | Phase 1 | Pending |
| CORE-03 | Phase 1 | Pending |
| CORE-04 | Phase 1 | Pending |
| CORE-05 | Phase 1 | Pending |
| CORE-06 | Phase 1 | Pending |
| CORE-07 | Phase 1 | Pending |
| TUI-01 | Phase 2 | Pending |
| TUI-02 | Phase 2 | Pending |
| TUI-03 | Phase 2 | Pending |
| TUI-04 | Phase 2 | Pending |
| TUI-05 | Phase 2 | Pending |
| TUI-06 | Phase 2 | Pending |
| TUI-07 | Phase 2 | Pending |
| TUI-08 | Phase 2 | Pending |
| TUI-09 | Phase 4 | Pending |
| TUI-10 | Phase 2 | Pending |
| TUI-11 | Phase 2 | Pending |
| BACK-01 | Phase 5 | Pending |
| BACK-02 | Phase 5 | Pending |
| BACK-03 | Phase 5 | Pending |
| BACK-04 | Phase 5 | Pending |
| BACK-05 | Phase 7 | Pending |
| BACK-06 | Phase 7 | Pending |
| BACK-07 | Phase 7 | Pending |
| BACK-08 | Phase 7 | Pending |
| BACK-09 | Phase 7 | Pending |
| BACK-10 | Phase 7 | Pending |
| AGENT-01 | Phase 3 | Pending |
| AGENT-02 | Phase 4 | Pending |
| AGENT-03 | Phase 4 | Pending |
| AGENT-04 | Phase 4 | Pending |
| AGENT-05 | Phase 4 | Pending |
| AGENT-06 | Phase 3 | Pending |
| AGENT-07 | Phase 3 | Pending |
| AGENT-08 | Phase 3 | Pending |
| AGENT-09 | Phase 6 | Pending |
| AGENT-10 | Phase 6 | Pending |
| AGENT-11 | Phase 4 | Pending |
| AGENT-12 | Phase 4 | Pending |
| AGENT-13 | Phase 6 | Pending |
| AGENT-14 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 42 total
- Mapped to phases: 42
- Unmapped: 0

---
*Requirements defined: 2026-02-10*
*Last updated: 2026-02-10 after roadmap creation*
