"""
Generate Synthetic Feedback Dataset with Exact Target Ratios
============================================================
Creates synthetic_feedback_dataset.csv with 900 rows:
  - code_quality: 300 records (80% helpful)
  - devops: 300 records (40% helpful)
  - process: 70% helpful (300 records)
Spread across 3 projects chronologically with rich metric evidence fields.
"""

import csv
import os
import random
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUTPUT_CSV = os.path.join(DATA_DIR, "synthetic_feedback_dataset.csv")

# Category configurations & exact target ratios
CATEGORY_PLAN = {
    "code_quality": {
        "count": 300,
        "helpful_ratio": 0.80,
        "metrics": [
            {"id": 1, "name": "Code Coverage", "target": 80.0, "unit": "%", "lower_better": False},
            {"id": 2, "name": "Cyclomatic Complexity", "target": 10.0, "unit": "", "lower_better": True},
            {"id": 3, "name": "Code Duplication", "target": 5.0, "unit": "%", "lower_better": True},
            {"id": 4, "name": "Technical Debt Ratio", "target": 5.0, "unit": "%", "lower_better": True},
            {"id": 5, "name": "Maintainability Index", "target": 85.0, "unit": "pts", "lower_better": False},
        ],
    },
    "devops": {
        "count": 300,
        "helpful_ratio": 0.40,
        "metrics": [
            {"id": 6, "name": "Deployment Frequency", "target": 3.0, "unit": "/wk", "lower_better": False},
            {"id": 7, "name": "MTTR", "target": 4.0, "unit": "hrs", "lower_better": True},
            {"id": 8, "name": "Change Failure Rate", "target": 10.0, "unit": "%", "lower_better": True},
            {"id": 9, "name": "Lead Time for Changes", "target": 7.0, "unit": "days", "lower_better": True},
            {"id": 10, "name": "Build Success Rate", "target": 95.0, "unit": "%", "lower_better": False},
        ],
    },
    "process": {
        "count": 300,
        "helpful_ratio": 0.70,
        "metrics": [
            {"id": 11, "name": "Sprint Velocity", "target": 40.0, "unit": "pts", "lower_better": False},
            {"id": 12, "name": "Sprint Burndown Rate", "target": 90.0, "unit": "%", "lower_better": False},
            {"id": 13, "name": "Defect Density", "target": 2.0, "unit": "/kloc", "lower_better": True},
            {"id": 14, "name": "Backlog Growth Rate", "target": 5.0, "unit": "%", "lower_better": True},
            {"id": 15, "name": "Story Cycle Time", "target": 3.0, "unit": "days", "lower_better": True},
        ],
    },
}

ROLES = ["Developer", "Team Lead", "QA Engineer", "DevOps", "SRE", "Scrum Master", "Product Owner"]
PROJECT_IDS = [1, 2, 3]

def generate_records():
    records = []
    random.seed(42)  # Reproducible generation

    for cat, plan in CATEGORY_PLAN.items():
        total_count = plan["count"]
        helpful_count = int(round(total_count * plan["helpful_ratio"]))
        unhelpful_count = total_count - helpful_count

        helpfulness_list = [True] * helpful_count + [False] * unhelpful_count
        random.shuffle(helpfulness_list)

        for i, was_helpful in enumerate(helpfulness_list):
            metric_def = random.choice(plan["metrics"])
            target = metric_def["target"]

            # Generate realistic actual value with deviation
            if metric_def["lower_better"]:
                actual = round(target + random.uniform(0.5, target * 1.5), 2)
                deviation = round(actual - target, 2)
            else:
                actual = round(max(0.0, target - random.uniform(1.0, target * 0.4)), 2)
                deviation = round(target - actual, 2)

            severity = round(min(1.0, max(0.1, deviation / (target or 1.0))), 2)
            priority_score = round(30.0 + severity * 45.0 + random.uniform(-5.0, 10.0), 1)

            records.append({
                "category": cat,
                "metric_id": metric_def["id"],
                "metric": metric_def["name"],
                "actual": actual,
                "target": target,
                "deviation": deviation,
                "severity": severity,
                "priority_score": priority_score,
                "was_helpful": was_helpful,
            })

    # Shuffle across categories for realistic continuous arrival
    random.shuffle(records)

    # Assign sequential timestamps, IDs, recommendations, roles, projects
    start_time = datetime(2026, 5, 1, 9, 0, 0)
    final_rows = []

    for idx, rec in enumerate(records, start=1):
        ts = start_time + timedelta(minutes=idx * 15 + random.randint(-3, 3))
        proj_id = PROJECT_IDS[(idx - 1) % len(PROJECT_IDS)]
        rec_id = 100 + (idx % 450)  # Maps to valid rec ID range

        final_rows.append({
            "feedback_id": idx,
            "project_id": proj_id,
            "recommendation_id": rec_id,
            "metric_id": rec["metric_id"],
            "metric": rec["metric"],
            "category": rec["category"],
            "actual": rec["actual"],
            "target": rec["target"],
            "deviation": rec["deviation"],
            "severity": rec["severity"],
            "priority_score": rec["priority_score"],
            "was_helpful": rec["was_helpful"],
            "user_role": random.choice(ROLES),
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
        })

    # Sort chronologically by timestamp
    final_rows.sort(key=lambda r: r["timestamp"])
    for idx, r in enumerate(final_rows, start=1):
        r["feedback_id"] = idx

    return final_rows

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    records = generate_records()

    fieldnames = [
        "feedback_id", "project_id", "recommendation_id", "metric_id", "metric",
        "category", "actual", "target", "deviation", "severity", "priority_score",
        "was_helpful", "user_role", "timestamp"
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Generated {len(records)} feedback records -> {OUTPUT_CSV}")

    # Print distribution stats
    cat_stats = {}
    for r in records:
        cat = r["category"]
        cat_stats.setdefault(cat, {"total": 0, "helpful": 0})
        cat_stats[cat]["total"] += 1
        if r["was_helpful"]:
            cat_stats[cat]["helpful"] += 1

    print("\nTarget Ratio Verification:")
    for cat, st in cat_stats.items():
        rate = st["helpful"] / st["total"]
        print(f"  {cat:15s}: {st['helpful']}/{st['total']} helpful ({rate:.1%})")

if __name__ == "__main__":
    main()
