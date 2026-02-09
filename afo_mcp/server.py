"""AFO MCP Server - Exposes firewall orchestration tools to LLMs.

This server provides tools for:
- Gathering network context (interfaces, IPs, current rules)
- Validating nftables syntax
- Detecting rule conflicts
- Safe deployment with rollback capability
"""

import os
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP

from afo_mcp.models import ConflictReport, DeploymentResult, NetworkContext, ValidationResult
from afo_mcp.tools.conflicts import detect_conflicts as _detect_conflicts
from afo_mcp.tools.deployer import confirm_deployment, deploy_policy as _deploy_policy, rollback_deployment
from afo_mcp.tools.network import get_network_context as _get_network_context
from afo_mcp.tools.validator import validate_syntax as _validate_syntax

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("AFO - Autonomous Firewall Orchestrator")


@mcp.tool()
def get_network_context() -> dict[str, Any]:
    """Get current network context for firewall rule generation.

    Returns information about:
    - Network interfaces (names, IPs, MACs, VLANs, state)
    - Current nftables ruleset
    - System hostname

    Use this before generating firewall rules to understand the network topology.
    """
    ctx: NetworkContext = _get_network_context()
    return ctx.model_dump()


@mcp.tool()
def validate_syntax(command: str, platform: str = "nftables") -> dict[str, Any]:
    """Validate nftables command syntax without applying it.

    Args:
        command: The nftables command or ruleset to validate
        platform: Target platform (currently only 'nftables')

    Returns validation result with:
    - valid: Whether syntax is correct
    - errors: List of error messages
    - warnings: List of warnings
    - line_numbers: Lines with errors

    Always validate rules before deployment!
    """
    result: ValidationResult = _validate_syntax(command, platform)
    return result.model_dump()


@mcp.tool()
def detect_conflicts(proposed_rule: str, active_ruleset: str | None = None) -> dict[str, Any]:
    """Check for conflicts between a proposed rule and active rules.

    Args:
        proposed_rule: The nftables rule to check
        active_ruleset: Current ruleset (fetched automatically if not provided)

    Returns conflict report with:
    - has_conflicts: Whether any conflicts found
    - conflicts: List of {type, existing_rule, explanation}
    - recommendations: Suggested resolutions

    Conflict types:
    - shadow: New rule will never match (shadowed by existing)
    - redundant: New rule duplicates existing
    - contradiction: Rules have opposite actions
    - overlap: Partial overlap in criteria

    Run this before deploying new rules to catch issues early.
    """
    report: ConflictReport = _detect_conflicts(proposed_rule, active_ruleset)
    return report.model_dump()


@mcp.tool()
def deploy_policy(
    rule_id: str,
    rule_content: str,
    approved: bool = False,
    enable_heartbeat: bool = True,
    heartbeat_timeout: int = 30,
) -> dict[str, Any]:
    """Deploy a firewall rule with safety mechanisms.

    Args:
        rule_id: Unique identifier for tracking this rule
        rule_content: The nftables rule(s) to deploy
        approved: MUST be True to actually deploy (safety requirement)
        enable_heartbeat: Start auto-rollback timer (recommended)
        heartbeat_timeout: Seconds before auto-rollback (default 30)

    Returns deployment result with:
    - success: Whether deployment succeeded
    - status: pending/approved/deployed/failed/rolled_back
    - backup_path: Location of rollback backup
    - heartbeat_active: Whether auto-rollback is armed

    Safety features:
    1. Requires explicit approved=True
    2. Creates backup before any changes
    3. Heartbeat monitor auto-rolls back if not confirmed
    4. Use confirm_deployment() to finalize or rollback_deployment() to revert

    IMPORTANT: After deployment, call confirm_deployment(rule_id) to stop
    the auto-rollback timer, or let it expire to automatically revert.
    """
    result: DeploymentResult = _deploy_policy(
        rule_id=rule_id,
        rule_content=rule_content,
        approved=approved,
        enable_heartbeat=enable_heartbeat,
        heartbeat_timeout=heartbeat_timeout,
    )
    return result.model_dump()


@mcp.tool()
def confirm_rule_deployment(rule_id: str) -> dict[str, Any]:
    """Confirm a deployment and disable auto-rollback.

    Args:
        rule_id: The rule ID from deploy_policy()

    Call this after verifying the deployed rules work correctly.
    This stops the heartbeat timer that would otherwise rollback.

    Returns:
        success: Whether confirmation succeeded
    """
    success = confirm_deployment(rule_id)
    return {"success": success, "rule_id": rule_id}


@mcp.tool()
def rollback_rule(rule_id: str) -> dict[str, Any]:
    """Manually rollback a deployed rule.

    Args:
        rule_id: The rule ID to rollback

    Restores the system to the state before this rule was deployed.
    """
    result: DeploymentResult = rollback_deployment(rule_id)
    return result.model_dump()


def main() -> None:
    """Run the MCP server."""
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8765"))

    print(f"Starting AFO MCP Server on {host}:{port}")
    print("Tools available:")
    print("  - get_network_context: Gather network state")
    print("  - validate_syntax: Check nftables syntax")
    print("  - detect_conflicts: Find rule conflicts")
    print("  - deploy_policy: Apply rules with rollback")
    print("  - confirm_rule_deployment: Finalize deployment")
    print("  - rollback_rule: Revert deployment")

    mcp.run()


if __name__ == "__main__":
    main()
