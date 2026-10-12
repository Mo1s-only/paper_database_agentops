#!/usr/bin/env python3
"""Controlled invalid route for the real routing-error case."""
import json

print(json.dumps({"task": "retrieve_document", "required_capability": "retrieval",
                  "selected_role": "generalist", "selected_capabilities": ["summarization"],
                  "route_valid": False}, sort_keys=True))
