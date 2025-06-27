#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os

CROP_FILE = "crop.json"

class CropHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/crop":
            self.send_response(404)
            self.end_headers()
            return

        content_len = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(content_len)
        try:
            incoming_crop = json.loads(data)

            # Load existing crop data if exists
            if os.path.exists(CROP_FILE):
                with open(CROP_FILE, "r") as f:
                    full_crop = json.load(f)
            else:
                full_crop = {}

            full_crop.update(incoming_crop)

            with open(CROP_FILE, "w") as f:
                json.dump(full_crop, f)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK\n")
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Invalid crop: {e}".encode())

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    print("Crop server running on port 8080")
    HTTPServer(("0.0.0.0", 8080), CropHandler).serve_forever()
