# template-job

The Valxel template for a **job**: work that runs on a schedule, does its part, and exits. Use it
for nightly reconciliations, reminders, expiring holds and consents, retention purges, report
builds and syncs. An event worker suits work that reacts to events as they arrive; a job suits
work due at a time.

The Valxel SDLC creates repos from this template (role `job`). OpenChoreo runs each one as a
Kubernetes CronJob (component type `cronjob/scheduled-task`), with the schedule from `job.yaml`.

## What a run does

`job-run` runs once and exits:

1. **Takes the run lock.** A Postgres advisory lock is held for the whole run. A second run that
   overlaps it (one started by hand, or a CronJob pod started again after a node failure) logs
   `valxel.job skipped` and exits 0.
2. **Works out its window.** A run covers the period from the last successful run to its own
   scheduled time. After an outage, that window reaches back over the runs that didn't happen, so
   one run makes up for them (`catch_up: window`). With `catch_up: latest`, a run covers only its
   own period.
3. **Notices missed runs.** When `missed_after` scheduled runs passed without a success, it logs
   `valxel.job.missed`; the platform's `job-missed` alert rule turns that into an incident in
   production.
4. **Runs your work** (`src/job/work.py`), stopping cleanly 30 s before the time limit, or when
   Kubernetes asks the pod to stop. A stopped run isn't a success, so the next run covers its
   window again.
5. **Records the outcome** in `job_runs` and logs it:

| Outcome | Log line | Exit |
| --- | --- | --- |
| succeeded | `valxel.job finished` (info) | 0 |
| stopped | `valxel.job stopped` (warning) | 0 |
| failed | `valxel.job failed` (error, with the exception) | 1: the platform's `job-failed` rule raises it |
| skipped | `valxel.job skipped` (info) | 0 |

Logs are JSON, one object a line, with `job`, `outcome`, `items`, `window_start` and
`window_end` fields.

## Writing the work

Replace `run` in `src/job/work.py`. Its contract:

- **Cover `run.window_start` to `run.window_end`.** Read what changed in that window, or what
  falls due in it.
- **Be safe to repeat.** The same window can run twice: a run stopped part-way, a run started by
  hand, a retry. Use upserts keyed by the item, or record what was done and skip it next time.
  Never send "everything in the window" without remembering what was sent.
- **Call `run.check()` between items**, so the run stops cleanly at its time limit.
- **When `run.dry_run` is set, change nothing**: read and count only.
- **Return how many items you handled.**
- **Reach other components through their APIs or events**, never their databases. The job's own
  Postgres holds its run history, and any state the work keeps.

The example work keeps the job's own run history to `JOB_KEEP_RUNS_DAYS` days.

## job.yaml

```yaml
name: template-job              # the component's name: keys the run lock and history
schedule: "15 3 * * *"          # minute hour day-of-month month day-of-week
timezone: America/Chicago
time_limit_minutes: 30
catch_up: window                # or latest
missed_after: 2
environments:                   # optional, outside production
  dev: { schedule: "15 * * * *" }
  staging: { schedule: "45 */6 * * *" }
```

**Schedules.** Use numbers (`*`, `5`, `1-5`, `*/15`, `1,15`); names like `MON` and macros like
`@daily` aren't accepted. When both day fields are set, a day matches either, as in cron. The time
zone is an IANA name, and a daily run keeps its local time across daylight saving.

**Deploys.** The Valxel SDLC reads `job.yaml` at the commit it deploys. It sets the CronJob's
schedule, time zone, time limit and `suspend` for each environment, so a schedule changes through a
pull request like any code. The architect's design names each job's schedule under `## Schedules`,
and G4 checks it.

## Settings

| Variable | Default | What it is |
| --- | --- | --- |
| `JOB_ENVIRONMENT` | `dev` | Picks `job.yaml`'s schedule for the environment (OpenChoreo sets it) |
| `JOB_DATABASE_URL` | none | The job's own Postgres: run history and the lock |
| `JOB_KEEP_RUNS_DAYS` | `90` | The example work's retention |
| `JOB_LOG_LEVEL` | `INFO` | |

Without `JOB_DATABASE_URL`, runs keep no history, so missed and overlapping runs can't be detected.
That's fine for a local try, but not for an environment.

## Running by hand

```bash
job-run --check                                   # check job.yaml (CI runs it for every environment)
job-run --dry-run                                 # count what would change, change nothing
job-run --from 2026-11-01T00:00:00Z --to 2026-11-02T00:00:00Z   # backfill one window, recorded as manual
```

In an environment, start a run now from OpenChoreo's "Run now" on the component. Its trigger
creates a Job from the CronJob, so it takes the same lock as the scheduled runs.

## Develop

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run pytest                                     # JOB_TEST_DATABASE_URL=postgresql://... for the Postgres tests
```

## Checks

`unit` (required) runs the linters, type checks, `job-run --check` for every environment, and the
tests with Postgres; coverage must stay at 90% or more. `image` builds the image, runs it once with
a read-only root file system and no capabilities (as the platform runs it), writes its SBOM and
fails on high or critical vulnerabilities with a fix. `dependency-review` checks new dependencies
on pull requests. CodeQL runs from GitHub's default setup.
