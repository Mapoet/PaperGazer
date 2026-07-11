"""Recoverable pipeline repository tests."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from papergazer.pipeline import JobStatus, PipelineRepository, RunStatus
from papergazer.store.db import get_session, init_db


def test_pipeline_run_can_finish_partially(tmp_path: Path) -> None:
    init_db(tmp_path / "pipeline.sqlite3")
    session = get_session()
    try:
        repository = PipelineRepository(session)
        run = repository.create_run(["metadata"], code_revision="abc123")
        jobs = repository.enqueue_jobs(run, "metadata", [1, 2], max_attempts=1)
        repository.start_run(run)
        repository.start_job(jobs[0])
        repository.succeed_job(jobs[0], {"updated": True})
        repository.start_job(jobs[1])
        repository.fail_job(jobs[1], category="invalid_data", message="bad record")

        assert repository.finish_run(run) == RunStatus.PARTIAL
        assert jobs[1].status == JobStatus.DEAD.value
        session.commit()
    finally:
        session.close()


def test_retryable_job_only_resumes_after_delay(tmp_path: Path) -> None:
    init_db(tmp_path / "pipeline.sqlite3")
    session = get_session()
    try:
        repository = PipelineRepository(session)
        run = repository.create_run(["fulltext"])
        job = repository.enqueue_jobs(run, "fulltext", [1])[0]
        repository.start_job(job)
        repository.fail_job(
            job,
            category="timeout",
            message="temporary",
            retry_delay=timedelta(minutes=5),
        )

        assert repository.resumable_jobs(run, now=datetime.now(UTC)) == []
        assert repository.resumable_jobs(run, now=datetime.now(UTC) + timedelta(minutes=6)) == [job]
    finally:
        session.close()


def test_invalid_state_transition_is_rejected(tmp_path: Path) -> None:
    init_db(tmp_path / "pipeline.sqlite3")
    session = get_session()
    try:
        repository = PipelineRepository(session)
        run = repository.create_run(["metadata"])
        job = repository.enqueue_jobs(run, "metadata", [1])[0]

        with pytest.raises(ValueError, match="cannot complete"):
            repository.succeed_job(job)
    finally:
        session.close()
