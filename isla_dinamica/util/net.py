"""Peticiones HTTP sencillas (JSON con tiempo de espera)."""
import json
import urllib.request


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "isla-dinamica/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)
