"""Deployment tool - safely applies firewall rules with rollback capability."""

import os
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from afo_mcp.models import DeploymentResult, DeploymentStatus
from afo_mcp.security import contains_dangerous_chars

# Global state for heartbeat monitors
_active_heartbeats: dict[str, threading.Event] = {}
_heartbeat_threads: dict[str, threading.Thread] = {}

# Default paths
BACKUP_DIR = Path("/var/lib/afo/backups")
ROLLBACK_TIMEOUT = int(os.environ.get("ROLLBACK_TIMEOUT", "30"))


def _ensure_backup_dir() -> Path:
    """Ensure backup directory exists."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def _create_backup(rule_id: str) -> Path | None:
    """Create a backup of current ruleset."""
    try:
        result = subprocess.run(
            ["nft", "list", "ruleset"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        backup_dir = _ensure_backup_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"backup_{rule_id}_{timestamp}.nft"
        backup_path.write_text(result.stdout)
        return backup_path
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        return None


def _restore_backup(backup_path: Path) -> bool:
    """Restore ruleset from backup."""
    if not backup_path.exists():
        return False

    try:
        # Flush current ruleset and restore backup
        subprocess.run(
            ["nft", "flush", "ruleset"],
            capture_output=True,
            timeout=10,
        )
        result = subprocess.run(
            ["nft", "-f", str(backup_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        return False


def _heartbeat_monitor(
    rule_id: str,
    backup_path: Path,
    timeout: int,
    stop_event: threading.Event,
    heartbeat_fn: Callable[[], bool] | None = None,
) -> None:
    """Monitor for heartbeat and rollback if it fails.

    This runs in a separate thread after deployment. If the heartbeat
    function returns False or times out, it automatically rolls back.
    """
    start_time = time.time()

    while not stop_event.is_set():
        elapsed = time.time() - start_time

        if elapsed >= timeout:
            # Timeout - rollback
            _restore_backup(backup_path)
            break

        if heartbeat_fn is not None:
            try:
                if not heartbeat_fn():
                    # Heartbeat failed - rollback
                    _restore_backup(backup_path)
                    break
            except Exception:
                # Heartbeat error - rollback
                _restore_backup(backup_path)
                break

        time.sleep(1)


def confirm_deployment(rule_id: str) -> bool:
    """Confirm a deployment and stop the heartbeat monitor.

    Call this after verifying the deployment works correctly.
    This stops the automatic rollback timer.
    """
    if rule_id in _active_heartbeats:
        _active_heartbeats[rule_id].set()
        if rule_id in _heartbeat_threads:
            _heartbeat_threads[rule_id].join(timeout=2)
            del _heartbeat_threads[rule_id]
        del _active_heartbeats[rule_id]
        return True
    return False


def rollback_deployment(rule_id: str) -> DeploymentResult:
    """Manually rollback a deployment."""
    # Stop heartbeat monitor if running
    if rule_id in _active_heartbeats:
        _active_heartbeats[rule_id].set()

    # Find most recent backup for this rule
    backup_dir = _ensure_backup_dir()
    backups = sorted(
        backup_dir.glob(f"backup_{rule_id}_*.nft"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not backups:
        return DeploymentResult(
            success=False,
            status=DeploymentStatus.FAILED,
            rule_id=rule_id,
            error="No backup found for this rule",
        )

    backup_path = backups[0]
    if _restore_backup(backup_path):
        return DeploymentResult(
            success=True,
            status=DeploymentStatus.ROLLED_BACK,
            rule_id=rule_id,
            backup_path=str(backup_path),
        )
    else:
        return DeploymentResult(
            success=False,
            status=DeploymentStatus.FAILED,
            rule_id=rule_id,
            error="Failed to restore backup",
        )


def deploy_policy(
    rule_id: str,
    rule_content: str,
    approved: bool = False,
    enable_heartbeat: bool = True,
    heartbeat_timeout: int | None = None,
    heartbeat_fn: Callable[[], bool] | None = None,
) -> DeploymentResult:
    """Deploy a firewall rule with safety mechanisms.

    Args:
        rule_id: Unique identifier for this rule
        rule_content: The nftables rule(s) to deploy
        approved: Must be True to actually deploy (safety check)
        enable_heartbeat: Whether to start heartbeat monitor for auto-rollback
        heartbeat_timeout: Seconds before auto-rollback (default from env)
        heartbeat_fn: Optional function that returns True if deployment is healthy

    Returns:
        DeploymentResult with deployment status and backup info.

    Safety features:
    - Requires explicit approval flag
    - Creates backup before deployment
    - Optional heartbeat monitor for automatic rollback
    - Atomic deployment via nft -f
    """
    # Require explicit approval
    require_approval = os.environ.get("REQUIRE_APPROVAL", "1") == "1"
    if require_approval and not approved:
        return DeploymentResult(
            success=False,
            status=DeploymentStatus.PENDING,
            rule_id=rule_id,
            error="Deployment requires explicit approval (approved=True)",
        )

    # Validate content doesn't have shell injection
    if contains_dangerous_chars(rule_content):
        return DeploymentResult(
            success=False,
            status=DeploymentStatus.FAILED,
            rule_id=rule_id,
            error="Rule content contains potentially dangerous characters",
        )

    # Create backup
    backup_path = _create_backup(rule_id)
    if backup_path is None:
        return DeploymentResult(
            success=False,
            status=DeploymentStatus.FAILED,
            rule_id=rule_id,
            error="Failed to create backup - aborting deployment",
        )

    # Write rule to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".nft", delete=False
    ) as tmp:
        tmp.write(rule_content)
        tmp_path = Path(tmp.name)

    try:
        # Deploy atomically
        result = subprocess.run(
            ["nft", "-f", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            # Deployment failed - restore backup
            _restore_backup(backup_path)
            return DeploymentResult(
                success=False,
                status=DeploymentStatus.FAILED,
                rule_id=rule_id,
                backup_path=str(backup_path),
                error=result.stderr or "nft command failed",
            )

        # Start heartbeat monitor if enabled
        heartbeat_active = False
        if enable_heartbeat:
            timeout = heartbeat_timeout or ROLLBACK_TIMEOUT
            stop_event = threading.Event()
            _active_heartbeats[rule_id] = stop_event

            thread = threading.Thread(
                target=_heartbeat_monitor,
                args=(rule_id, backup_path, timeout, stop_event, heartbeat_fn),
                daemon=True,
            )
            thread.start()
            _heartbeat_threads[rule_id] = thread
            heartbeat_active = True

        return DeploymentResult(
            success=True,
            status=DeploymentStatus.DEPLOYED,
            rule_id=rule_id,
            backup_path=str(backup_path),
            heartbeat_active=heartbeat_active,
        )

    except subprocess.TimeoutExpired:
        _restore_backup(backup_path)
        return DeploymentResult(
            success=False,
            status=DeploymentStatus.FAILED,
            rule_id=rule_id,
            backup_path=str(backup_path),
            error="Deployment timed out",
        )
    except FileNotFoundError:
        return DeploymentResult(
            success=False,
            status=DeploymentStatus.FAILED,
            rule_id=rule_id,
            error="nft command not found",
        )
    except PermissionError:
        return DeploymentResult(
            success=False,
            status=DeploymentStatus.FAILED,
            rule_id=rule_id,
            error="Permission denied - need root for nft",
        )
    finally:
        tmp_path.unlink(missing_ok=True)
