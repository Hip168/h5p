import http.server
import socketserver
import os
import re

PORT = 8000

class VideoRangeHandler(http.server.SimpleHTTPRequestHandler):
    # Enable CORS for the local dev environment
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    # Byte-range support for videos (Safari/Chrome requires this)
    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
            
        range_header = self.headers.get('Range')
        if not range_header or not range_header.startswith('bytes='):
            return super().send_head()
            
        try:
            size = os.path.getsize(path)
            ranges = re.findall(r'(\d+)-(\d*)', range_header)
            if not ranges:
                return super().send_head()
                
            start, end = ranges[0]
            start = int(start)
            end = int(end) if end else size - 1
            
            if start >= size:
                self.send_error(416, 'Requested Range Not Satisfiable')
                return None
                
            self.send_response(206)
            self.send_header('Content-Type', self.guess_type(path))
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.send_header('Content-Length', str(end - start + 1))
            self.end_headers()
            
            f = open(path, 'rb')
            f.seek(start)
            return f
        except Exception:
            return super().send_head()

print("="*60)
print(f"🎬 Video Static Server đang chạy tại http://localhost:{PORT}")
print("="*60)
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), VideoRangeHandler) as httpd:
    httpd.serve_forever()
