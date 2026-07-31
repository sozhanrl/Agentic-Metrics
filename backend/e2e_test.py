"""
Full end-to-end test of the multi-agent pipeline.
Uses httpx (already in requirements.txt) with generous timeouts for Neon cold-start.
Run with: .\\venv\\Scripts\\python.exe e2e_test.py
"""
import json
import httpx

BASE = "http://localhost:8000"
PID  = 2   # "Metrics Engine Core"

client = httpx.Client(base_url=BASE, timeout=120.0)


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


# ── 1. Health ────────────────────────────────────────────────
section("1. Health check")
r = client.get("/health")
print(r.json())

# ── 2. Confirm project exists ────────────────────────────────
section("2. Projects")
projects = client.get("/projects").json()
for p in projects:
    print(f"  id={p['id']}  {p['name']}")

# ── 3. Seed demo data ────────────────────────────────────────
section(f"3. Seed demo data for project {PID}")
r = client.post(f"/dev/seed/{PID}")
print(r.json())

# ── 4. Set risk profile ──────────────────────────────────────
section("4. Set risk profile (adaptive weighting context)")
profile_payload = {
    "team_size": 4,
    "tech_debt_index": 0.78,
    "risk_tolerance": "low",
    "deployment_env": "cloud",
    "notes": "E2E test — high debt, low tolerance, small team"
}
r = client.put(f"/projects/{PID}/risk-profile", json=profile_payload)
print(json.dumps(r.json(), indent=2))

# ── 5. Run multi-agent pipeline ──────────────────────────────
section("5. Run multi-agent pipeline  POST /recommendations/{pid}/generate")
r = client.post(f"/recommendations/{PID}/generate")
recs = r.json()
print(f"\n  Generated {len(recs)} recommendations\n")

for i, rec in enumerate(recs):
    print(f"  ── Rec #{i+1}: {rec['title']}")
    print(f"     priority_score : {rec['priority_score']}")
    print(f"     trend_slope    : {rec.get('trend_slope', 'n/a')}")
    print(f"     conflict_note  : {'YES → '+rec['conflict_note'][:60] if rec.get('conflict_note') else 'none'}")
    aw = rec.get("adaptive_weights") or {}
    print(f"     adaptive_weights: {aw}")
    trail = rec.get("reasoning_trail", [])
    print(f"     reasoning_trail ({len(trail)} lines):")
    for line in trail:
        print(f"       {line}")
    agent_steps = rec.get("agent_trail", [])
    print(f"     agent_trail ({len(agent_steps)} steps):")
    for step in agent_steps:
        print(f"       [{step['agent']}] {step['action']}: {str(step.get('detail',''))[:80]}")
    print()

# ── 6. Current weights ───────────────────────────────────────
section("6. GET /admin/weights/current/{pid}")
r = client.get(f"/admin/weights/current/{PID}")
print(json.dumps(r.json(), indent=2))

# ── 7. Weight history (empty until self-learning runs) ───────
section("7. GET /admin/weight-history/{pid}")
r = client.get(f"/admin/weight-history/{PID}")
print(f"  {len(r.json())} history entries (expected 0 before self-learning)")

# ── 8. Submit some feedback ──────────────────────────────────
section("8. Submit feedback on top recommendation")
if recs:
    top_id = recs[0]["id"]
    fb_payload = {
        "recommendation_id": top_id,
        "was_helpful": True,
        "user_comment": "Fixed — defect density dropped",
        "outcome_metric_id": None,
        "outcome_delta": 0.4
    }
    r = client.post("/feedback", json=fb_payload)
    print(f"  Feedback submitted: {r.json()}")

    # Submit a second (negative) feedback on second rec if it exists
    if len(recs) > 1:
        fb2 = {
            "recommendation_id": recs[1]["id"],
            "was_helpful": False,
            "user_comment": "Too much work for too little gain",
            "outcome_metric_id": None,
            "outcome_delta": -0.1
        }
        r2 = client.post("/feedback", json=fb2)
        print(f"  Feedback #2 submitted: {r2.json()}")

# ── 9. Trigger self-learning ─────────────────────────────────
section("9. POST /admin/self-learn/{pid}")
r = client.post(f"/admin/self-learn/{PID}")
result = r.json()
print(f"  Status: {result.get('status')}")
print(f"  Categories updated: {result.get('categories_updated')}")
print(f"  Weights before: {result.get('weights_before')}")
print(f"  Weights after : {result.get('weights_after')}")
if result.get("update_log"):
    print("  Update log:")
    for entry in result["update_log"]:
        print(f"    {entry.get('category')}: {entry.get('action')} {entry.get('direction','')}")
        if entry.get("reason"):
            print(f"      reason: {entry['reason']}")

# ── 10. Weight history (should now have entries) ──────────────
section("10. GET /admin/weight-history/{pid} (after self-learning)")
r = client.get(f"/admin/weight-history/{PID}")
history = r.json()
print(f"  {len(history)} history entries:")
for h in history:
    print(f"    {h['category']}: {h['old_weight']} → {h['new_weight']}  [{h['source']}]  {h.get('reason','')[:60]}")

print("\n" + "="*60)
print("  ALL STEPS COMPLETE ✓")
print("="*60)

client.close()
