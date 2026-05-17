"""
Fractal Job Definitions
========================
Exported job definitions for Core scheduler registration.
The module does NOT run these jobs internally.
Core scheduler calls them based on the schedule.
"""

from dataclasses import dataclass
from typing import Callable, List


@dataclass
class ScheduledJobDef:
    """A job that Core scheduler can register and run."""
    name: str
    schedule: str  # cron expression
    handler: Callable
    run_on_startup: bool = False
    description: str = ""


def get_fractal_jobs() -> List[ScheduledJobDef]:
    """Return all scheduled jobs for the Fractal module."""
    from forecast.scheduler import run_daily, run_eval_job, run_gen_job

    return [
        ScheduledJobDef(
            name="fractal:daily",
            schedule="10 0 * * *",  # 00:10 UTC daily
            handler=run_daily,
            run_on_startup=True,
            description="Full daily cycle: EVAL → GEN → DRIFT → SHADOW → GRADUATION",
        ),
    ]
