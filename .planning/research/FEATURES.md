# Feature Landscape

**Domain:** AI-powered firewall orchestration with autonomous threat detection
**Researched:** 2026-02-10
**Research basis:** Domain expertise from security tooling ecosystem (Wazuh, CrowdSec, fail2ban, Suricata, fwbuilder, Panorama, k9s, lazydocker). WebSearch was unavailable; all findings are from training data. Confidence is MEDIUM overall -- patterns in this domain are mature and stable, but specific library versions and newest entrants could not be verified.

---

## Table Stakes

Features users expect. Missing = product feels incomplete.

### TUI Interface

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Chat prompt for NL commands | Core value prop -- typing natural language to get firewall rules is the reason AFO exists. TUI must replicate what Streamlit chat does. | Low | Port existing `chat()` and `generate_rule()` flow to TUI input. Textual provides `Input` widget. |
| Live rule listing with search/filter | Every firewall management tool shows current rules. `nft list ruleset` output is dense; TUI must make it scannable. | Med | Filterable table of parsed rules. Needs the rule parser from `conflicts.py` or a better one. |
| Rule approval workflow | Existing Streamlit has approve/reject. TUI users expect the same safety gate. Without it, autonomous mode has no human override. | Med | Inline approve/reject keybindings on proposed rules. Must integrate with `deployer.deploy_policy()`. |
| Deployment status and history | Users need to see what was deployed, when, and whether it succeeded. Basic operational visibility. | Low | Display `DeploymentResult` history. Requires persisting deployment records (currently in-memory only). |
| Keyboard shortcuts | TUI users expect vim-like or emacs-like navigation. No mouse required. k9s, htop, lazydocker all have this. | Low | Textual has built-in keybinding support. Define a keymap for navigation, approval, search. |
| Color-coded severity and status | Security tools universally use red/yellow/green for severity. Rules, alerts, and status must be visually distinct. | Low | Textual Rich integration provides styling. |
| Multi-pane layout | Sysadmins expect to see multiple information streams simultaneously (rules, alerts, status, chat) without tab-switching for every action. | Med | Textual CSS-based layout with resizable panes. Common pattern: left sidebar (navigation), main content, bottom bar (status/input). |
| Error messages and help | When things fail (Ollama down, permission denied, invalid rule), clear actionable error messages. Help command or `?` showing available commands. | Low | Map existing error returns to formatted TUI output. |

### Universal Firewall Management

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Plugin/backend interface | "Universal" implies extensibility. Without a defined backend interface, adding each firewall type is ad-hoc and fragile. This is the architectural prerequisite for everything else. | Med | Abstract base class defining: `list_rules()`, `validate_rule()`, `deploy_rule()`, `rollback()`, `get_status()`. Each backend implements this. |
| Abstract (vendor-neutral) rule model | Users must express intent once, deploy to any backend. The current `FirewallRule` model is nftables-specific (`to_nft_command()`). Need a neutral intermediate representation. | High | New `PolicyRule` model with vendor-neutral fields. Each backend plugin translates to native syntax. This is the hardest design problem. |
| nftables backend (existing behavior preserved) | Cannot break what already works. Current nftables flow must continue functioning as the first plugin. | Med | Refactor existing `deployer.py`, `validator.py`, `network.py` into an nftables plugin implementing the backend interface. |
| iptables backend | iptables is still the most widely deployed Linux firewall. Any "universal" firewall tool that does not support iptables is not credible. | Med | Translate abstract rules to `iptables`/`iptables-save`/`iptables-restore` commands. Well-documented CLI, simpler than nftables. |
| Import existing rules | Users have existing firewalls. They need to import current rules into AFO's model before managing them. Not being able to see what is already there is a dealbreaker. | Med | Parse output of `nft list ruleset`, `iptables-save`, cloud API responses into the abstract rule model. |
| Backend auto-detection | On first run, detect which firewall backend is available on the system. Do not force manual configuration when the answer is obvious. | Low | Check for `nft`, `iptables`, cloud CLI presence. Default to detected backend. |

