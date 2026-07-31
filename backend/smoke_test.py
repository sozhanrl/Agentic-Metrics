"""End-to-end smoke test for the multi-agent pipeline."""
import json, os
import urllib.request, urllib.error

BASE = "http://localhost:8000"

def get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                  headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def put(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                  headers={"Content-Type": "application/json"}, method="PUT")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

print("=" * 60)
print("MULTI-AGENT PIPELINE SMOKE TEST")
print("=" * 60)

# 1. Health check
health = get("/health")
print(f"\n[1] Health: {health}")

# 2. List or create a project
projects = get("/projects")
if projects:
    project = projects[0]
    print(f"\n[2] Using existing project: id={project['id']} name={project['name']}")
else:
    project = post("/projects", {"name": "Demo Project", "source": "github", "external_id": "demo"})
    print(f"\n[2] Created project: id={project['id']}")

pid = project["id"]

# 3. Seed demo data
seed = post(f"/dev/seed/{pid}")
print(f"\n[3] Seeded: {seed}")

# 4. Set risk profile (to exercise adaptive weighting)
profile = put(f"/projects/{pid}/risk-profile", {
    "team_size": 4,
    "tech_debt_index": 0.75,
    "risk_tolerance": "low",
    "deployment_env": "cloud",
    "notes": "Smoke test profile"
})
print(f"\n[4] Risk profile set: tech_debt_index={profile['tech_debt_index']} risk_tolerance={profile['risk_tolerance']}")

# 5. Run the multi-agent pipeline
print(f"\n[5] Running multi-agent pipeline for project {pid}...")
recs = post(f"/recommendations/{pid}/generate")
print(f"    Generated {len(recs)} recommendations")

for i, r in enumerate(recs[:3]):  # show top 3
    print(f"\n    [{i+1}] {r['title']}")
    print(f"         score={r['priority_score']}  trend_slope={r.get('trend_slope', 0):.4f}")
    print(f"         adaptive_weights={r.get('adaptive_weights')}")
    trail = r.get('reasoning_trail', [])
    print(f"         trail lines: {len(trail)}")
    for line in trail[:4]:
        print(f"           {line}")
    if r.get('conflict_note'):
        print(f"         CONFLICT: {r['conflict_note'][:80]}...")
    agent_steps = r.get('agent_trail', [])
    print(f"         agent_trail steps: {len(agent_steps)}")

# 6. Check weight history (should be empty before self-learning)
wh = get(f"/admin/weight-history/{pid}")
print(f"\n[6] Weight history entries: {len(wh)}")

# 7. Current weights
cw = get(f"/admin/weights/current/{pid}")
print(f"\n[7] Current effective weights: {cw['weights']}")

print("\n" + "=" * 60)
print("SMOKE TEST COMPLETE")
print("=" * 60)
