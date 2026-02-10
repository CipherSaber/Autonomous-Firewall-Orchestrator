# Architecture Patterns

**Domain:** AI firewall orchestrator -- TUI, plugin system, autonomous daemon integration
**Researched:** 2026-02-10
**Confidence:** MEDIUM (based on codebase analysis + training data; web verification unavailable)

## Existing Architecture (Baseline)

Before defining new components, here is the architecture that already exists and must be preserved:

```
                                  Consumers
                    +----------------------------------+
                    |                                  |
               [Streamlit UI]                  [MCP Server]
               ui/app.py                    afo_mcp/server.py
                    |                              |
                    v                              v
               [Agent Layer]              [FastMCP Tool Registry]
           agents/firewall_agent.py        @mcp.tool() wrappers
           agents/prompts.py                       |
           agents/tools.py                         |
                    |                              |
          +---------+---------+                    |
          |                   |                    |
     [RAG Store]         [Tool Layer] <------------+
  db/vector_store.py    afo_mcp/tools/
                         network.py      -- ip addr, nft list ruleset
                         validator.py    -- nft --check
                         conflicts.py   -- rule comparison
                         deployer.py    -- nft -f, heartbeat rollback
                              |
                       [Pydantic Models]
                       afo_mcp/models.py
                              |
                       [Security Utils]
                       afo_mcp/security.py
```

### Current Coupling Analysis

These coupling points determine how new components must integrate:

| Caller | Calls | Coupling Type |
|--------|-------|---------------|
| `ui/app.py` | `agents.firewall_agent.chat()` | Direct import |
| `ui/app.py` | `db.vector_store.ingest_docs()` | Direct import |
| `ui/app.py` | `afo_mcp.tools.deployer.deploy_policy()` | Direct import |
| `agents/firewall_agent.py` | `db.vector_store.retrieve()` | Direct import |
| `agents/firewall_agent.py` | `afo_mcp.tools.network.get_network_context()` | Direct import |
| `agents/firewall_agent.py` | `afo_mcp.tools.validator.validate_rule_structure()` | Direct import |
| `agents/firewall_agent.py` | `afo_mcp.tools.conflicts.detect_conflicts()` | Direct import |
| `afo_mcp/server.py` | `afo_mcp/tools/*` | Direct import |
| `afo_mcp/tools/deployer.py` | `subprocess(nft ...)` | Hardcoded nftables CLI |
| `afo_mcp/tools/validator.py` | `subprocess(nft --check ...)` | Hardcoded nftables CLI |
| `afo_mcp/tools/network.py` | `subprocess(ip ..., nft ...)` | Hardcoded nftables CLI |
| `FirewallRule.to_nft_command()` | nftables syntax | Hardcoded in model |

**Critical observation:** The nftables dependency is spread across 4 files and baked into the `FirewallRule` model itself (`to_nft_command()`). The plugin system must abstract all of these touch points.

**State is in-memory and fragmented:** Streamlit uses `session_state` (per-browser-tab), deployer uses module-level dicts for heartbeats. No persistent state store exists for rule history, events, or daemon state. This must be resolved before daemon or TUI can share state.

## Recommended Architecture

### Component Diagram

```
                         Consumers (Presentation)
          +------------------+------------------+------------------+
          |                  |                  |                  |
     [Textual TUI]    [Streamlit UI]    [Daemon Process]    [MCP Server]
     tui/app.py        ui/app.py      daemon/supervisor.py  afo_mcp/server.py
          |                  |                  |                  |
          +------------------+------------------+------------------+
                             |
                      [Service Layer]  <-- NEW: single entry point
                      core/service.py
                             |
          +------------------+------------------+
          |                  |                  |
     [Agent Layer]     [Tool Layer]      [Event System]  <-- NEW
   agents/firewall_    afo_mcp/tools/    core/events.py
   agent.py            (refactored)
          |                  |                  |
     [RAG Store]      [Plugin System]   [Data Sources]  <-- NEW
  db/vector_store.py   core/backends/    daemon/sources/
                             |
                      [Backend ABC]  <-- NEW
                      core/backends/base.py
                             |
          +------------------+------------------+
          |                  |                  |
   [NftablesBackend]  [IptablesBackend]  [OPNsenseBackend]
   core/backends/     core/backends/     core/backends/
   nftables.py        iptables.py        opnsense.py
          |
   [Pydantic Models]       [State Store]  <-- NEW
   afo_mcp/models.py       core/state.py (SQLite)
          |
   [Security Utils]
   afo_mcp/security.py
```

