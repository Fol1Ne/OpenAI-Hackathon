import { useEffect, useRef, useState } from 'react';
import { CameraActivity, isCurrent, type Camera } from './CameraActivity';
import { MapContainer, TileLayer, Polyline, CircleMarker, Popup, useMap, useMapEvents } from 'react-leaflet';
type LL = [number, number];
type Route = { coords: LL[]; minutes: number; distance_m: number; camera_ids: string[]; street_names: string[] };
type Result = { route: Route; sources: { routing: string }; disclaimer: string };
const PLACES: { name: string; point: LL }[] = [
  { name: 'Trinity College', point: [53.3438, -6.2546] }, { name: 'Temple Bar', point: [53.3454, -6.2645] },
  { name: 'Grafton Street', point: [53.3425, -6.26] }, { name: "St Stephen's Green", point: [53.3392, -6.26] },
];
const TILE = import.meta.env.VITE_TILE_URL || 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
function MapClicks({ select }: { select: (point: LL) => void }) {
  useMapEvents({ click: e => select([e.latlng.lat, e.latlng.lng]) }); return null;
}
function FitRoute({ route }: { route: Route | null }) {
  const map = useMap();
  useEffect(() => {
    const fit = () => {
      map.invalidateSize({ pan: false });
      if (route) map.fitBounds(route.coords, { padding: [35, 35], maxZoom: 17, animate: false });
    };
    const frame = requestAnimationFrame(fit);
    const observer = new ResizeObserver(fit);
    observer.observe(map.getContainer());
    return () => { cancelAnimationFrame(frame); observer.disconnect(); };
  }, [map, route]);
  return null;
}

