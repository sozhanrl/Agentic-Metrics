import json
import urllib.request

def get_json(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode('utf-8'))

status = get_json('http://127.0.0.1:8000/api/ml/dataset/status')
print("=== STATUS ===")
print(json.dumps(status, indent=2))

eval_res = get_json('http://127.0.0.1:8000/api/ml/dataset/evaluation')
print("\n=== EVALUATION KEYS ===")
for k, v in eval_res.items():
    print(k, "->", list(v.keys()) if isinstance(v, dict) else type(v))
    if isinstance(v, dict):
        if "champion_model" in v:
            print(f"  champion: {v.get('champion_model')}, f1: {v.get('champion_f1')}")
        if "random_forest" in v:
            rf = v.get("random_forest", {})
            print(f"  RF: f1={rf.get('f1')}, auc={rf.get('roc_auc')}, acc={rf.get('accuracy')}")
        if "xgboost" in v:
            xgb = v.get("xgboost", {})
            print(f"  XGB: f1={xgb.get('f1')}, auc={xgb.get('roc_auc')}, acc={xgb.get('accuracy')}")
