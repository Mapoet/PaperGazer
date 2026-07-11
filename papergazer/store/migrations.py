"""Versioned database upgrade entry points."""

from pathlib import Path

from alembic.config import Config

from alembic import command  # type: ignore[attr-defined]


def upgrade_database(db_path: str | Path, revision: str = "head") -> None:
    """Upgrade a PaperGazer SQLite database to a requested revision."""
    resolved = Path(db_path).resolve()
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{resolved}")
    command.upgrade(config, revision)
