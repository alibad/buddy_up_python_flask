import requests
import json
import os

class VercelKV:
    def __init__(self):
        self.token = os.getenv("KV_REST_API_TOKEN")
        self.base_url = os.getenv("KV_REST_API_URL")

    def _send_request(self, method, command, key, value=None):
        url = f"{self.base_url}/{command}/{key}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        data = json.dumps(value) if value is not None else None
        response = requests.request(method, url, headers=headers, data=data)
        return response

    def set(self, key, value):
        print(f"Setting key '{key}' with value '{value}'")
        value = {"value": str(value)}
        response = self._send_request("POST", "set", key, value)
        
        if response.status_code != 200:
            raise Exception(f"Failed to set key {key}. Response: {response.text}")

    def get(self, key):
        print(f"Getting key '{key}'")
        response = self._send_request("GET", "get", key)
        
        if response.status_code != 200:
            raise Exception(f"Failed to get key {key}. Response: {response.text}")
        
        # After this line in your code:
        j = response.json()

        print(f"Raw GET: '{j}'")
        
        # Deserialize the inner JSON string:
        if 'result' in j:
            inner_json = json.loads(j['result'])

            if 'value' in inner_json:
                j = inner_json['value']

        print(f"Cleaned GET: '{j}'")

        return j

    def delete(self, key):
        response = self._send_request("DELETE", "delete", key)
        if response.status_code != 200:
            raise Exception(f"Failed to delete key {key}. Response: {response.text}")

    def update(self, key, value):
        response = self._send_request("POST", "set", key, value)
        if response.status_code != 200:
            raise Exception(f"Failed to update key {key}. Response: {response.text}")
