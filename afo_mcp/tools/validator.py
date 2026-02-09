"""Syntax validation tool - validates nftables commands before execution."""

import subprocess
import tempfile
from pathlib import Path

from afo_mcp.models import ValidationResult


def validate_syntax(command: str, platform: str = "nftables") -> ValidationResult:
    """Validate firewall command syntax without applying it.

    Args:
        command: The nftables command or ruleset to validate
        platform: Target platform (currently only 'nftables' supported)

    Returns:
        ValidationResult with validity status and any errors/warnings.

    This tool performs a dry-run validation using nft --check, catching
    syntax errors before rules are applied to the system.
    """
    if platform != "nftables":
        return ValidationResult(
            valid=False,
            command=command,
            errors=[f"Unsupported platform: {platform}. Only 'nftables' is supported."],
        )

    # Sanitize command - prevent shell injection
    if any(char in command for char in [";", "|", "&", "$", "`", "\\"]):
        return ValidationResult(
            valid=False,
            command=command,
            errors=["Command contains potentially dangerous characters"],
        )

    errors: list[str] = []
    warnings: list[str] = []
    line_numbers: list[int] = []

    # Write command to temp file for validation
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".nft", delete=False
    ) as tmp:
        tmp.write(command)
        tmp_path = Path(tmp.name)

    try:
        # Use nft --check to validate without applying
        result = subprocess.run(
            ["nft", "--check", "-f", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            # Parse error output
            for line in result.stderr.strip().split("\n"):
                if not line:
                    continue

                # Try to extract line number from error
                # Format: "/tmp/xxx.nft:3:1-5: Error: ..."
                import re

                line_match = re.search(r":(\d+):\d+-\d+:", line)
                if line_match:
                    line_numbers.append(int(line_match.group(1)))

                # Categorize as warning or error
                if "warning" in line.lower():
                    warnings.append(line)
                else:
                    errors.append(line)

            # If we got stderr but no parsed errors, add raw output
            if result.stderr and not errors:
                errors.append(result.stderr.strip())

        # Also check stdout for any warnings
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line and "warning" in line.lower():
                    warnings.append(line)

        return ValidationResult(
            valid=result.returncode == 0,
            command=command,
            errors=errors,
            warnings=warnings,
            line_numbers=line_numbers,
        )

    except subprocess.TimeoutExpired:
        return ValidationResult(
            valid=False,
            command=command,
            errors=["Validation timed out after 10 seconds"],
        )
    except FileNotFoundError:
        return ValidationResult(
            valid=False,
            command=command,
            errors=["nft command not found - is nftables installed?"],
        )
    except PermissionError:
        return ValidationResult(
            valid=False,
            command=command,
            errors=["Permission denied - nft --check may require elevated privileges"],
        )
    finally:
        # Clean up temp file
        tmp_path.unlink(missing_ok=True)


def validate_rule_structure(command: str) -> ValidationResult:
    """Perform basic structural validation without calling nft.

    This is a lightweight check that can run without root privileges.
    It validates the command structure follows nftables syntax patterns.
    """
    warnings: list[str] = []
    errors: list[str] = []

    command = command.strip()

    # Check for basic nftables command structure
    valid_prefixes = [
        "add table",
        "add chain",
        "add rule",
        "add set",
        "add map",
        "delete table",
        "delete chain",
        "delete rule",
        "flush table",
        "flush chain",
        "flush ruleset",
        "list table",
        "list chain",
        "list ruleset",
        "table",  # For script format
        "chain",  # For script format
    ]

    # For multi-line scripts, check each statement
    lines = [l.strip() for l in command.split("\n") if l.strip() and not l.strip().startswith("#")]

    if not lines:
        return ValidationResult(
            valid=False,
            command=command,
            errors=["Empty command"],
        )

    # Simple structural checks
    for i, line in enumerate(lines, 1):
        # Skip closing braces
        if line in ["}", "};"]:
            continue

        # Check opening braces match
        if "{" in line and "}" not in line:
            # This is opening a block, that's fine
            pass

        # Check for unbalanced quotes
        if line.count('"') % 2 != 0:
            errors.append(f"Line {i}: Unbalanced quotes")

        # Warn about common mistakes
        if "iptables" in line.lower():
            warnings.append(f"Line {i}: iptables syntax detected - this is nftables")

    return ValidationResult(
        valid=len(errors) == 0,
        command=command,
        errors=errors,
        warnings=warnings,
        line_numbers=[],
    )
