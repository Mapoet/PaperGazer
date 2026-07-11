# PaperGazer Engineering Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current PaperGazer alpha prototype into an installable, testable, migration-safe, failure-isolated literature ingestion application with one truthful CLI and documentation contract.

**Architecture:** Preserve the existing `sources → core → store` structure while separating discovery providers, metadata enrichment, and full-text resolution at the service boundary. Establish packaging and tests first, then introduce versioned SQLite migrations and per-source run outcomes, and finally make Typer the canonical interface over reusable library functions.

**Tech Stack:** Python 3.11+, setuptools, Typer/Rich, Pydantic Settings, httpx, SQLAlchemy 2, Alembic, pytest/pytest-asyncio, Ruff, mypy.

## Global Constraints

- Work only on branch `dev-codex`; preserve unrelated user changes.
- Support Python 3.11 and 3.12 as declared in `pyproject.toml`.
- Network-dependent tests must be opt-in; the default suite must be deterministic and offline.
- SQLite databases created by existing PaperGazer versions must remain readable and upgradeable.
- Do not silently skip a failed source: persist and return its failure outcome while allowing other sources to continue.
- Keep secrets and local configuration out of Git.
- Every task must finish with focused tests before broader validation.

---

## File Structure and Responsibility Map

- `pyproject.toml`: canonical package metadata, package discovery, dependency groups, tool configuration.
- `papergazer/config.py`: validated YAML settings, including HTTP behavior.
- `papergazer/utils/http_client.py`: client construction only; no provider-specific policy.
- `papergazer/store/db.py`: ORM models and repository operations, not ad-hoc schema evolution.
- `papergazer/store/migrations.py`: legacy-database compatibility and Alembic hand-off.
- `alembic/`: ordered, reviewable schema migrations.
- `papergazer/core/ingest.py`: source orchestration and per-source outcomes.
- `papergazer/services/`: reusable query, export, analysis, and weekly-report application services.
- `papergazer/cli.py`: thin Typer command groups over services.
- `tests/fixtures/api/`: frozen provider responses for offline contract tests.
- `tests/packaging/`: wheel-content and clean-install smoke tests.
- `tests/migrations/`: legacy database upgrade tests.

### Task 1: Packaging and Dependency Contract

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Create: `tests/packaging/test_package_metadata.py`
- Create: `tests/test_optional_dependencies.py`

**Interfaces:**
- Consumes: existing `papergazer` package hierarchy.
- Produces: setuptools auto-discovery for `papergazer*`; extras named `tei`, `analytics`, `embeddings`, and `dev`.

- [ ] **Step 1: Write a failing package-discovery test**

```python
from setuptools import find_packages


def test_all_runtime_packages_are_discovered() -> None:
    packages = set(find_packages(include=["papergazer*"]))
    assert {"papergazer.analytics", "papergazer.utils"} <= packages
```

- [ ] **Step 2: Run the focused test and record the current packaging mismatch**

Run: `pytest tests/packaging/test_package_metadata.py -v`

Expected before implementation: packaging metadata does not use automatic discovery and a built wheel omits `analytics` and `utils`.

- [ ] **Step 3: Replace the manual package list and declare feature extras**

```toml
[tool.setuptools.packages.find]
include = ["papergazer*"]

[project.optional-dependencies]
tei = ["lxml>=4.9"]
analytics = ["networkx>=3.0"]
embeddings = ["sentence-transformers>=2.2"]
dev = [
  "build>=1.2",
  "pytest>=7.4.3",
  "pytest-asyncio>=0.21.1",
  "black>=23.11.0",
  "isort>=5.12.0",
  "mypy>=1.7.0",
  "ruff>=0.1.6",
]
```

- [ ] **Step 4: Build and inspect the wheel**

Run: `python -m build --wheel && python -m zipfile -l dist/papergazer-0.1.0-py3-none-any.whl`

Expected: wheel contains `papergazer/analytics/` and `papergazer/utils/`.

- [ ] **Step 5: Run package and import smoke tests**

Run: `pytest tests/packaging/test_package_metadata.py tests/test_optional_dependencies.py -v`

Expected: PASS; optional modules produce an actionable feature-extra error when their dependency is absent.