### Component Boundaries

| Component | Responsibility | Communicates With | New/Existing |
|-----------|---------------|-------------------|--------------|
| **Textual TUI** | Terminal UI for chat, rule review, daemon status dashboard | Service Layer | NEW |
| **Streamlit UI** | Web UI for chat, rule review (preserved for backward compat) | Service Layer (minor refactor) | EXISTING (modified) |
| **Daemon Supervisor** | Long-running process: monitors sources, detects threats, triggers actions | Service Layer, Event System, Data Sources | NEW |
| **MCP Server** | Exposes tools to external LLM clients via MCP protocol | Tool Layer (unchanged) | EXISTING (unchanged) |
| **Service Layer** | Unified API consumed by all presentation layers. Orchestrates agent calls, rule lifecycle, state persistence | Agent, Tools, State Store, Plugin System | NEW |
| **Agent Layer** | NLP-to-rule translation via LLM + RAG | RAG Store, Ollama | EXISTING (minor refactor) |
| **Tool Layer** | Core logic: validation, conflict detection, deployment | Plugin System (replaces hardcoded nft calls) | EXISTING (refactored) |
| **Plugin System** | Abstract firewall backend interface + backend registry | Individual backend implementations | NEW |
| **Backend: nftables** | Implements FirewallBackend for nftables via `nft` CLI | System `nft` binary | NEW (extracted from existing tools) |
| **Backend: iptables** | Implements FirewallBackend for iptables/iptables-nft | System `iptables` binary | NEW |
| **Backend: OPNsense** | Implements FirewallBackend for OPNsense via REST API | OPNsense API over HTTPS | NEW |
| **Event System** | Typed event bus for daemon-to-TUI communication and audit trail | State Store | NEW |
| **Data Sources** | Pluggable monitors: log files, netflow, threat feeds | Daemon Supervisor | NEW |
| **State Store** | Persistent storage for rules, events, daemon state, audit log | SQLite via aiosqlite | NEW |
| **RAG Store** | Document embeddings for nftables reference retrieval | Ollama embeddings API | EXISTING (unchanged) |
| **Pydantic Models** | Shared data structures for all components | None (leaf dependency) | EXISTING (extended) |
| **Security Utils** | Input sanitization, injection prevention | None (leaf dependency) | EXISTING (unchanged) |

### Data Flow

#### Flow 1: Interactive Rule Creation (TUI or Streamlit)

```
User types "block SSH from guest VLAN"
         |
    [TUI or Streamlit]
         |
         v
    service.generate_rule(user_input, backend="nftables")
         |
         +---> agent.generate_rule(user_input)
         |         |---> rag.retrieve(user_input)
         |         |---> tools.network.get_network_context()  (via active backend)
         |         |---> LLM generates JSON
         |         |---> builds FirewallRule
         |         \---> returns {rule, explanation, rag_sources}
         |
         +---> backend.render_rule(rule)  -->  platform-specific command
         +---> backend.validate(command)
         +---> tools.conflicts.detect_conflicts(command, backend.list_rules())
         |
         v
    service returns {rule, command, validation, conflicts, explanation}
         |
    [TUI or Streamlit] displays for approval
         |
    User approves
         |
    service.deploy_rule(rule_id, command, backend="nftables")
         |
         +---> backend.create_backup()
         +---> backend.deploy(command)
         +---> state.record_deployment(rule_id, ...)
         +---> heartbeat monitor starts
         |
         v
    service.confirm_deployment(rule_id)  or  auto-rollback on timeout
```

#### Flow 2: Autonomous Daemon Monitoring

