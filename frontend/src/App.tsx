import { useEffect, useState } from "react";
import { CameraActivity, isCurrent, type Camera } from "./CameraActivity";
import { MapContainer, TileLayer, Polyline, CircleMarker, Popup, useMapEvents } from "react-leaflet";
type LL = [number, number];
type R = { coords: LL[]; minutes: number; distance_m: number; pct_lit: number; pct_unlit: number; pct_unknown: number; streets_with_live_traffic: number; total_streets: number };
type Res = { fastest: R; well_lit: R; routes_available: number; explanation: string; sources: { routing: string; lighting: string; demo_mode: boolean }; disclaimer: string };
type Seg = { id: string; name: string; coords: LL[]; lit: string; foot_traffic: string };
const LIT: Record<string, string> = { yes: "#34d399", no: "#fb923c", unknown: "#6b7280" };
const PLACES: { n: string; p: LL }[] = [{ n: "Trinity College", p: [53.3438, -6.2546] }, { n: "Temple Bar", p: [53.3454, -6.2645] }, { n: "Grafton Street", p: [53.3425, -6.26] }, { n: "St Stephen's Green", p: [53.3392, -6.26] }];
const TILE = (import.meta.env.VITE_TILE_URL as string | undefined) || "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const SRC: Record<string, string> = { demo: "DEMO DATA", osrm: "OSRM", "osm-live": "OSM / live", "osm-cached": "OSM / cached" };
function Clicks({ on }: { on: (p: LL) => void }) { useMapEvents({ click: e => on([e.latlng.lat, e.latlng.lng]) }); return null; }


