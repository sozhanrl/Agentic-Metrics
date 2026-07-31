"""
Run Online Feedback-Adaptation Algorithm on dataset
===================================================
Simulates continuous developer feedback processing in chronological batches,
computing weight trajectories and writing audit log to weight_trajectory.csv.
"""

import csv
import os
import sys
from pathlib import Path
from dataclasses import asdict

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.online_feedback_adapter import OnlineFeedbackAdapter, BASE_WEIGHTS

CSV_INPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "feedback_seed.csv")
CSV_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "weight_trajectory.csv")

def main():
    if not os.path.exists(CSV_INPUT):
        print(f"ERROR: Input dataset missing at {CSV_INPUT}")
        sys.exit(1)

    records = []
    with open(CSV_INPUT, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)

    print(f"Loaded {len(records)} feedback records from feedback_seed.csv.")

    adapter = OnlineFeedbackAdapter()
    final_weights, history = adapter.run_over_dataset(records, batch_size=50)

    print("\n=== Final learned weights ===")
    for cat, w in final_weights.items():
        base_w = BASE_WEIGHTS.get(cat, 1.0)
        direction = "^ BOOSTED" if w > base_w else ("v REDUCED" if w < base_w else "= UNCHANGED")
        print(f"  {cat:15s}: {base_w:.3f} -> {w:.4f}  ({direction})")

    # Prepare trajectory rows
    trajectory_rows = [asdict(e) for e in history]

    # Write CSV output
    fieldnames = ["batch_number", "category", "old_weight", "new_weight", "helpful_rate", "sample_size", "reason"]
    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trajectory_rows)

    print(f"\nWrote {len(trajectory_rows)} weight-update events to {CSV_OUTPUT}")

    # Print top events for inspection
    print("\n=== Weight Update Trajectory (Sample) ===")
    print(f"{'Batch':<7} {'Category':<15} {'Old':<8} {'New':<8} {'Rate':<8} Reason")
    print("-" * 75)
    for e in history[:18]:
        print(f"{e.batch_number:<7} {e.category:<15} {e.old_weight:<8.4f} {e.new_weight:<8.4f} {e.helpful_rate:<8.0%} {e.reason}")

if __name__ == "__main__":
    main()
