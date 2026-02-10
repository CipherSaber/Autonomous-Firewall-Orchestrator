# Domain Pitfalls

**Domain:** AI Firewall Orchestration -- Autonomous Security Agent, Universal Plugin Architecture, Log/Traffic Processing, TUI Interface
**Researched:** 2026-02-10
**Overall confidence:** MEDIUM-HIGH (training data; web verification unavailable)

**Note on sources:** WebSearch and WebFetch were unavailable during this research. All findings derive from training data covering firewall management, autonomous security response systems (SOAR/IDS/IPS), plugin architecture patterns, log processing at scale, and Python TUI development. These are mature, well-documented domains with decades of post-mortem literature. Confidence is MEDIUM-HIGH overall but flagged per-pitfall where uncertainty exists.

---

## Critical Pitfalls

Mistakes that cause security incidents, system outages, or architectural rewrites.

---

### Pitfall 1: Autonomous Rule Feedback Loops (Self-Amplifying Blocks)

**Severity:** CRITICAL -- can cause complete network outage
**Confidence:** HIGH (well-documented in IDS/IPS/SOAR literature)
**Phase:** Autonomous daemon / threat response

**What goes wrong:** The autonomous daemon detects suspicious traffic and auto-blocks an IP. The block causes upstream health checks to fail, generating new "anomalous" log entries. The daemon interprets these new anomalies as a second threat and blocks additional IPs. This cascading loop can escalate to blocking legitimate infrastructure (DNS servers, gateways, monitoring endpoints) within seconds, causing a complete network outage.

Real-world precedent: Automated IPS systems have historically caused outages by blocking their own management interfaces, NTP servers (causing time drift that triggers further anomalies), or DNS resolvers (causing application failures that look like attacks).

**Why it happens:**
- The daemon's own actions generate log events indistinguishable from threats
- No distinction between primary threats and secondary effects of defensive actions
- Blocking network services creates cascading failures that produce anomaly signals
- The system lacks awareness that it caused the condition it is now responding to

**Consequences:**
- Complete network blackout if gateway/DNS/management IPs are blocked
- Loss of management access to the firewall (cannot undo the damage remotely)
- If heartbeat rollback is disabled or not covering daemon actions, recovery requires physical/console access
- Potential data loss from severed active connections

**Prevention:**
1. **Never-block list:** Hardcode a protected IP/subnet list that the daemon cannot block under any circumstances: management IPs, DNS servers, gateways, NTP servers, the machine's own IPs, monitoring endpoints. This list must not be modifiable by the LLM.
2. **Action attribution:** Tag every firewall rule the daemon creates with a unique identifier. When analyzing logs, filter out events that are downstream consequences of the daemon's own recent actions.
3. **Rate limiting on rule creation:** Cap the number of rules the daemon can create per time window (e.g., max 10 blocks per minute). If the cap is hit, halt autonomous action and alert the human.
4. **Cooldown periods:** After blocking an IP, wait N seconds before analyzing any new anomalies related to traffic patterns involving that IP.
5. **Circuit breaker:** If the daemon creates more than N rules in M minutes, automatically pause autonomous mode and switch to alert-only.

**Detection (warning signs):**
- Daemon creating rules at an accelerating rate
- Blocked IPs include infrastructure addresses
- Network connectivity tests failing after daemon actions
- Log volume spiking after a block action

**AFO-specific risk:** The existing heartbeat rollback in `deployer.py` covers individual rule deployments but not a series of daemon-generated blocks. The daemon needs its own meta-level safety mechanism beyond per-rule heartbeats.

---

### Pitfall 2: LLM Hallucinating Firewall Rules in Autonomous Mode

**Severity:** CRITICAL -- security incident (opening ports, wrong IPs)
**Confidence:** HIGH (directly observed in existing codebase concerns)
**Phase:** Autonomous daemon / threat response

**What goes wrong:** In human-in-the-loop mode, a hallucinated rule is caught during review. In autonomous mode, the LLM misinterprets a threat signal and generates a rule that opens a port instead of closing it, blocks the wrong IP, or creates an overly broad rule (e.g., blocking an entire /8 subnet). With no human review gate, the bad rule goes live immediately.

Specific scenarios:
- LLM confuses `accept` and `drop` actions in its generated rule
- LLM targets the wrong IP address (source vs. destination confusion)
- LLM generates a rule for the wrong chain (input vs. forward vs. output)
- LLM creates a rule with overly broad match criteria (any protocol, any port)

**Why it happens:**
- Small local models (3B-8B parameters) have higher hallucination rates than large cloud models
- The model may not reliably distinguish between "block traffic FROM bad IP" and "block traffic TO bad IP"
- Autonomous mode bypasses the human review gate that currently catches these errors
- Under time pressure (real-time threat response), the system may skip validation steps

