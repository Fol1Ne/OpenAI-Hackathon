import { useEffect, useState } from 'react';

type Frame = { url: string; timestamp: number; people: number; passages: number; observed: number; complete: boolean; simulated: boolean };

export default function TempleBarDemo() {
  const [frame, setFrame] = useState<Frame | null>(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 500);
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let activeUrl: string | null = null;
    const controller = new AbortController();
    const poll = async () => {
      let delay = 250;
      try {
        const response = await fetch('/api/frames/cam1.jpg', {
          cache: 'no-store', signal: AbortSignal.any([controller.signal, AbortSignal.timeout(3000)]),
        });
        if (!response.ok) throw new Error('No current frame');
        const timestamp = Number(response.headers.get('x-frame-time')) * 1000;
        if (!Number.isFinite(timestamp) || Date.now() - timestamp > 3000) throw new Error('Frame expired');
        const blob = await response.blob();
        if (stopped) return;
        const url = URL.createObjectURL(blob);
        const previous = activeUrl;
        activeUrl = url;
        setFrame({ url, timestamp, people: Number(response.headers.get('x-people-now')),
          passages: Number(response.headers.get('x-passages')), observed: Number(response.headers.get('x-observed-seconds')),
          complete: response.headers.get('x-window-complete') === 'true', simulated: response.headers.get('x-camera-source') === 'synthetic' });
        if (previous) URL.revokeObjectURL(previous);
      } catch {
        if (!stopped) {
          setFrame(null);
          if (activeUrl) URL.revokeObjectURL(activeUrl);
          activeUrl = null;
        }
        delay = 1000;
      } finally {
        if (!stopped) timer = setTimeout(poll, delay);
      }
    };
    poll();
    return () => {
      stopped = true; controller.abort(); clearTimeout(timer); clearInterval(tick);
      if (activeUrl) URL.revokeObjectURL(activeUrl);
    };
  }, []);
  const current = frame !== null && now - frame.timestamp <= 3500;
  const observed = frame ? Math.floor(frame.observed / 6) / 10 : 0;
  return <main className="demo-screen">
    <header className="demo-header"><div><a href="/">← Street map</a><h1>Temple Bar</h1><p>Live pedestrian detection · demo preview</p></div>
      <span className={'badge ' + (current ? 'active' : '')}>{current ? frame.simulated ? 'SIMULATED REPLAY' : 'LIVE CAMERA' : 'CONNECTING / NO CURRENT DATA'}</span>
    </header>
    <div className="demo-video">
      {current ? <img src={frame.url} alt="Live Temple Bar camera with green boxes around detected pedestrians and a yellow counting line" /> :
        <div className="demo-wait"><h2>No current camera image</h2><p>Waiting for fresh observations. The preview reconnects automatically.</p></div>}
    </div>
    <section className="demo-stats" aria-label="Live camera measurements">
      <div><strong>{current ? frame.people : '—'}</strong><span>pedestrians detected in this frame</span></div>
      <div><strong>{current ? frame.passages : '—'}</strong><span>{current && frame.complete ? 'passages in the last 10 minutes' : `passages during ${current ? observed : '—'} minutes observed`}</span></div>
      <div><strong>{current ? `${observed} / 10 min` : '—'}</strong><span>{current && frame.complete ? 'full observation window' : 'collecting data'}</span></div>
    </section>
    <div className="demo-notes"><p><span className="box-key" /> Green boxes: detected pedestrians · <span className="line-key" /> Yellow line: passage counter</p>
      <p>{current ? `Frame updated ${new Date(frame.timestamp).toLocaleTimeString()}` : 'No current data'} · Detected people are blurred. Only the latest annotated frame is held in memory.</p>
      <p>Detection can miss people or count incorrectly in crowds. Decision support, not a guarantee of safety.</p></div>
  </main>;
}
