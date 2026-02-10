# Coding Conventions

**Analysis Date:** 2026-02-10

## Naming Patterns

**Files:**
- Use `snake_case.py` for all Python modules: `firewall_agent.py`, `vector_store.py`, `test_mcp_tools.py`
- Test files prefixed with `test_`: `tests/test_mcp_tools.py`, `tests/test_phase2.py`
- Package `__init__.py` files contain docstrings and re-exports

**Functions:**
- Use `snake_case` for all functions: `get_network_context()`, `validate_rule_structure()`, `_extract_json()`
- Prefix private/internal functions with a single underscore: `_parse_rule()`, `_get_llm()`, `_create_backup()`
- Public API functions have no prefix: `detect_conflicts()`, `deploy_policy()`, `retrieve()`
- CLI entry points end with `_cli`: `ingest_docs_cli()` in `db/vector_store.py`

**Variables:**
- Use `snake_case` for local variables and parameters: `rule_content`, `backup_path`, `heartbeat_timeout`
- Use `UPPER_SNAKE_CASE` for module-level constants: `OLLAMA_HOST`, `EMBED_MODEL`, `BACKUP_DIR`, `ROLLBACK_TIMEOUT`
- Constants defined via `os.environ.get()` use `UPPER_SNAKE_CASE`: `OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")`

**Types/Classes:**
- Use `PascalCase` for all classes: `FirewallRule`, `NetworkContext`, `ValidationResult`, `ParsedRule`
- Pydantic models use `PascalCase` nouns: `ConflictReport`, `DeploymentResult`
- Enums use `PascalCase` and extend `StrEnum`: `RuleAction`, `Protocol`, `ConflictType`, `DeploymentStatus`
- Enum members use `UPPER_SNAKE_CASE`: `RuleAction.ACCEPT`, `ConflictType.ROLLED_BACK`
- Test classes use `Test` prefix with `PascalCase`: `TestModels`, `TestValidator`, `TestConflictDetection`

## Code Style

**Formatting:**
- Ruff is the formatter and linter (configured in `pyproject.toml`)
- Line length: 100 characters
- Target Python version: 3.11

