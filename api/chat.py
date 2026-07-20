"""POST /api/chat -- Vercel Python serverless function entrypoint.

Returns the full structured pipeline response in one shot (no token
streaming -- see DESIGN.md for the rationale). The frontend renders the
`steps` list as a visible multi-agent pipeline instead.
"""

import json
import traceback
from http.server import BaseHTTPRequestHandler

from agents.orchestrator import handle_query


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
        self._send_json(200, {"status": "ok"})

    def _send_json(self, status: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
