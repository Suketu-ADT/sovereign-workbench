import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

def _is_number(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool)

class SandboxHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/calculate":
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
            return

        elif self.path == "/execute":
            content_length_str = self.headers.get("Content-Length", "")
            if not content_length_str.isdigit():
                self.send_error(400, "Bad Request: Content-Length required")
                return

            content_length = int(content_length_str)
            if content_length > 65536:  # 64KB max code script
                self.send_error(413, "Payload Too Large: Code exceeds 64KB")
                return

            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Bad Request: Invalid JSON")
                return

            if not isinstance(data, dict) or "code" not in data:
                self.send_error(400, "Bad Request: 'code' field required")
                return

            code_str = str(data["code"])
            timeout_sec = float(data.get("timeout", 5.0))
            timeout_sec = min(max(timeout_sec, 0.5), 15.0)

            # Execute code inside isolated container environment
            import subprocess
            import sys
            import tempfile
            import os

            result_payload = {}
            temp_script = None
            try:
                # Write to tmpfs mount /tmp
                with tempfile.NamedTemporaryFile("w", suffix=".py", dir="/tmp", delete=False) as tf:
                    tf.write(code_str)
                    temp_script = tf.name

                proc = subprocess.run(
                    [sys.executable, temp_script],
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                )
                result_payload = {
                    "status": "success" if proc.returncode == 0 else "error",
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "exit_code": proc.returncode,
                }
            except subprocess.TimeoutExpired:
                result_payload = {
                    "status": "timeout",
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout_sec}s",
                    "exit_code": -1,
                }
            except Exception as e:
                result_payload = {
                    "status": "error",
                    "stdout": "",
                    "stderr": str(e),
                    "exit_code": -1,
                }
            finally:
                if temp_script and os.path.exists(temp_script):
                    try:
                        os.remove(temp_script)
                    except Exception:
                        pass

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result_payload).encode("utf-8"))
            return

        else:
            self.send_error(404, "Not Found")
            return

def run(port=8080):
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, SandboxHandler)
    print(f"Sandbox listening on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
