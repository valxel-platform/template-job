"""The job's work. Replace `run` with yours; keep its contract.

A run covers the period from `run.window_start` to `run.window_end`. After an outage the window
reaches back to the last successful run (job.yaml catch_up: window), so one run makes up for the
runs that didn't happen. Write the work so a run can be repeated over the same window without
harm: the platform may start a run twice, a run may be stopped part-way and run again, and people
can start one by hand. Use upserts keyed by the item, or record what you did and skip it next
time; never "send everything in the window" without remembering what was sent.

Call `run.check()` between items: it stops the run cleanly when the time limit is near or the
platform asks the pod to stop, and the next run picks up what's left. When `run.dry_run` is set,
read and count but change nothing.

Return how many items the run handled; it is logged and kept in the run's record.

What comes with every run, for the work to use:

- `with run.item():` around each unit of work. The feature flags read and product events
  recorded inside count for it, so a gradual release compares items with the feature on and off
  (cohorts.py); an item that raises counts as failed.
- `flags.enabled(key, user=<what the release splits on>)`: the feature's new behavior goes behind
  its flag, off by default (flags.py).
- `events.record("<event>")`: the events the feature's goal counts, where they happen (events.py).
- `run.audit("<record>.<action>", resource=(type, ids))`: an audit record for what the work did to
  records, with this job as the actor; ids only, never values (audit.py). For payments and PHI a
  record that can't be published raises: the item isn't done.
- Calls to other services through httpx or requests carry the run's trace (telemetry.py).

The example keeps the job's own run history to `JOB_KEEP_RUNS_DAYS` days: real work, and nothing
outside this component.
"""

from __future__ import annotations

from datetime import timedelta

from .context import Run


def run(run: Run) -> int:
    before = run.window_end - timedelta(days=run.settings.keep_runs_days)
    run.check()
    if run.dry_run:
        run.log.info("would remove run records finished before %s", before.isoformat())
        return 0
    with run.item():
        removed = run.runlog.purge(run.job, before)
    run.audit("job_runs.purge", resource=("job_runs", []), details={"removed": removed, "before": before.isoformat()})
    return removed
