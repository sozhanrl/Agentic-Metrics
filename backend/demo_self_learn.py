"""
Self-learning demo workflow.
Runs against the live API to:
  1. Seed + generate recommendations
  2. Submit 10 skewed feedback entries per category
  3. Trigger self-learning
  4. Print before/after weight comparison
"""

import urllib.request
import urllib.error
import json
import sys

BASE = "http://127.0.0.1:8000"

def req(method, path, body=None, timeout=60):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        print(f"  HTTP {e.code} on {method} {path}: {text[:200]}")
        return None
    except Exception as e:
        print(f"  ERROR on {method} {path}: {e}")
        return None

def banner(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print('='*60)

# ── Step 1: find project ────────────────────────────────────────
banner("Step 1 — Finding project")
projects = req("GET", "/projects")
if not projects:
    print("No projects found. Creating one...")
    proj = req("POST", "/projects", {"name": "Demo Project", "source": "github", "external_id": "demo/repo"})
    project_id = proj["id"]
else:
    project_id = projects[0]["id"]
    print(f"  Using project: '{projects[0]['name']}' (id={project_id})")

# ── Step 2: seed demo data (skip if metrics already exist) ─────
banner("Step 2 — Seeding demo metrics (if needed)")
existing_metrics = req("GET", f"/metrics/latest/{project_id}")
if existing_metrics:
    print(f"  Project already has {len(existing_metrics)} metrics — skipping seed.")
else:
    print("  No metrics yet — seeding...")
    seed = req("POST", f"/dev/seed/{project_id}", timeout=90)
    print(f"  Seeded: {seed}")

# ── Step 3: generate recommendations ───────────────────────────
banner("Step 3 — Running multi-agent pipeline")
recs = req("POST", f"/recommendations/{project_id}/generate")
if not recs:
    print("  ERROR: no recommendations generated — check backend logs")
    sys.exit(1)

print(f"  Generated {len(recs)} recommendations:")
for r in recs:
    print(f"    id={r['id']:3d}  score={r['priority_score']:5.1f}  '{r['title'][:55]}'")
    print(f"           related_metrics={r['related_metrics']}")

# ── Step 4: get metric definitions for category mapping ─────────
banner("Step 4 — Building metric→category map")
defs = req("GET", "/metrics/definitions")
cat_map = {d["id"]: d["category"] for d in defs}  # metric_id → category
print("  Metric→category map:", json.dumps(cat_map, indent=4))

# ── Step 5: map each rec to its category ────────────────────────
banner("Step 5 — Mapping recs to categories")
cat_recs = {}  # category → list of rec ids
for r in recs:
    for mid in (r["related_metrics"] or []):
        cat = cat_map.get(mid)
        if cat:
            cat_recs.setdefault(cat, []).append(r["id"])
            break

for cat, ids in cat_recs.items():
    print(f"  {cat}: rec ids {ids}")

if not cat_recs:
    print("  WARNING: Could not map any recs to categories. Submitting feedback to all recs.")
    for r in recs:
        cat_recs.setdefault("unknown", []).append(r["id"])

# ── Step 6: submit skewed feedback ─────────────────────────────
banner("Step 6 — Submitting skewed feedback (10 per category)")
# Strategy: devops → 9/10 helpful (weight should RISE)
#           code_quality → 2/10 helpful (weight should FALL)
#           process → 5/10 helpful (neutral, small movement)

SKEW = {
    "devops":       [True]*9  + [False]*1,
    "code_quality": [True]*2  + [False]*8,
    "process":      [True]*5  + [False]*5,
}

submitted = 0
for cat, helpfulness_list in SKEW.items():
    ids = cat_recs.get(cat, [])
    if not ids:
        print(f"  {cat}: no recs to attach feedback to — skipping")
        continue
    for i, was_helpful in enumerate(helpfulness_list):
        rec_id = ids[i % len(ids)]   # cycle through available rec ids
        result = req("POST", "/feedback", {
            "recommendation_id": rec_id,
            "was_helpful": was_helpful,
            "user_comment": None,
            "outcome_metric_id": None,
            "outcome_delta": None,
        })
        submitted += 1
    helpful_count = sum(helpfulness_list)
    print(f"  {cat}: submitted {len(helpfulness_list)} feedback entries "
          f"({helpful_count} helpful / {len(helpfulness_list)-helpful_count} unhelpful) "
          f"→ {helpful_count/len(helpfulness_list):.0%} helpfulness rate")

print(f"\n  Total feedback submitted: {submitted}")

# ── Step 7: capture weights BEFORE ──────────────────────────────
banner("Step 7 — Weights BEFORE self-learning")
before = req("GET", f"/admin/weights/current/{project_id}")
weights_before = before.get("weights", {})
for cat, w in weights_before.items():
    print(f"  {cat}: {w:.4f}")

# ── Step 8: trigger self-learning ───────────────────────────────
banner("Step 8 — Triggering self-learning cycle")
learn = req("POST", f"/admin/self-learn/{project_id}")
if not learn:
    print("  ERROR triggering self-learning")
    sys.exit(1)

print(f"  Status: {learn.get('status')}")
print(f"  Categories updated: {learn.get('categories_updated')}")
print("\n  Update log:")
for entry in (learn.get("update_log") or []):
    arrow = "→"
    print(f"    [{entry['category']:15s}] {entry['old_weight']:.4f} {arrow} "
          f"{entry.get('new_weight', entry['old_weight']):.4f}  "
          f"({entry.get('reason', '')})")

# ── Step 9: weights AFTER ───────────────────────────────────────
banner("Step 9 — Weights AFTER self-learning")
after_resp = req("GET", f"/admin/weights/current/{project_id}")
weights_after = after_resp.get("weights", {})

print(f"\n  {'Category':<16} {'Before':>8} {'After':>8} {'Delta':>8}  Direction")
print(f"  {'-'*56}")
for cat in weights_before:
    wb = weights_before.get(cat, 0)
    wa = weights_after.get(cat, wb)
    delta = wa - wb
    direction = ("↑ BOOSTED" if delta > 0.001 else
                 "↓ REDUCED" if delta < -0.001 else
                 "→ unchanged")
    print(f"  {cat:<16} {wb:>8.4f} {wa:>8.4f} {delta:>+8.4f}  {direction}")

# ── Step 10: audit trail ─────────────────────────────────────────
banner("Step 10 — Audit trail (weight history ledger)")
history = req("GET", f"/admin/weight-history/{project_id}")
recent = (history or [])[:6]
for row in recent:
    print(f"  [{row.get('created_at','')[:19]}] {row['category']:16s} "
          f"{row['old_weight']:.4f} → {row['new_weight']:.4f}  "
          f"source={row['source']}  reason={row.get('reason','')[:60]}")

# ── Step 11: regenerate and compare ─────────────────────────────
banner("Step 11 — Regenerating recommendations with new weights")
new_recs = req("POST", f"/recommendations/{project_id}/generate")

print("\n  BEFORE scores:                       AFTER scores:")
print(f"  {'Title':<45} {'Before':>7}  {'After':>7}  {'Delta':>7}")
print(f"  {'-'*70}")

after_by_title = {r["title"]: r["priority_score"] for r in (new_recs or [])}
for r in recs:
    before_score = r["priority_score"]
    after_score  = after_by_title.get(r["title"], "—")
    if isinstance(after_score, float):
        delta = after_score - before_score
        delta_str = f"{delta:+.1f}"
    else:
        delta_str = "  n/a"
        after_score = "—"
    title = r["title"][:44]
    print(f"  {title:<45} {before_score:>7.1f}  {str(after_score):>7}  {delta_str:>7}")

banner("DONE — self-learning cycle complete")
print("  Refresh the frontend Weight Lens panel to see the updated tiers.")
