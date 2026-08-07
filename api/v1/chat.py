"""POST /api/v1/chat -- explicit V1 interview-demo API alias.

Not a copy of V1's orchestration: this imports and calls the exact same
agents.orchestrator.handle_query() that /api/chat already uses. This file
exists only to give V1 an explicit, documented `/api/v1/chat` URL alongside
the pre-existing `/api/chat` (which stays exactly as it is, for backward
compatibility with the live demo link), so the interview demo can address
both versions by clearly labeled paths.
"""

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# api/v1/chat.py is one directory deeper than api/chat.py, so the sibling
# `agents` package (which lives at api/agents/) is reached via parent.parent,
# not parent -- same Vercel importlib quirk documented in api/chat.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.orchestrator import handle_query  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(body or b"{}")
            query = (payload.get("query") or "").strip()
            if not query:
                self._send_json(400, {"error": "query is required"})
                return
            result = handle_query(query)
            self._send_json(200, result)
        except Exception as e:
            self._send_json(500, {"error": str(e), "trace": traceback.format_exc()})

    def do_GET(self):
        self._send_json(200, {"status": "ok", "version": "v1"})

    def _send_json(self, status: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