```
    [Daemon Supervisor] (asyncio event loop)
         |
         +---> starts data source monitors (concurrent tasks)
         |
    [LogSource]     [NetflowSource]     [ThreatFeedSource]
    watches syslog  watches netflow     polls threat intel
    /auth.log       /pcap data          APIs (local cache)
         |               |                    |
         v               v                    v
    SecurityEvent   SecurityEvent        SecurityEvent
    {type, severity, source_ip, ...}
         |
         +---> [ThreatAnalyzer]
         |         |---> correlates events across sources
         |         |---> queries LLM for complex analysis (optional)
         |         |---> produces ThreatAssessment
         |
         v
    ThreatAssessment {threat_level, recommended_actions, evidence}
         |
         +---> if threat_level >= configured_threshold:
         |         |
         |         +---> service.generate_rule(auto_prompt, backend=...)
         |         +---> validation + conflict check (same pipeline)
         |         +---> based on autonomy_level:
         |                  "alert"    -> state.record_alert(...)
         |                  "propose"  -> state.queue_for_approval(...)
         |                  "auto"     -> service.deploy_rule(...)
         |
         +---> state.record_event(event)
         +---> events.emit(SecurityEventOccurred(...))  --> TUI updates
```

#### Flow 3: TUI Daemon Dashboard

```
    [Textual TUI]
         |
         +---> on_mount():
         |         state.get_daemon_status()
         |         state.get_recent_events(limit=50)
         |         state.get_pending_rules()
         |
         +---> Textual Worker (polling or reactive):
         |         while running:
         |             new_events = state.get_events_since(last_seen)
         |             self.post_message(EventsUpdated(new_events))
         |             await asyncio.sleep(1)
         |
         +---> on EventsUpdated:
         |         update dashboard widgets
         |         flash notification for critical events
         |
         +---> user reviews proposed rule:
                  service.deploy_rule(...)  or  service.reject_rule(...)
```

#### Flow 4: Plugin System (Backend Selection)

```
    [Service Layer]
         |
         +---> backend_registry.get("nftables")  --> NftablesBackend instance
         |
    [NftablesBackend]
         |---> render_rule(FirewallRule) -> "add rule inet filter input ..."
         |---> validate(command) -> ValidationResult
         |---> deploy(command) -> DeploymentResult
         |---> list_rules() -> str (active ruleset)
         |---> create_backup() -> Path
         |---> restore_backup(path) -> bool
         |---> get_network_context() -> NetworkContext
         |
    All backends implement the same interface.
    Service layer is backend-agnostic.
```

## Patterns to Follow

### Pattern 1: Service Layer (Facade)

**What:** A single `FirewallService` class that all consumers use. Encapsulates the orchestration flow (agent -> validate -> conflicts -> deploy) and manages state.

**When:** Always. Every consumer (TUI, Streamlit, daemon, MCP) goes through this layer.

**Why:** Currently, `ui/app.py` directly calls `chat()`, then separately calls `deploy_policy()`, managing flow in the UI code. This cannot be duplicated across TUI and daemon. The service layer owns the workflow.

**Example:**

```python
# core/service.py

class FirewallService:
    def __init__(
        self,
        backend: FirewallBackend,
        state: StateStore,
        events: EventBus,
    ):
        self._backend = backend
        self._state = state
        self._events = events

    def generate_rule(self, user_input: str) -> RuleProposal:
        """Full pipeline: NLP -> rule -> validate -> conflicts."""
        result = firewall_agent.generate_rule(user_input)
        if not result["success"]:
            return RuleProposal(success=False, error=result["error"])

        rule = FirewallRule(**result["rule"])
        command = self._backend.render_rule(rule)
        validation = self._backend.validate(command)
        conflicts = detect_conflicts(
            command,
            self._backend.list_rules(),
        )

        proposal = RuleProposal(
            success=True,
            rule=rule,
            command=command,
            validation=validation,
            conflicts=conflicts,
            explanation=result["explanation"],
        )
        self._state.save_proposal(proposal)
        self._events.emit(RuleProposed(proposal))
        return proposal

    def deploy_rule(
        self, proposal_id: str, approved_by: str = "user"
    ) -> DeploymentResult:
        """Deploy an approved rule through the active backend."""
        proposal = self._state.get_proposal(proposal_id)
        result = self._backend.deploy(proposal.command)
        self._state.record_deployment(proposal_id, result)
        self._events.emit(RuleDeployed(proposal_id, result))
        return result

    def chat(self, user_input: str, history: list | None = None) -> dict:
        """Delegate to agent for chat or rule generation."""
        return firewall_agent.chat(user_input, history)
```

