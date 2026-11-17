"""Settings, from the environment (prefix JOB_)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JOB_")

    config_path: str = "job.yaml"
    # dev | staging | production: picks job.yaml's schedule for the environment. OpenChoreo sets it.
    environment: str = "dev"
    # The job's own Postgres: its run history and lock. Without one, runs keep no history, so missed
    # runs and overlapping runs can't be detected (fine for a local try, not for an environment).
    database_url: str = ""
    keep_runs_days: int = 90  # the example work: how long run records are kept
    log_level: str = "INFO"
