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
- `run.call("<component>", "POST", "/v1/...", json=..., idempotency_key=<item id>)`: another
  component's API, as this job's own identity (services.py). Only components in JOB_SERVICES; never
  their databases; on a dry run only GET goes out. Calls carry the run's trace (telemetry.py).

The example keeps the job's own run history to `JOB_KEEP_RUNS_DAYS` days: real work, and nothing
outside this component.
"""

from __future__ import annotations

from datetime import timedelta

from . import flags
from .context import Run


def example_flag(product: str) -> str:
    """The example feature's flag. It shows the pattern every feature follows: the tool gives the
    feature a flag in the product's Flipt (on in dev and staging, off in production until it's
    released) and the new behaviour reads it. Replace it with your first feature's own."""
    return f"{product or 'example'}.example.purge-oldest"


def run(run: Run) -> int:
    before = run.window_end - timedelta(days=run.settings.keep_runs_days)
    run.check()
    if run.dry_run:
        run.log.info("would remove run records finished before %s", before.isoformat())
        return 0
    with run.item():
        removed = run.runlog.purge(run.job, before)
        # The template's example feature, behind its flag (split by job): off, the run is today's.
        if flags.enabled(example_flag(run.settings.product), user=run.job):
            run.log.info("removed %d run records; the oldest kept starts after %s", removed, before.isoformat())
    run.audit("job_runs.purge", resource=("job_runs", []), details={"removed": removed, "before": before.isoformat()})
    return removed