**Consequences:**
- Opening firewall ports = direct security vulnerability
- Blocking wrong IPs = denial of service to legitimate users
- Overly broad rules = collateral damage across the network
- All consequences happen silently without human awareness

**Prevention:**
1. **Action-restricted autonomous mode:** The daemon should ONLY be allowed to create `drop`/`reject` rules autonomously. Never `accept`. This is enforced at the deployment layer, not the LLM layer.
2. **Deterministic rule generation for autonomous mode:** Do NOT use the LLM to generate nftables syntax in autonomous mode. Instead, use the LLM only for threat classification, then use deterministic templates to create the actual firewall rules. Template: `add rule inet filter input ip saddr {detected_ip} drop comment "afo-daemon: {threat_type} at {timestamp}"`.
3. **Scope limits:** Autonomous rules may only target specific IPs (not subnets broader than /24), specific ports, and must use the `drop` action. Enforce this with Pydantic validation on autonomous rule proposals.
4. **Shadow-first deployment:** In autonomous mode, deploy rules in a "shadow" state first (log only, no action) for a configurable period before activating them. If the rule would have triggered on legitimate traffic during the shadow period, discard it.
5. **Mandatory `nft --check` before autonomous deployment:** The existing validation pipeline must be non-skippable for daemon-generated rules.

**Detection (warning signs):**
- Autonomous rules containing `accept` action
- Rules with subnet masks broader than /24
- Rules targeting well-known ports (22, 80, 443) for blocking
- Rules that conflict with existing allow rules

**AFO-specific risk:** The existing `deploy_policy()` has a `REQUIRE_APPROVAL` env var that defaults to `1`. The autonomous daemon will need to bypass this. The bypass mechanism must be carefully scoped so only the daemon process can use it, and only for restricted rule types.

---

### Pitfall 3: Plugin Abstraction Leaking Firewall Semantics

**Severity:** CRITICAL -- causes incorrect rules on non-nftables backends
**Confidence:** HIGH (well-documented abstraction problem)
**Phase:** Plugin architecture

**What goes wrong:** The universal plugin interface is designed around nftables concepts (tables, chains, families, hooks, priorities). When implementing plugins for iptables, cloud firewalls (AWS Security Groups, Azure NSGs), or appliance APIs (OPNsense, pfSense), the abstraction does not map cleanly. Developers force-fit non-nftables concepts into nftables-shaped interfaces, producing rules that are syntactically valid but semantically wrong on the target platform.

Specific mismatches:
- **nftables vs. iptables:** nftables has families (inet, ip, ip6, bridge, arp); iptables has fixed tables (filter, nat, mangle, raw). Chain types differ. nftables uses named sets and maps; iptables uses ipset as a separate system.
- **nftables vs. AWS Security Groups:** SGs are stateful-only, allow-only (no deny rules in SGs, use NACLs for deny). SGs have no concept of chains or hook priorities. SGs are per-ENI, not per-host.
- **nftables vs. OPNsense API:** OPNsense uses pf (packet filter) under the hood, which has fundamentally different rule evaluation (last match wins vs. first match wins). OPNsense API is REST-based with UUIDs, not CLI-based.

**Why it happens:**
- The team builds the abstraction by generalizing FROM the first implementation (nftables) rather than designing FROM the problem space
- "Works on nftables" becomes the test, and other backends are squeezed to fit
- nftables is the most expressive of these firewall systems, so the abstraction carries capabilities that do not exist elsewhere

**Consequences:**
- Rules that "look right" in the abstraction but do wrong things on the target platform
- Silent security gaps (rule exists but does not actually filter traffic as intended)
- Features that work on nftables but crash or no-op on other backends
- Eventually, plugins accumulate backend-specific hacks that defeat the purpose of the abstraction

**Prevention:**
1. **Design the interface from the intersection, not the union.** The plugin interface should represent what ALL backends can do, not everything nftables can do. Start with: block IP, allow IP+port, rate limit, log. Complex nftables features (sets, maps, verdict maps, ct helpers, flowtables) are nftables-plugin-specific, not part of the universal interface.
2. **Capability negotiation.** Each plugin declares its capabilities: `supports_stateful`, `supports_deny`, `supports_rate_limit`, `supports_ipv6`, `evaluation_order` (first-match vs. last-match). The orchestrator checks capabilities before generating rules and fails explicitly rather than silently.
3. **Semantic validation per plugin.** Each plugin validates rules against its own constraints. The nftables plugin accepts anything; the AWS SG plugin rejects deny rules; the OPNsense plugin warns about evaluation order implications.
4. **Use the "two rules" test.** Before finalizing the interface, implement two rules ("block this IP" and "allow HTTP from this subnet") on three different backends. If the interface cannot express both rules cleanly on all three, redesign.

**Detection (warning signs):**
- Plugin interface has fields like `table_name` or `chain_name` that only make sense for nftables/iptables
- Cloud firewall plugins have methods that silently no-op
- Plugin tests only run against nftables
- Interface methods have `**kwargs` for "backend-specific options"

