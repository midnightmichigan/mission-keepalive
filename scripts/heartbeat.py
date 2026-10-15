#!/usr/bin/env python3
"""Heartbeat: proof-of-life for the token-free keepalive system.
Writes status/heartbeat.json with the current UTC timestamp.
No network, no LLM, no tokens."""
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(ROOT, "status", "heartbeat.json")
os.makedirs(os.path.dirname(STATUS), exist_ok=True)
with open(STATUS, "w") as f:
    json.dump({"last_heartbeat_utc": datetime.now(timezone.utc).isoformat(),
               "system": "mission-keepalive-systemd"}, f, indent=2)
print("heartbeat written")
