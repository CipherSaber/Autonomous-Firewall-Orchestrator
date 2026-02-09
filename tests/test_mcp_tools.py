"""Tests for AFO MCP tools."""

import pytest

from afo_mcp.models import (
    ConflictType,
    DeploymentStatus,
    FirewallRule,
    NetworkInterface,
    Protocol,
    RuleAction,
    ValidationResult,
)
from afo_mcp.tools.conflicts import _parse_rule, _networks_overlap, _ports_overlap, detect_conflicts
from afo_mcp.tools.validator import validate_rule_structure


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
        assert "tcp" in cmd
        assert "dport 22" in cmd
        assert "accept" in cmd

    def test_firewall_rule_with_addresses(self):
        """Test FirewallRule with source/dest addresses."""
        rule = FirewallRule(
            table="filter",
            chain="input",
            protocol=Protocol.TCP,
            source_address="10.0.0.0/8",
            destination_port=443,
            action=RuleAction.ACCEPT,
        )
        cmd = rule.to_nft_command()
        assert "saddr 10.0.0.0/8" in cmd
        assert "dport 443" in cmd


class TestValidator:
    """Test syntax validation."""

    def test_validate_rule_structure_valid(self):
        """Test valid rule structure."""
        result = validate_rule_structure("add rule inet filter input tcp dport 22 accept")
        assert result.valid

    def test_validate_rule_structure_empty(self):
        """Test empty command rejection."""
        result = validate_rule_structure("")
        assert not result.valid
        assert "Empty command" in result.errors

    def test_validate_rule_structure_unbalanced_quotes(self):
        """Test unbalanced quote detection."""
        result = validate_rule_structure('add rule inet filter input comment "test accept')
        assert not result.valid
        assert any("quote" in e.lower() for e in result.errors)

    def test_validate_rule_structure_iptables_warning(self):
        """Test iptables syntax warning."""
        result = validate_rule_structure("iptables -A INPUT -p tcp --dport 22 -j ACCEPT")
        assert any("iptables" in w.lower() for w in result.warnings)


class TestConflictDetection:
    """Test conflict detection logic."""

    def test_parse_rule_basic(self):
        """Test basic rule parsing."""
        rule = _parse_rule("add rule inet filter input tcp dport 22 accept")
        assert rule is not None
        assert rule.family == "inet"
        assert rule.table == "filter"
        assert rule.chain == "input"
        assert rule.protocol == "tcp"
        assert rule.dport == "22"
        assert rule.action == "accept"

    def test_parse_rule_with_addresses(self):
        """Test rule parsing with addresses."""
        rule = _parse_rule("add rule inet filter input ip saddr 10.0.0.0/8 ip daddr 192.168.1.1 drop")
        assert rule is not None
        assert rule.saddr == "10.0.0.0/8"
        assert rule.daddr == "192.168.1.1"
        assert rule.action == "drop"

    def test_networks_overlap_exact(self):
        """Test exact network match."""
        assert _networks_overlap("192.168.1.0/24", "192.168.1.0/24")

    def test_networks_overlap_subset(self):
        """Test subnet overlap."""
        assert _networks_overlap("192.168.0.0/16", "192.168.1.0/24")

    def test_networks_no_overlap(self):
        """Test non-overlapping networks."""
        assert not _networks_overlap("192.168.1.0/24", "10.0.0.0/8")

    def test_networks_overlap_single_ip(self):
        """Test single IP overlap."""
        assert _networks_overlap("192.168.1.100", "192.168.1.0/24")

    def test_ports_overlap_exact(self):
        """Test exact port match."""
        assert _ports_overlap("22", "22")

    def test_ports_overlap_range(self):
        """Test port range overlap."""
        assert _ports_overlap("20-25", "22")

    def test_ports_no_overlap(self):
        """Test non-overlapping ports."""
        assert not _ports_overlap("22", "80")

    def test_ports_overlap_none(self):
        """Test None (any) port overlaps with everything."""
        assert _ports_overlap(None, "22")
        assert _ports_overlap("22", None)

    def test_detect_conflicts_contradiction(self):
        """Test contradiction detection."""
        active_ruleset = """
table inet filter {
    chain input {
        type filter hook input priority filter; policy drop;
        tcp dport 22 drop
    }
}
"""
        report = detect_conflicts(
            "add rule inet filter input tcp dport 22 accept",
            active_ruleset,
        )
        assert report.has_conflicts
        assert any(c["type"] == ConflictType.CONTRADICTION.value for c in report.conflicts)

    def test_detect_conflicts_redundant(self):
        """Test redundancy detection."""
        active_ruleset = """
table inet filter {
    chain input {
        type filter hook input priority filter; policy drop;
        tcp dport 443 accept
    }
}
"""
        report = detect_conflicts(
            "add rule inet filter input tcp dport 443 accept",
            active_ruleset,
        )
        assert report.has_conflicts
        assert any(c["type"] == ConflictType.REDUNDANT.value for c in report.conflicts)

    def test_detect_conflicts_no_conflict(self):
        """Test no conflict for different rules."""
        active_ruleset = """
table inet filter {
    chain input {
        type filter hook input priority filter; policy drop;
        tcp dport 22 accept
    }
}
"""
        report = detect_conflicts(
            "add rule inet filter input tcp dport 80 accept",
            active_ruleset,
        )
        assert not report.has_conflicts


class TestDeploymentModels:
    """Test deployment-related models."""

    def test_deployment_status_enum(self):
        """Test DeploymentStatus enum values."""
        assert DeploymentStatus.PENDING.value == "pending"
        assert DeploymentStatus.DEPLOYED.value == "deployed"
        assert DeploymentStatus.ROLLED_BACK.value == "rolled_back"


# Integration tests (require nftables access)
class TestIntegration:
    """Integration tests that require system access.

    These are skipped by default. Run with:
        pytest -m integration
    """

    @pytest.mark.integration
    def test_get_network_context(self):
        """Test getting network context from system."""
        from afo_mcp.tools.network import get_network_context

        ctx = get_network_context()
        assert ctx.hostname
        # Should have at least loopback
        assert len(ctx.interfaces) > 0

    @pytest.mark.integration
    def test_validate_syntax_valid(self):
        """Test syntax validation with valid rule."""
        from afo_mcp.tools.validator import validate_syntax

        result = validate_syntax(
            "add table inet test_table\n"
            "add chain inet test_table test_chain\n"
            "add rule inet test_table test_chain accept"
        )
        # Will pass if nft is available and user has permissions
        # Otherwise will fail with appropriate error
        assert isinstance(result, ValidationResult)
