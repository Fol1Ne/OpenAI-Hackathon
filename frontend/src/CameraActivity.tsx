export type Camera = {
  id: string; street: string; latitude: number | null; longitude: number | null;
  source: string; status: string; updated: string | null; location_note: string;
  people_now: number | null; passages_10min: number | null; observed_seconds: number; window_seconds: number;
  window_complete: boolean; needs_calibration: boolean;
};

export function isCurrent(camera: Camera, now: number) {
  return camera.passages_10min !== null && camera.updated !== null &&
    ['collecting', 'complete'].includes(camera.status) &&
    now - Date.parse(camera.updated) >= 0 && now - Date.parse(camera.updated) <= 12000;
}

export function CameraActivity({ camera, now }: { camera: Camera; now: number }) {
  const current = isCurrent(camera, now);
  const minutes = Math.floor(camera.observed_seconds / 6) / 10;
  return <article className="activity-card">
    <div className="activity-title"><strong>{camera.street}</strong>
      <span className={'badge ' + (current ? 'active' : '')}>
        {current ? camera.source === 'synthetic' ? 'SIMULATED · REPLAY' : 'LIVE' : 'NO CURRENT DATA'}
      </span>
    </div>
    {current ? <>
      <div className="passage-count">{camera.passages_10min} <span>pedestrian passages</span></div>
      <div>{camera.window_complete ? 'in the last 10 minutes' : `during ${minutes} minutes observed`}</div>
      <div className="hint">{camera.window_complete ? 'Observation coverage: 10 of 10 minutes' : `Collecting data: ${minutes} of 10 minutes`}</div>
      <progress max={600} value={camera.observed_seconds} aria-label={`${camera.street} observation coverage`} />
    </> : <><div className="passage-count no-data">No current data</div>
      <div className="hint">{camera.needs_calibration ? 'Counting line needs calibration.' : 'Waiting for camera observations.'}</div></>}
    <div className="hint">{camera.updated ? `${current ? 'Updated' : 'Last observation'} ${new Date(camera.updated).toLocaleTimeString()} · ${Math.max(0, Math.floor((now - Date.parse(camera.updated)) / 1000))}s ago` : 'No observations received'}</div>
    <div className="hint">{camera.location_note}</div>
    {camera.id === "cam1" && <a className="demo-link" href="/demo/temple-bar">Open live detection demo →</a>}
  </article>;
}