### Pattern 2: Abstract Backend (Plugin System)

**What:** An abstract base class defining the contract all firewall backends must implement. Backends register themselves and are selected by configuration.

**When:** Any time firewall operations are performed. The service layer never calls `nft` directly.

**Why:** The current code has `subprocess.run(["nft", ...])` scattered across `network.py`, `validator.py`, `deployer.py`, and `FirewallRule.to_nft_command()`. Making this pluggable requires consolidating all platform-specific logic behind one interface.

**Example:**

```python
# core/backends/base.py

from abc import ABC, abstractmethod

class FirewallBackend(ABC):
    """Interface for firewall platform implementations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier, e.g., 'nftables', 'iptables', 'opnsense'."""

    @abstractmethod
    def render_rule(self, rule: FirewallRule) -> str:
        """Convert a FirewallRule to platform-specific command syntax."""

    @abstractmethod
    def validate(self, command: str) -> ValidationResult:
        """Dry-run validation of a platform command."""

    @abstractmethod
    def deploy(self, command: str) -> DeploymentResult:
        """Apply a command to the live system."""

    @abstractmethod
    def list_rules(self) -> str:
        """Return the current active ruleset as text."""

    @abstractmethod
    def create_backup(self) -> Path | None:
        """Snapshot current state for rollback."""

    @abstractmethod
    def restore_backup(self, backup_path: Path) -> bool:
        """Restore from a previous snapshot."""

    @abstractmethod
    def get_network_context(self) -> NetworkContext:
        """Gather network state relevant to this backend."""
```

```python
# core/backends/registry.py

_BACKENDS: dict[str, type[FirewallBackend]] = {}

def register_backend(name: str, cls: type[FirewallBackend]) -> None:
    _BACKENDS[name] = cls

def get_backend(name: str, **kwargs) -> FirewallBackend:
    if name not in _BACKENDS:
        raise ValueError(f"Unknown backend: {name}. Available: {list(_BACKENDS)}")
    return _BACKENDS[name](**kwargs)

def available_backends() -> list[str]:
    return list(_BACKENDS.keys())
```

```python
# core/backends/nftables.py

class NftablesBackend(FirewallBackend):
    """nftables backend -- extracted from existing afo_mcp/tools/ code."""

    @property
    def name(self) -> str:
        return "nftables"

    def render_rule(self, rule: FirewallRule) -> str:
        # Logic from FirewallRule.to_nft_command(), moved here
        parts = [f"add rule {rule.family} {rule.table} {rule.chain}"]
        # ... same nft syntax generation ...
        return " ".join(parts)

    def validate(self, command: str) -> ValidationResult:
        # Logic from afo_mcp/tools/validator.py validate_syntax()
        ...

    def deploy(self, command: str) -> DeploymentResult:
        # Logic from afo_mcp/tools/deployer.py deploy_policy()
        ...

    # etc.

# Self-register
register_backend("nftables", NftablesBackend)
```

**Discovery mechanism:** Use simple explicit imports (not entry_points). Each backend module registers itself when imported. A config file or env var lists which backends to load:

```python
# core/backends/__init__.py
import importlib

def load_backends(names: list[str]) -> None:
    for name in names:
        importlib.import_module(f"core.backends.{name}")
```

**Why not `importlib.metadata.entry_points()`:** Entry points require the backend to be an installed package. For a single-repo project with built-in backends, explicit registration is simpler and more debuggable. Entry points make sense later if third-party backends become a goal.

### Pattern 3: Async Daemon with Data Source Monitors

**What:** An asyncio-based supervisor that manages multiple concurrent data source monitors, each producing `SecurityEvent` objects that feed into a threat analysis pipeline.

**When:** Daemon mode (background 24/7 operation).

**Why:** Multiple data sources (logs, netflow, threat feeds) must be monitored simultaneously. asyncio tasks are the natural concurrency model -- no threads needed for I/O-bound monitoring.

**Example:**

