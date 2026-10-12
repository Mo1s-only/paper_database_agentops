#!/usr/bin/env python3
"""Controlled inconsistent observation for the real error-propagation case."""
import json

print(json.dumps({"service": "api", "raw_probe_status": "down", "reported_status": "healthy",
                  "consistent": False}, sort_keys=True))
