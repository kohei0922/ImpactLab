from __future__ import annotations

from typing import Iterable


class AnalysisError(Exception):
    def __init__(
        self,
        message: str,
        details: Iterable[str] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = list(details or [])
        self.status_code = status_code