export default function App() {
  const [points, setPoints] = useState<LL[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [activeCamera, setActiveCamera] = useState('cam1');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [from, setFrom] = useState(0);
  const [to, setTo] = useState(3);
  const request = useRef<AbortController | null>(null);
  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => { clearInterval(tick); request.current?.abort(); };
  }, []);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const response = await fetch('/api/cameras', { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(4000)]) });
        if (!response.ok) throw new Error();
        const data: Camera[] = await response.json();
        if (!stopped) setCameras(data);
      } catch {
        if (!stopped) setCameras(previous => previous.map(c => ({ ...c, status: 'no_data', passages_10min: null, needs_calibration: false })));
      } finally { if (!stopped) timer = setTimeout(poll, 5000); }
    };
    poll();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, []);
  const go = async (a: LL, b: LL) => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setPoints([a, b]); setResult(null); setError(''); setLoading(true);
    try {
      const response = await fetch(`/api/route?from=${a.join(',')}&to=${b.join(',')}`, {
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Walking routing is unavailable. Try again shortly.');
      if (!controller.signal.aborted) setResult(data);
    } catch (e) {
      if (!controller.signal.aborted) setError(e instanceof Error && e.name !== 'TimeoutError' ? e.message : 'Walking routing timed out. Try again shortly.');
    } finally { if (!controller.signal.aborted) setLoading(false); }
  };
  const select = (point: LL) => {
    if (points.length === 1) go(points[0], point);
    else {
      request.current?.abort(); setPoints([point]); setResult(null); setLoading(false); setError('');
    }
  };
  const route = result?.route ?? null;
  const selectedCamera = cameras.find(c => c.id === activeCamera);
  const cameraTabs = [{ id: 'cam1', name: 'Temple Bar' }, { id: 'cam2', name: 'Cabra Road' }, { id: 'cam3', name: 'North Circular Road' }];
  const onRoute = route ? cameras.filter(c => route.camera_ids.includes(c.id)) : [];
  const warnings = onRoute.filter(c => isCurrent(c, now) && c.source === 'live' &&
    ((c.window_complete && c.passages_10min === 0) || c.people_now === 0));
  return <div className="app">
    <header><span>SAFE ROUTES HOME</span><a className="header-link" href="/demo/temple-bar">Live camera demos →</a></header>
    <div className="map"><MapContainer center={[53.3455, -6.2643]} zoom={16} zoomControl>
      <TileLayer url={TILE} attribution="© OpenStreetMap contributors" />
      <MapClicks select={select} /><FitRoute route={route} />
      {route && <Polyline positions={route.coords} pathOptions={{ color: '#2563eb', weight: 6, opacity: .95 }} />}
      {points.map((point, index) => <CircleMarker key={index} center={point} radius={8} pathOptions={{ color: index ? '#b45309' : '#172033', fillOpacity: .9 }}>
        <Popup>{index ? 'B · Destination' : 'A · Start'}</Popup></CircleMarker>)}
      {cameras.filter(c => c.latitude !== null && c.longitude !== null).map(c => <CircleMarker key={c.id} center={[c.latitude!, c.longitude!]} radius={9}
        pathOptions={{ color: warnings.some(w => w.id === c.id) ? '#b45309' : isCurrent(c, now) ? '#2563eb' : '#6b7280', fillOpacity: .8 }}>
        <Popup><CameraActivity camera={c} now={now} /></Popup>
      </CircleMarker>)}
    </MapContainer>
      <div className="legend"><div>Blue line: walking route · ● Camera</div><div>Grey camera: no current data · Amber: zero observed pedestrians</div></div>
    </div>
    <section className="panel" aria-label="Plan a walking route">
      <div className="card route-form">
        <h4>A TO B · WALKING ROUTE</h4>
        <p className="hint">Click the map twice to set A and B, or choose locations below.</p>
        <div className="route-controls"><label>A · Start<select value={from} onChange={e => setFrom(Number(e.target.value))}>{PLACES.map((p, i) => <option value={i} key={p.name}>{p.name}</option>)}</select></label>
          <label>B · Destination<select value={to} onChange={e => setTo(Number(e.target.value))}>{PLACES.map((p, i) => <option value={i} key={p.name}>{p.name}</option>)}</select></label>
          <button onClick={() => go(PLACES[from].point, PLACES[to].point)} disabled={loading}>{loading ? 'Finding route…' : 'Get walking route'}</button></div>
        {points.length === 1 && <p className="hint">A is set. Click your destination to set B.</p>}
        {error && <p role="alert" className="err">{error}</p>}
        {route && <><div className="big">{Math.ceil(route.minutes)} min · {route.distance_m} m</div><p className="hint">Fastest available walking route</p></>}
        {warnings.map(c => <p key={c.id} role="status" className="route-warning">⚠ {c.street}: {c.window_complete && c.passages_10min === 0 ? 'no passages recorded in the last 10 minutes' : 'no pedestrians detected in the latest frame'} at the camera-covered section.</p>)}
      </div>
      <section className="card camera-slide" aria-label="Street cameras">
        <div className="camera-slide-heading"><h4>STREET ACTIVITY</h4><span>Rolling 10-minute window</span></div>
        <div className="camera-tabs" role="tablist" aria-label="Camera locations">
          {cameraTabs.map(c => <button key={c.id} id={`tab-${c.id}`} role="tab" aria-selected={activeCamera === c.id}
            aria-controls="camera-slide-content" tabIndex={activeCamera === c.id ? 0 : -1}
            onClick={() => setActiveCamera(c.id)} onKeyDown={e => {
              if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
              e.preventDefault();
              const index = cameraTabs.findIndex(tab => tab.id === activeCamera);
              const next = e.key === 'Home' ? 0 : e.key === 'End' ? 2 : (index + (e.key === 'ArrowRight' ? 1 : 2)) % 3;
              setActiveCamera(cameraTabs[next].id);
              document.getElementById(`tab-${cameraTabs[next].id}`)?.focus();
            }}>{c.name}</button>)}
        </div>
        <div id="camera-slide-content" role="tabpanel" aria-labelledby={`tab-${activeCamera}`}>
          {selectedCamera ? <CameraActivity camera={selectedCamera} now={now} /> : <p className="hint">No current data. Waiting for camera observations.</p>}
        </div>
      </section>
    </section>
    <footer className="app-footer">Decision support, not a guarantee of safety.</footer>
  </div>;
}
