import http.server
import socketserver
import json
import os
from datetime import datetime

PORT = 9000
LOG_FILE = "student_tracking.json"

class TrackingLogger(http.server.SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        # Handle CORS preflight for the new domain
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        # Endpoint API để lấy đọc toàn bộ logs
        if self.path == '/api/logs':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b'[]')
            return
            
        # Các đường dẫn khác sẽ hoạt động như Web Server thường
        return super().do_GET()

    def do_POST(self):
        if self.path == '/log':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                # Parse the incoming JSON
                data = json.loads(post_data)
                
                # Append to our local JSON file log
                logs = []
                if os.path.exists(LOG_FILE):
                    try:
                        with open(LOG_FILE, 'r', encoding='utf-8') as f:
                            logs = json.load(f)
                    except ValueError:
                        pass # File is empty or invalid
                
                # Add timestamp server-side
                data['server_time'] = datetime.now().isoformat()
                logs.append(data)
                
                # Write back to file securely
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(logs, f, ensure_ascii=False, indent=2)
                
                event_type = data.get('action') or data.get('event_type') or 'unknown'
                print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Đã ghi log sự kiện: {event_type} -> {LOG_FILE}")
                
            except Exception as e:
                print(f"❌ Lỗi ghi log: {e}")
            
            # Respond with success to client
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"status":"success"}')
            return
        
        # Fallback for other paths
        self.send_error(404, "Endpoint not found")

print("="*60)
print(f"🚀 Tracking Logger Server (Tên miền phụ) đang chạy!")
print(f"📥 Nơi NHẬN dữ liệu (POST): http://localhost:{PORT}/log")
print(f"📤 Nơi ĐỌC API log   (GET):  http://localhost:{PORT}/api/logs")
print(f"📂 File lưu JSON thực tế:    {LOG_FILE}")
print("="*60)

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), TrackingLogger) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("\n🛑 Đã dừng server.")