- [ ] **Step 6: Commit the independently installable package contract**

```bash
git add pyproject.toml requirements.txt tests/packaging tests/test_optional_dependencies.py
git commit -m "build: make package discovery and feature dependencies complete"
```

### Task 2: Deterministic Test and Static-Quality Baseline

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_integration.py`
- Modify: `tests/test_core/test_fetch.py`
- Modify: `tests/test_core/test_ingest.py`
- Modify: `tests/test_sources/*.py`
- Create: `tests/fixtures/api/*.json`
- Create: `.github/workflows/ci.yml`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: source parser APIs and temporary SQLite fixtures.
- Produces: offline test suite, `network` pytest marker, Python 3.11/3.12 CI matrix.

- [ ] **Step 1: Add frozen provider response fixtures and explicit response factories**

```python
@pytest.fixture
def api_fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "api"


def load_json_fixture(api_fixture_dir: Path, name: str) -> dict:
    return json.loads((api_fixture_dir / name).read_text(encoding="utf-8"))
```

- [ ] **Step 2: Replace weak empty-pipeline assertions with exact outcomes**

```python
assert results["arxiv"].status == "success"
assert results["arxiv"].processed == 0
assert results["crossref"].status == "success"
assert session.query(RunRecord).count() == 2
```

- [ ] **Step 3: Add parser tests for pagination, duplicate cursors, 429, timeout, and malformed responses**

Run: `pytest tests/test_sources -v`

Expected before fixes: failing tests identify the exact unsupported cases; after minimal source fixes: PASS.

- [ ] **Step 4: Auto-fix mechanical Ruff findings, then manually fix semantic F/E findings**

Run: `ruff check papergazer scripts tests --fix`

Run: `ruff check papergazer scripts tests --select E,F`

Expected: no E/F findings; no behavior-changing unsafe fixes.

- [ ] **Step 5: Add CI with offline gates**

```yaml
strategy:
  matrix:
    python-version: ["3.11", "3.12"]
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: ${{ matrix.python-version }}
  - run: pip install -e ".[dev,tei,analytics]"
  - run: ruff check papergazer scripts tests
  - run: pytest -m "not network" -q
```

- [ ] **Step 6: Run the full offline baseline**

Run: `ruff check papergazer scripts tests && pytest -m "not network" -q && mypy papergazer`

Expected: all commands exit 0.

- [ ] **Step 7: Commit the quality baseline**

```bash
git add tests .github pyproject.toml papergazer scripts
git commit -m "test: establish deterministic offline quality gates"
```

### Task 3: Configurable HTTP Policy

**Files:**
- Modify: `papergazer/config.py`
- Modify: `configs/config.yaml.example`
- Modify: `papergazer/utils/http_client.py`
- Modify: provider call sites under `papergazer/sources/` and `papergazer/utils/`
- Create: `tests/test_http_client.py`

**Interfaces:**
- Produces: `HttpConfig`; `async_client(config: HttpConfig, **overrides)`; `sync_client(config: HttpConfig, **overrides)`.

- [ ] **Step 1: Write failing policy tests**

```python
def test_http_config_respects_environment_proxy_by_default() -> None:
    config = HttpConfig()
    assert config.trust_env is True


def test_client_override_wins_over_config() -> None:
    config = HttpConfig(trust_env=True)
    client = sync_client(config, trust_env=False)
    assert client._trust_env is False
    client.close()
```

- [ ] **Step 2: Add validated HTTP settings**

```python
class HttpConfig(BaseSettings):
    trust_env: bool = True
    connect_timeout: float = Field(default=10.0, gt=0)
    read_timeout: float = Field(default=60.0, gt=0)
    write_timeout: float = Field(default=60.0, gt=0)
    pool_timeout: float = Field(default=10.0, gt=0)
```

- [ ] **Step 3: Make client factories accept policy explicitly**

```python
def sync_client(config: HttpConfig, **kwargs: Any) -> httpx.Client:
    kwargs.setdefault("trust_env", config.trust_env)
    kwargs.setdefault("timeout", _timeout(config))
    return httpx.Client(**kwargs)
```

- [ ] **Step 4: Update provider call sites without changing provider-specific timeout overrides**

Run: `pytest tests/test_http_client.py tests/test_sources -v`

Expected: PASS for both proxy-respecting and direct-connection configurations.

- [ ] **Step 5: Commit HTTP policy configuration**

```bash
git add papergazer/config.py papergazer/utils/http_client.py papergazer/sources papergazer/utils configs/config.yaml.example tests/test_http_client.py
git commit -m "refactor: make HTTP proxy and timeout policy configurable"
```

### Task 4: Versioned Schema Migration and Legacy Compatibility

**Files:**
- Modify: `pyproject.toml`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_baseline.py`
- Create: `papergazer/store/migrations.py`
- Modify: `papergazer/store/db.py`
- Create: `tests/migrations/test_legacy_upgrade.py`

**Interfaces:**
- Produces: `upgrade_database(db_path: str | Path) -> None`; schema revision recorded in `alembic_version`.

- [ ] **Step 1: Create a legacy SQLite fixture in a failing migration test**

```python
def test_legacy_database_upgrades_without_losing_papers(tmp_path: Path) -> None:
    db_path = create_legacy_database(tmp_path / "legacy.sqlite3")
    upgrade_database(db_path)
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("select title from items").fetchone() == ("legacy",)
        assert conn.execute("select version_num from alembic_version").fetchone()
```

- [ ] **Step 2: Add Alembic and a baseline migration matching ORM metadata**

Run: `alembic -c alembic.ini upgrade head`

Expected: a new empty database reaches revision `0001` with every ORM table and index.

- [ ] **Step 3: Implement a transactional legacy bridge**

```python
def upgrade_database(db_path: str | Path) -> None:
    engine = create_engine(_sqlite_url(db_path))
    with engine.begin() as connection:
        normalize_pre_alembic_schema(connection)
    run_alembic_upgrade(db_path, revision="head")
```

- [ ] **Step 4: Replace `_ensure_schema()` calls with `upgrade_database()`**

Run: `pytest tests/migrations tests/test_store -v`

Expected: fresh and legacy database tests pass, and existing rows survive migration.

- [ ] **Step 5: Commit versioned migrations**

```bash
git add pyproject.toml alembic.ini alembic papergazer/store tests/migrations
git commit -m "feat: introduce versioned and tested database migrations"
```

### Task 5: Failure-Isolated Ingestion and Composite Checkpoints

**Files:**
- Modify: `papergazer/models.py`
- Modify: `papergazer/store/db.py`
- Modify: `papergazer/core/ingest.py`
- Modify: `papergazer/sources/arxiv.py`
- Modify: `papergazer/sources/crossref.py`
- Create: `tests/test_core/test_ingest_outcomes.py`
- Create: `tests/test_core/test_checkpoint_boundaries.py`

**Interfaces:**
- Produces: `SourceRunOutcome(source: str, status: Literal["success", "failed"], processed: int, checkpoint: Checkpoint | None, error: str | None)`; `run_daily_check(config) -> dict[str, SourceRunOutcome]`.

- [ ] **Step 1: Write a failing source-isolation test**

```python
async def test_crossref_runs_when_arxiv_fails(settings) -> None:
    with patch("papergazer.core.ingest.ingest_arxiv", side_effect=ArxivAPIError("down")), patch(
        "papergazer.core.ingest.ingest_crossref", return_value=3
    ):
        outcomes = await run_daily_check(settings)
    assert outcomes["arxiv"].status == "failed"
    assert outcomes["crossref"].processed == 3
```

- [ ] **Step 2: Introduce typed outcomes and persist error summaries**

```python
class SourceRunOutcome(BaseModel):
    source: str
    status: Literal["success", "failed"]
    processed: int = 0
    checkpoint: Checkpoint | None = None
    error: str | None = None
```

- [ ] **Step 3: Orchestrate each source independently**

```python
for source, operation in operations.items():
    try:
        processed = await operation(config)
        outcomes[source] = SourceRunOutcome(source=source, status="success", processed=processed)
    except Exception as exc:
        outcomes[source] = SourceRunOutcome(source=source, status="failed", error=str(exc))
```

- [ ] **Step 4: Add composite checkpoint boundary tests**

Test cases: multiple records sharing an update timestamp across page boundaries; duplicate Crossref cursor; restart after a partial page; late record inside the overlap window.

Run: `pytest tests/test_core/test_ingest_outcomes.py tests/test_core/test_checkpoint_boundaries.py -v`

Expected: no record is lost; duplicates are absorbed by upsert; failed sources have persisted summaries.

- [ ] **Step 5: Commit resilient ingestion semantics**

```bash
git add papergazer/models.py papergazer/store/db.py papergazer/core/ingest.py papergazer/sources tests/test_core
git commit -m "feat: isolate source failures and harden incremental checkpoints"
```

### Task 6: Canonical CLI, Weekly Workflow, and Truthful Documentation

**Files:**
- Create: `papergazer/services/__init__.py`
- Create: `papergazer/services/query.py`
- Create: `papergazer/services/export.py`
- Create: `papergazer/services/weekly.py`
- Modify: `papergazer/cli.py`
- Modify: `scripts/query_papers.py`
- Modify: `scripts/export_abstracts.py`
- Modify: `scripts/daily_ingest.py`
- Modify: `weekly.sh`
- Modify: `README.md`
- Modify: `docs/PROJECT_STRUCTURE.md`
- Create: `tests/test_cli.py`
- Create: `tests/test_services/test_weekly.py`

**Interfaces:**
- Produces: Typer commands `ingest`, `fetch`, `query`, `analyze`, `export`, `weekly-report`; scripts become thin compatibility wrappers.

- [ ] **Step 1: Write failing CLI behavior tests**

```python
def test_query_command_is_implemented(runner: CliRunner) -> None:
    result = runner.invoke(app, ["query", "keyword", "GNSS", "--config", str(config_path)])
    assert result.exit_code == 0
    assert "待实现" not in result.stdout
```

- [ ] **Step 2: Extract script logic into service functions**

```python
def export_abstracts(request: ExportRequest, settings: Settings) -> ExportResult:
    ...


async def build_weekly_report(request: WeeklyReportRequest, settings: Settings) -> WeeklyReportResult:
    ...
```

- [ ] **Step 3: Replace placeholder CLI commands with thin adapters**

```python
@app.command("weekly-report")
def weekly_report(days: int = 7, config_path: Path = CONFIG_OPTION) -> None:
    result = asyncio.run(build_weekly_report(WeeklyReportRequest(days=days), load_config(config_path)))
    render_weekly_result(result)
```

- [ ] **Step 4: Make weekly output atomic and failure-aware**

Write each report to a temporary sibling path, replace the destination only after successful generation, and return a non-zero CLI exit code when ingestion fails.

Run: `pytest tests/test_cli.py tests/test_services/test_weekly.py -v`

Expected: failed ingestion leaves previous reports unchanged; successful workflow writes all requested reports.

- [ ] **Step 5: Correct documentation boundaries**

Document OpenAlex as an enrichment provider rather than a discovery source, list real package paths, document extras, migration behavior, CLI commands, and cron invocation through `papergazer weekly-report`.

- [ ] **Step 6: Run final repository validation**

Run: `git diff --check && bash -n weekly.sh scripts/*.sh && ruff check papergazer scripts tests && mypy papergazer && pytest -m "not network" -q && python -m build --wheel`

Expected: every command exits 0 and the wheel contains every `papergazer` subpackage.

- [ ] **Step 7: Commit the canonical product interface**

```bash
git add papergazer/services papergazer/cli.py scripts weekly.sh README.md docs tests
git commit -m "feat: unify CLI workflows and align documentation"
```

## Self-Review Result

- Spec coverage: packaging, dependencies, tests, HTTP policy, migrations, failure isolation, checkpoints, CLI, weekly automation, and documentation are each assigned to an independently testable task.
- Placeholder scan: implementation steps contain concrete interfaces, tests, commands, and expected outcomes; no deferred implementation markers are used.
- Type consistency: `HttpConfig`, `SourceRunOutcome`, `Checkpoint`, `ExportRequest`, and `WeeklyReportRequest` are introduced before downstream consumers and retain the same names across tasks.
- Deliberate deferral: PostgreSQL/vector-database migration and new scientific data sources are excluded until the engineering baseline is stable.
