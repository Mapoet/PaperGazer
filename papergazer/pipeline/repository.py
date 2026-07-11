"""Transactional persistence for recoverable pipeline runs and jobs."""

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from papergazer.pipeline.models import JobStatus, RunStatus
from papergazer.store.db import PipelineJob, PipelineRun


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class PipelineRepository:
    """State transitions for one database session."""

    def __init__(self, session: Session):
        self.session = session

    def create_run(
        self,
        stages: list[str],
        *,
        scope: dict[str, Any] | None = None,
        config_summary: dict[str, Any] | None = None,
        code_revision: str | None = None,
    ) -> PipelineRun:
        config_json = _canonical_json(config_summary or {})
        run = PipelineRun(
            run_uid=str(uuid.uuid4()),
            status=RunStatus.PENDING.value,
            requested_stages_json=_canonical_json(stages),
            scope_json=_canonical_json(scope or {}),
            config_digest=hashlib.sha256(config_json.encode()).hexdigest(),
            config_summary_json=config_json,
            code_revision=code_revision,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def enqueue_jobs(
        self,
        run: PipelineRun,
        stage: str,
        paper_ids: list[int],
        *,
        max_attempts: int = 3,
    ) -> list[PipelineJob]:
        jobs = [
            PipelineJob(
                run_id=run.id,
                paper_id=paper_id,
                stage=stage,
                status=JobStatus.PENDING.value,
                max_attempts=max_attempts,
            )
            for paper_id in dict.fromkeys(paper_ids)
        ]
        self.session.add_all(jobs)
        self.session.flush()
        return jobs

    def start_run(self, run: PipelineRun) -> None:
        if run.status != RunStatus.PENDING.value:
            raise ValueError(f"cannot start run in state {run.status}")
        run.status = RunStatus.RUNNING.value
        run.started_at = datetime.now(UTC)

    def start_job(self, job: PipelineJob) -> None:
        if job.status not in {JobStatus.PENDING.value, JobStatus.RETRYABLE.value}:
            raise ValueError(f"cannot start job in state {job.status}")
        if job.attempt_count >= job.max_attempts:
            raise ValueError("job exhausted its retry budget")
        job.status = JobStatus.RUNNING.value
        job.attempt_count += 1
        job.started_at = datetime.now(UTC)
        job.finished_at = None
        job.next_retry_at = None
        job.error_category = None
        job.error_message = None

    def succeed_job(self, job: PipelineJob, result: dict[str, Any] | None = None) -> None:
        if job.status != JobStatus.RUNNING.value:
            raise ValueError(f"cannot complete job in state {job.status}")
        job.status = JobStatus.SUCCEEDED.value
        job.finished_at = datetime.now(UTC)
        job.result_json = _canonical_json(result or {})

    def fail_job(
        self,
        job: PipelineJob,
        *,
        category: str,
        message: str,
        retry_delay: timedelta = timedelta(minutes=5),
    ) -> None:
        if job.status != JobStatus.RUNNING.value:
            raise ValueError(f"cannot fail job in state {job.status}")
        job.finished_at = datetime.now(UTC)
        job.error_category = category
        job.error_message = message
        if job.attempt_count >= job.max_attempts:
            job.status = JobStatus.DEAD.value
            job.next_retry_at = None
        else:
            job.status = JobStatus.RETRYABLE.value
            job.next_retry_at = datetime.now(UTC) + retry_delay
        self.session.flush()

    def resumable_jobs(self, run: PipelineRun, *, now: datetime | None = None) -> list[PipelineJob]:
        current = now or datetime.now(UTC)
        return (
            self.session.query(PipelineJob)
            .filter(
                PipelineJob.run_id == run.id,
                (
                    (PipelineJob.status == JobStatus.PENDING.value)
                    | (
                        (PipelineJob.status == JobStatus.RETRYABLE.value)
                        & (PipelineJob.next_retry_at <= current)
                    )
                ),
            )
            .order_by(PipelineJob.id)
            .all()
        )

    def finish_run(self, run: PipelineRun) -> RunStatus:
        jobs = self.session.query(PipelineJob).filter(PipelineJob.run_id == run.id).all()
        statuses = {job.status for job in jobs}
        if not jobs or statuses == {JobStatus.SUCCEEDED.value}:
            final = RunStatus.SUCCEEDED
        elif statuses <= {JobStatus.SUCCEEDED.value, JobStatus.DEAD.value}:
            final = RunStatus.PARTIAL if JobStatus.SUCCEEDED.value in statuses else RunStatus.FAILED
        else:
            raise ValueError("cannot finish a run with non-terminal jobs")
        run.status = final.value
        run.finished_at = datetime.now(UTC)
        run.summary_json = _canonical_json(
            {status: sum(job.status == status for job in jobs) for status in sorted(statuses)}
        )
        return final
