"""
Online Feedback-Adaptation Algorithm
=====================================
This module provides an online, rule-based, bounded adaptation algorithm
for software quality metric category prioritization via developer feedback.

Algorithm Details:
------------------
Given a batch of feedback records grouped by category:
  1. For each category with >= MIN_SAMPLES records in the batch:
       helpful_rate = (# was_helpful=True) / (# records)
  2. Raw adjustment:
       raw_adjustment = (helpful_rate - 0.5) * 2 * LEARNING_RATE
  3. Damped update against previous weight:
       new_weight = old_weight + raw_adjustment
  4. Clamped to [MIN_WEIGHT, MAX_WEIGHT].
  5. Audit log entry (WeightUpdateEvent) records full provenance.
"""

from dataclasses import dataclass, asdict
from typing import Any

LEARNING_RATE = 0.08        # max raw nudge per batch
MIN_SAMPLES = 3              # batch/category combo below this is skipped (too noisy)
MIN_WEIGHT = 0.5
MAX_WEIGHT = 2.0

BASE_WEIGHTS = {
    "code_quality": 1.0,
    "process": 0.8,
    "devops": 1.1,
}


@dataclass
class WeightUpdateEvent:
    batch_number: int
    category: str
    old_weight: float
    new_weight: float
    helpful_rate: float
    sample_size: int
    reason: str


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class OnlineFeedbackAdapter:
    """Stateful adapter: call update_from_batch() repeatedly as new feedback
    arrives. Weight state persists across calls (in memory or database audit ledger)."""

    def __init__(self, base_weights: dict[str, float] | None = None):
        self.weights = dict(base_weights or BASE_WEIGHTS)
        self.history: list[WeightUpdateEvent] = []
        self._batch_number = 0

    def update_from_batch(self, batch_records: list[dict[str, Any]]) -> list[WeightUpdateEvent]:
        """Process a list of feedback dicts (must contain 'category' and 'was_helpful').
        Returns list of WeightUpdateEvents generated in this call."""
        self._batch_number += 1
        events: list[WeightUpdateEvent] = []

        # Group feedback by category
        category_groups: dict[str, list[dict[str, Any]]] = {}
        for row in batch_records:
            cat = row.get("category")
            if cat:
                category_groups.setdefault(cat, []).append(row)

        for category, group in category_groups.items():
            n = len(group)
            if n < MIN_SAMPLES:
                continue

            helpful_count = sum(1 for r in group if str(r.get("was_helpful")).strip().lower() in ("true", "1"))
            helpful_rate = helpful_count / n
            old_weight = self.weights.get(category, 1.0)

            raw_adjustment = (helpful_rate - 0.5) * 2 * LEARNING_RATE
            new_weight = _clamp(round(old_weight + raw_adjustment, 4), MIN_WEIGHT, MAX_WEIGHT)

            if new_weight == old_weight:
                continue

            direction = "up" if new_weight > old_weight else "down"
            reason = (
                f"batch #{self._batch_number}: {n} feedback entries, "
                f"{helpful_rate:.0%} helpful -> nudged {direction} by {abs(new_weight - old_weight):.4f}"
            )

            event = WeightUpdateEvent(
                batch_number=self._batch_number,
                category=category,
                old_weight=old_weight,
                new_weight=new_weight,
                helpful_rate=round(float(helpful_rate), 3),
                sample_size=n,
                reason=reason,
            )
            self.weights[category] = new_weight
            self.history.append(event)
            events.append(event)

        return events

    def run_over_dataset(self, records: list[dict[str, Any]], batch_size: int = 50):
        """Feeds records through in chronological batches, simulating
        feedback arriving over time rather than all at once."""
        # Sort by timestamp if available
        records_sorted = sorted(records, key=lambda r: str(r.get("timestamp", "")))
        for start in range(0, len(records_sorted), batch_size):
            batch = records_sorted[start:start + batch_size]
            self.update_from_batch(batch)
        return self.weights, self.history
