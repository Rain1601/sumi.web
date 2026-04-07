"""Tiny HTTP health check server for Cloud Run.

Cloud Run requires an HTTP endpoint to verify the container is healthy.
The LiveKit worker itself doesn't serve HTTP, so we run this alongside it.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *args):
        pass  # Suppress access logs

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
