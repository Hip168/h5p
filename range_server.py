import http.server
import socketserver
import os
import re
import json

PORT = 8000

class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        # API nhận Log JSON từ trình duyệt
        if self.path == '/log-interaction':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                print("\n" + "="*50)
                print(f"📥 NHẬN DỮ LIỆU xAPI: {data.get('verb', {}).get('display', {}).get('en-US', 'unknown')}")
                print("="*50)
                print(json.dumps(data, indent=2, ensure_ascii=False))
                print("="*50 + "\n")
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as e:
                print(f"❌ Lỗi xử lý JSON: {e}")
                self.send_error(400, "Invalid JSON")
            return

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

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

print(f"🚀 Server đang chạy tại http://localhost:{PORT}")
with socketserver.TCPServer(("", PORT), RangeRequestHandler) as httpd:
    httpd.serve_forever()
