"""Local continuous person detection. Persist aggregate numbers only.

Run: python cv/run.py
Calibrate: python cv/run.py --calibrate cam1 (click two pavement points, Enter)
Replay: python cv/run.py --camera cam1 --video clip.mp4 --line .2,.6,.8,.6
"""
import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse

from counting import PassageCounter
from preview import Preview

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'backend/app/data/cameras.json'
OUT = ROOT / 'data/cache/camera_metrics.json'


def load_env():
    path = ROOT / '.env'
    if path.exists():
        for raw in path.read_text().splitlines():
            if '=' in raw and not raw.lstrip().startswith('#'):
                key, value = raw.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


def source_for(camera, video=None):
    n = camera['id'].removeprefix('cam')
    replay = video or os.getenv(f'VIDEO_{n}')
    return (replay, True) if replay else (os.getenv(f'CAMERA_{n}_URL') or camera.get('stream_url'), False)


def resolve(source):
    host = urlparse(source).hostname or ''
    if host == 'youtu.be' or host == 'youtube.com' or host.endswith('.youtube.com'):
        result = subprocess.run(
            [sys.executable, '-m', 'yt_dlp', '--js-runtimes', 'node', '--no-playlist',
             '--socket-timeout', '8', '--retries', '1', '--get-url',
             '-f', 'bestvideo[height<=720]/best', source],
            capture_output=True, text=True, timeout=30, check=True)
        return result.stdout.strip().splitlines()[0]
    return source


def open_capture(source, replay):
    import cv2
    if replay:
        cap = cv2.VideoCapture(source)
    else:
        cap = cv2.VideoCapture(resolve(source), cv2.CAP_FFMPEG,
                               [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000,
                                cv2.CAP_PROP_READ_TIMEOUT_MSEC, 15000])
    if not cap.isOpened():
        cap.release()
        raise RuntimeError('Stream could not be opened')
    return cap


class LatestFrame:
    """Drain live capture continuously, keeping just the latest frame in memory."""
    def __init__(self, cap):
        self.cap, self.latest, self.stopped = cap, None, False
        self.lock = threading.Lock()
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        import cv2
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        period = 1 / fps if 1 <= fps <= 120 else 1 / 25
        deadline = time.monotonic()
        try:
            while not self.stopped:
                time.sleep(max(0, deadline - time.monotonic()))
                deadline = max(deadline + period, time.monotonic())
                ok, frame = self.cap.read()
                if not ok:
                    break
                with self.lock:
                    self.latest = (time.monotonic(), time.time(), frame)
        finally:
            self.stopped = True
            self.cap.release()

    def get(self):
        with self.lock:
            return self.latest


