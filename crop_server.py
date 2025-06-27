from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class CropHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/crop":
            self.send_response(404)
            self.end_headers()
            return

        content_len = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(content_len)
        try:
            crop = json.loads(data)
            with open("crop.json", "w") as f:
                json.dump(crop, f)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK\n")
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid crop\n")

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    print("Crop server running on port 8080")
    HTTPServer(("0.0.0.0", 8080), CropHandler).serve_forever()
