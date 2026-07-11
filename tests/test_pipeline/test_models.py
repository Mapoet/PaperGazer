"""Pipeline state contract tests."""

from papergazer.pipeline.models import (
    TERMINAL_JOB_STATUSES,
    TERMINAL_RUN_STATUSES,
    JobStatus,
    RunStatus,
)


def test_only_finished_run_states_are_terminal() -> None:
    assert RunStatus.RUNNING not in TERMINAL_RUN_STATUSES
    assert RunStatus.PARTIAL in TERMINAL_RUN_STATUSES


def test_retryable_job_is_not_terminal() -> None:
    assert JobStatus.RETRYABLE not in TERMINAL_JOB_STATUSES
    assert TERMINAL_JOB_STATUSES == {JobStatus.SUCCEEDED, JobStatus.DEAD}