def worker(camera, source, replay, output, model_path):
    (ROOT / 'cv/.runtime').mkdir(exist_ok=True)
    os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / 'cv/.runtime'))
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'cv/.runtime/matplotlib'))
    import cv2
    import numpy as np
    import torch
    from ultralytics import YOLO
    # Each camera has isolated memory and a separate detector.
    torch.set_num_threads(2)
    model = YOLO(model_path)
    model.predict(np.zeros((384, 640, 3), dtype=np.uint8), classes=[0], device='cpu', verbose=False, save=False)
    preview = Preview(8100 + int(camera['id'].removeprefix('cam')))
    counter = PassageCounter(camera['counting_line'])
    reader = None
    last_sent = 0
    last_preview = 0
    while True:
        try:
            cap = open_capture(source, replay)
            counter.disconnect()
            reader = None if replay else LatestFrame(cap)
            last_frame = None
            stalled = False
            previous_thumb, changed_at = None, time.monotonic()
            fps = max(1, cap.get(cv2.CAP_PROP_FPS) or 25)
            next_frame = time.monotonic()
            while True:
                if replay:
                    time.sleep(max(0, next_frame - time.monotonic()))
                    next_frame = max(next_frame + 1 / fps, time.monotonic())
                    ok, frame = cap.read()
                    if not ok:
                        cap.release()
                        break  # reopen clip; crossing tracks reset at the boundary
                    mono, wall = time.monotonic(), time.time()
                else:
                    item = reader.get()
                    if reader.stopped:
                        raise RuntimeError('Stream read ended')
                    if item and time.monotonic() - item[0] > 2:
                        if not stalled:
                            counter.disconnect()
                            preview.clear()
                            output.put({'id': camera['id'], 'state': 'no_data'})
                            stalled = True
                        time.sleep(.02)
                        continue
                    stalled = False
                    if item is None or item[0] == last_frame:
                        time.sleep(.01)
                        continue
                    mono, wall, frame = item
                last_frame = mono
                # Exact repeated imagery can indicate a frozen video source.
                thumb = cv2.resize(frame, (64, 36))
                if previous_thumb is None or not np.array_equal(previous_thumb, thumb):
                    changed_at = mono
                elif mono - changed_at > 3:
                    raise RuntimeError('Frozen video')
                previous_thumb = thumb
                result = model.predict(frame, classes=[0], conf=.35, imgsz=640,
                                       device='cpu', verbose=False, save=False)[0]
                # Slow inference leaves observation gaps, never fills them with zero.
                if time.monotonic() - mono > 1:
                    counter.disconnect()
                    raise RuntimeError('Frame processing is falling behind')
                height, width = frame.shape[:2]
                boxes = result.boxes.xyxy.cpu().tolist()
                points = [((x1 + x2) / (2 * width), y2 / height)
                          for x1, y1, x2, y2 in boxes]
                metrics = counter.update(points, mono)
                if mono - last_preview >= .25:
                    preview.publish(frame, boxes, camera['counting_line'], wall, metrics, replay)
                    last_preview = mono
                if mono - last_sent >= 1:
                    output.put({'id': camera['id'], 'ts': wall, 'state': 'observing',
                                'source': 'synthetic' if replay else 'live',
                                'people_now': len(points),
                                'brightness': round(float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean() / 255), 3),
                                **metrics})
                    last_sent = mono
                del frame, result
        except Exception as error:
            preview.clear()
            counter.disconnect()
            if reader:
                reader.stopped = True
            restricted = isinstance(error, subprocess.CalledProcessError) and "Sign in to confirm" in (error.stderr or '')
            reason = 'youtube_sign_in' if restricted else type(error).__name__
            detail = 'YouTube requires sign-in to confirm access' if restricted else str(error) if isinstance(error, RuntimeError) else type(error).__name__
            delay = 300 if restricted else 10
            print(f"{camera['id']}: no current data ({detail}); retrying in {delay}s", flush=True)
            # Heartbeats prevent the watchdog from turning access failures into a retry loop.
            for _ in range(delay // 5):
                output.put({'id': camera['id'], 'state': 'no_data', 'error': reason})
                time.sleep(5)


def calibrate(camera, source, replay):
    import cv2
    # No frame files: the preview and two-click line exist only in memory.
    cap = open_capture(source, replay)
    points = []
    title = 'Click two pavement endpoints; Enter saves; R resets; Esc cancels'
    cv2.namedWindow(title)
    def click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 2:
            points.append((x / preview_width, y / preview_height))
    cv2.setMouseCallback(title, click)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError('No frame available for calibration')
            frame = cv2.resize(frame, (960, round(frame.shape[0] * 960 / frame.shape[1])))
            preview_height, preview_width = frame.shape[:2]
            pixels = [(round(x * preview_width), round(y * preview_height)) for x, y in points]
            for p in pixels:
                cv2.circle(frame, p, 6, (0, 255, 255), -1)
            if len(pixels) == 2:
                cv2.line(frame, *pixels, (0, 255, 255), 2)
            cv2.imshow(title, frame)
            key = cv2.waitKey(20) & 255
            if key == 27:
                return
            if key == ord('r'):
                points.clear()
            if key in (10, 13) and len(points) == 2:
                PassageCounter(points)  # validate before saving
                cameras = json.loads(CONFIG.read_text())
                for item in cameras:
                    if item['id'] == camera['id']:
                        item.update(counting_line=points, calibrated_for=source)
                CONFIG.write_text(json.dumps(cameras, indent=2) + '\n')
                print(f"Saved counting line for {camera['street']}. Restart the CV process.")
                return
    finally:
        cap.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera', choices=['cam1', 'cam2', 'cam3'])
    parser.add_argument('--video', help='Replay a file in real time, labelled simulated')
    parser.add_argument('--line', help='Confirmed normalized endpoints x1,y1,x2,y2')
    parser.add_argument('--calibrate', choices=['cam1', 'cam2', 'cam3'])
    parser.add_argument('--model', default=str(ROOT / 'cv/yolov8n.pt'))
    args = parser.parse_args()
    load_env()
    cameras = json.loads(CONFIG.read_text())
    selected = args.calibrate or args.camera
    if (args.video or args.line) and not selected:
        parser.error('--video and --line require --camera or --calibrate')
    cameras = [c for c in cameras if not selected or c['id'] == selected]
    context = mp.get_context('spawn')
    output = context.Queue()
    jobs, state = {}, {}
    for camera in cameras:
        source, replay = source_for(camera, args.video)
        if args.line:
            try:
                values = [float(v) for v in args.line.split(',')]
                if len(values) != 4:
                    raise ValueError()
                camera['counting_line'] = [values[:2], values[2:]]
                PassageCounter(camera['counting_line'])
                camera['calibrated_for'] = source
            except ValueError:
                parser.error('--line needs four normalized coordinates with distinct endpoints')
        if args.calibrate:
            if not source:
                parser.error('Configure the camera URL before calibration')
            try:
                calibrate(camera, source, replay)
            except Exception as error:
                raise SystemExit(f'Calibration unavailable: {type(error).__name__}. No line saved.')
            return
        initial = 'no_data' if not source else 'needs_calibration' if camera.get('calibrated_for') != source else 'connecting'
        state[camera['id']] = {'state': initial}
        if initial != 'connecting':
            print(f"{camera['street']}: {initial}", flush=True)
            continue
        if not Path(args.model).is_file():
            state[camera['id']] = {'state': 'no_data'}
            print(f'Missing model: {args.model}. See RUN.md.', flush=True)
            continue
        process = context.Process(target=worker, args=(camera, source, replay, output, args.model), daemon=True)
        process.start()
        jobs[camera['id']] = [process, time.monotonic(), camera, source, replay]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        while True:
            try:
                message = output.get(timeout=1)
                key = message.pop('id')
                previous = state.get(key, {})
                state[key] = message if message['state'] == 'observing' else {**previous, **message}
                if key in jobs:
                    jobs[key][1] = time.monotonic()
            except queue.Empty:
                pass
            for key, job in jobs.items():
                process, seen, camera, source, replay = job
                if not process.is_alive() or time.monotonic() - seen > 60:
                    process.terminate()
                    process.join(timeout=3)
                    if process.is_alive():
                        process.kill()
                        process.join(timeout=2)
                    state[key] = {**state[key], 'state': 'no_data'}
                    replacement = context.Process(target=worker, args=(camera, source, replay, output, args.model), daemon=True)
                    replacement.start()
                    jobs[key] = [replacement, time.monotonic(), camera, source, replay]
            temporary = OUT.with_suffix('.tmp')
            temporary.write_text(json.dumps(state))
            temporary.replace(OUT)
    except KeyboardInterrupt:
        pass
    finally:
        for process, *_ in jobs.values():
            process.terminate()
            process.join(timeout=3)
        OUT.write_text(json.dumps({key: {**value, 'state': 'no_data'} for key, value in state.items()}))


if __name__ == '__main__':
    main()
