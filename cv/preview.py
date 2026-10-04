"""One annotated JPEG per camera, held in memory and served on loopback only."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time


class Preview:
    def __init__(self, port):
        self.latest = None
        self.lock = threading.Lock()
        preview = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != '/frame.jpg':
                    self.send_error(404)
                    return
                with preview.lock:
                    item = preview.latest
                if item is None or time.time() - item[0] > 3:
                    self.send_response(503)
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    return
                timestamp, jpeg, metadata = item
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Cache-Control', 'no-store, max-age=0')
                self.send_header('Content-Length', str(len(jpeg)))
                self.send_header('X-Frame-Time', str(timestamp))
                for key, value in metadata.items():
                    self.send_header(key, str(value))
                self.end_headers()
                try:
                    self.wfile.write(jpeg)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def clear(self):
        with self.lock:
            self.latest = None

    def publish(self, frame, boxes, line, timestamp, metrics, replay):
        import cv2
        picture = frame.copy()
        height, width = picture.shape[:2]
        rectangles = []
        for box in boxes:
            x1, y1, x2, y2 = [int(v) for v in box]
            x1, x2 = max(0, x1), min(width, x2)
            y1, y2 = max(0, y1), min(height, y2)
            if x2 > x1 and y2 > y1:
                # Blur each detected person, without detecting faces or identity.
                picture[y1:y2, x1:x2] = cv2.GaussianBlur(picture[y1:y2, x1:x2], (31, 31), 12)
                rectangles.append((x1, y1, x2, y2))
        for x1, y1, x2, y2 in rectangles:
            cv2.rectangle(picture, (x1, y1), (x2, y2), (0, 255, 0), 2)
        a, b = [(int(x * width), int(y * height)) for x, y in line]
        cv2.line(picture, a, b, (0, 220, 255), 2)
        encoded, jpeg = cv2.imencode('.jpg', picture, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if encoded:
            with self.lock:
                self.latest = (timestamp, jpeg.tobytes(), {
                    'X-People-Now': len(boxes),
                    'X-Passages': metrics['passages_10min'],
                    'X-Observed-Seconds': metrics['observed_seconds'],
                    'X-Window-Complete': str(metrics['window_complete']).lower(),
                    'X-Camera-Source': 'synthetic' if replay else 'live',
                })