```python
# daemon/supervisor.py

import asyncio
import signal

class DaemonSupervisor:
    def __init__(
        self,
        service: FirewallService,
        state: StateStore,
        sources: list[DataSource],
        autonomy_level: str = "propose",  # alert | propose | auto
    ):
        self._service = service
        self._state = state
        self._sources = sources
        self._autonomy = autonomy_level
        self._event_queue: asyncio.Queue[SecurityEvent] = asyncio.Queue()
        self._running = False

    async def start(self) -> None:
        self._running = True
        tasks = []

        # Start each data source as a concurrent task
        for source in self._sources:
            tasks.append(
                asyncio.create_task(
                    self._run_source(source),
                    name=f"source:{source.name}",
                )
            )

        # Start the event processor
        tasks.append(
            asyncio.create_task(
                self._process_events(),
                name="event_processor",
            )
        )

        # Wait for shutdown signal
        await asyncio.gather(*tasks)

    async def _run_source(self, source: DataSource) -> None:
        """Run a data source monitor, feeding events to the queue."""
        async for event in source.monitor():
            if not self._running:
                break
            await self._event_queue.put(event)
            await self._state.record_event(event)

    async def _process_events(self) -> None:
        """Consume events, analyze threats, take action."""
        while self._running:
            event = await self._event_queue.get()
            assessment = await self._analyze_threat(event)

            if assessment.threat_level >= ThreatLevel.HIGH:
                await self._respond(assessment)

    async def _respond(self, assessment: ThreatAssessment) -> None:
        """Take action based on autonomy level."""
        if self._autonomy == "alert":
            await self._state.record_alert(assessment)
        elif self._autonomy == "propose":
            proposal = self._service.generate_rule(
                assessment.recommended_prompt
            )
            await self._state.queue_for_approval(proposal, assessment)
        elif self._autonomy == "auto":
            proposal = self._service.generate_rule(
                assessment.recommended_prompt
            )
            if proposal.success and proposal.validation.valid:
                self._service.deploy_rule(
                    proposal.id, approved_by="daemon:auto"
                )

    async def stop(self) -> None:
        self._running = False
```

```python
# daemon/sources/base.py

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

class DataSource(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Source identifier."""

    @abstractmethod
    async def monitor(self) -> AsyncIterator[SecurityEvent]:
        """Yield security events as they are detected. Runs indefinitely."""
```

### Pattern 4: Textual TUI with Worker-Based Backend Communication

**What:** A Textual application using Screens for navigation and Workers for non-blocking backend calls. The TUI shares the service layer with the daemon.

**When:** Interactive terminal sessions.

**Why:** Textual provides rich terminal UIs with an async-native architecture. Workers prevent LLM calls (which take seconds) from freezing the UI. The message-passing system provides clean separation between UI updates and backend operations.

**Example:**

```python
# tui/app.py

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Input, RichLog
from textual.worker import Worker

class ChatScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="chat-log")
        yield Input(placeholder="Describe your firewall rule...")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value
        event.input.clear()

        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold]You:[/bold] {user_input}")

        # Run LLM call in a worker so UI stays responsive
        self.generate_rule(user_input)

    @work(thread=True)  # thread=True for sync service calls
    def generate_rule(self, user_input: str) -> None:
        result = self.app.service.generate_rule(user_input)
        # Post result back to UI thread via message
        self.app.call_from_thread(
            self._display_result, result
        )

    def _display_result(self, result: RuleProposal) -> None:
        log = self.query_one("#chat-log", RichLog)
        if result.success:
            log.write(f"[green]Rule:[/green] {result.command}")
            log.write(f"[dim]{result.explanation}[/dim]")
        else:
            log.write(f"[red]Error:[/red] {result.error}")


class AFOApp(App):
    TITLE = "AFO - Autonomous Firewall Orchestrator"
    SCREENS = {
        "chat": ChatScreen,
        "dashboard": DashboardScreen,
        "rules": RuleBrowserScreen,
    }

    def __init__(self, service: FirewallService):
        super().__init__()
        self.service = service
```

### Pattern 5: Shared State via SQLite

