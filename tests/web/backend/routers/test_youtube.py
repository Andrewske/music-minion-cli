"""Tests for YouTube API router."""

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Add web directory to path for imports
web_path = Path(__file__).parent.parent.parent.parent.parent / "web"
sys.path.insert(0, str(web_path))

from backend.routers.youtube import (
    JOB_TTL_SECONDS,
    JobStatus,
    _cleanup_old_jobs,
    _jobs,
    _jobs_lock,
    create_job,
    get_job,
    update_job,
)


class TestJobManagement:
    """Tests for job creation, update, and cleanup."""

    def setup_method(self) -> None:
        """Clear job storage before each test."""
        with _jobs_lock:
            _jobs.clear()

    def test_create_job_returns_uuid(self) -> None:
        """create_job returns a valid UUID string."""
        job_id = create_job()

        assert isinstance(job_id, str)
        assert len(job_id) == 36  # UUID format: 8-4-4-4-12

    def test_create_job_initializes_status(self) -> None:
        """create_job initializes job with PENDING status."""
        job_id = create_job()
        job = get_job(job_id)

        assert job is not None
        assert job["status"] == JobStatus.PENDING
        assert job["progress"] is None
        assert job["result"] is None
        assert job["error"] is None

    def test_create_job_excludes_created_at_from_get(self) -> None:
        """get_job excludes internal created_at field."""
        job_id = create_job()
        job = get_job(job_id)

        assert job is not None
        assert "created_at" not in job

    def test_update_job_changes_status(self) -> None:
        """update_job can change job status."""
        job_id = create_job()
        update_job(job_id, status=JobStatus.RUNNING)

        job = get_job(job_id)
        assert job["status"] == JobStatus.RUNNING

    def test_update_job_sets_result(self) -> None:
        """update_job can set result data."""
        job_id = create_job()
        result_data = {"imported_count": 5, "tracks": []}
        update_job(job_id, status=JobStatus.COMPLETED, result=result_data)

        job = get_job(job_id)
        assert job["status"] == JobStatus.COMPLETED
        assert job["result"] == result_data

    def test_update_job_sets_error(self) -> None:
        """update_job can set error message."""
        job_id = create_job()
        update_job(job_id, status=JobStatus.FAILED, error="Download failed")

        job = get_job(job_id)
        assert job["status"] == JobStatus.FAILED
        assert job["error"] == "Download failed"

    def test_update_nonexistent_job_no_error(self) -> None:
        """update_job silently ignores nonexistent job IDs."""
        # Should not raise
        update_job("nonexistent-id", status=JobStatus.RUNNING)

    def test_get_nonexistent_job_returns_none(self) -> None:
        """get_job returns None for nonexistent job ID."""
        job = get_job("nonexistent-id")
        assert job is None

    def test_cleanup_removes_old_jobs(self) -> None:
        """_cleanup_old_jobs removes jobs older than TTL."""
        # Create a job with old timestamp
        with _jobs_lock:
            _jobs["old-job"] = {
                "status": JobStatus.COMPLETED,
                "progress": None,
                "result": None,
                "error": None,
                "created_at": time.time() - JOB_TTL_SECONDS - 100,  # Expired
            }
            _jobs["new-job"] = {
                "status": JobStatus.RUNNING,
                "progress": None,
                "result": None,
                "error": None,
                "created_at": time.time(),  # Fresh
            }

        # Trigger cleanup via create_job
        create_job()

        # Old job should be removed, new job should remain
        assert get_job("old-job") is None
        assert get_job("new-job") is not None

    def test_multiple_jobs_independent(self) -> None:
        """Multiple jobs can exist independently."""
        job1 = create_job()
        job2 = create_job()

        update_job(job1, status=JobStatus.COMPLETED)
        update_job(job2, status=JobStatus.FAILED, error="Test error")

        assert get_job(job1)["status"] == JobStatus.COMPLETED
        assert get_job(job2)["status"] == JobStatus.FAILED
        assert get_job(job2)["error"] == "Test error"
