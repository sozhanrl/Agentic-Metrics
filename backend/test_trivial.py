import json
import urllib.request

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/ml/dataset/train',
    data=json.dumps({"datasets": ["trivial"]}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        print(json.dumps(res, indent=2))
except Exception as e:
    print("Error:", e)
