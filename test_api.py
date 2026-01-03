
import requests
import json

url = "https://www.thrustcurve.org/api/v1/download.json"
payload = {
    "motorIds": ["5f4294d20002310000000002"]
}
headers = {'Content-Type': 'application/json'}

try:
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
