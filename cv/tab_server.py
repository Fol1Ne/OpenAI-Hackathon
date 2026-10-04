"""Local-only shared-tab inference. Frames and anonymous tracks stay in memory."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from pathlib import Path
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from counting import PassageCounter

torch.set_num_threads(2)
model = YOLO(str(Path(__file__).with_name('yolov8n.pt')))
lock = threading.Lock()
sessions = {}

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.connection.settimeout(5)
        if self.path != '/detect':
            self.send_error(404)
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 1000000:
                self.send_error(413)
                return
            session = self.headers.get('X-Session', '')
            if not session or len(session) > 80:
                raise ValueError('Invalid session')
            line = json.loads(self.headers.get('X-Line', 'null'))
            if not isinstance(line, list) or len(line) != 2 or any(
                not isinstance(p, list) or len(p) != 2 or any(
                    not isinstance(v, (int, float)) or not 0 <= v <= 1 for v in p
                ) for p in line
            ):
                raise ValueError('Invalid counting line')
            counter = PassageCounter(line)
            frame = cv2.imdecode(np.frombuffer(self.rfile.read(size), np.uint8), cv2.IMREAD_COLOR)
            if frame is None or max(frame.shape[:2]) > 1280:
                raise ValueError('Invalid frame')
            if not lock.acquire(blocking=False):
                self.send_error(429)
                return
            try:
                now = time.monotonic()
                for key in list(sessions):
                    if now - sessions[key][0] > 3:
                        del sessions[key]
                if session in sessions and sessions[session][1] == line:
                    counter = sessions[session][2]
                if len(sessions) >= 8 and session not in sessions:
                    self.send_error(429)
                    return
                boxes = model.predict(frame, classes=[0], conf=.35, imgsz=640, verbose=False)[0].boxes.xyxy.cpu().tolist()
                h, w = frame.shape[:2]
                metrics = counter.update([((a+c)/2/w, d/h) for a,b,c,d in boxes], now)
                sessions[session] = (now, line, counter)
                data = json.dumps({'boxes': boxes, **metrics}).encode()
            finally:
                lock.release()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (ValueError, TypeError, OSError):
            self.send_error(400, 'Invalid capture request')

    def log_message(self, *args):
        pass

def expire_sessions():
    while True:
        time.sleep(2)
        with lock:
            for key in list(sessions):
                if time.monotonic() - sessions[key][0] > 3:
                    del sessions[key]

if __name__ == '__main__':
    threading.Thread(target=expire_sessions, daemon=True).start()
    print('Shared-tab detector listening on 127.0.0.1:8110', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8110), Handler).serve_forever()
