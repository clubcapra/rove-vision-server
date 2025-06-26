#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

CROP_FILE = "crop.json"

class CropRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/crop":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        try:
            crop_data = json.loads(post_data)
            if not all(k in crop_data for k in ["left", "top", "right", "bottom"]):
                raise ValueError("Missing crop keys")

            with open(CROP_FILE, "w") as f:
                json.dump(crop_data, f)
                f.write("\n")

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Crop written to crop.json\n")

        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Invalid request: {e}".encode())

    def log_message(self, format, *args):
        pass  # Silence logs

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), CropRequestHandler)
    print("Crop server running at http://localhost:8080/crop")
    server.serve_forever()
