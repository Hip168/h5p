"""
H5P Secure Range Server - Port 8000
Chức năng:
  1. Phục vụ file tĩnh (video range requests)
  2. GET  /token          → Cấp phiên token bảo mật
  3. POST /heartbeat      → Nhận nhịp đập 1s, phát hiện gian lận
  4. POST /xapi           → Nhận câu trả lời, chấm điểm phía server
  5. GET  /status?t=TOKEN → Trả về trạng thái phiên học hiện tại
"""

import http.server
import socketserver
import os
import re
import json
import time
import uuid
import threading

PORT = 8001

# ════════════════════════════════════════════════
# SESSION STORE (in-memory cho môi trường test)
# Trong production → dùng Redis / PostgreSQL
# ════════════════════════════════════════════════
sessions = {}
sessions_lock = threading.Lock()

# ────────────────────────────────────────────────
# Đọc đáp án chuẩn từ content.json (1 lần khi khởi động)
# ────────────────────────────────────────────────
CORRECT_ANSWERS = {}  # { subContentId: correct_answer_text }

def load_correct_answers():
    try:
        content_path = os.path.join(os.path.dirname(__file__),
                                    'h5p-content', 'content', 'content.json')
        with open(content_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        interactions = (data.get('interactiveVideo', {})
                            .get('assets', {})
                            .get('interactions', []))
        for i in interactions:
            action = i.get('action', {})
            lib = action.get('library', '')
            params = action.get('params', {})
            sub_id = action.get('subContentId', '')
            if 'MultiChoice' in lib and sub_id:
                answers = params.get('answers', [])
                correct = [
                    re.sub(r'<[^>]*>', '', a.get('text', '')).strip()
                    for a in answers if a.get('correct')
                ]
                CORRECT_ANSWERS[sub_id] = correct
        print(f"[Security] Loaded {len(CORRECT_ANSWERS)} correct answer(s) from content.json")
    except Exception as e:
        print(f"[Security] Warning: Could not load content.json for grading: {e}")

load_correct_answers()


# ════════════════════════════════════════════════
# HEARTBEAT VALIDATOR
# ════════════════════════════════════════════════
CHEAT_THRESHOLD = 3.0  # giây: nếu video nhảy > wall_time * này thì nghi ngờ

def validate_heartbeat(session, current_video_time, wall_now):
    """
    Trả về (is_valid, verdict_message, is_suspicious)
    """
    heartbeats = session['heartbeats']

    if not heartbeats:
        return True, "FIRST_BEAT", False

    last = heartbeats[-1]
    video_delta = current_video_time - last['video_time']
    wall_delta  = wall_now - last['wall_time']

    # Sinh viên có thể pause video → video_delta ≈ 0, wall_delta > 0 → hợp lệ
    # Sinh viên tua tới         → video_delta >> wall_delta → gian lận
    # Sinh viên tua lùi         → video_delta < 0 → bình thường (go back)

    if video_delta < 0:
        return True, "SEEK_BACK_OK", False

    if wall_delta <= 0:
        return True, "SYNC", False

    suspected_skip = video_delta > (wall_delta * CHEAT_THRESHOLD + 1.5)

    if suspected_skip:
        return False, f"CHEAT_DETECTED: video+{video_delta:.1f}s trong {wall_delta:.1f}s wall-time", True

    return True, "VALID", False


# ════════════════════════════════════════════════
# HTTP REQUEST HANDLER
# ════════════════════════════════════════════════
class SecureH5PHandler(http.server.SimpleHTTPRequestHandler):

    def log_message(self, format, *args):
        # Tắt log mặc định cho /heartbeat để không spam terminal
        if '/heartbeat' not in str(args[0] if args else ''):
            super().log_message(format, *args)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Session-Token')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == '/token':
            self._handle_token()
        elif self.path.startswith('/status'):
            self._handle_status()
        else:
            # Delegate to parent → parent calls send_head() then copyfile()
            super().do_GET()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body   = json.loads(self.rfile.read(length)) if length else {}

        if self.path == '/heartbeat':
            self._handle_heartbeat(body)
        elif self.path == '/xapi':
            self._handle_xapi(body)
        else:
            self.send_error(404)

    # ── 1. Cấp Token ──────────────────────────────
    def _handle_token(self):
        token = str(uuid.uuid4())
        with sessions_lock:
            sessions[token] = {
                'created_at'       : time.time(),
                'heartbeats'       : [],
                'cheat_count'      : 0,
                'valid_watch_secs' : 0,
                'answers'          : {},   # { subContentId: {answer, correct} }
                'is_passed'        : False,
                'verdict'          : 'IN_PROGRESS',
                'last_video_time'  : 0,
            }
        print(f"\n[Security] ✅ New session token issued: {token[:8]}...")
        self._json_response({'token': token, 'status': 'ok'})

    # ── 2. Nhận Heartbeat ─────────────────────────
    def _handle_heartbeat(self, body):
        token       = body.get('token')
        video_time  = float(body.get('currentTime', 0))
        duration    = float(body.get('duration', 0))
        answered    = int(body.get('answeredCount', 0))
        total_q     = int(body.get('totalQuestions', 0))
        wall_now    = time.time()

        with sessions_lock:
            if token not in sessions:
                self._json_response({'error': 'invalid_token'}, 401)
                return

            session = sessions[token]
            is_valid, verdict_msg, is_cheat = validate_heartbeat(session, video_time, wall_now)

            if is_cheat:
                session['cheat_count'] += 1
                print(f"[Security] 🚨 [{token[:8]}] {verdict_msg}")
            elif is_valid and verdict_msg == "VALID":
                session['valid_watch_secs'] += 1

            session['heartbeats'].append({
                'video_time': video_time,
                'wall_time' : wall_now,
                'valid'     : is_valid,
            })
            session['last_video_time'] = video_time

            # ── Tính toán xem học viên có THỰC SỰ hoàn thành không ──
            required_watch = duration * 0.9   # Cần xem ít nhất 90% thời lượng
            all_q_answered = (total_q == 0) or (answered >= total_q)
            enough_watch   = (session['valid_watch_secs'] >= required_watch) if duration > 0 else False
            no_cheating    = session['cheat_count'] == 0

            if enough_watch and all_q_answered and no_cheating:
                session['is_passed'] = True
                session['verdict']   = 'PASSED'
            elif session['cheat_count'] > 3:
                session['verdict'] = 'FAILED_CHEAT'
            else:
                session['verdict'] = 'IN_PROGRESS'

            self._json_response({
                'verdict'         : session['verdict'],
                'valid'           : is_valid,
                'cheat_count'     : session['cheat_count'],
                'valid_watch_secs': session['valid_watch_secs'],
                'required_watch'  : round(required_watch, 1),
                'verdict_detail'  : verdict_msg,
            })

    # ── 3. Nhận XAPI (chấm điểm server-side) ────
    def _handle_xapi(self, body):
        token      = body.get('token')
        sub_id     = body.get('subContentId', '')
        user_ans   = body.get('answer', '')
        verb       = body.get('verb', '')

        with sessions_lock:
            if token not in sessions:
                self._json_response({'error': 'invalid_token'}, 401)
                return
            session = sessions[token]

            if verb == 'answered' and sub_id:
                correct_answers = CORRECT_ANSWERS.get(sub_id, [])
                # So sánh đáp án (case-insensitive, bỏ HTML tags)
                clean_user = re.sub(r'<[^>]*>', '', user_ans).strip().lower()
                is_correct = any(
                    clean_user == re.sub(r'<[^>]*>', '', ca).strip().lower()
                    for ca in correct_answers
                )
                session['answers'][sub_id] = {
                    'user_answer'   : user_ans,
                    'correct'       : is_correct,
                    'server_graded' : True,
                }
                status = "✅ CORRECT" if is_correct else "❌ WRONG"
                print(f"[Security] 📝 [{token[:8]}] Answer graded: {status} | '{user_ans[:50]}'")
                self._json_response({'graded': True, 'correct': is_correct})
            else:
                self._json_response({'graded': False})

    # ── 4. Trả về trạng thái phiên ──────────────
    def _handle_status(self):
        import urllib.parse
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        token  = (params.get('t', [None])[0])

        with sessions_lock:
            if not token or token not in sessions:
                self._json_response({'error': 'invalid_token'}, 404)
                return
            s = sessions[token]
            self._json_response({
                'verdict'         : s['verdict'],
                'cheat_count'     : s['cheat_count'],
                'valid_watch_secs': s['valid_watch_secs'],
                'answers_count'   : len(s['answers']),
                'answers'         : s['answers'],
                'is_passed'       : s['is_passed'],
            })

    # ── Range request support (called by parent's do_GET pipeline) ──────
    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()

        range_header = self.headers.get('Range')
        if not range_header or not range_header.startswith('bytes='):
            return super().send_head()

        try:
            size   = os.path.getsize(path)
            ranges = re.findall(r'(\d+)-(\d*)', range_header)
            if not ranges:
                return super().send_head()
            start, end = ranges[0]
            start = int(start)
            end   = int(end) if end else size - 1
            if start >= size:
                self.send_error(416)
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

    # ── JSON helper ───────────────────────────────
    def _json_response(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ════════════════════════════════════════════════
print("=" * 60)
print(f"🔐 H5P Secure Server  →  http://localhost:{PORT}")
print(f"   GET  /token        →  Cấp session token")
print(f"   POST /heartbeat    →  Nhận nhịp đập 1s (Fraud Detection)")
print(f"   POST /xapi         →  Server-side grading")
print(f"   GET  /status?t=T   →  Trạng thái phiên học")
print("=" * 60)

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), SecureH5PHandler) as httpd:
    httpd.serve_forever()
