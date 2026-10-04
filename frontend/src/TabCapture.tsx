import { useEffect, useRef, useState } from 'react';
type Point = [number, number];
type Result = { boxes: number[][]; passages_10min: number; observed_seconds: number };
const links: Record<string, string> = {cam1: '3nyPER2kzqk', cam2: 'f43rKPCALls', cam3: 'eSWxGOZLgCU'};

export default function TabCapture({ cameraId }: { cameraId: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const stopRef = useRef<() => void>(() => {});
  const lineRef = useRef<Point[]>([]);
  const [active, setActive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [line, setLine] = useState<Point[]>([]);
  const [message, setMessage] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const generation = useRef(0);
  useEffect(() => () => { generation.current++; stopRef.current(); }, []);
  function calibrate() { lineRef.current = []; setLine([]); setResult(null); }
  async function start() {
    if (!navigator.mediaDevices?.getDisplayMedia) {
      setMessage('Tab sharing is unavailable here. Open this demo in Chrome or Edge on localhost.'); return;
    }
    const run = ++generation.current;
    setStarting(true); setMessage('');
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 10 }, audio: false });
      if (run !== generation.current) { stream.getTracks().forEach(t => t.stop()); return; }
      const video = document.createElement('video');
      video.muted = true; video.srcObject = stream;
      let stopped = false;
      let timer: ReturnType<typeof setTimeout>;
      const controller = new AbortController();
      stopRef.current = () => {
        stopped = true; controller.abort(); clearTimeout(timer);
        stream.getTracks().forEach(t => t.stop()); video.pause(); video.srcObject = null;
        setActive(false); setResult(null);
        const ctx = canvas.current?.getContext('2d');
        if (ctx && canvas.current) ctx.clearRect(0, 0, canvas.current.width, canvas.current.height);
      };
      stream.getVideoTracks()[0].onended = () => stopRef.current();
      setActive(true); calibrate();
      await video.play();
      const raw = document.createElement('canvas');
      const session = crypto.randomUUID();
      let previous = ''; let lastChange = performance.now();
      async function process() {
        if (stopped) return;
        try {
          const display = canvas.current;
          if (!display || !video.videoWidth) throw new Error('Waiting for shared video…');
          const scale = Math.min(1, 960/video.videoWidth, 720/video.videoHeight);
          raw.width = Math.round(video.videoWidth*scale); raw.height = Math.round(video.videoHeight*scale);
          const context = raw.getContext('2d')!;
          context.drawImage(video, 0, 0, raw.width, raw.height);
          const selected = lineRef.current.slice();
          let data: Result | null = null;
          if (selected.length === 2) {
            const fingerprint = raw.toDataURL('image/jpeg', .15);
            if (fingerprint !== previous) { previous = fingerprint; lastChange = performance.now(); }
            if (performance.now()-lastChange > 3000) throw new Error('Shared video appears paused. Resume playback for current observations.');
            const blob = await new Promise<Blob | null>(resolve => raw.toBlob(resolve, 'image/jpeg', .75));
            if (!blob) throw new Error('Could not capture the shared video.');
            const response = await fetch('/api/tab-capture/detect', {method: 'POST', body: blob,
              headers: {'Content-Type': 'image/jpeg', 'X-Session': session, 'X-Line': JSON.stringify(selected)},
              signal: AbortSignal.any([controller.signal, AbortSignal.timeout(2500)])});
            if (!response.ok) throw new Error('Local detector unavailable. Check the shared-tab detector is running.');
            data = await response.json();
          }
          if (stopped || JSON.stringify(selected) !== JSON.stringify(lineRef.current)) return;
          display.width = raw.width; display.height = raw.height;
          const ctx = display.getContext('2d')!;
          ctx.drawImage(raw, 0, 0);
          for (const [x1,y1,x2,y2] of data?.boxes || []) {
            ctx.save(); ctx.beginPath(); ctx.rect(x1,y1,x2-x1,y2-y1); ctx.clip(); ctx.filter = 'blur(12px)'; ctx.drawImage(raw,0,0); ctx.restore();
            ctx.strokeStyle = '#00ff00'; ctx.lineWidth = 2; ctx.strokeRect(x1,y1,x2-x1,y2-y1);
          }
          ctx.strokeStyle = '#eab308'; ctx.fillStyle = '#eab308'; ctx.lineWidth = 3;
          selected.forEach(([x,y]) => { ctx.beginPath(); ctx.arc(x*raw.width,y*raw.height,5,0,Math.PI*2); ctx.fill(); });
          if (selected.length === 2) {ctx.beginPath(); ctx.moveTo(selected[0][0]*raw.width,selected[0][1]*raw.height); ctx.lineTo(selected[1][0]*raw.width,selected[1][1]*raw.height); ctx.stroke();}
          setResult(data); setMessage('');
        } catch (error) {
          if (!stopped) { setResult(null); setMessage(error instanceof Error ? error.message : 'Capture interrupted.');
            const ctx = canvas.current?.getContext('2d'); if (ctx && canvas.current) ctx.clearRect(0,0,canvas.current.width,canvas.current.height);
          }
        } finally { if (!stopped) timer = setTimeout(process, 150); }
      }
      process();
    } catch (error) { stopRef.current(); setMessage(error instanceof Error && error.name === 'NotAllowedError' ? 'Sharing was cancelled or denied. You can try again.' : 'Could not start tab sharing. Try Chrome or Edge on localhost.'); }
    finally { setStarting(false); }
  }
  return <section className="tab-capture">
    <h2>Share a camera tab</h2>
    <p>Open the stream, play it live, then share only that browser tab. Frames are processed locally and never saved.</p>
    <div className="capture-actions">
      <a href={`https://www.youtube.com/watch?v=${links[cameraId]}`} target="_blank" rel="noreferrer">Open camera stream ↗</a>
      {active ? <><button onClick={() => stopRef.current()}>Stop sharing</button><button onClick={calibrate}>Reset counting line</button></> : <button disabled={starting} onClick={start}>{starting ? 'Choose a tab…' : 'Share camera tab'}</button>}
    </div>
    <p role="status">{message || (active ? line.length < 2 ? `Click ${line.length ? 'the second' : 'the first'} endpoint of a line across the pavement below.` : 'Shared-tab demo · selected video is not independently verified.' : 'Use Chrome or Edge if this browser does not offer tab sharing.')}</p>
    <canvas ref={canvas} hidden={!active} aria-label="Shared camera preview. Click two endpoints to set the counting line." onClick={event => {
      if (lineRef.current.length >= 2) return;
      const rect = event.currentTarget.getBoundingClientRect();
      const next: Point[] = [...lineRef.current, [(event.clientX-rect.left)/rect.width, (event.clientY-rect.top)/rect.height]];
      lineRef.current = next; setLine(next);
    }} />
    {active && <p>{result ? `${result.boxes.length} pedestrians detected · ${result.passages_10min} passages during ${(result.observed_seconds/60).toFixed(1)} of 10 minutes observed` : 'No current passage data'}.</p>}
    <small>Keep the video playing and sharing active. Counts cover this shared-tab demo only; they do not update map observations. Reset the line if the video layout changes.</small>
  </section>;
}
