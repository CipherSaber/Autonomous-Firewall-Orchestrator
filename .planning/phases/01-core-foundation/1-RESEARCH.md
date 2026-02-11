# Phase 1: Core Foundation - Research

**Researched:** 2026-02-11
**Domain:** Python Backend Architecture (Persistence, Abstraction, Logging)
**Confidence:** HIGH

## Summary

Phase 1 establishes the bedrock for AFO, transitioning from a prototype to a robust system. The core goals are persistence, abstraction of firewall backends, and structured logging. Research confirms that **SQLModel** is the optimal choice for persistence given our heavy use of Pydantic. **Structlog** is the industry standard for structured logging in Python. The **Service Layer pattern** with Dependency Injection will decouple the MCP/TUI consumers from the underlying firewall logic, facilitating testing and future backend additions.

**Primary recommendation:** implement `FirewallService` as the single entry point, backed by `SQLModel` for state and `structlog` for observability, using `abc.ABC` for the backend interface.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **SQLModel** | ^0.0.16 | ORM / Persistence | Unifies Pydantic models with SQLAlchemy Core; perfect for FastAPI/MCP stacks. |
| **structlog** | ^24.1.0 | Structured Logging | fast, flexible, and standard for modern Python apps requiring JSON logs. |
| **alembic** | ^1.13.0 | DB Migrations | Standard companion to SQLAlchemy/SQLModel for schema evolution. |
| **tenacity** | ^8.2.0 | Retries | Robust retry logic for flaky subprocess/network calls (firewall commands). |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-asyncio** | ^0.23.0 | Async Testing | Essential for testing async service methods. |
| **polyfactory** | ^2.14.0 | Model Factories | Simplifies creating test data for Pydantic/SQLModel models. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **SQLModel** | SQLAlchemy 2.0 | SQLAlchemy is more verbose; SQLModel reduces duplication between DB and Pydantic schemas. |
| **structlog** | standard `logging` | Stdlib logging is clunky for structured/JSON output; structlog wraps it elegantly. |
| **SQLite** | PostgreSQL | SQLite is sufficient for single-host; Postgres adds operational complexity unnecessary for v1. |

**Installation:**
```bash
pip install sqlmodel structlog alembic tenacity
```

## Architecture Patterns

### Recommended Project Structure
We should introduce a `core` package to house the foundational logic, keeping it distinct from `afo_mcp` (transport) and `ui` (presentation).

```
src/
├── core/
│   ├── __init__.py
│   ├── config.py          # Centralized configuration
│   ├── database.py        # SQLModel engine and session
│   ├── events.py          # Event bus (optional for now, good for audit)
│   ├── exceptions.py      # Core domain exceptions
│   ├── logging.py         # Structlog configuration
│   ├── models/            # Domain models (PolicyRule, etc.)
│   │   └── ...
│   ├── interfaces/        # Abstract Base Classes
│   │   └── backend.py     # FirewallBackend ABC
│   └── services/          # Business logic
│       └── firewall.py    # FirewallService
├── backends/              # Implementations of FirewallBackend
│   ├── __init__.py
│   └── nftables.py        # NftablesBackend (refactored from agents)
```

### Pattern 1: Service Layer with Dependency Injection
**What:** The `FirewallService` class encapsulates all business logic (validation, persistence, deployment). It accepts a `FirewallBackend` instance at initialization.
**When to use:** Always when mediating between consumers (MCP, TUI) and infrastructure (nftables).
**Example:**
```python
# core/interfaces/backend.py
from abc import ABC, abstractmethod
from core.models.policy import PolicyRule

class FirewallBackend(ABC):
    @abstractmethod
    async def apply_rule(self, rule: PolicyRule) -> bool:
        """Apply a rule to the system."""
        pass

# core/services/firewall.py
class FirewallService:
    def __init__(self, backend: FirewallBackend, db_session):
        self.backend = backend
        self.db = db_session

    async def deploy_rule(self, rule: PolicyRule):
        # 1. Validate
        # 2. Persist to DB (pending)
        # 3. Call Backend
        # 4. Update DB (active)
        pass
```

### Pattern 2: Structured Logging Context
**What:** Bind context (request ID, user, rule ID) to the logger at the start of an operation.
**When to use:** In every public method of the Service Layer.
**Example:**
```python
import structlog
logger = structlog.get_logger()

async def deploy_rule(self, rule_id: str):
    log = logger.bind(rule_id=rule_id)
    log.info("deploying_rule")
    try:
        # ...
        log.info("rule_deployed")
    except Exception:
        log.exception("deployment_failed")
```

