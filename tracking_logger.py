import http.server
import socketserver
import json
import os
from datetime import datetime

PORT = 9000
PORT = 9000
LOG_FILE = "activity_summary.json"

class TrackingLogger(http.server.SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        # API trả về nội dung file Log duy nhất
        if self.path.startswith('/api/logs'):
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
        return super().do_GET()

    def do_POST(self):
        if self.path == '/log':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                log_type = data.get('type', 'raw')
                
                if log_type == 'reset':
                    with open(LOG_FILE, 'w', encoding='utf-8') as f:
                        json.dump([], f)
                    print(f"🧹 [{datetime.now().strftime('%H:%M:%S')}] Đã dọn sạch dữ liệu Log (Reset).")
                else:
                    # Ghi log duy nhất
                    self.save_to_file(LOG_FILE, data)
                    action = data.get('action') or data.get('verb', {}).get('display', {}).get('en-US', 'unknown')
                    print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Logged: {action}")
                
            except Exception as e:
                print(f"❌ Lỗi ghi log: {e}")
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"status":"success"}')
            return
        self.send_error(404)

    def save_to_file(self, target_file, data):
        """Hàm lưu log vào file JSON"""
        logs = []
        if os.path.exists(target_file):
            try:
                with open(target_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except: pass
        
        if 'server_time' not in data:
            data['server_time'] = datetime.now().isoformat()
            
        logs.append(data)
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

print("="*60)
print(f"🚀 H5P Activity Tracker đang chạy tại Port {PORT}")
print(f"📂 File báo cáo: {LOG_FILE}")
print("="*60)

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), TrackingLogger) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("\n🛑 Đã dừng server.")
