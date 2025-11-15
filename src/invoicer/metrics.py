"""Performance metrics and profiling infrastructure - latency focused."""

import time
from typing import Optional


class MetricsCollector:
    """Collects and tracks performance metrics (latency/timing only)."""

    def __init__(self):
        self.model_load_time: Optional[float] = None
        self._start_times: dict[str, float] = {}

    def start_timer(self, name: str) -> None:
        """Start a named timer."""
        self._start_times[name] = time.perf_counter()

    def stop_timer(self, name: str) -> float:
        """Stop a named timer and return elapsed time."""
        if name not in self._start_times:
            return 0.0
        elapsed = time.perf_counter() - self._start_times[name]
        del self._start_times[name]
        return elapsed

    def create_email_metrics(
        self,
        parse_time: float,
        attachment_time: float,
        classification_time: float,
        extraction_time: float,
        num_attachments: int,
        total_attachment_bytes: int,
    ) -> dict:
        """Create metrics for a single email processing."""
        total_time = parse_time + attachment_time + classification_time + extraction_time

        return {
            "model_load_time_sec": self.model_load_time,
            "total_time_sec": total_time,
            "parse_time_sec": parse_time,
            "attachment_extraction_time_sec": attachment_time,
            "classification_time_sec": classification_time,
            "extraction_time_sec": extraction_time,
            "num_attachments": num_attachments,
            "total_attachment_bytes": total_attachment_bytes,
        }
