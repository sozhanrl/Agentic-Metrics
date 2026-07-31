"""
Generate Weight Trajectory CSV, SVG, and PNG Chart (Presentation Ready)
========================================================================
Runs OnlineFeedbackAdapter over synthetic_feedback_dataset.csv (900 records, 18 batches),
exports weight_trajectory.csv, weight_trajectory.svg, and weight_trajectory.png.
"""

import csv
import os
import sys
from pathlib import Path
from dataclasses import asdict

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.agents.online_feedback_adapter import OnlineFeedbackAdapter, BASE_WEIGHTS

DATA_DIR = os.path.join(backend_dir, "data")
INPUT_CSV = os.path.join(DATA_DIR, "synthetic_feedback_dataset.csv")
TRAJECTORY_CSV = os.path.join(DATA_DIR, "weight_trajectory.csv")
CHART_SVG = os.path.join(DATA_DIR, "weight_trajectory.svg")
CHART_PNG = os.path.join(DATA_DIR, "weight_trajectory.png")
ARTIFACT_DIR = r"C:\Users\pandi\.gemini\antigravity-ide\brain\8afcc61e-bfe7-4ff8-8548-0ac45e1c4328"

def generate_svg_chart(batches, weight_series, output_svg_path):
    """Generate clean, dark-themed presentation SVG chart with zero external dependencies."""
    width, height = 900, 500
    margin_left, margin_right, margin_top, margin_bottom = 80, 50, 70, 60
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom

    min_y, max_y = 0.4, 2.0
    max_x = max(batches) if batches else 18

    def x_pixel(b):
        return margin_left + (b / max_x) * plot_width

    def y_pixel(w):
        return margin_top + plot_height - ((w - min_y) / (max_y - min_y)) * plot_height

    colors = {
        "code_quality": "#10B981",  # Emerald Green
        "process": "#3B82F6",       # Blue
        "devops": "#EF4444",        # Red
    }

    labels = {
        "code_quality": "Code Quality (80% Helpful Target)",
        "process": "Process (70% Helpful Target)",
        "devops": "DevOps (40% Helpful Target)",
    }

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">',
        f'  <rect width="{width}" height="{height}" fill="#0F172A" rx="12"/>',
        f'  <text x="{width/2}" y="36" fill="#F8FAFC" font-family="Segoe UI, sans-serif" font-size="18" font-weight="bold" text-anchor="middle">Online Feedback-Adaptation: Category Weight Trajectory</text>',
        f'  <text x="{width/2}" y="56" fill="#94A3B8" font-family="Segoe UI, sans-serif" font-size="12" text-anchor="middle">18 Chronological Batches (900 Total Feedback Records, 50/Batch)</text>',
    ]

    # Gridlines & Y-axis labels
    for y_val in [0.5, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0]:
        yp = y_pixel(y_val)
        svg_lines.append(f'  <line x1="{margin_left}" y1="{yp}" x2="{width - margin_right}" y2="{yp}" stroke="#334155" stroke-dasharray="4,4" stroke-width="1"/>')
        svg_lines.append(f'  <text x="{margin_left - 10}" y="{yp + 4}" fill="#94A3B8" font-family="Segoe UI, sans-serif" font-size="11" text-anchor="end">{y_val:.1f}</text>')

    # X-axis ticks & labels
    for b in range(0, max_x + 1, 2):
        xp = x_pixel(b)
        svg_lines.append(f'  <line x1="{xp}" y1="{margin_top}" x2="{xp}" y2="{margin_top + plot_height}" stroke="#1E293B" stroke-dasharray="2,2"/>')
        svg_lines.append(f'  <text x="{xp}" y="{margin_top + plot_height + 20}" fill="#94A3B8" font-family="Segoe UI, sans-serif" font-size="11" text-anchor="middle">B{b}</text>')

    # X and Y axis titles
    svg_lines.append(f'  <text x="{width/2}" y="{height - 15}" fill="#CBD5E1" font-family="Segoe UI, sans-serif" font-size="12" text-anchor="middle">Chronological Batch Number (50 Records per Batch)</text>')

    # Plot lines & points
    for cat in ["code_quality", "process", "devops"]:
        pts = [f"{x_pixel(b):.1f},{y_pixel(w):.1f}" for b, w in zip(batches, weight_series[cat])]
        polyline_pts = " ".join(pts)
        svg_lines.append(f'  <polyline points="{polyline_pts}" fill="none" stroke="{colors[cat]}" stroke-width="3" stroke-linecap="round"/>')

        # Draw points
        for b, w in zip(batches, weight_series[cat]):
            cx, cy = x_pixel(b), y_pixel(w)
            svg_lines.append(f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" fill="{colors[cat]}" stroke="#0F172A" stroke-width="1.5"/>')

        # Annotate end value
        end_b = batches[-1]
        end_w = weight_series[cat][-1]
        ex, ey = x_pixel(end_b), y_pixel(end_w)
        svg_lines.append(f'  <text x="{ex + 8}" y="{ey + 4}" fill="{colors[cat]}" font-family="Segoe UI, sans-serif" font-size="12" font-weight="bold">{end_w:.2f}</text>')

    # Legend
    legend_x = margin_left + 20
    legend_y = margin_top + 15
    svg_lines.append(f'  <rect x="{legend_x}" y="{legend_y}" width="260" height="80" fill="#1E293B" rx="6" stroke="#475569" stroke-width="1"/>')

    for idx, cat in enumerate(["code_quality", "process", "devops"]):
        ly = legend_y + 20 + idx * 22
        svg_lines.append(f'  <line x1="{legend_x + 12}" y1="{ly - 4}" x2="{legend_x + 32}" y2="{ly - 4}" stroke="{colors[cat]}" stroke-width="3"/>')
        svg_lines.append(f'  <circle cx="{legend_x + 22}" cy="{ly - 4}" r="3.5" fill="{colors[cat]}"/>')
        svg_lines.append(f'  <text x="{legend_x + 40}" y="{ly}" fill="#E2E8F0" font-family="Segoe UI, sans-serif" font-size="11">{labels[cat]}</text>')

    svg_lines.append('</svg>')

    with open(output_svg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))

    print(f"Generated presentation SVG chart -> {output_svg_path}")