**Linting:**
- Ruff with rule sets: `E` (pycodestyle errors), `F` (pyflakes), `I` (isort), `N` (pep8-naming), `W` (pycodestyle warnings), `UP` (pyupgrade)
- Configuration in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`
- Run with: `ruff check .` and `ruff format .`

**Type Annotations:**
- Use modern Python 3.11+ syntax for type hints throughout
- Use `str | None` instead of `Optional[str]`: see `afo_mcp/models.py` line 77
- Use `list[str]` instead of `List[str]`: see `afo_mcp/models.py` line 18
- Use `dict[str, Any]` instead of `Dict[str, Any]`: see `afo_mcp/server.py` line 39
- Return type annotations on all public functions
- Parameter type annotations on all function signatures

## Import Organization

**Order (enforced by ruff isort):**
1. Standard library: `import json`, `import os`, `import re`, `import subprocess`
2. Third-party: `from langchain_core.tools import tool`, `from pydantic import BaseModel, Field`
3. Local/project: `from afo_mcp.models import FirewallRule`, `from agents.prompts import SYSTEM_PROMPT`

**Style:**
- Combine `as` imports on one line (`combine-as-imports = true` in `pyproject.toml`)
- Use `from X import Y` for specific imports, not bare `import X` (except standard library modules like `json`, `os`, `re`)
- Alias private imports with underscore prefix when wrapping for different interfaces:
  ```python
  # In afo_mcp/server.py
  from afo_mcp.tools.conflicts import detect_conflicts as _detect_conflicts
  from afo_mcp.tools.network import get_network_context as _get_network_context
  ```

**Path Aliases:**
- No path aliases configured. All imports use direct package names: `afo_mcp.tools.conflicts`, `agents.firewall_agent`, `db.vector_store`

## Error Handling

**Patterns:**
- Return structured result objects instead of raising exceptions for expected failures. Functions return `DeploymentResult`, `ValidationResult`, `ConflictReport` with success/error fields:
  ```python
  # afo_mcp/tools/deployer.py
  return DeploymentResult(
      success=False,
      status=DeploymentStatus.FAILED,
      rule_id=rule_id,
      error="Rule content contains potentially dangerous characters",
  )
  ```

- Use try/except for external system calls (`subprocess`, `httpx`), catching specific exceptions:
  ```python
  # afo_mcp/tools/network.py
  except subprocess.TimeoutExpired:
      return "# Timeout listing ruleset"
  except FileNotFoundError:
      return "# nft command not found"
  except PermissionError:
      return "# Permission denied - need root for nft"
  ```

- Return `None` from parsing/builder functions to signal failure instead of raising:
  ```python
  # agents/firewall_agent.py
  def _build_firewall_rule(data: dict) -> FirewallRule | None:
      try:
          ...
          return rule
      except Exception:
          return None
  ```

- Graceful degradation pattern: fall back to simpler behavior when services are unavailable:
  ```python
  # db/vector_store.py - falls back to keyword search when Ollama is down
  if not embeddings or not _ollama_reachable():
      return _keyword_search(chunks, query, n_results)
  ```

- Dict-based return values for high-level agent functions with `success` bool key:
  ```python
  # agents/firewall_agent.py
  return {
      "success": False,
      "error": f"LLM connection failed: {e}. Is Ollama running?",
      "rag_sources": rag_sources,
  }
  ```

## Logging

**Framework:** No logging framework. Uses `print()` for CLI output only.

**Patterns:**
- Print statements only in CLI entry points: `afo_mcp/server.py` `main()`, `db/vector_store.py` `ingest_docs_cli()`
- No logging within library/tool functions
- Error information is conveyed through return values, not logged

## Comments

**When to Comment:**
- Module-level docstrings on every `.py` file, describing purpose and key details
- Inline comments for non-obvious logic steps, especially in `agents/firewall_agent.py` numbered steps (Step 1, Step 2, etc.)
- Comments for regex patterns and parser logic in `afo_mcp/tools/conflicts.py`

**Docstrings:**
- Use triple-quoted docstrings on all public functions and classes
- Google-style docstring format with `Args:` and `Returns:` sections:
  ```python
  def deploy_policy(
      rule_id: str,
      rule_content: str,
      ...
  ) -> DeploymentResult:
      """Deploy a firewall rule with safety mechanisms.

      Args:
          rule_id: Unique identifier for this rule
          rule_content: The nftables rule(s) to deploy
          ...

      Returns:
          DeploymentResult with deployment status and backup info.
      """
  ```
- All `__init__.py` have single-line module docstrings
- MCP tool docstrings serve dual purpose: Python documentation and LLM tool descriptions

## Function Design

**Size:**
- Functions are generally 20-50 lines
- Largest functions are `detect_conflicts()` (~90 lines) and `deploy_policy()` (~100 lines) in the tools layer
- Complex operations are broken into smaller private helper functions (e.g., `_parse_rule()`, `_networks_overlap()`, `_ports_overlap()`)

**Parameters:**
- Use keyword arguments with defaults for optional parameters
- Boolean flags for safety-critical operations: `approved: bool = False`
- Use `| None` for optional parameters: `active_ruleset: str | None = None`

**Return Values:**
- Pydantic models for structured tool outputs: `ValidationResult`, `ConflictReport`, `DeploymentResult`
- Plain dicts for agent-layer responses (returned to UI): `{"success": True, "rule": ..., "nft_command": ...}`
- `None` for "could not parse" / "not found" cases
- Strings for formatted text output (LangChain tool wrappers in `agents/tools.py`)

## Module Design

**Exports:**
- Explicit `__all__` lists in package `__init__.py` files: `afo_mcp/__init__.py`, `afo_mcp/tools/__init__.py`
- Re-export key models from package root: `afo_mcp/__init__.py` re-exports all models from `afo_mcp/models.py`

**Barrel Files:**
- `afo_mcp/__init__.py` serves as barrel file, re-exporting all models
- `afo_mcp/tools/__init__.py` re-exports all tool functions

**Data Modeling:**
- All shared data structures are Pydantic `BaseModel` subclasses in `afo_mcp/models.py`
- Use `Field(...)` with `description` for every field (serves as schema docs for LLMs)
- Use `default_factory` for mutable defaults: `Field(default_factory=list)`
- Enums extend `StrEnum` for JSON serialization compatibility
- Internal-only dataclasses used for intermediate parsing: `ParsedRule` in `afo_mcp/tools/conflicts.py`

## Security Conventions

**Input Validation:**
- All user/LLM-provided input passes through security checks before shell execution
- Shared security utilities in `afo_mcp/security.py`
- Use `contains_dangerous_chars()` before any subprocess call with user content
- Validate names with dedicated functions: `is_valid_interface_name()`, `is_valid_table_name()`, `is_valid_chain_name()`

**Subprocess Calls:**
- Always use list-form arguments (never shell=True): `subprocess.run(["nft", "--check", "-f", str(tmp_path)], ...)`
- Always set `capture_output=True` and `timeout`
- Always handle `subprocess.TimeoutExpired`, `FileNotFoundError`, `PermissionError`

**Environment Variables:**
- Access via `os.environ.get()` with sensible defaults
- Never hardcode secrets or credentials
- `.env` file loaded via `python-dotenv` in `afo_mcp/server.py`

---

*Convention analysis: 2026-02-10*