**What:** A lightweight SQLite database (via `aiosqlite` for async, `sqlite3` for sync) replaces all in-memory state with persistent, shareable storage.

**When:** All state operations across all components.

**Why:** Current state is scattered: Streamlit `session_state` (per-tab, in-memory), deployer heartbeat dicts (per-process, in-memory). The daemon and TUI need shared persistent state. SQLite requires no server, works in containers, and handles concurrent reads from multiple processes.

**Example:**

```python
# core/state.py

import sqlite3
from pathlib import Path

class StateStore:
    def __init__(self, db_path: Path = Path("/var/lib/afo/state.db")):
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY,
                    rule_json TEXT NOT NULL,
                    command TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    approved_by TEXT,
                    approved_at TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS deployments (
                    id TEXT PRIMARY KEY,
                    proposal_id TEXT REFERENCES proposals(id),
                    status TEXT NOT NULL,
                    backup_path TEXT,
                    error TEXT,
                    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS daemon_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def save_proposal(self, proposal: RuleProposal) -> None: ...
    def get_proposal(self, proposal_id: str) -> RuleProposal: ...
    def get_pending_proposals(self) -> list[RuleProposal]: ...
    def record_deployment(self, proposal_id: str, result: DeploymentResult) -> None: ...
    def record_event(self, event: SecurityEvent) -> None: ...
    def get_recent_events(self, limit: int = 50) -> list[SecurityEvent]: ...
    def get_events_since(self, timestamp: datetime) -> list[SecurityEvent]: ...
    def set_daemon_state(self, key: str, value: str) -> None: ...
    def get_daemon_state(self, key: str) -> str | None: ...
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Direct Tool Calls from Presentation Layer

**What:** TUI or Streamlit directly importing and calling `afo_mcp.tools.deployer.deploy_policy()` or `afo_mcp.tools.network.get_network_context()`.

**Why bad:** The current Streamlit code does this. It means every consumer must re-implement the orchestration flow (generate -> validate -> conflicts -> approve -> deploy). Adding the daemon as a third consumer would triple the duplicated logic. It also bypasses state persistence and event emission.

**Instead:** All consumers call the service layer. The service layer calls tools.

### Anti-Pattern 2: Baking Platform Syntax into Data Models

**What:** The current `FirewallRule.to_nft_command()` method puts nftables-specific syntax generation directly in the shared data model.

**Why bad:** `FirewallRule` is used by every component. If it has nftables-specific methods, it cannot cleanly represent rules for iptables or OPNsense. The model becomes tied to one backend.

**Instead:** `FirewallRule` stays as a backend-agnostic data structure. Each `FirewallBackend` implementation has its own `render_rule(rule: FirewallRule) -> str` method. The `to_nft_command()` method can remain for backward compatibility but should be deprecated and delegate to `NftablesBackend.render_rule()`.

### Anti-Pattern 3: Synchronous Blocking in the Daemon

**What:** Using `subprocess.run()` or synchronous LLM calls in the daemon's asyncio event loop.

**Why bad:** Blocks the entire event loop. Other data source monitors stop processing during the blocking call. Missed events, delayed responses.

**Instead:** Use `asyncio.create_subprocess_exec()` for system commands. For synchronous LLM calls (LangChain + Ollama is synchronous), use `asyncio.to_thread()` or `loop.run_in_executor()`.

### Anti-Pattern 4: Per-Process In-Memory State

**What:** Using module-level dictionaries or class attributes for shared state (like the current `_active_heartbeats` dict in `deployer.py`).

**Why bad:** State is lost on restart. Cannot be shared between daemon and TUI if they run as separate processes. Cannot survive container restarts.

**Instead:** Persistent state in SQLite. Heartbeat state specifically should use a watchdog file or SQLite row that the heartbeat thread updates, so rollback logic survives process crashes.

### Anti-Pattern 5: Monolithic Daemon Process

**What:** Building the daemon as one big loop that does everything: monitors logs, parses netflow, polls threat feeds, analyzes threats, generates rules, deploys them.

**Why bad:** Cannot add or remove data sources without modifying core daemon code. Testing requires the full stack. Failure in one source crashes everything.

**Instead:** Each data source is a separate `DataSource` implementation running as its own asyncio task. The supervisor manages lifecycle. Sources can be enabled/disabled via configuration.

## File/Module Structure

```
/mnt/Projects/AFO/
  core/                          # NEW: shared core (service layer, backends, state)
    __init__.py
    service.py                   # FirewallService facade
    state.py                     # SQLite state store
    events.py                    # Event types and event bus
    backends/
      __init__.py                # Backend loader
      base.py                    # FirewallBackend ABC
      registry.py                # Backend registration
      nftables.py                # Extracted from afo_mcp/tools/
      iptables.py                # New backend
      opnsense.py                # New backend

  daemon/                        # NEW: autonomous monitoring
    __init__.py
    supervisor.py                # DaemonSupervisor (asyncio)
    analyzer.py                  # ThreatAnalyzer
    models.py                    # SecurityEvent, ThreatAssessment, ThreatLevel
    sources/
      __init__.py
      base.py                    # DataSource ABC
      syslog.py                  # Syslog/auth.log monitor
      firewall_log.py            # Firewall log parser (nftables log, OPNsense)
      netflow.py                 # Netflow/sFlow analyzer
      threat_feed.py             # Threat intelligence feed poller

  tui/                           # NEW: Textual TUI
    __init__.py
    app.py                       # AFOApp main application
    screens/
      chat.py                    # Chat screen (rule generation)
      dashboard.py               # Daemon status + live events
      rules.py                   # Rule browser (pending, deployed, history)
      settings.py                # Configuration screen
    widgets/
      rule_card.py               # Rule display with approve/reject
      event_log.py               # Scrolling event display
      status_bar.py              # Daemon connection status

  agents/                        # EXISTING (minor changes)
    firewall_agent.py            # Keep generate_rule() and chat()
    prompts.py                   # Keep prompt templates
    tools.py                     # Keep LangChain tool wrappers

  afo_mcp/                       # EXISTING (refactored tools)
    __init__.py
    models.py                    # Keep, extend with new event models
    server.py                    # Keep MCP server (unchanged interface)
    security.py                  # Keep security utils
    tools/
      __init__.py
      network.py                 # Refactor: delegate to active backend
      validator.py               # Refactor: delegate to active backend
      conflicts.py               # Keep (backend-agnostic rule comparison)
      deployer.py                # Refactor: delegate to active backend

  db/                            # EXISTING (unchanged)
    vector_store.py

  ui/                            # EXISTING (minor refactor)
    app.py                       # Refactor: use service layer instead of direct imports

  docs/                          # EXISTING (unchanged)
    nftables_reference.md