### Anti-Patterns to Avoid
- **Global State:** Avoid global variables for DB sessions or backend instances. Pass them explicitly.
- **God Object:** Don't let `FirewallService` become a dump for everything. Delegate specific tasks (like parsing) to helpers.
- **Leaky Abstractions:** `FirewallBackend` should NOT expose nftables-specific concepts (like "handles") in its public API if possible.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Retry Logic** | Custom `while` loops | `tenacity` | Correctly handles backoff, jitter, and stop conditions. |
| **Migrations** | Custom SQL scripts | `alembic` | Handles dependency tracking, rollback, and state management. |
| **Input Validation** | Manual `if` checks | `Pydantic` | Declarative, robust, and handles coercion correctly. |

**Key insight:** Firewall operations are inherently flaky (locks, race conditions). Robust retry logic is essential and hard to get right manually.

## Common Pitfalls

### Pitfall 1: Mixing Async and Sync DB Operations
**What goes wrong:** Blocking the event loop with synchronous DB calls.
**Why it happens:** SQLModel/SQLAlchemy has both sync and async APIs; easy to mix them up.
**How to avoid:** Use `AsyncSession` explicitly. Ensure all DB IO is awaited.
**Warning signs:** "Event loop is closed" errors or UI freezes.

### Pitfall 2: Backend-Specific Logic in Service Layer
**What goes wrong:** Nftables commands leaking into `FirewallService`.
**Why it happens:** "Just getting it working" without proper abstraction.
**How to avoid:** If you write `nft` in `FirewallService`, you are wrong. Move it to `backends/nftables.py`.
**Warning signs:** `subprocess.run` calls inside Service classes.

### Pitfall 3: Not testing Rollbacks
**What goes wrong:** Deployment fails, system left in inconsistent state.
**Why it happens:** Testing only the "happy path".
**How to avoid:** Write tests specifically for failure scenarios that assert the system state is restored.

## Code Examples

### Abstract Base Class (CORE-02)
```python
from abc import ABC, abstractmethod
from typing import List
from core.models import PolicyRule, SystemStatus

class FirewallBackend(ABC):
    @abstractmethod
    async def list_rules(self) -> List[PolicyRule]:
        """Return current active rules in abstract format."""
        pass

    @abstractmethod
    async def validate_rule(self, rule: PolicyRule) -> bool:
        """Check if rule is syntactically valid for this backend."""
        pass

    @abstractmethod
    async def deploy_rule(self, rule: PolicyRule) -> bool:
        """Apply rule to the live system."""
        pass

    @abstractmethod
    async def delete_rule(self, rule_id: str) -> bool:
        """Remove rule from live system."""
        pass
```

### SQLModel Persistence (CORE-01)
```python
from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

class FirewallRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: str = Field(index=True)
    action: str
    source: str
    destination: str
    status: str = "pending"  # pending, active, deleted
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Raw SQL / string building** | **Pydantic + ORM** | ~2022 (SQLModel) | Type safety, injection prevention, auto-docs. |
| **print() debugging** | **Structured Logging** | ~2018 (mainstream) | Logs can be queried, parsed, and alerted on. |
| **Tightly coupled code** | **Ports & Adapters** | Decades old, but critical here | Allows swapping nftables for iptables/cloud later. |

## Open Questions

1.  **Event Bus?**
    *   What we know: We need audit trails (AGENT-06).
    *   What's unclear: Should we implement a full event bus now or just direct calls?
    *   Recommendation: Keep it simple for v1. Direct service method calls that write to AuditLog table.

2.  **Concurrency Control**
    *   What we know: `nft` command holds a lock.
    *   What's unclear: How to handle multiple MCP tools trying to modify rules simultaneously.
    *   Recommendation: Use `tenacity` to retry on lock file contention.

## Sources

### Primary (HIGH confidence)
- **SQLModel Docs** - Verified features for Pydantic v2 integration.
- **Structlog Docs** - Verified configuration patterns.
- **Python Standard Library** - `abc` module documentation.

### Secondary (MEDIUM confidence)
- **Architecture Patterns** - Common industry practices for Python microservices.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Widely adopted, mature libraries.
- Architecture: HIGH - Standard Service/Repository/Adapter patterns.
- Pitfalls: MEDIUM - Specific nftables edge cases might still surprise us.

**Research date:** 2026-02-11
**Valid until:** 2026-05-11