def main():
    if not os.path.exists(INPUT_CSV):
        print(f"ERROR: Dataset missing at {INPUT_CSV}")
        sys.exit(1)

    records = []
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    print(f"Loaded {len(records)} records from {INPUT_CSV}")

    adapter = OnlineFeedbackAdapter(base_weights=BASE_WEIGHTS)
    final_weights, history = adapter.run_over_dataset(records, batch_size=50)

    print("\n=== Final Learned Weights ===")
    for cat, w in final_weights.items():
        base_w = BASE_WEIGHTS[cat]
        delta = w - base_w
        direction = f"^ BOOSTED ({delta:+.4f})" if delta > 0 else f"v REDUCED ({delta:+.4f})"
        print(f"  {cat:15s}: {base_w:.2f} -> {w:.4f}  {direction}")

    trajectory_rows = [asdict(e) for e in history]
    fieldnames = ["batch_number", "category", "old_weight", "new_weight", "helpful_rate", "sample_size", "reason"]

    with open(TRAJECTORY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trajectory_rows)

    print(f"\nWrote {len(trajectory_rows)} weight update events to {TRAJECTORY_CSV}")

    # Build timeline series
    batches = [0]
    weight_series = {
        "code_quality": [BASE_WEIGHTS["code_quality"]],
        "process": [BASE_WEIGHTS["process"]],
        "devops": [BASE_WEIGHTS["devops"]],
    }

    current = dict(BASE_WEIGHTS)
    batch_map = {}
    for e in history:
        batch_map.setdefault(e.batch_number, {})[e.category] = e.new_weight

    max_batch = max(batch_map.keys()) if batch_map else 18
    for b in range(1, max_batch + 1):
        batches.append(b)
        updates = batch_map.get(b, {})
        for cat in current:
            if cat in updates:
                current[cat] = updates[cat]
            weight_series[cat].append(current[cat])

    # Always generate SVG chart
    generate_svg_chart(batches, weight_series, CHART_SVG)

    # Try Matplotlib PNG if installed
    try:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
        colors = {"code_quality": "#10B981", "process": "#3B82F6", "devops": "#EF4444"}
        labels = {
            "code_quality": "Code Quality (80% Helpful Target)",
            "process": "Process (70% Helpful Target)",
            "devops": "DevOps (40% Helpful Target)",
        }
        for cat in ["code_quality", "process", "devops"]:
            ax.plot(batches, weight_series[cat], marker="o", linewidth=2.5, color=colors[cat], label=labels[cat])

        ax.set_title("Online Feedback-Adaptation: Category Weight Trajectory", fontsize=14, fontweight="bold")
        ax.set_xlabel("Batch Number (50 Records / Batch)")
        ax.set_ylabel("Category Priority Weight")
        ax.set_ylim(0.4, 2.0)
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.legend(loc="upper left")
        plt.tight_layout()
        plt.savefig(CHART_PNG)
        plt.close()
        print(f"Generated PNG chart -> {CHART_PNG}")
    except Exception as e:
        print(f"Note: Matplotlib PNG chart creation skipped ({e}). SVG chart generated successfully.")

    # Copy files to artifact directory
    if os.path.exists(ARTIFACT_DIR):
        import shutil
        shutil.copy(TRAJECTORY_CSV, os.path.join(ARTIFACT_DIR, "weight_trajectory.csv"))
        shutil.copy(CHART_SVG, os.path.join(ARTIFACT_DIR, "weight_trajectory.svg"))
        if os.path.exists(CHART_PNG):
            shutil.copy(CHART_PNG, os.path.join(ARTIFACT_DIR, "weight_trajectory.png"))
        shutil.copy(INPUT_CSV, os.path.join(ARTIFACT_DIR, "synthetic_feedback_dataset.csv"))
        print("Copied all trajectory outputs to artifact directory.")

if __name__ == "__main__":
    main()
