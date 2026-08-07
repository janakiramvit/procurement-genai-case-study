"""POST /api/v2/chat -- Step 3B agent-loop API.

Accepts {"query": str, "conversation_history": [{"user": str, "assistant": str}, ...]}.
conversation_history is optional and independently re-validated/re-truncated
server-side by agents.memory regardless of what's sent -- see
agents/orchestrator_v2.py.
"""

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.orchestrator_v2 import handle_query_v2  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(body or b"{}")
            query = (payload.get("query") or "").strip()
            conversation_history = payload.get("conversation_history") or []
            if not query:
                self._send_json(400, {"error": "query is required"})
                return
            result = handle_query_v2(query, conversation_history)
            self._send_json(200, result)
        except Exception as e:
            self._send_json(500, {"error": str(e), "trace": traceback.format_exc()})

    def do_GET(self):
        self._send_json(200, {"status": "ok", "version": "v2"})

    def _send_json(self, status: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
