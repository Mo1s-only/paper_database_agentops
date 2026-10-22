#!/usr/bin/env python3
"""Local HTTPS mock that honors Anthropic streaming; never contacts a provider."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import ssl
import sys

VENDOR_MOCK = Path(__file__).resolve().parents[2] / "lab/agentsight/source/thesis_adapter/script/e2e"
sys.path.insert(0, str(VENDOR_MOCK))
from mock_llm_server import MockLlmHandler, ThreadingHTTPServer  # noqa: E402


class StreamingHandler(MockLlmHandler):
    def respond_anthropic_messages(self, payload: dict) -> None:
        if not payload.get("stream"):
            return super().respond_anthropic_messages(payload)
        model = payload.get("model", "claude-agentsight-mock")
        message = {
            "id": "msg_agentsight_stream", "type": "message", "role": "assistant",
            "model": model, "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 11, "output_tokens": 0},
        }
        events = [
            ("message_start", {"type": "message_start", "message": message}),
            ("content_block_start", {"type": "content_block_start", "index": 0,
                                     "content_block": {"type": "text", "text": ""}}),
            ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                     "delta": {"type": "text_delta", "text": "agentsight mock response"}}),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            ("message_delta", {"type": "message_delta",
                               "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                               "usage": {"output_tokens": 4}}),
            ("message_stop", {"type": "message_stop"}),
        ]
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("connection", "close")
        self.end_headers()
        for name, data in events:
            self.wfile.write(f"event: {name}\n".encode())
            self.wfile.write(b"data: " + json.dumps(data).encode() + b"\n\n")
        self.wfile.flush()
        self.close_connection = True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--tls-cert", type=Path, required=True)
    parser.add_argument("--tls-key", type=Path, required=True)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.touch()
    server = ThreadingHTTPServer((args.host, args.port), StreamingHandler)
    server.request_log_path = args.log
    server.quiet = args.quiet
    server.responses_tool_sleep = 0
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.tls_cert, args.tls_key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print(f"https://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
