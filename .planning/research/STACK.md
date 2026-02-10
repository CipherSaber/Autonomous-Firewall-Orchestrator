# Stack Research

**Domain:** AI-powered firewall orchestrator -- TUI, universal plugin architecture, autonomous security daemon
**Researched:** 2026-02-10
**Confidence:** MEDIUM (no live version verification available; versions based on training data + installed package inspection)

**Methodology note:** WebSearch and WebFetch were unavailable during this research session. Library versions were verified against packages already installed in the project venv (Python 3.14) where possible. All other versions are from training data (cutoff: early 2025) and are flagged as needing validation before pinning in `pyproject.toml`. The installed venv packages provided high-confidence anchors for Rich, Pluggy, Watchdog, Pydantic, and FastMCP versions.

---

## Existing Stack (Not Re-Researched)

These are already in `pyproject.toml` and documented in `.planning/codebase/STACK.md`. Listed here only for compatibility reference.

| Technology | Installed Version | Purpose |
|------------|-------------------|---------|
| Python | 3.14 (venv) / >=3.11 (spec) | Runtime |
| LangChain | >=0.3.0 | Agent orchestration |
| LangChain-Ollama | >=0.2.0 | LLM integration |
| FastMCP | 2.14.5 (installed) | MCP server |
| Pydantic | 2.12.5 (installed) | Data models |
| Streamlit | >=1.38.0 | Web UI (legacy) |
| httpx | 0.28.1 (installed) | HTTP client |
| python-dotenv | 1.2.1 (installed) | Env config |
| Rich | 14.3.2 (installed) | Terminal rendering (transitive dep) |

---

## Recommended New Stack

### 1. TUI Framework

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Textual | >=1.0.0 | Terminal UI application framework | Built on Rich (already installed at 14.3.2, same author Will McGugan). Async-first architecture meshes with asyncio daemon. CSS-like styling for layout. Built-in widget system with inputs, data tables, markdown rendering, tree views. The only serious Python TUI framework with a component model comparable to web frameworks. | MEDIUM -- version needs live verification |

