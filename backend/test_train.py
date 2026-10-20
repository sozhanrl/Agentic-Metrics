import json
import urllib.request

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/ml/dataset/train',
    data=json.dumps({"datasets": ["defect", "trivial", "nontrivial"]}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, timeout=120) as response:
        data = json.loads(response.read().decode('utf-8'))
        print("Status:", data.get("status"))
        print("Duration ms:", data.get("duration_ms"))
        print("Pipelines:", list(data.get("pipelines", {}).keys()))
        for k, v in data.get("pipelines", {}).items():
            print(f"  {k}: champion={v.get('champion_model')}, champion_f1={v.get('champion_f1')}")
except Exception as e:
    print("Error:", e)
