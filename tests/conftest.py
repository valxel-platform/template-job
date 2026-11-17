import os

import pytest

DB = os.environ.get("JOB_TEST_DATABASE_URL")


@pytest.fixture
def db():
    if not DB:
        pytest.skip("set JOB_TEST_DATABASE_URL to run the Postgres tests")
    import psycopg

    with psycopg.connect(DB, autocommit=True) as conn:
        conn.execute("drop table if exists job_runs")
    return DB
