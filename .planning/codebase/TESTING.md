# Testing Patterns

**Analysis Date:** 2026-02-10

## Test Framework

**Runner:**
- pytest >= 8.0
- pytest-asyncio >= 0.23 (for async test support)
- Config: `pyproject.toml` under `[tool.pytest.ini_options]` and `pytest.ini`

**Assertion Library:**
- Built-in `assert` statements (pytest native assertions)

**Run Commands:**
```bash
pytest                           # Run all tests (excluding integration)
pytest -m integration            # Run integration tests only
pytest -v                        # Verbose output
pytest tests/test_mcp_tools.py   # Run specific test file
pytest -k "TestValidator"        # Run specific test class
```

## Test File Organization

**Location:**
- Separate `tests/` directory at project root (not co-located with source)
- Configured via `testpaths = ["tests"]` in `pyproject.toml`

**Naming:**
- Test files: `test_<component>.py` (e.g., `tests/test_mcp_tools.py`, `tests/test_phase2.py`)
- Test classes: `Test<Component>` (e.g., `TestModels`, `TestValidator`, `TestConflictDetection`)
- Test methods: `test_<what_is_tested>` (e.g., `test_firewall_rule_to_nft_command`, `test_networks_overlap_exact`)

**Structure:**
```
tests/
├── __init__.py          # Package init with docstring
├── test_mcp_tools.py    # Phase 1 tests: models, validator, conflicts, security
└── test_phase2.py       # Phase 2 tests: agent, prompts, tools, vector store
```

## Test Structure

**Suite Organization:**
- Tests are grouped into classes by component/concern
- Each class tests one logical unit (model, tool, security module)
- No setUp/tearDown methods -- tests are self-contained

```python
# Pattern from tests/test_mcp_tools.py
class TestModels:
    """Test Pydantic model validation."""

    def test_network_interface_creation(self):
        """Test NetworkInterface model."""
        iface = NetworkInterface(
            name="eth0",
            mac_address="00:11:22:33:44:55",
            ipv4_addresses=["192.168.1.1"],
            ipv6_addresses=["fe80::1"],
            state="UP",
            mtu=1500,
        )
        assert iface.name == "eth0"
        assert iface.state == "UP"

    def test_firewall_rule_to_nft_command(self):
        """Test FirewallRule.to_nft_command()."""
        rule = FirewallRule(
            table="filter",
            chain="input",
            family="inet",
            protocol=Protocol.TCP,
            destination_port=22,
            action=RuleAction.ACCEPT,
            comment="Allow SSH",
        )
        cmd = rule.to_nft_command()
        assert "add rule inet filter input" in cmd
        assert "tcp dport 22" in cmd
        assert "accept" in cmd
```

**Test Classes by File:**

`tests/test_mcp_tools.py`:
- `TestModels` -- Pydantic model creation and `to_nft_command()` generation (4 tests)
- `TestValidator` -- Rule structure validation (4 tests)
- `TestConflictDetection` -- Rule parsing, network/port overlap, conflict detection (12 tests)
- `TestDeploymentModels` -- Enum value correctness (1 test)
- `TestSecurity` -- Shell injection detection, name validation (6 tests)
- `TestIntegration` -- System-access tests marked with `@pytest.mark.integration` (2 tests)

`tests/test_phase2.py`:
- `TestJsonExtraction` -- JSON parsing from LLM responses (5 tests)
- `TestRuleBuilding` -- `_build_firewall_rule()` conversion (6 tests)
- `TestPrompts` -- Prompt template formatting (2 tests)
- `TestAgentTools` -- LangChain tool wrapper invocation (3 tests)
- `TestVectorStore` -- Document chunking and retrieval (2 tests)

## Test Markers

**Custom Markers (defined in `pytest.ini`):**
- `integration` -- Tests requiring system access (nftables, root privileges)

**Usage:**
```python
# tests/test_mcp_tools.py
@pytest.mark.integration
def test_get_network_context(self):
    """Test getting network context from system."""
    from afo_mcp.tools.network import get_network_context
    ctx = get_network_context()
    assert ctx.hostname
    assert len(ctx.interfaces) > 0
```

**Conditional Skips:**
```python
# tests/test_phase2.py
def _ollama_available() -> bool:
    """Check if Ollama is running with nomic-embed-text."""
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=2)
        data = resp.json()
        models = [m["name"] for m in data.get("models", [])]
        return any("nomic-embed-text" in m for m in models)
    except Exception:
        return False

@pytest.mark.skipif(
    not _ollama_available(),
    reason="Ollama not running or nomic-embed-text not available",
)
def test_ingest_and_retrieve(self):
    ...
```

## Async Testing

**Configuration:**
- `asyncio_mode = "auto"` in `pyproject.toml` -- async tests run automatically without explicit `@pytest.mark.asyncio`
- No async tests exist yet, but the infrastructure is ready

## Mocking

**Framework:** No mocking framework in use. No `unittest.mock`, no `pytest-mock`, no `monkeypatch`.

**Current Approach:**
- Tests call real functions directly with controlled input data
- Integration tests that need system access are marked and skipped by default
- Tests needing Ollama use a helper function to check availability and skip if unavailable
- LangChain tool wrappers are tested via `.invoke()` with dict args