```

## Scalability Considerations

| Concern | Single Host (current) | Multi-Backend | Production Daemon |
|---------|----------------------|---------------|-------------------|
| State storage | SQLite file | SQLite file (still fine) | SQLite or upgrade to PostgreSQL |
| Daemon-TUI communication | Same process or file-based | Same | Unix socket or SQLite polling |
| Event throughput | asyncio queue | asyncio queue | Add Redis if >1000 events/sec |
| LLM inference | Single Ollama instance | Same | Multiple Ollama instances behind load balancer |
| Backend concurrency | One backend active | Multiple backends simultaneously | Same, each backend is independent |
| Log volume | Tail file, filter in-process | Same | External log aggregation (rsyslog) feeding daemon |

For the foreseeable use case (single host firewall management), SQLite + asyncio + in-process communication is sufficient. Do not introduce Redis, PostgreSQL, or message queues unless measured throughput demands it.

## Build Order (Dependencies)

The components have the following dependency chain. This determines build order:

```
1. State Store (core/state.py)
   No dependencies on new code. Unlocks everything else.

2. Backend ABC + Registry (core/backends/base.py, registry.py)
   No dependencies on new code. Defines the plugin contract.

3. Nftables Backend (core/backends/nftables.py)
   Depends on: Backend ABC
   Extracts existing code from afo_mcp/tools/ into backend interface.

4. Service Layer (core/service.py)
   Depends on: State Store, Backend ABC, existing agent/tools
   Wires everything together. Unlocks TUI and daemon.

