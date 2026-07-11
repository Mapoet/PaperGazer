"""Inventory audit CLI tests."""

from pathlib import Path

from typer.testing import CliRunner

from papergazer.cli import app


def test_audit_inventory_command_writes_reports(config_file: Path, tmp_path: Path) -> None:
    output = tmp_path / "audit-report"
    result = CliRunner().invoke(
        app,
        ["audit", "inventory", "--config", str(config_file), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert (output / "data_quality.json").exists()
    assert (output / "data_quality.md").exists()
