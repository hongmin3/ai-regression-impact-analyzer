from __future__ import annotations

import argparse
import json
import shutil
import urllib.request
from pathlib import Path


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:12000")
    parser.add_argument("--disk-path", type=Path, default=Path("."))
    parser.add_argument("--min-free-gb", type=float, default=2.0)
    args = parser.parse_args()
    health = fetch_json(f"{args.base_url.rstrip('/')}/health")
    config = fetch_json(f"{args.base_url.rstrip('/')}/config/status")
    operations = fetch_json(f"{args.base_url.rstrip('/')}/operations/status")
    free_gb = shutil.disk_usage(args.disk_path).free / (1024 ** 3)
    token = config.get("daily_token_usage", {})
    alerts = []
    if health.get("status") != "ok": alerts.append("health_not_ok")
    if free_gb < args.min_free_gb: alerts.append("disk_low")
    if token.get("exceeded"): alerts.append("daily_token_limit_exceeded")
    if operations.get("database_integrity") != "ok": alerts.append("database_integrity_failed")
    if operations.get("stale_jobs", 0): alerts.append("stale_jobs")
    if (operations.get("last_sync") or {}).get("status") == "FAILED": alerts.append("last_sync_failed")
    print(json.dumps({"status": "alert" if alerts else "ok", "alerts": alerts, "free_gb": round(free_gb, 2), "daily_token_usage": token, "operations": operations}, ensure_ascii=False))
    return 1 if alerts else 0


if __name__ == "__main__":
    raise SystemExit(main())