**What to Mock (when adding mocks):**
- `subprocess.run` calls in `afo_mcp/tools/network.py`, `afo_mcp/tools/validator.py`, `afo_mcp/tools/deployer.py`
- `httpx` calls in `db/vector_store.py` for Ollama API
- `ChatOllama` in `agents/firewall_agent.py`
- File system operations (`Path.read_text`, `Path.write_text`) for backup/restore

**What NOT to Mock:**
- Pydantic model construction and validation
- Pure logic functions: `_parse_rule()`, `_networks_overlap()`, `_ports_overlap()`, `_extract_json()`
- Enum values and constants

## Fixtures and Factories

**Test Data:**
- Test data is constructed inline within each test method
- No shared fixtures, conftest.py, or factory functions
- Pydantic models are instantiated directly with test values:
  ```python
  rule = FirewallRule(
      table="filter",
      chain="input",
      family="inet",
      protocol=Protocol.TCP,
      destination_port=22,
      action=RuleAction.ACCEPT,
      comment="Allow SSH",
  )
  ```
- Multi-line strings used for ruleset test data:
  ```python
  active_ruleset = """
  table inet filter {
      chain input {
          type filter hook input priority filter; policy drop;
          tcp dport 22 drop
      }
  }
  """
  ```

**Location:**
- All test data is inline within test methods
- No separate fixtures directory
- No conftest.py file

## Coverage

**Requirements:** None enforced. No coverage configuration or thresholds.

**View Coverage:**
```bash
pip install pytest-cov                    # Install coverage plugin (not in dev deps)
pytest --cov=afo_mcp --cov=agents --cov=db --cov=ui   # Run with coverage
```

## Test Types

**Unit Tests:**
- Primary test type. Test individual functions with controlled inputs.
- Cover: model creation, command generation, rule parsing, conflict logic, security checks, JSON extraction, prompt formatting
- Files: `tests/test_mcp_tools.py` (classes `TestModels`, `TestValidator`, `TestConflictDetection`, `TestDeploymentModels`, `TestSecurity`), `tests/test_phase2.py` (classes `TestJsonExtraction`, `TestRuleBuilding`, `TestPrompts`)

**Component Tests:**
- Test tool wrappers that combine multiple internal functions
- Cover: LangChain tool invocation, vector store chunking
- Files: `tests/test_phase2.py` (classes `TestAgentTools`, `TestVectorStore`)

**Integration Tests:**
- Require system access (nftables binary, root privileges, Ollama service)
- Marked with `@pytest.mark.integration` or `@pytest.mark.skipif`
- Skipped by default in CI/local runs
- Files: `tests/test_mcp_tools.py` (class `TestIntegration`), `tests/test_phase2.py` (`test_ingest_and_retrieve`)

**E2E Tests:**
- Not implemented. No Streamlit UI tests, no end-to-end agent workflow tests.

## Common Patterns

**Testing Pydantic Models:**
```python
# Construct model, verify fields, test methods
rule = FirewallRule(
    table="filter", chain="input", family="inet",
    protocol=Protocol.TCP, destination_port=22,
    action=RuleAction.ACCEPT, comment="Allow SSH",
)
cmd = rule.to_nft_command()
assert "add rule inet filter input" in cmd
assert "tcp dport 22" in cmd
```

**Testing Pure Functions with Edge Cases:**
```python
# Test positive case
assert _networks_overlap("192.168.1.0/24", "192.168.1.0/24")
# Test subset case
assert _networks_overlap("192.168.0.0/16", "192.168.1.0/24")
# Test negative case
assert not _networks_overlap("192.168.1.0/24", "10.0.0.0/8")
# Test edge case (single IP)
assert _networks_overlap("192.168.1.100", "192.168.1.0/24")
```

**Testing Validation (valid/invalid pairs):**
```python
# Valid input
result = validate_rule_structure("add rule inet filter input tcp dport 22 accept")
assert result.valid

# Invalid input
result = validate_rule_structure("")
assert not result.valid
assert "Empty command" in result.errors
```

**Testing with String Containment:**
```python
# Most assertions use `in` or `any()` for flexible output matching
assert "VALID" in result
assert any("iptables" in w.lower() for w in result.warnings)
```

**Testing LangChain Tools:**
```python
# Invoke via .invoke() with dict arguments
from agents.tools import validate_structure
result = validate_structure.invoke({"command": "add rule inet filter input accept"})
assert "VALID" in result
```

**Testing with External Service Dependencies:**
```python
# Module-level helper to check service availability
def _ollama_available() -> bool:
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=2)
        ...
        return True
    except Exception:
        return False

# Skip test if service unavailable
@pytest.mark.skipif(not _ollama_available(), reason="Ollama not running")
def test_ingest_and_retrieve(self):
    ...
```

## Test Gaps

**Not Tested:**
- `ui/app.py` -- No Streamlit UI tests
- `afo_mcp/tools/deployer.py` -- No unit tests for deployment, backup, rollback, heartbeat logic
- `agents/firewall_agent.py` `generate_rule()` and `chat()` -- No tests for full agent workflow (requires LLM)
- `afo_mcp/server.py` -- No MCP server endpoint tests
- Error paths in `afo_mcp/tools/network.py` -- No tests for subprocess failure scenarios
- `db/vector_store.py` keyword search fallback -- No isolated test for `_keyword_search()`

---

*Testing analysis: 2026-02-10*
