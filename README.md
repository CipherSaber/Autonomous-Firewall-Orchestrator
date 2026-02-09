# AFO - Autonomous Firewall Orchestrator

Translate natural language security requirements into executable nftables/OPNsense firewall rules.

## Quick Start

```bash
# Run with Docker
docker compose up -d

# Run tests
docker compose --profile test up test
```

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

## Architecture

- **MCP Server**: Exposes firewall tools to LLMs via Model Context Protocol
- **Hybrid Approach**: AI for intent translation, deterministic logic for verification
- **Safety First**: Rules require approval, automatic rollback on failure

## MCP Tools

| Tool | Description |
|------|-------------|
| `get_network_context` | Get interfaces, IPs, current ruleset |
| `validate_syntax` | Dry-run nftables syntax check |
| `detect_conflicts` | Find rule conflicts before deployment |
| `deploy_policy` | Apply rules with rollback capability |

## License

MIT