5. Refactor existing tools to use backend
   Depends on: Nftables Backend, Service Layer
   afo_mcp/tools/{network,validator,deployer}.py delegate to backend.
   FirewallRule.to_nft_command() delegates to NftablesBackend.
   ui/app.py uses service layer.

6. TUI (tui/)
   Depends on: Service Layer, State Store
   Can be built in parallel with daemon once service layer exists.

7. Daemon Data Source ABC + Event Models (daemon/sources/base.py, daemon/models.py)
   Depends on: State Store, Event models
   Defines the monitoring contract.

8. Daemon Supervisor (daemon/supervisor.py)
   Depends on: Data Source ABC, Service Layer, State Store
   Orchestrates data sources and threat analysis.

9. Individual Data Sources (daemon/sources/syslog.py, etc.)
   Depends on: Data Source ABC
   Can be built incrementally, one source at a time.

10. Additional Backends (iptables, OPNsense)
    Depends on: Backend ABC
    Can be built any time after step 2, in any order.
```

**Critical path:** State Store -> Backend ABC -> Nftables Backend -> Service Layer -> (TUI | Daemon in parallel)

**Safe parallelization:**
- Steps 1 and 2 can be built in parallel (no dependency between them)
- Steps 6 and 7-8 can be built in parallel (both depend on service layer)
- Step 10 can happen any time after step 2

## Integration with Existing MCP Server

The MCP server (`afo_mcp/server.py`) should remain unchanged in its external interface. The 6 tools it exposes are a stable API for external LLM clients. Internally, the tools can be rewired:

**Current:** `@mcp.tool() deploy_policy(...)` -> `afo_mcp.tools.deployer.deploy_policy()`
**Future:** `@mcp.tool() deploy_policy(...)` -> `afo_mcp.tools.deployer.deploy_policy()` -> `active_backend.deploy()`

The MCP server does not need to know about the service layer, TUI, or daemon. It continues to be a thin wrapper around the tool functions, which themselves get refactored to use the backend system. This means the MCP server gets the plugin system "for free" without any changes to `server.py`.

## New Pydantic Models Needed

```python
# Extend afo_mcp/models.py or create daemon/models.py

class ThreatLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SecurityEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source: str          # "syslog", "netflow", "threat_feed"
    event_type: str      # "brute_force", "port_scan", "known_bad_ip"
    severity: ThreatLevel
    source_ip: str | None = None
    destination_ip: str | None = None
    port: int | None = None
    protocol: str | None = None
    raw_data: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)

class ThreatAssessment(BaseModel):
    events: list[SecurityEvent]
    threat_level: ThreatLevel
    description: str
    recommended_prompt: str   # NL prompt to feed to agent for rule generation
    evidence: list[str]
    auto_actionable: bool     # Whether daemon should auto-respond

class RuleProposal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    success: bool
    rule: FirewallRule | None = None
    command: str = ""
    backend: str = ""
    validation: ValidationResult | None = None
    conflicts: ConflictReport | None = None
    explanation: str = ""
    error: str | None = None
    source: str = "user"      # "user", "daemon:auto", "daemon:propose"
    created_at: datetime = Field(default_factory=datetime.now)

class DaemonStatus(BaseModel):
    running: bool
    uptime_seconds: float
    active_sources: list[str]
    autonomy_level: str
    events_processed: int
    actions_taken: int
    last_event_at: datetime | None = None
```

## Sources

- Codebase analysis: All files in `/mnt/Projects/AFO/` (read directly)
- Existing architecture doc: `/mnt/Projects/AFO/.planning/codebase/ARCHITECTURE.md`
- Existing integrations doc: `/mnt/Projects/AFO/.planning/codebase/INTEGRATIONS.md`
- Project definition: `/mnt/Projects/AFO/.planning/PROJECT.md`
- Project design: `/mnt/Projects/AFO/claude.md`
- Textual framework: Training data knowledge (MEDIUM confidence -- could not verify against current docs)
- Python ABC/plugin patterns: Training data knowledge (HIGH confidence -- stable patterns)
- asyncio daemon patterns: Training data knowledge (HIGH confidence -- stable stdlib)
- SQLite for shared state: Training data knowledge (HIGH confidence -- well-established pattern)

---

*Architecture research: 2026-02-10*