**AFO-specific risk:** The existing `FirewallRule` Pydantic model in `afo_mcp/models.py` is deeply nftables-specific: it has `table`, `chain`, `family` (nftables families), `protocol` as nftables enum values. This model cannot represent AWS Security Group rules or OPNsense pf rules. The plugin architecture must introduce a new abstract rule model, with `FirewallRule` becoming the nftables-specific implementation.

---

### Pitfall 4: Losing Management Access via Autonomous Firewall Rules

**Severity:** CRITICAL -- system becomes unrecoverable remotely
**Confidence:** HIGH (the #1 cause of firewall-related outages)
**Phase:** Autonomous daemon, plugin architecture (deployment)

**What goes wrong:** The daemon deploys a rule that blocks SSH, the management API, or the network path between the operator and the firewall host. The operator can no longer reach the system to undo the change. If heartbeat rollback is not active (e.g., the daemon confirmed the deployment, or the heartbeat check passes because it runs locally), the lockout is permanent until physical access or out-of-band console is available.

**Why it happens:**
- The heartbeat function checks local connectivity (can this machine reach the internet?) rather than management-plane reachability (can the admin reach this machine?)
- Daemon rules may be auto-confirmed without waiting for the heartbeat timeout
- A rule blocking inbound SSH does not affect outbound heartbeat checks
- Rules deployed in "autonomous" mode may skip the heartbeat entirely for speed

**Consequences:**
- Complete loss of remote management access
- Requires physical console access or IPMI/iLO/DRAC to recover
- On cloud VMs, may require instance reboot or serial console
- On container deployments, may require Docker exec from the host

**Prevention:**
1. **Management-plane heartbeat:** The heartbeat function must verify that the management interface is reachable FROM the outside, not just that the machine can reach out. Options: have an external monitoring endpoint ping the management port; or have the heartbeat open a test connection TO the management IP from a known-good source.
2. **Pre-deployment management rule check:** Before deploying ANY rule (human or autonomous), verify that the proposed rule does not match the management IP/port. Reject rules that would affect management connectivity.
3. **Persistent management allow rule:** Deploy a high-priority rule allowing management access that cannot be overridden by daemon-generated rules. Use nftables chain priorities: management rules at priority -200, daemon rules at priority 0.
4. **Out-of-band recovery:** Document a recovery procedure that does not require network access. For containers: `docker exec`. For VMs: serial console. For bare metal: IPMI. Include this in deployment documentation.
5. **"Canary" connection:** After each autonomous deployment, the daemon immediately tests that it can still receive commands via its management interface. If the test fails, immediate automatic rollback.

**Detection (warning signs):**
- Proposed rule matches the management subnet or SSH port
- Heartbeat function only tests outbound connectivity
- No explicit management-plane protection rules in the ruleset

**AFO-specific risk:** The existing heartbeat in `deployer.py` (lines 74-108) uses a caller-provided `heartbeat_fn`. If no function is provided, the heartbeat just runs on a timer and rolls back after timeout. There is no default management-plane check. The daemon must provide a meaningful heartbeat function that tests management reachability.

---

### Pitfall 5: Log Processing Overwhelms the System Under Attack

**Severity:** CRITICAL -- daemon fails precisely when needed most
**Confidence:** HIGH (classic monitoring system failure mode)
**Phase:** Autonomous daemon, log ingestion

**What goes wrong:** During a DDoS attack or port scan, log volume increases by 100x-1000x. The daemon tries to process every log line through the LLM for threat analysis, consuming all CPU/memory. The LLM inference queue backs up. The daemon falls behind real-time, analyzing stale data. Eventually, the daemon crashes (OOM) or becomes so slow that threats are detected minutes or hours after they began. The system fails at precisely the moment it is most needed.

**Why it happens:**
- No distinction between "process every event" and "sample at a sustainable rate"
- LLM inference is orders of magnitude slower than log generation rate
- During an attack, the interesting events (the attack traffic) are mixed with flood noise
- No backpressure mechanism: log reader produces faster than LLM consumer can process

**Consequences:**
- Daemon OOM-killed during attacks
- Threat detection latency increases from seconds to minutes/hours
- System appears healthy during normal traffic but fails catastrophically under load
- Ollama instance becomes unresponsive, blocking both daemon and human-interactive use

**Prevention:**
1. **Two-tier analysis.** Use fast deterministic rules (regex/pattern matching) for high-volume triage. Only escalate ambiguous events to the LLM. Known-bad patterns (port scans, brute force, known exploit signatures) should be detected without LLM involvement.
2. **Sampling and aggregation.** During high-volume periods, aggregate events (e.g., "47 connection attempts from 10.0.0.5 to port 22 in the last 60 seconds") and send the summary to the LLM, not individual events.
3. **Bounded queue with backpressure.** Use a fixed-size queue for LLM analysis. When the queue is full, drop low-priority events (not high-priority). Log when events are dropped.
4. **Rate-aware processing.** Track log ingestion rate. When rate exceeds a threshold, automatically switch to sampling mode. When rate returns to normal, resume full processing.
5. **Separate Ollama instances.** Use a dedicated Ollama instance for daemon analysis, separate from the interactive TUI instance. Prevent the daemon from starving the human interface.
6. **Pre-filter with bloom filters or IP reputation cache.** Keep an in-memory set of recently-analyzed IPs. Do not re-analyze the same IP within a cooldown window.

**Detection (warning signs):**
- Daemon memory usage growing without bound
- LLM inference queue depth increasing
- Gap between log timestamp and analysis timestamp growing
- Ollama response times increasing during traffic spikes

---

## Moderate Pitfalls

Mistakes that cause significant technical debt, rework, or degraded functionality.

---

### Pitfall 6: Daemon and TUI Fighting Over Shared State

**Severity:** MODERATE -- causes data corruption, UX confusion
**Confidence:** MEDIUM-HIGH
**Phase:** TUI interface, daemon architecture

**What goes wrong:** The daemon runs as a background process modifying firewall rules. The TUI runs as an interactive process displaying firewall state and accepting commands. Both read/write to the same firewall (via nft), the same audit log, and potentially the same rule tracking database. Race conditions occur: the TUI shows a ruleset that the daemon modifies while the user is reviewing it; the user deploys a rule that conflicts with a daemon-deployed rule; the daemon rolls back a rule the user just confirmed.

**Why it happens:**
- No coordination protocol between daemon and TUI processes
- Firewall state (nftables ruleset) is a shared mutable resource with no locking
- Both processes may use the deployer module simultaneously, corrupting the global `_active_heartbeats` dict
- Event ordering is non-deterministic across processes

**Prevention:**
1. **Single writer architecture.** All firewall modifications go through a single deployment service (the daemon). The TUI sends deployment requests TO the daemon rather than calling `nft` directly. The daemon queues and serializes all deployments.
2. **Event bus for state changes.** When the daemon modifies the firewall, it publishes an event. The TUI subscribes and refreshes its view. This prevents stale state display.
3. **Rule ownership tracking.** Tag rules with their source: `daemon`, `user-tui`, `user-mcp`. The daemon should never modify or roll back user-created rules. The user should be warned before modifying daemon-created rules.
4. **Process-safe state management.** Replace in-memory dicts (`_active_heartbeats`) with a proper IPC mechanism: Unix domain socket, SQLite database, or shared memory with locking.

**Detection (warning signs):**
- TUI displaying stale ruleset after daemon action
- Heartbeat rollback undoing user-confirmed rules
- Concurrent deployment errors or partial rule application

---

### Pitfall 7: Plugin Interface Too Thin (Lowest Common Denominator Trap)

**Severity:** MODERATE -- cripples advanced backends
**Confidence:** HIGH (the inverse of Pitfall 3)
**Phase:** Plugin architecture

**What goes wrong:** To avoid the leaky abstraction problem (Pitfall 3), the team designs the plugin interface to only include features available on ALL backends: block/allow an IP. The nftables plugin cannot access sets, rate limiting, connection tracking, NAT, or any of nftables' advanced features through the universal interface. Users who chose AFO specifically for nftables management find the new version less capable than the old one.

**Why it happens:**
- Overcorrection from Pitfall 3
- Cloud firewalls (AWS SGs) have very limited capabilities, dragging the interface down
- "Universal" is interpreted as "identical behavior everywhere" rather than "works everywhere with platform-appropriate behavior"

**Prevention:**
1. **Tiered interface design.** Core interface: `block_ip()`, `allow_port()`, `list_rules()`, `remove_rule()`. Extended interface: `rate_limit()`, `create_set()`, `stateful_rule()`. Backend-specific interface: full nftables syntax passthrough, OPNsense API raw access.
2. **Capability-based feature exposure.** The TUI and LLM check plugin capabilities before offering features. If the user is on nftables, they see the full feature set. If on AWS SGs, they see the restricted set. No features silently no-op.
3. **Preserve the existing nftables-specific code path.** Do not break the existing `FirewallRule.to_nft_command()` flow. The plugin architecture adds a new abstract layer above it; it does not replace the nftables-specific logic.

**Detection (warning signs):**
- Feature requests to "pass through" raw nftables commands
- Users switching back to direct nft CLI because the abstraction is too limiting
- Plugin interface has no way to express rules that the existing codebase handles

---

### Pitfall 8: Threat Intelligence Feed Poisoning

**Severity:** MODERATE -- causes blocking of legitimate IPs
**Confidence:** MEDIUM (documented in threat intel literature, but specific to AFO's local-LLM context)
**Phase:** Autonomous daemon, threat intel integration

**What goes wrong:** The daemon ingests a threat intelligence feed (known bad IPs, domains, CVEs). The feed data is either stale (IPs have been reassigned to legitimate users), compromised (attacker injects their target's IPs into the feed), or overly broad (entire cloud provider IP ranges flagged). The daemon blindly blocks all IPs from the feed, causing legitimate traffic to be dropped.

**Why it happens:**
- Threat intel feeds vary wildly in quality and freshness
- IPs are dynamic; an IP that hosted malware last month may host a legitimate service today
- Free/open threat intel feeds have higher false positive rates
- No validation of feed data against local traffic patterns

**Prevention:**
1. **Feed quality scoring.** Track the false positive rate of each feed. Feeds with high FP rates get lower confidence scores, requiring human review before autonomous blocking.
2. **Cross-reference with local traffic.** Before blocking a threat-intel IP, check if that IP has established, long-running sessions with the protected network. If so, flag for human review rather than auto-blocking.
3. **Time-bounded blocks from threat intel.** Auto-blocks from threat intel should have automatic expiration (e.g., 24 hours). The daemon must re-evaluate before renewing.
4. **Feed age checking.** Discard indicators older than a configurable threshold (e.g., 7 days for IP-based indicators, 30 days for domain-based).
5. **Whitelisting.** Allow operators to whitelist IPs/subnets that should never be blocked regardless of threat intel. This overlaps with the never-block list from Pitfall 1.

**Detection (warning signs):**
- Legitimate services becoming unreachable after threat intel feed update
- Large number of blocks from a single feed in a short period
- Blocked IPs belonging to major cloud providers or CDNs

---

### Pitfall 9: nftables Flush-and-Replace Destroys Stateful Connections

**Severity:** MODERATE -- causes brief outage on every rule change
**Confidence:** HIGH (nftables-specific, well-documented)
**Phase:** Plugin architecture (nftables plugin), daemon deployment

**What goes wrong:** The current deployment strategy in `deployer.py` uses `nft flush ruleset` followed by `nft -f backup.nft` for rollback. During the interval between flush and restore, there are ZERO firewall rules. All traffic is allowed (or denied, depending on default policy). Additionally, `nft flush ruleset` destroys all connection tracking state, causing established TCP connections to be dropped when the new ruleset is loaded and stateful rules (`ct state established,related accept`) no longer match them.

**Why it happens:**
- `nft flush ruleset` is the "easy" approach to ensuring clean state
- The time window between flush and restore is typically milliseconds, so it appears safe in testing
- Connection tracking state loss is invisible unless the operator checks established connections

**Prevention:**
1. **Use `nft -f` with atomic replacement.** nftables supports atomic ruleset replacement: write the COMPLETE new ruleset (not just the delta) to a file and load it with `nft -f`. This replaces the old ruleset in a single kernel operation with no gap. Do NOT use `flush` followed by `load`.
2. **For rollback, use atomic replace too.** Instead of `flush + load`, use `nft -f backup.nft` where the backup file includes a `flush ruleset` directive AS ITS FIRST LINE, followed by the complete ruleset. nftables processes the entire file atomically.
3. **For delta changes (adding/removing single rules),** use `nft add rule` / `nft delete rule` instead of reloading the entire ruleset. This preserves connection tracking state.
4. **The daemon should prefer delta operations.** When auto-blocking an IP, use `nft add rule` to add a single block rule, not a full ruleset reload. This is faster and preserves state.

**Detection (warning signs):**
- Brief connectivity blips during rule deployment
- Established connections dropping after rule changes
- Rollback procedure using `flush` as a separate step from `load`

**AFO-specific risk:** `_restore_backup()` in `deployer.py` (lines 57-62) explicitly calls `nft flush ruleset` as a separate subprocess call before `nft -f backup.nft`. This creates a race window. The backup file should include `flush ruleset` as its first line and be loaded in a single atomic `nft -f` operation.

---

### Pitfall 10: Textual TUI Blocking the Event Loop with Synchronous Operations

**Severity:** MODERATE -- causes frozen/unresponsive UI
**Confidence:** MEDIUM (Textual-specific; based on training data patterns)
**Phase:** TUI interface

**What goes wrong:** Textual (the Python TUI framework) is built on `asyncio`. Long-running synchronous operations -- like calling Ollama for LLM inference (which can take 5-30 seconds), running `nft list ruleset`, reading large log files, or querying threat intel feeds -- block the asyncio event loop. The TUI freezes completely: no key input, no screen updates, no status indicators. The user thinks the application has crashed.

**Why it happens:**
- The existing codebase uses synchronous `subprocess.run()` calls and synchronous `httpx` calls
- Developers call sync functions directly from Textual event handlers without wrapping them
- LLM inference via Ollama is inherently slow (seconds to tens of seconds)
- "It works in Streamlit" -- Streamlit handles blocking differently (reruns the script)

**Prevention:**
1. **Run all I/O in workers.** Textual provides `run_worker()` for offloading blocking operations to threads. Every LLM call, subprocess call, and network request must use this pattern. Never call `subprocess.run()` directly in a Textual event handler.
2. **Use `asyncio.create_subprocess_exec()` instead of `subprocess.run()`.** This is the async equivalent and integrates natively with Textual's event loop.
3. **Progress indicators for all blocking operations.** When the user triggers a rule generation (5-30 second LLM call), show a spinner or progress bar immediately. This is not just UX polish -- it prevents the user from thinking the app crashed and pressing Ctrl+C.
4. **Timeout all external calls.** If Ollama is unresponsive, the TUI should timeout and show an error, not freeze indefinitely.
5. **Separate the agent/daemon logic from TUI event handlers.** The TUI should communicate with the agent/daemon via an async message-passing interface (asyncio queues, Unix sockets), not direct function calls.

**Detection (warning signs):**
- TUI stops responding to keypresses during operations
- Screen does not update while waiting for LLM response
- Ctrl+C needed to exit during long operations
- Test: press a key during LLM inference -- if the keypress is not echoed, the event loop is blocked

---

### Pitfall 11: Daemon Process Management and Lifecycle Gaps

**Severity:** MODERATE -- daemon silently dies, no monitoring
**Confidence:** HIGH
**Phase:** Autonomous daemon

**What goes wrong:** The daemon is implemented as a simple Python script that runs in the foreground or background. It has no supervision, no restart-on-crash, no health checks, no graceful shutdown, no signal handling. When it crashes (OOM, unhandled exception, Ollama connection lost), nobody notices until a threat goes undetected.

**Why it happens:**
- Focus on the "interesting" daemon logic (threat detection, LLM analysis) while neglecting operational concerns
- "I'll add systemd integration later" -- later never comes
- Testing happens with manual starts, not with production process managers

**Prevention:**
1. **Implement proper signal handling.** Handle SIGTERM for graceful shutdown (finish current analysis, clean up temporary rules). Handle SIGHUP for configuration reload. Handle SIGUSR1 for status dump.
2. **Systemd service unit.** Provide a systemd service file with `Restart=on-failure`, `WatchdogSec` for health monitoring, and proper `After=network-online.target ollama.service` dependencies.
3. **Health check endpoint.** The daemon should expose a simple health check (Unix socket or localhost HTTP) that reports: is it running, when did it last analyze a log, how deep is its processing queue, is Ollama reachable.
4. **Structured logging from day one.** Use Python `logging` module with structured output (JSON or structured format). Log every daemon action, every rule created, every threat detected. This is not optional for a security tool.
5. **PID file and single-instance lock.** Prevent multiple daemon instances from running simultaneously (each would create conflicting firewall rules).

**Detection (warning signs):**
- No process manager integration
- Daemon started with `python daemon.py &`
- No structured logging
- No way to check daemon health from TUI

---

### Pitfall 12: Inadequate Audit Trail for Autonomous Actions

**Severity:** MODERATE -- compliance failure, forensic gaps
**Confidence:** HIGH (the existing codebase already flags missing audit logging)
**Phase:** Autonomous daemon, TUI interface

**What goes wrong:** The daemon auto-blocks an IP at 3 AM. The next morning, a customer reports they cannot access the service. The operator looks at the TUI and sees the block rule but has no record of: what triggered the block, what evidence the daemon analyzed, what confidence level the LLM assigned, whether other response options were considered, or what the network state looked like at the time. The operator cannot determine if the block was correct or a false positive, and cannot improve the system.

**Why it happens:**
- The existing codebase uses `print()` with no logging framework
- In-memory state (Streamlit session state) is lost on restart
- The planned PostgreSQL audit store was never implemented
- Focus on "make it work" before "make it auditable"

**Prevention:**
1. **Log before act.** Every autonomous action must be logged BEFORE the firewall rule is deployed: the triggering event(s), the LLM's analysis, the proposed rule, the validation result, and the deployment result. If the deployment crashes, the log still shows what was attempted.
2. **Structured decision records.** For each autonomous action, store: `{timestamp, trigger_events: [...], llm_analysis: "...", proposed_rule: {...}, validation: {...}, confidence: 0.87, action_taken: "block", rule_id: "...", deployment_result: {...}}`.
3. **Immutable audit log.** Use an append-only log (SQLite WAL mode, append-only file, or PostgreSQL with no DELETE permissions). The daemon should not be able to modify or delete its own audit records.
4. **TUI audit viewer.** The TUI should have a dedicated view for browsing the audit log: what the daemon did, when, and why. This is table-stakes for a security tool.
5. **Build the audit system BEFORE the autonomous daemon.** If audit logging is added after the daemon is built, critical events will be missed during development and testing.

**Detection (warning signs):**
- Cannot answer "why was this IP blocked?" from system logs
- No persistent storage for daemon decisions
- Audit records only exist in memory
- No way to reconstruct the daemon's reasoning for a past action

---

### Pitfall 13: iptables/nftables Coexistence Conflicts

**Severity:** MODERATE -- silent rule conflicts, rules not taking effect
**Confidence:** HIGH (well-documented Linux firewall issue)
**Phase:** Plugin architecture (iptables plugin)

**What goes wrong:** Many Linux systems have both `iptables` and `nftables` installed. Modern distros ship `iptables-nft` (iptables commands backed by the nftables kernel subsystem) rather than `iptables-legacy`. When AFO's nftables plugin creates rules and the iptables plugin also creates rules on the same system, they both write to the nftables kernel backend but in different nftables tables. The rules interact unpredictably, and `nft list ruleset` shows both sets of rules in the same output. Rule conflicts occur silently.

**Why it happens:**
- `iptables-nft` translates iptables commands into nftables rules stored in tables named `filter`, `nat`, `mangle` (in the `ip` family), which look different from the typical `inet filter` tables that nftables scripts create
- Developers test plugins in isolation, never on the same system simultaneously
- The conflict detection in `afo_mcp/tools/conflicts.py` does not distinguish between nftables-native and iptables-nft rules

**Prevention:**
1. **Detect the iptables backend at plugin initialization.** Check if `/usr/sbin/iptables` is `iptables-nft` or `iptables-legacy` (`iptables --version` shows `nf_tables` or `legacy`). Warn if both nftables and iptables-nft are in use.
2. **Mutual exclusion.** If the nftables plugin is active, do not activate the iptables plugin on the same system (and vice versa). Document this constraint.
3. **Namespace nftables tables.** AFO-managed nftables rules should use a distinctive table name (e.g., `afo_filter` instead of `filter`) to avoid collisions with system-managed or iptables-nft rules.

**Detection (warning signs):**
- `nft list ruleset` shows tables the AFO did not create
- Rules deployed by AFO are not having the expected effect
- Both iptables and nftables commands are available on the system

---

## Minor Pitfalls

Mistakes that cause UX issues, developer friction, or cosmetic problems.

---

### Pitfall 14: TUI and Streamlit Maintaining Separate Codepaths

**Severity:** MINOR (initially) escalating to MODERATE (over time)
**Confidence:** MEDIUM-HIGH
**Phase:** TUI interface

**What goes wrong:** The TUI is built as a separate frontend that directly imports the same agent/tool modules as the Streamlit app. Over time, feature development happens in one frontend but not the other. The Streamlit app supports features the TUI does not, and vice versa. Bug fixes must be applied in two places. The team effectively maintains two products.

**Prevention:**
1. **Extract a CLI/API service layer.** All orchestration logic (rule generation, deployment, monitoring) should live in a service layer that both TUI and Streamlit import. Neither frontend should contain business logic.
2. **Designate one frontend as primary.** Per the project plan, TUI is primary. Streamlit is legacy. Accept that Streamlit will not get new features. Do not try to maintain feature parity.
3. **Share state management.** Both frontends should read from the same state source (daemon status, rule history, audit log). Do not build parallel state management.

**Detection (warning signs):**
- TUI and Streamlit have different views of system state
- Bug exists in one frontend but not the other
- Business logic in TUI event handlers

---

### Pitfall 15: Overly Aggressive Threat Detection Sensitivity Defaults

**Severity:** MINOR (UX) escalating to MODERATE (trust erosion)
**Confidence:** MEDIUM
**Phase:** Autonomous daemon configuration

**What goes wrong:** The daemon ships with aggressive default detection thresholds (e.g., 3 failed SSH logins = block). Users in environments with many legitimate login failures (shared servers, development environments, automated deployment systems) find the daemon blocking their own users within minutes of activation. They disable the daemon entirely and never re-enable it. The feature is technically functional but practically useless.

**Prevention:**
1. **Conservative defaults.** Ship with thresholds that produce zero false positives on a typical server: 50+ failed SSH logins from a single IP in 5 minutes, 100+ port scans from a single IP in 1 minute. Let users tighten thresholds.
2. **Learning mode.** First 24-48 hours in "observe only" mode: detect and log, but do not block. Show the operator what WOULD have been blocked. Let them adjust thresholds before enabling autonomous response.
3. **Per-source tuning.** Allow different thresholds for different source networks. Internal networks get higher thresholds than external.
4. **Configurable aggression levels.** The PROJECT.md already mentions "configurable aggression levels" -- implement this as a first-class feature with named presets (paranoid, balanced, permissive) plus custom.

**Detection (warning signs):**
- Users disabling the daemon after first day
- High false positive rate in audit logs
- Thresholds that would trigger on normal development activity

---

### Pitfall 16: Inconsistent Rule Identification Across Components

**Severity:** MINOR -- causes confusion, complicates debugging
**Confidence:** MEDIUM
**Phase:** Plugin architecture, daemon, TUI

**What goes wrong:** The daemon creates a rule and assigns it ID `threat-2026-001`. The nftables plugin deploys it as an nft rule with handle `42`. The audit log refers to it by the daemon's ID. The TUI shows the nft handle. The user asks about `threat-2026-001` and the system cannot find it because the nft handle is what is stored. Rule comments in nftables have a 128-byte limit and may be truncated.

**Prevention:**
1. **Canonical ID system.** Each rule gets a UUID assigned at creation time. This UUID is stored in the rule's comment field in nftables, in the audit log, in the daemon's tracking database, and displayed in the TUI.
2. **ID mapping table.** Maintain a mapping between AFO rule IDs and backend-specific identifiers (nft handles, AWS SG rule IDs, OPNsense UUIDs).
3. **Rule reconciliation.** Periodically compare the mapping table against the live firewall state. Flag rules that exist in one but not the other (orphaned rules, externally-modified rules).

**Detection (warning signs):**
- Different components refer to the same rule by different identifiers
- Cannot trace a rule from TUI display to nftables output to audit log
- `nft list ruleset` shows rules without AFO comment markers

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Severity | Mitigation |
|-------------|---------------|----------|------------|
| Plugin architecture design | Pitfall 3 (leaky abstraction) + Pitfall 7 (too thin) | CRITICAL + MODERATE | Design from intersection; use capability negotiation; preserve nftables-specific path |
| Autonomous daemon core | Pitfall 1 (feedback loops) + Pitfall 2 (LLM hallucination) | CRITICAL + CRITICAL | Never-block list; deterministic templates for auto-response; circuit breaker; rate limiting |
| Daemon deployment integration | Pitfall 4 (management lockout) + Pitfall 9 (flush-and-replace) | CRITICAL + MODERATE | Management-plane heartbeat; atomic nft replacement; pre-deploy management check |
| Log/traffic ingestion | Pitfall 5 (overwhelm under attack) | CRITICAL | Two-tier analysis; sampling/aggregation; bounded queues; separate Ollama instances |
| TUI development | Pitfall 10 (blocking event loop) + Pitfall 14 (dual codepath) | MODERATE + MINOR | Workers for all I/O; service layer extraction; async subprocess calls |
| Daemon lifecycle | Pitfall 11 (process management) + Pitfall 12 (audit trail) | MODERATE + MODERATE | Systemd service; structured logging; build audit before daemon |
| Threat intel integration | Pitfall 8 (feed poisoning) | MODERATE | Feed quality scoring; cross-reference local traffic; time-bounded blocks |
| Multi-backend deployment | Pitfall 13 (iptables/nftables coexistence) | MODERATE | Backend detection; mutual exclusion; namespaced tables |
| Configuration/UX | Pitfall 15 (aggressive defaults) | MINOR | Conservative defaults; learning mode; named presets |
| Rule tracking | Pitfall 16 (inconsistent IDs) | MINOR | Canonical UUID system; ID mapping table; reconciliation |

## Implementation Order Recommendations Based on Pitfalls

The pitfall analysis suggests this defensive ordering:

1. **Audit system first** (addresses Pitfall 12). Build structured logging and audit storage before building the daemon. Every subsequent feature benefits from auditability.
2. **Plugin architecture before daemon** (addresses Pitfalls 3, 7, 13). The daemon must deploy through the plugin layer. Designing the daemon deployment before the plugin layer means rework.
3. **Safety mechanisms before autonomous logic** (addresses Pitfalls 1, 2, 4). Implement the never-block list, circuit breaker, management-plane protection, and rate limits BEFORE implementing threat detection and auto-response. These are not enhancements -- they are prerequisites.
4. **TUI as a view layer** (addresses Pitfalls 10, 14). Build the TUI as a thin presentation layer over the service/daemon layer, not as an independent application with its own logic.

## Sources

- Training data on nftables wiki scripting and atomic rule replacement documentation
- Training data on IDS/IPS/SOAR failure modes (Snort, Suricata, TheHive/Cortex post-mortems)
- Training data on firewall management best practices (CIS Benchmarks, NIST 800-41)
- Training data on Python Textual framework architecture patterns
- Training data on plugin architecture patterns (hexagonal architecture, strategy pattern literature)
- Direct analysis of existing AFO codebase: `afo_mcp/tools/deployer.py`, `afo_mcp/security.py`, `afo_mcp/models.py`, `.planning/codebase/CONCERNS.md`, `.planning/codebase/ARCHITECTURE.md`
- **No web verification was possible** -- all findings should be validated against current documentation during implementation

---

*Pitfalls research: 2026-02-10*
*Confidence: MEDIUM-HIGH (training data only; web verification unavailable)*
