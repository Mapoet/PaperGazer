"""Database migration compatibility tests."""

import sqlite3
from pathlib import Path

from papergazer.store.db import PaperItem, get_session, init_db


def _create_legacy_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                identifier TEXT NOT NULL,
                title TEXT
            );
            CREATE TABLE runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                last_checkpoint DATETIME NOT NULL,
                items_count INTEGER DEFAULT 0,
                created_at DATETIME
            );
            INSERT INTO items(source, identifier, title)
            VALUES ('arxiv', '2501.00001', 'legacy paper');
            """
        )


def test_legacy_database_upgrades_without_losing_papers(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    _create_legacy_database(db_path)

    init_db(db_path)

    session = get_session()
    try:
        assert session.query(PaperItem).one().title == "legacy paper"
    finally:
        session.close()

    with sqlite3.connect(db_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        columns = {row[1] for row in connection.execute("PRAGMA table_info(items)")}

    assert revision == ("0001_schema_baseline",)
    assert {"tei_path", "openalex_json", "figures_json"} <= columns


def test_database_upgrade_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.sqlite3"

    init_db(db_path)
    init_db(db_path)

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM alembic_version").fetchone() == (1,)