**Why Textual over alternatives:**
- **Rich is already a dependency** (14.3.2 installed as transitive dep). Textual is built on Rich. Zero-friction integration.
- **Async-native** -- uses asyncio event loop, which aligns with the daemon architecture and LangChain's async support.
- **CSS-like styling** -- layout and theming via `.tcss` files, not hardcoded terminal escape codes.
- **Widget library** -- `Input`, `TextArea`, `RichLog`, `DataTable`, `Header`, `Footer`, `Static`, `ListView` cover the chat interface and dashboard needs.
- **Reactive data binding** -- Pydantic models can drive reactive widget updates.
- **Actively maintained** -- by Textualize (Will McGugan's company), the most actively developed Python TUI framework.

**Key Textual widgets for AFO:**
- `Input` + `RichLog` -- chat interface (user types commands, system streams responses)
- `DataTable` -- firewall rule display, active threats table, deployment history
- `Static` + `Markdown` -- status panels, help text
- `TabbedContent` -- switching between chat, dashboard, logs views (mirrors existing Streamlit tab pattern)
- `Footer` -- keyboard shortcuts for common operations

**What NOT to use for TUI:**

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| urwid | Callback-based, not async. Aging API, small community. Hard to build modern UIs. | Textual |
| blessed/blessings | Low-level terminal library, not a framework. You would rebuild everything Textual already provides. | Textual |
| prompt_toolkit | Excellent for CLIs and REPLs, not for full dashboard TUIs with panels and widgets. | Textual (use prompt_toolkit only if building a pure REPL) |
| curses (stdlib) | Raw terminal manipulation. No widgets, no layout engine, no async. Extreme development cost. | Textual |
| npyscreen | Unmaintained since 2020. Python 2 era design. | Textual |

### 2. Plugin Architecture (Universal Firewall Backends)

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Python ABCs | stdlib | Firewall backend interface contracts | `abc.ABC` + `abc.abstractmethod` define the `FirewallBackend` interface that all adapters must implement. Zero dependencies. Type-checkable. The standard Python pattern for "interface" definitions. | HIGH |
| importlib.metadata | stdlib (3.9+) | Plugin discovery via entry points | Entry points in `pyproject.toml` are the official Python packaging mechanism for plugin registration. Each adapter declares an entry point, the core discovers them at runtime. Replaces need for any third-party plugin framework. | HIGH |
| Pydantic | 2.12.5 (installed) | Adapter configuration models | Each firewall backend has its own Pydantic config model (credentials, endpoints, etc.). Already the project standard. | HIGH |

**Architecture pattern:** ABC interface + entry points. Each firewall adapter is a Python package that:
1. Implements the `FirewallBackend` ABC
2. Declares an entry point in its `pyproject.toml` under `[project.entry-points."afo.backends"]`
3. Gets discovered at runtime via `importlib.metadata.entry_points(group="afo.backends")`

**Why NOT pluggy for this:**
- Pluggy (1.6.0, already installed as pytest dep) is excellent for hook-based plugin systems where multiple plugins respond to the same event (like pytest's fixture/assertion hooks).
- Firewall backends are *not* hook-based -- you pick ONE backend for a given firewall and call its methods. This is a strategy/adapter pattern, not a hook/event pattern.
- ABC + entry points is simpler, more Pythonic, and directly supported by the packaging ecosystem.
- Pluggy adds unnecessary complexity for adapter-pattern plugins.

**Why NOT stevedore:**
- stevedore (OpenStack) wraps setuptools entry points with driver/hook/extension patterns. It is feature-rich but heavy for this use case.
- It adds a dependency when `importlib.metadata` does the same job in 5 lines of code.
- stevedore's maintenance pace has slowed since OpenStack's decline in mindshare.

**Backend adapters to support (implementation priority order):**

| Backend | Interface | Complexity | Notes |
|---------|-----------|------------|-------|
| nftables | subprocess (`nft` CLI) | Low | Already implemented. Refactor into adapter. |
| iptables | subprocess (`iptables`/`iptables-restore`) | Low | Similar pattern to nftables. Legacy but ubiquitous. |
| pfSense | REST API (httpx) | Medium | pfSense has a REST API via pfSense Plus or FauxAPI package. |
| OPNsense | REST API (httpx) | Medium | Official REST API. Already mentioned in `claude.md`. |
| AWS Security Groups | boto3 SDK | Medium | `ec2.authorize_security_group_ingress/egress`. Needs AWS creds. |
| Azure NSG | azure-mgmt-network SDK | Medium | Network security group rules. Needs Azure identity. |
| GCP Firewall | google-cloud-compute SDK | Medium | Firewall rules via Compute API. Needs GCP creds. |

**Cloud SDK dependencies (optional, per-adapter):**

| Library | Version | When Needed | Confidence |
|---------|---------|-------------|------------|
| boto3 | >=1.35.0 | AWS Security Groups adapter | LOW -- version needs verification |
| azure-mgmt-network | >=26.0.0 | Azure NSG adapter | LOW -- version needs verification |
| google-cloud-compute | >=1.20.0 | GCP Firewall adapter | LOW -- version needs verification |

These should be optional dependencies (`pip install afo[aws]`, `pip install afo[azure]`, `pip install afo[gcp]`), not core requirements.

### 3. Autonomous Security Daemon

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| asyncio | stdlib | Daemon event loop and task orchestration | The foundation. All monitoring tasks (log tailing, traffic analysis, feed polling) run as concurrent asyncio tasks. Already the standard for Python async services. LangChain supports async (`ainvoke`). Textual uses asyncio. Unifies the entire runtime. | HIGH |
| watchdog | 6.0.0 (installed) | Log file monitoring (inotify-based) | Already installed. Watches log files for new entries using OS-native events (inotify on Linux). Zero-polling overhead. Use `watchdog.observers.Observer` + custom `FileSystemEventHandler` for log rotation awareness. | HIGH |
| structlog | >=24.0.0 | Structured logging for daemon operations | The standard Python structured logging library. JSON output for machine consumption, colored output for human TUI display. Contextual logging (bind request IDs, rule IDs). Integrates with stdlib `logging`. Critical for a daemon that needs to report what it detected and acted on. | MEDIUM -- version needs verification |
| scapy | >=2.6.0 | Network packet capture and analysis | The gold standard for Python packet manipulation. Capture live traffic, parse pcap files, decode protocols. Needed for traffic anomaly detection (port scans, unusual protocols, traffic spikes). Supports BPF filters for efficient capture. Runs in async mode with `AsyncSniffer`. | MEDIUM -- version needs verification |
| dpkt | >=1.9.8 | Lightweight packet parsing (high-volume) | Lighter than scapy for high-throughput packet parsing in the daemon's hot path. Use dpkt for continuous monitoring (fast parsing) and scapy for deep inspection (when anomaly detected). Complementary, not competing. | LOW -- version needs verification |
| psutil | >=6.0.0 | System resource monitoring | Process management, CPU/memory/network stats, connection tables. Used by daemon for self-monitoring (resource limits) and for network connection enumeration (alternative to netstat/ss). | MEDIUM -- version needs verification |
| schedule | >=1.2.0 | Periodic task scheduling (feed polling) | Simple, human-readable scheduling (`schedule.every(5).minutes.do(poll_feeds)`). For the daemon's periodic tasks: threat feed updates, rule audits, health checks. Lighter than APScheduler for simple periodic tasks. | MEDIUM -- version needs verification |

**Why asyncio over threading:**
- The existing codebase uses `threading.Thread` for heartbeat monitoring. New daemon code should use asyncio because:
  1. LangChain supports async operations (`ainvoke`, `astream`)
  2. Textual requires asyncio (its event loop IS an asyncio loop)
  3. httpx supports async (`AsyncClient`) for feed polling
  4. Better resource efficiency for I/O-bound monitoring tasks
  5. `asyncio.TaskGroup` (Python 3.11+) provides structured concurrency
- The existing heartbeat threads should be migrated to asyncio tasks in a later phase.

**Daemon components as asyncio tasks:**

```
DaemonSupervisor (asyncio event loop)
  +-- LogWatcher task       -- watches /var/log/*, firewall logs via watchdog
  +-- TrafficAnalyzer task  -- captures/analyzes packets via scapy AsyncSniffer
  +-- FeedPoller task       -- polls threat intel feeds on schedule
  +-- ThreatCorrelator task -- combines signals, makes block decisions
  +-- ActionExecutor task   -- applies firewall rules via backend adapter
```

**What NOT to use for daemon:**

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| python-daemon | Unmaintained (last release 2021). Modern Python services use systemd for daemonization. The library fights with asyncio. | systemd service unit + asyncio |
| Celery / Dramatiq | Massive overkill. Needs Redis/RabbitMQ broker. Designed for distributed task queues, not local monitoring daemons. | asyncio tasks + schedule |
| APScheduler | Heavier than needed. Database-backed job stores add complexity. Fine for web apps, overkill for a single-process daemon. | schedule (simple) or raw asyncio.sleep loops |
| multiprocessing | GIL is not the bottleneck here (I/O-bound workload). Adds complexity of IPC. | asyncio (single-process, concurrent I/O) |

### 4. Threat Intelligence Integration

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| httpx | 0.28.1 (installed) | Async HTTP for fetching threat feeds | Already installed and used. `httpx.AsyncClient` for polling abuse.ch, emerging threats, and other HTTP-based feeds. No new dependency needed. | HIGH |
| ipaddress | stdlib | IP/CIDR matching and validation | Parse and match IPs against threat intel blocklists. CIDR network containment checks. Already in stdlib. | HIGH |
| stix2 | >=3.0.0 | STIX 2.1 threat intelligence objects | Official OASIS library for creating and parsing STIX 2.1 objects (indicators, observables, attack patterns). Needed if consuming STIX-formatted threat feeds (MITRE ATT&CK, ISACs). | LOW -- version needs verification, may still be at 2.x |
| taxii2-client | >=2.3.0 | TAXII 2.1 server communication | Official client for discovering and polling TAXII servers (the transport protocol for STIX). Needed for enterprise threat intel sharing (ISACs, commercial feeds). | LOW -- version needs verification |

**Threat feed sources (no library needed, just httpx):**

| Feed | Format | URL Pattern | Update Frequency |
|------|--------|-------------|------------------|
| abuse.ch Feodo Tracker | CSV | `https://feodotracker.abuse.ch/downloads/ipblocklist.csv` | Every 5 min |
| abuse.ch SSL Blocklist | CSV | `https://sslbl.abuse.ch/blacklist/sslipblacklist.csv` | Hourly |
| Emerging Threats | Suricata/Snort rules | `https://rules.emergingthreats.net/open/...` | Daily |
| Spamhaus DROP | CIDR list | `https://www.spamhaus.org/drop/drop.txt` | Hourly |
| MITRE ATT&CK | STIX 2.1 | TAXII server | Periodic |
| AlienVault OTX | JSON API | `https://otx.alienvault.com/api/v1/pulses/...` | Continuous |

Most feeds are simple CSV/text over HTTP -- `httpx` handles them directly. STIX/TAXII libraries are only needed for structured threat intel exchange.

### 5. Log Monitoring and Analysis

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| watchdog | 6.0.0 (installed) | File system event monitoring | Already installed. Watch log files for new entries via inotify. Handles log rotation (detect file rename/create). | HIGH |
| systemd-python | >=235 | systemd journal reader | Read from systemd journal (journald) directly, without parsing text log files. Most modern Linux systems log to journald. Access auth logs, kernel messages, service logs. | LOW -- package name/version needs verification. Alternative: `cysystemd` or `pystemd`. |
| re (stdlib) | stdlib | Log line parsing | Regex-based log parsing for syslog, auth.log, nftables log entries. Stdlib is sufficient for structured log formats. | HIGH |

**Log sources the daemon should monitor:**

| Log Source | Access Method | What to Detect |
|------------|---------------|----------------|
| nftables log | `nft` log actions write to kernel log / syslog | Blocked connections, rate limit hits, policy violations |
| /var/log/auth.log | watchdog file monitoring | SSH brute force, failed logins, sudo abuse |
| /var/log/syslog | watchdog file monitoring | System events, service failures |
| journald | systemd-python journal reader | All of the above plus service-specific logs |
| Firewall appliance logs | Syslog receiver (UDP 514) | Remote firewall events (pfSense/OPNsense syslog export) |

**For syslog reception (remote firewalls sending logs to AFO):**
- Python stdlib `socketserver.UDPServer` or asyncio `DatagramProtocol` for receiving syslog messages
- No third-party library needed for basic syslog (RFC 3164/5424) reception

### 6. Development and Testing

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| pytest | 9.0.2 (installed) | Test runner | Already installed and configured. | HIGH |
| pytest-asyncio | 1.3.0 (installed) | Async test support | Already installed. Essential for testing asyncio daemon tasks. | HIGH |
| pytest-textual-snapshot | >=1.0.0 | TUI snapshot testing | Official Textual testing tool. Captures terminal output as snapshots for regression testing. Recommended by Textualize. | LOW -- version needs verification |
| respx | >=0.22.0 | Mock httpx requests | For testing threat feed polling without network. Mocks `httpx.AsyncClient` requests. Pairs with pytest-asyncio. | LOW -- version needs verification |
| ruff | 0.15.0 (installed) | Linting and formatting | Already installed. | HIGH |

---

## Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| pydantic-settings | 2.12.0 (installed) | Typed configuration | Replace `os.environ.get()` pattern with validated config models. Already installed as FastMCP dep. | HIGH |
| structlog | >=24.0.0 | Structured logging | Everywhere. Replace all `print()` statements. JSON for daemon, colored for TUI. | MEDIUM |
| psutil | >=6.0.0 | System monitoring | Daemon self-monitoring, connection enumeration, resource limits. | MEDIUM |
| maxminddb | >=2.6.0 | GeoIP lookups | Threat analysis enrichment. Map source IPs to countries for geo-blocking decisions. Requires GeoLite2 database (free with registration). | LOW -- version needs verification |
| orjson | >=3.10.0 | Fast JSON parsing | High-throughput JSON parsing for threat feeds and log processing in daemon hot path. 3-10x faster than stdlib json. | LOW -- version needs verification |

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Textual | Rich (direct) | If only rendering output, not building interactive UI. Rich is already used by Textual internally. |
| ABC + entry points | pluggy | If plugins need to respond to hooks/events (multiple plugins for same event). Not needed for adapter pattern. |
| ABC + entry points | stevedore | If you need named driver patterns with automatic error handling. Adds unnecessary dep for this project. |
| asyncio | threading | Only for CPU-bound work that needs true parallelism. All daemon tasks are I/O-bound. |
| scapy | pyshark | If you want tshark as backend (requires Wireshark installed). Scapy is self-contained and more flexible. |
| scapy + dpkt | raw sockets | Never. Raw socket programming is error-prone and reimplements what scapy provides. |
| structlog | loguru | If you prefer magic-method logging over explicit structured fields. structlog is more explicit and configurable. |
| schedule | cron | If you want OS-level scheduling. But daemon needs in-process scheduling for coordination. |
| watchdog | inotifyx | If you want lower-level inotify access. watchdog already uses inotify on Linux and adds rotation handling. |
| stix2 + taxii2-client | raw HTTP | If only consuming simple CSV/text feeds (abuse.ch, Spamhaus). STIX/TAXII only needed for enterprise feed exchange. |
| pydantic-settings | python-dotenv | python-dotenv is already used but pydantic-settings (already installed) provides typed, validated config with env var loading built in. Migrate to pydantic-settings. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| curses / ncurses | Raw terminal API. No widgets, no layout, no async. Massive dev cost for minimal gain. | Textual |
| urwid | Legacy callback-based TUI. No async support. Small community. | Textual |
| python-daemon | Unmaintained. Fights with asyncio event loop. Modern services use systemd. | systemd service unit + asyncio |
| Celery / Dramatiq | Distributed task queues requiring message brokers. Extreme overkill for a local monitoring daemon. | asyncio tasks |
| APScheduler | Database-backed scheduler adds storage dependencies. Overkill for simple periodic polling. | schedule or asyncio.sleep loops |
| Suricata/Snort Python bindings | AFO is not an IDS. It should consume threat intel and apply firewall rules, not duplicate IDS functionality. | Scapy for light traffic analysis + threat feed integration |
| PyQt / Tkinter | GUI frameworks. AFO is terminal-first. | Textual |
| Flask / Django | Web frameworks for building APIs. AFO already has FastMCP for its server protocol and Streamlit for web. | Existing stack |
| Click / Typer | CLI frameworks for command-line tools. AFO needs a persistent TUI, not a CLI. | Textual (which can embed CLI-like input) |

---

## Stack Patterns by Variant

**If deploying on systemd Linux (recommended production):**
- Daemon runs as systemd service (`afo-daemon.service`)
- Uses `sd_notify` for readiness signaling
- Journal logging via structlog -> systemd journal
- Socket activation possible for syslog receiver

**If deploying in Docker (development / testing):**
- Daemon runs as container foreground process
- Log output to stdout/stderr (Docker captures)
- No systemd -- use asyncio signal handlers for graceful shutdown
- Syslog receiver binds to container port

**If cloud firewall backends needed:**
- Install optional deps: `pip install afo[aws]` / `afo[azure]` / `afo[gcp]`
- Cloud SDK credentials via environment variables or config files
- Each cloud adapter is a separate optional dependency group

**If STIX/TAXII enterprise threat intel needed:**
- Install optional deps: `pip install afo[threatintel]`
- Only needed for TAXII server polling (ISACs, commercial feeds)
- Most open-source feeds are simple HTTP/CSV -- no STIX library needed

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| Textual >=1.0.0 | Rich >=13.0.0 | Textual requires Rich. Rich 14.3.2 is installed -- compatible. |
| Textual >=1.0.0 | Python >=3.8 | Textual supports wide Python range. Compatible with both 3.11 (Docker) and 3.14 (local). |
| scapy >=2.6.0 | Python >=3.8 | Broad compatibility. May need `libpcap-dev` system package. |
| structlog >=24.0.0 | Python >=3.8 | No conflicts with existing deps. |
| watchdog 6.0.0 | Python >=3.9 | Already installed and working. |
| pluggy 1.6.0 | Python >=3.9 | Already installed (pytest dep). Not recommended for direct use -- see architecture section. |
| pydantic-settings 2.12.0 | Pydantic 2.12.5 | Already installed and version-aligned. |
| stix2 + taxii2-client | Python >=3.8 | May have dependency conflicts with `requests` vs `httpx`. Test in isolation. |

**Potential conflict:** `stix2` and `taxii2-client` traditionally depend on `requests`, while AFO uses `httpx`. This should not cause a conflict (both can coexist) but means threat intel polling would use httpx directly for most feeds and only use stix2/taxii2-client for STIX-formatted feeds.

**System dependencies for new features:**

| System Package | Needed For | Install |
|----------------|------------|---------|
| libpcap-dev | scapy packet capture | `apt install libpcap-dev` |
| libsystemd-dev | systemd journal reader | `apt install libsystemd-dev` (if using cysystemd) |
| nftables | Existing -- firewall management | Already in Dockerfile |

---

## Installation

```bash
# Core new dependencies (add to pyproject.toml dependencies)
pip install textual structlog scapy psutil schedule

# Development dependencies (add to [project.optional-dependencies] dev)
pip install respx pytest-textual-snapshot

# Optional: threat intel (add as [project.optional-dependencies] threatintel)
pip install stix2 taxii2-client

# Optional: cloud backends (add as [project.optional-dependencies])
pip install boto3              # afo[aws]
pip install azure-mgmt-network # afo[azure]
pip install google-cloud-compute # afo[gcp]

# Optional: performance (add as [project.optional-dependencies] perf)
pip install orjson dpkt maxminddb

# System dependencies (Dockerfile)
apt install libpcap-dev
```

**Proposed pyproject.toml additions:**

```toml
[project]
dependencies = [
    # ... existing deps ...
    "textual>=1.0.0",
    "structlog>=24.0.0",
    "scapy>=2.6.0",
    "psutil>=6.0.0",
    "schedule>=1.2.0",
]

[project.optional-dependencies]
dev = [
    # ... existing dev deps ...
    "respx>=0.22.0",
    "pytest-textual-snapshot>=1.0.0",
]
aws = ["boto3>=1.35.0"]
azure = ["azure-mgmt-network>=26.0.0", "azure-identity>=1.18.0"]
gcp = ["google-cloud-compute>=1.20.0"]
threatintel = ["stix2>=3.0.0", "taxii2-client>=2.3.0"]
perf = ["orjson>=3.10.0", "dpkt>=1.9.8", "maxminddb>=2.6.0"]

[project.entry-points."afo.backends"]
nftables = "afo.backends.nftables:NftablesBackend"
iptables = "afo.backends.iptables:IptablesBackend"
```

---

## Integration with Existing Stack

### Textual + LangChain
- Textual's `Worker` API runs LangChain calls in background threads (avoiding blocking the UI event loop)
- LangChain's async `astream()` pipes token-by-token output to Textual's `RichLog` widget for streaming chat responses
- Pydantic models (already used for `FirewallRule`, etc.) work natively as Textual reactive data sources

### Plugin Architecture + Existing Tools
- Current `afo_mcp/tools/deployer.py` and `afo_mcp/tools/network.py` contain nftables-specific logic
- Refactor into a `NftablesBackend` adapter implementing the `FirewallBackend` ABC
- MCP tools (`afo_mcp/server.py`) call the backend adapter through the ABC interface instead of direct nftables subprocess calls
- Existing Pydantic models (`FirewallRule`, `DeploymentResult`) become the shared contract between backends

### Daemon + Existing Heartbeat
- Current heartbeat monitor (`afo_mcp/tools/deployer.py` threading-based) becomes one task in the async daemon
- Daemon shares the same `FirewallBackend` adapter used by the TUI and MCP server
- Daemon uses LangChain agent for threat assessment (same `agents/firewall_agent.py` logic)

### structlog + Existing print() Statements
- Replace all `print()` in `afo_mcp/server.py` and throughout with `structlog.get_logger()`
- structlog processors handle both JSON (daemon/file) and colored (TUI) output from the same log calls
- Bind contextual fields: `log = log.bind(rule_id=rule.id, backend="nftables")`

---

## Sources

- `/mnt/Projects/AFO/.venv/lib/python3.14/site-packages/rich-14.3.2.dist-info/METADATA` -- Rich version verified (HIGH confidence)
- `/mnt/Projects/AFO/.venv/lib/python3.14/site-packages/pluggy-1.6.0.dist-info/METADATA` -- Pluggy version verified (HIGH confidence)
- `/mnt/Projects/AFO/.venv/lib/python3.14/site-packages/watchdog-6.0.0.dist-info/METADATA` -- Watchdog version verified (HIGH confidence)
- `/mnt/Projects/AFO/.venv/lib/python3.14/site-packages/pydantic-2.12.5.dist-info/METADATA` -- Pydantic version verified (HIGH confidence)
- `/mnt/Projects/AFO/.venv/lib/python3.14/site-packages/pydantic_settings-2.12.0.dist-info/METADATA` -- pydantic-settings version verified (HIGH confidence)
- `/mnt/Projects/AFO/.venv/lib/python3.14/site-packages/httpx-0.28.1.dist-info/METADATA` -- httpx version verified (HIGH confidence)
- `/mnt/Projects/AFO/.venv/lib/python3.14/site-packages/fastmcp-2.14.5.dist-info/METADATA` -- FastMCP version verified (HIGH confidence)
- Training data (early 2025) -- Textual, scapy, structlog, stix2, taxii2-client, psutil, schedule, dpkt versions (LOW-MEDIUM confidence, need live verification)
- `/mnt/Projects/AFO/.planning/codebase/STACK.md` -- Existing stack documentation
- `/mnt/Projects/AFO/.planning/codebase/ARCHITECTURE.md` -- Existing architecture
- `/mnt/Projects/AFO/.planning/codebase/INTEGRATIONS.md` -- Existing integrations
- `/mnt/Projects/AFO/.planning/PROJECT.md` -- Project requirements and constraints

---

## Validation Needed Before Implementation

These items could not be verified with live sources and should be checked before adding to `pyproject.toml`:

| Item | What to Check | How |
|------|---------------|-----|
| Textual version | Latest stable release, Python 3.14 compatibility | `pip index versions textual` or PyPI |
| scapy version | Latest stable, Python 3.14 compatibility | `pip index versions scapy` |
| structlog version | Latest stable | `pip index versions structlog` |
| stix2 version | Whether 3.x exists or still 2.x | PyPI -- the 3.0 version may not exist yet |
| taxii2-client version | Latest stable, compatibility with stix2 | PyPI |
| systemd journal library | Which package is current: `systemd-python`, `cysystemd`, or `pystemd` | PyPI -- the systemd Python bindings landscape is fragmented |
| pytest-textual-snapshot | Whether this is the correct package name | Textualize docs / PyPI |
| dpkt Python 3.14 compat | dpkt may lag on newest Python versions | PyPI |

---
*Stack research for: AFO autonomous firewall orchestrator -- TUI, plugins, daemon*
*Researched: 2026-02-10*
