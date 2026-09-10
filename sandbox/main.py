import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

def _is_number(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool)

class SandboxHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/calculate":
            self.send_error(404, "Not Found")
            return

        content_length_str = self.headers.get("Content-Length", "")
        if not content_length_str.isdigit():
            self.send_error(400, "Bad Request: Content-Length required")
            return

        content_length = int(content_length_str)
        if content_length > 1024:
            self.send_error(413, "Payload Too Large")
            return

        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Bad Request: Invalid JSON")
            return

        if not isinstance(data, dict):
            self.send_error(400, "Bad Request: JSON must be an object")
            return

        # STRICT validation
        allowed_keys = {"inlet_pressure", "outlet_pressure"}
        if set(data.keys()) != allowed_keys:
            self.send_error(400, "Bad Request: Invalid keys in JSON object")
            return

        in_p = data["inlet_pressure"]
        out_p = data["outlet_pressure"]

        if not _is_number(in_p) or not _is_number(out_p):
            self.send_error(400, "Bad Request: Values must be numbers")
            return

        # Deterministic Calculation
        delta_p = float(in_p) - float(out_p)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response_data = json.dumps({"pressure_drop": delta_p})
        self.wfile.write(response_data.encode("utf-8"))

def run(port=8080):
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, SandboxHandler)
    print(f"Sandbox listening on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