export default function App() {
  const [pts, setPts] = useState<LL[]>([]); const [res, setRes] = useState<Res | null>(null); const [sel, setSel] = useState<"fastest" | "well_lit">("well_lit");
  const [cams, setCams] = useState<Camera[]>([]); const [segs, setSegs] = useState<Seg[]>([]); const [err, setErr] = useState("");
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const tick = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(tick); }, []);
  const [health, setHealth] = useState<{ demo_mode: boolean } | null>(null);
  useEffect(() => { fetch("/api/health").then(r => r.json()).then(setHealth).catch(() => setErr("BACKEND UNAVAILABLE")); fetch("/api/segments").then(r => r.json()).then(setSegs).catch(() => {}); }, []);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const r = await fetch("/api/cameras", { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(4000)]) });
        if (!r.ok) throw new Error("Camera request failed");
        const cameras: Camera[] = await r.json();
        if (!stopped) setCams(cameras);
      } catch {
        if (!stopped) setCams(previous => previous.map(c => ({ ...c, status: "no_data", passages_10min: null, needs_calibration: false })));
      } finally {
        if (!stopped) timer = setTimeout(poll, 5000);
      }
    };
    poll();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, []);
  const go = (a: LL, b: LL) => { setPts([a, b]); setErr(""); setRes(null);
    fetch(`/api/route?from=${a.join(",")}&to=${b.join(",")}`).then(async r => { if (!r.ok) throw new Error(r.status === 503 ? "ROUTING SERVICE UNAVAILABLE" : "Route request failed"); setRes(await r.json()); }).catch(e => setErr(e.message)); };
  const click = (p: LL) => { if (pts.length === 1) go(pts[0], p); else { setPts([p]); setRes(null); } };
  const card = (k: "fastest" | "well_lit", title: string, icon: string) => { const r = res![k]; return (
    <div className={"card" + (sel === k ? " sel" : "")} onClick={() => setSel(k)}><h4>{icon} {title}</h4><div className="big">{Math.round(r.minutes)} min</div>
      <div className="row">{r.pct_lit}% lit · {r.pct_unlit}% unlit · {r.pct_unknown}% unknown</div>
      <div className="row">{r.streets_with_live_traffic} / {r.total_streets} streets with live pedestrian data</div></div>); };
  return (<div className="app">
    <header><span>SAFE ROUTES HOME</span><span>{health?.demo_mode && <span className="badge warn">DEMO ROUTING / LIGHTING</span>} {res && <span className="badge">{res.sources.routing === "demo" ? "DEMO ROUTE" : "routing: OSRM"} · lighting: {SRC[res.sources.lighting] ?? res.sources.lighting}</span>}</span></header>
    <div className="map"><MapContainer center={[53.3455, -6.2643]} zoom={16} zoomControl={false}>
      <TileLayer url={TILE} attribution="© OpenStreetMap contributors" />
      <Clicks on={click} />
      {segs.map(s => <Polyline key={s.id} positions={s.coords} pathOptions={{ color: LIT[s.lit], weight: 3, opacity: 0.45, dashArray: s.lit === "unknown" ? "4 6" : undefined }} />)}
      {res && (["fastest", "well_lit"] as const).map(k => <Polyline key={k} positions={res[k].coords} pathOptions={{ color: k === "fastest" ? "#e8ecf4" : "#60a5fa", weight: sel === k ? 7 : 3, opacity: sel === k ? 0.95 : 0.4 }} />)}
      {pts.map((p, i) => <CircleMarker key={i} center={p} radius={7} pathOptions={{ color: i ? "#f87171" : "#34d399" }} />)}
      {cams.filter(c => c.latitude !== null && c.longitude !== null).map(c => <CircleMarker key={c.id}
        center={[c.latitude!, c.longitude!]} radius={10}
        pathOptions={{ color: isCurrent(c, now) ? "#60a5fa" : "#6b7280", fillOpacity: 0.8 }}>
        <Popup><CameraActivity camera={c} now={now} /></Popup>
      </CircleMarker>)}
    </MapContainer>
      <div className="legend"><div><span className="dot" style={{ background: LIT.yes }} />Lit <span className="dot" style={{ background: LIT.no, marginLeft: 8 }} />Unlit <span className="dot" style={{ background: LIT.unknown, marginLeft: 8 }} />Unknown</div><div>Pedestrian passages: camera-covered pavement only</div><div>● Blue: current observations · Grey: no current data</div></div></div>
    <section className="activity-section" aria-label="Pedestrian activity">
      <div className="activity-heading"><strong>PEDESTRIAN ACTIVITY</strong><span>Crossings in either direction · rolling 10-minute window</span></div>
      <div className="activity-grid">{cams.length ? cams.map(camera => <CameraActivity key={camera.id} camera={camera} now={now} />) : <p>No current camera data. Waiting for the service.</p>}</div>
    </section>
    <div className="panel">
      <div>{res ? <>{card("fastest", "FASTEST", "⚡")}<div style={{ height: 8 }} />{card("well_lit", "WELL LIT", "💡")}{res.routes_available < 2 && <div className="hint">1 route available</div>}</> :
        <div><div className="hint">Pick demo locations, or click the map twice (start, then destination).</div>
          <div style={{ marginTop: 8, display: "flex", gap: 8 }}><select id="from" defaultValue="Trinity College">{PLACES.map(p => <option key={p.n}>{p.n}</option>)}</select>
          <select id="to" defaultValue="St Stephen's Green">{PLACES.map(p => <option key={p.n}>{p.n}</option>)}</select>
          <button onClick={() => { const v = (i: string) => PLACES.find(p => p.n === (document.getElementById(i) as HTMLSelectElement).value)!.p; go(v("from"), v("to")); }}>Compare routes</button></div></div>}
        {err && <div className="err hint">{err}</div>}</div>
      <div className="card" style={{ cursor: "default" }}>{res ? <><h4>ROUTE DETAILS · {sel === "fastest" ? "FASTEST" : "WELL LIT"}</h4>
        <div className="big">{res[sel].distance_m} m · {Math.round(res[sel].minutes)} min</div><div className="row">{res.explanation}</div>
        <div className="hint">Well-lit = highest lighting coverage among available alternatives. Unknown lighting is not treated as unlit.</div><div className="hint">{res.disclaimer}</div></> :
        <><h4>KNOW THE ROUTE. MAKE THE CHOICE.</h4><div className="row">We measure lighting coverage and pedestrian activity where data exists. Unknown stays unknown.</div><div className="hint">Decision support, not a safety guarantee. Data coverage varies by location and time.</div></>}</div>
    </div></div>);
}
