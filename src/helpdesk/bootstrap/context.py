"""Trusted per-call context assembled by application code, never the model."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return an aware application timestamp."""


@dataclass
class DemoClock:
    instant: datetime

    def __post_init__(self):
        if self.instant.tzinfo is None:
            raise ValueError("Demo clock requires a timezone")

    def now(self) -> datetime:
        return self.instant

    def advance(self, seconds: float):
        if seconds < 0:
            raise ValueError("Clock cannot move backwards")
        self.instant += timedelta(seconds=seconds)


@dataclass(frozen=True)
class ToolContext:
    session_id: str
    employee_id: str
    case_id: str
    identity_verified: bool
    clock: Clock