### Autonomous Security Agent

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Firewall log ingestion | The most basic threat signal. Every IDS (Wazuh, OSSEC, fail2ban, CrowdSec) starts with log analysis. Blocked connections, dropped packets, and rate-limited flows reveal attack patterns. | Med | Parse nftables log targets, iptables LOG rules, and journald/syslog entries. Need a log tail/follow mechanism. |
| Auth log monitoring | Brute force SSH/login detection is the single most common automated security response (fail2ban's entire purpose). If the agent cannot detect failed auth attempts, it is less useful than fail2ban. | Med | Parse `/var/log/auth.log` or journald for `sshd` failures, `su`/`sudo` failures, PAM messages. Pattern: N failures from same IP in M seconds = threat. |
| Pattern-based threat detection | Known attack signatures: brute force, port scan, SYN flood, credential stuffing. Users expect detection of these standard patterns without custom configuration. | Med | Rule engine with configurable thresholds. Start with: brute force (auth failures), port scan (many ports from one IP), and high connection rate (potential DDoS). |
| Automated blocking with configurable aggression | The autonomous agent's core value. Must auto-block threats but with tunable aggressiveness. Sysadmins will not trust a tool that blocks aggressively with no controls. | Med | Aggression levels: `monitor` (log only), `cautious` (block after high confidence), `aggressive` (block on first signal). Per-level thresholds. |
| Action audit trail | Every autonomous action must be logged. "What did it do while I was sleeping?" is the first question every sysadmin asks. Without an audit trail, the agent is untrusted. | Med | Persistent log of: timestamp, threat detected, evidence (source data), action taken, rule deployed, confidence level. |
| Whitelist/allowlist | Users must be able to exclude known-good IPs, ranges, and services from autonomous blocking. Without this, the agent will inevitably block legitimate traffic and lose trust immediately. | Low | Configurable allowlist in YAML/TOML. Checked before any blocking action. Support IPs, CIDR ranges, hostnames. |
| Daemon mode (background service) | Autonomous monitoring requires 24/7 operation. Must run as a proper daemon/service, not require an open terminal. | Med | systemd service unit, PID file, signal handling (SIGHUP for reload, SIGTERM for clean shutdown). |
| Graceful degradation when Ollama is down | The agent must continue pattern-based detection even if the LLM is unreachable. Pure rule-based detection does not need AI. LLM enriches analysis but must not be a hard dependency for the daemon. | Low | Two detection tiers: rule-based (always available) and LLM-enhanced (when Ollama is up). The daemon monitors Ollama health and operates in degraded mode if needed. |

---

## Differentiators

Features that set AFO apart. Not expected, but valued. These are what make AFO more than "yet another firewall wrapper."

### TUI Interface

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Live threat dashboard | Real-time display of detected threats, blocked IPs, and security events in the TUI. Goes beyond static rule listing to show the security posture as it evolves. Tools like k9s show live cluster state; AFO should show live security state. | Med | Streaming updates from the daemon to the TUI. Use Textual's reactive data binding. Requires IPC between daemon and TUI (Unix socket or shared state). |
| Inline rule explanation | When viewing a rule, press a key to get an LLM-generated plain-English explanation of what the rule does and why it exists. No other firewall TUI does this. | Low | Send the nftables/iptables rule text to the LLM with an "explain this rule" prompt. Display in a side panel. |
| Interactive rule builder | Beyond chat: a step-by-step form-based rule builder for users who want structured input rather than free-form NLP. Source IP? Destination port? Protocol? Action? Fill in fields, get a rule. | Med | Textual form widgets. Generate `PolicyRule` from structured input. Useful when users know exactly what they want without composing a sentence. |
| Context-aware suggestions | After the agent blocks a threat, suggest related hardening rules. "You just blocked a port scan from 10.0.0.5. Want to also rate-limit new connections on port 22?" | Med | Post-action LLM prompt with threat context. Display as dismissible suggestions in the TUI. |
| Split-view: chat + dashboard | Simultaneously see the chat interface and the live dashboard without switching tabs. Interactive and monitoring in one view. | Low | Textual CSS grid layout. Two primary panes. Already implied by multi-pane table stakes feature but the specific combination matters. |

### Universal Firewall Management

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Rule migration between backends | "Convert my iptables rules to nftables" or "migrate from nftables to cloud security groups." No existing open-source tool does NL-assisted firewall migration. | High | Import from source backend, translate through abstract model, export to target backend. LLM assists with semantic mapping for constructs that do not map 1:1 (e.g., iptables connection tracking vs nftables ct state). |
| Cloud firewall backends (AWS SG, Azure NSG, GCP) | Sysadmins managing hybrid infrastructure want one tool for all firewalls. Cloud firewall APIs are well-documented and SDK-accessible. | High | Each cloud provider is a separate plugin. AWS: boto3 Security Groups. Azure: azure-mgmt-network NSGs. GCP: google-cloud-compute Firewall Rules. Requires authentication handling per provider. |
| Multi-host deployment | Deploy the same policy across multiple hosts/firewalls simultaneously. Common in FortiManager, Panorama. Rare in open-source. | High | Host inventory (YAML config), SSH/agent-based deployment, per-host status tracking. This is the jump from single-machine tool to orchestrator. |
| Policy templates | Predefined security policies: "web server", "database server", "bastion host", "locked down workstation." Apply a template, get a complete ruleset. | Med | Template library in YAML/TOML. LLM can also generate templates from descriptions like "I need rules for a Django app server that talks to PostgreSQL on a separate host." |
| Firewall appliance backends (OPNsense, pfSense) | Extend beyond Linux CLI firewalls to appliances with REST APIs. OPNsense has a comprehensive API. This was already planned in the original `claude.md`. | High | REST API client for OPNsense/pfSense. Translate abstract rules to API payloads. Handle authentication, CSRF tokens, and appliance-specific concepts (aliases, interfaces). |
| Topology-aware conflict detection | Detect conflicts not just within one firewall but across an entire infrastructure. "Host A allows traffic that Host B blocks" -- cross-host policy inconsistencies. | High | Requires multi-host rule collection and cross-host analysis. Build a network topology model and check path-level policy consistency. |

### Autonomous Security Agent

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| LLM-enhanced threat analysis | Use the local LLM to analyze ambiguous situations beyond pattern matching. "Is this traffic pattern normal for a CI/CD pipeline, or is it lateral movement?" No open-source IDS does this with local LLMs. | Med | Feed threat context (log entries, traffic patterns, time of day, historical baseline) to LLM for classification. Use structured output parsing (already built for rule generation). |
| Threat intel feed integration | Subscribe to public threat intelligence feeds (AbuseIPDB, abuse.ch, AlienVault OTX, Emerging Threats). Preemptively block known-bad IPs before they attack. CrowdSec does this collaboratively. | Med | Feed parsers for common formats: STIX/TAXII, CSV blocklists, JSON APIs. Periodic refresh (configurable interval). Store in a local IP reputation database. |
| Network traffic analysis (netflow/pcap) | Go beyond log analysis to actual traffic inspection. Detect anomalies in traffic volume, unusual protocols, data exfiltration patterns. Suricata-level visibility without Suricata complexity. | High | libpcap or AF_PACKET socket for packet capture. Netflow aggregation (source/dest/port/bytes/packets). Anomaly detection on flow statistics. Heavy -- consider integration with existing tools rather than reimplementation. |
| Correlation across data sources | Combine signals: auth failures + port scan + traffic spike from same IP = high confidence attack. Single-source detection has high false positive rates. Multi-source correlation dramatically reduces false positives. | High | Event correlation engine. Time-windowed event matching across sources. Composite scoring: individual signals are LOW confidence, correlated signals are HIGH confidence. |
| Auto-expiring blocks (TTL) | Blocked IPs automatically unblock after a configurable duration. Prevents permanent blocks from accumulating. fail2ban does this; it is expected in automated blocking tools but elevating it because the LLM can suggest appropriate durations. | Low | TTL field on blocking rules. Background timer removes expired blocks. LLM suggests duration based on threat severity: port scan = 1 hour, brute force = 24 hours, confirmed malware = 7 days. |
| Adaptive thresholds | Detection thresholds that adjust based on baseline traffic patterns. A web server seeing 1000 connections/minute is normal; a database server seeing the same is anomalous. Static thresholds produce too many false positives. | High | Baseline learning period (observe normal patterns for N hours/days). Statistical anomaly detection (standard deviations from baseline). This is where the LLM can help -- ask it "is this traffic pattern normal for a [server role]?" |
| Scheduled threat reports | Daily/weekly summary: threats detected, actions taken, current block list, security posture score. Delivered as a report the sysadmin reads with morning coffee. | Low | Aggregate daemon action logs. LLM-generated natural language summary. Output to file, stdout, or optional email/webhook. |
| CrowdSec-style collaborative intelligence | Anonymously share threat data with other AFO instances. If one instance detects an attacker, all instances can preemptively block. Requires careful privacy controls given the local-first philosophy. | High | Opt-in only. Anonymized IP hashes or ranges. Central or P2P coordination server. This conflicts somewhat with the privacy-first ethos and should be very carefully scoped. |

---

## Anti-Features

Features to explicitly NOT build. Including these would hurt the product.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Cloud LLM API support | Core privacy guarantee. Firewall configurations are among the most sensitive infrastructure data. Sending them to OpenAI/Anthropic APIs violates the trust model. Users chose AFO specifically because it is local-only. | Keep Ollama/local LLM as the only supported inference backend. Abstract the LLM interface for different local providers (vLLM, llama.cpp) but never cloud APIs. |
| Web-based dashboard replacement | The Streamlit UI exists as legacy. Building a full web replacement would split development effort, create two interfaces to maintain, and move away from the terminal-first identity. | TUI is the primary interface. Keep Streamlit functional but do not invest in feature parity. Let the TUI be the canonical experience. |
| Full IDS/IPS reimplementation | Suricata and Snort exist and are battle-tested. Reimplementing deep packet inspection, protocol dissection, and signature matching would take years and produce an inferior result. | Integrate WITH Suricata/Snort via their alert outputs (EVE JSON, unified2). Let them do DPI; AFO responds to their alerts with firewall rules. |
| SIEM functionality | Log aggregation, indexing, dashboards, and long-term storage is the domain of the ELK stack, Wazuh, Splunk, Graylog. AFO should not become a log management platform. | Consume logs for threat detection, but do not store/index them long-term. Integrate with existing SIEMs via syslog forwarding or webhook alerts. |
| Mobile app or responsive web UI | Target users are at a terminal. Mobile firewall management is a niche that adds complexity without serving the core audience. | TUI works over SSH from any device, including mobile SSH clients. That is sufficient. |
| User management / multi-tenancy | AFO runs on your infrastructure for your team. Adding user management, RBAC, and multi-tenancy adds massive complexity. This is a tool, not a SaaS platform. | Single-operator model. Use OS-level permissions (sudo, groups) for access control. The daemon runs as a service user; the TUI runs as the operator. |
| Custom scripting/macro language | Inventing a DSL for firewall policies adds learning curve. Natural language IS the scripting language -- that is the entire value proposition. | Use NL for all policy expression. For automation, expose a CLI and MCP interface that scripts can call. |
| Real-time packet capture UI | Displaying live pcap data in a TUI is complex and Wireshark already does it perfectly. Attempting this distracts from the orchestration mission. | If pcap analysis is needed, use it as an internal data source for the detection engine. Never expose raw pcap to the UI -- show analyzed results and detected patterns instead. |

---

## Feature Dependencies

```
                    +-------------------+
                    | Abstract Rule     |
                    | Model (PolicyRule)|
                    +--------+----------+
                             |
              +--------------+--------------+
              |              |              |
    +---------v--+  +--------v---+  +-------v--------+
    | nftables   |  | iptables   |  | Cloud/Appliance|
    | Backend    |  | Backend    |  | Backends       |
    | (refactor) |  | (new)      |  | (new)          |
    +-----+------+  +------+-----+  +-------+--------+
          |                |                 |
          +----------------+-----------------+
                           |
                    +------v------+
                    | Plugin      |
                    | Registry    |
                    +------+------+
                           |
          +----------------+------------------+
          |                |                  |
   +------v------+  +-----v--------+  +------v--------+
   | TUI         |  | Daemon       |  | MCP Server    |
   | Interface   |  | (Autonomous  |  | (existing,    |
   |             |  |  Agent)      |  |  updated)     |
   +------+------+  +-----+--------+  +---------------+
          |                |
          |    +-----------+------------+
          |    |           |            |
          | +--v------+ +--v--------+ +-v-----------+
          | | Log     | | Threat    | | Response    |
          | | Ingest  | | Detector  | | Engine      |
          | +--+------+ +--+--------+ +-+--------+--+
          |    |           |            |         |
          |    +-----------+            |         |
          |          |                  |         |
          |   +------v-------+         |         |
          |   | Correlation  |         |         |
          |   | Engine       +---------+         |
          |   +--------------+                   |
          |                                      |
          +--------------------------------------+
                    TUI displays daemon state
                    via IPC (Unix socket)
```

### Critical dependency chains:

1. **Abstract Rule Model** must exist before any new backend can be built. It is the foundation of universal firewall support. The nftables backend must be refactored to implement this interface before iptables or cloud backends are added.

2. **Plugin Registry** depends on the abstract rule model. It manages backend lifecycle (discovery, initialization, health checking).

3. **TUI Interface** depends on the plugin registry (to show which backends are active) and on the daemon (to show live threat data). However, TUI can be built incrementally: start with chat + rule display against nftables only, then add daemon integration.

4. **Daemon** depends on the plugin registry (to deploy blocking rules to the correct backend) and on log ingestion (to have data to analyze). Can start with basic log parsing before LLM-enhanced analysis.

5. **Log Ingestion** is independent -- can be built and tested without the daemon framework. Start here for the autonomous agent.

6. **Threat Detector** depends on log ingestion. Pattern-based detection can work without the LLM. LLM-enhanced analysis is additive.

7. **Response Engine** depends on the threat detector (to know what to block) and the plugin registry (to deploy blocks to the right backend).

8. **Correlation Engine** depends on multiple log sources being active. Build after at least two ingestion sources work.

9. **TUI-Daemon IPC** is needed for the TUI to display live daemon state. Use a Unix domain socket with a simple JSON protocol or shared SQLite database.

### Build order implications:

- **Phase 1:** Abstract rule model + nftables backend refactor + basic TUI (chat + rules)
- **Phase 2:** iptables backend + daemon framework + log ingestion + basic detection
- **Phase 3:** Threat detection + response engine + TUI daemon integration
- **Phase 4:** Cloud/appliance backends + correlation + advanced detection

---

## MVP Recommendation

### Must ship (table stakes for credibility):

1. **TUI with chat prompt and rule display** -- The TUI is the new primary interface. Without it, the "terminal-first" identity claim is empty. Start with: NL input, rule output, approve/reject, current ruleset view.

2. **Abstract rule model and plugin interface** -- This is the architectural prerequisite for "universal." Ship it with nftables as the only backend, but the interface must be clean enough that iptables can be added without refactoring.

3. **nftables backend refactored as plugin** -- Preserve all existing functionality. The refactor is structural, not behavioral. All existing tests must continue passing.

4. **iptables backend** -- Second backend validates the plugin architecture. If iptables works through the same interface as nftables, the architecture is proven.

5. **Daemon with auth log monitoring and auto-blocking** -- The simplest autonomous use case: detect SSH brute force, auto-block the IP. This is fail2ban-level functionality but integrated into AFO's orchestration model. It proves the autonomous concept.

6. **Action audit trail** -- Every autonomous action logged. Non-negotiable for trust.

7. **Whitelist/allowlist** -- Non-negotiable for preventing the agent from blocking legitimate traffic.

### Defer to later phases:

- **Cloud firewall backends:** High complexity, requires cloud SDK dependencies and auth handling. Ship after the plugin architecture is proven with Linux firewalls.
- **Network traffic analysis (pcap/netflow):** High complexity, requires privileged access beyond NET_ADMIN. Start with log-based detection which is simpler and covers the most common threats.
- **Correlation engine:** Requires multiple data sources. Build after at least auth logs and firewall logs are working independently.
- **Threat intel feeds:** Valuable but additive. Pattern-based detection works without external feeds.
- **Multi-host deployment:** Transforms AFO from single-machine tool to orchestrator. Major scope increase. Defer until single-machine is solid.
- **Collaborative intelligence:** Conflicts with privacy-first ethos and adds significant infrastructure. Only consider after the core product is mature.

---

## Competitive Landscape Context

### What exists today that AFO competes with or complements:

| Tool | What It Does | AFO's Angle |
|------|-------------|-------------|
| fail2ban | Log-based auto-blocking (SSH, web) | AFO does this + NLP rules + multi-backend + LLM analysis |
| CrowdSec | Collaborative threat detection + blocking | AFO is local-only (privacy), no cloud dependency |
| Wazuh | Full HIDS/SIEM with log analysis | AFO is lighter, focused on firewall orchestration, not a SIEM |
| Suricata | Network IDS/IPS | AFO consumes Suricata alerts, does not replace DPI |
| Firewall Builder (fwbuilder) | Multi-firewall GUI rule editor | AFO uses NLP instead of GUI, adds autonomous detection |
| Terraform | IaC for cloud firewalls | AFO is interactive + autonomous, not declarative IaC |
| UFW | Simplified iptables CLI | AFO is AI-powered, multi-backend, autonomous |

### AFO's unique position:

No existing tool combines: (1) natural language firewall control, (2) local LLM inference, (3) multi-backend firewall support, (4) autonomous threat detection and response, and (5) terminal-native interface. Each individual capability exists, but the integration is novel.

---

## Sources

- Domain expertise from training data on: fail2ban, CrowdSec, Wazuh, OSSEC, Suricata, Snort, Firewall Builder, Panorama, FortiManager, k9s, lazydocker, htop, Textual (Python TUI framework)
- Existing AFO codebase analysis (read directly from `/mnt/Projects/AFO/.planning/`)
- **Confidence: MEDIUM** -- All findings are from training data. WebSearch was unavailable for verification of current versions, newest tools, or recent ecosystem changes. The security tooling patterns described here are mature and stable (fail2ban has been around since 2004, nftables since 2014, CrowdSec since 2020), so the risk of stale information is low for architectural patterns. Specific library versions and API details should be verified during implementation.

---

*Feature landscape research: 2026-02-10*
