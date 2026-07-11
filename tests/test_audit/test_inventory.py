"""Full-inventory audit tests."""

from pathlib import Path

from papergazer.audit.inventory import run_inventory_audit, write_inventory_audit
from papergazer.models import PaperMetadata
from papergazer.store.db import get_session, init_db, upsert_paper


def test_inventory_audit_uses_explicit_denominators(tmp_path: Path) -> None:
    init_db(tmp_path / "audit.sqlite3")
    session = get_session()
    try:
        upsert_paper(
            session,
            PaperMetadata(
                source="arxiv",
                identifier="2501.00001",
                title="Complete",
                doi="10.1000/complete",
                abstract="An abstract",
            ),
        )
        upsert_paper(
            session,
            PaperMetadata(source="arxiv", identifier="2501.00002", title="Sparse"),
        )
        session.commit()
    finally:
        session.close()

    audit = run_inventory_audit(tmp_path / "papers")

    assert audit.total_papers == 2
    assert audit.source_counts == {"arxiv": 2}
    assert audit.metric("doi_coverage").numerator == 1
    assert audit.metric("doi_coverage").denominator == 2
    assert audit.metric("doi_coverage").ratio == 0.5


def test_inventory_report_writes_machine_and_human_readable_outputs(tmp_path: Path) -> None:
    init_db(tmp_path / "empty.sqlite3")
    audit = run_inventory_audit(tmp_path / "papers", persist=False)

    json_path, markdown_path = write_inventory_audit(audit, tmp_path / "report")

    assert json_path.exists()
    assert markdown_path.exists()
    assert "论文总量：0" in markdown_path.read_text(encoding="utf-8")
