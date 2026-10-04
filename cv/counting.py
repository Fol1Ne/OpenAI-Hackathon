"""Anonymous geometric tracks and rolling passage aggregates; no images or IDs saved."""
from collections import deque
from dataclasses import dataclass
from math import hypot


@dataclass
class Track:
    point: tuple
    seen: float
    born: float
    anchor: tuple | None = None
    side: int = 0
    counted: bool = False
    hits: int = 1


class PassageCounter:
    """Count each short-lived track once across a finite line, in either direction.

    Input points are normalized bottom-centres of person boxes. Geometry alone is
    used for association. Tracks expire after 1s unseen or 30s total lifetime.
    A small dead band prevents box jitter on the line from creating crossings.
    """
    def __init__(self, line, window=600, max_gap=1.0):
        self.a, self.b = (tuple(p) for p in line)
        self.length = hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])
        if self.length < .05 or any(not 0 <= v <= 1 for p in line for v in p):
            raise ValueError("Counting line must have distinct normalized endpoints")
        self.window, self.max_gap = window, max_gap
        self.tracks = []
        self.events, self.intervals, self.samples = deque(), deque(), deque()
        self.previous = None

    def disconnect(self):
        self.previous = None
        self.tracks.clear()

    def _distance(self, p):
        return ((self.b[0] - self.a[0]) * (p[1] - self.a[1]) -
                (self.b[1] - self.a[1]) * (p[0] - self.a[0])) / self.length

    def _crosses_segment(self, p, q):
        d1, d2 = self._distance(p), self._distance(q)
        t = d1 / (d1 - d2)
        intersection = (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
        along = sum((intersection[i] - self.a[i]) * (self.b[i] - self.a[i]) for i in (0, 1)) / self.length ** 2
        return 0 <= along <= 1

    def update(self, points, now):
        if self.previous is not None:
            gap = now - self.previous
            if 0 < gap <= self.max_gap:
                self.intervals.append((self.previous, now))
            else:
                self.tracks.clear()
        self.previous = now
        self.tracks = [t for t in self.tracks if now - t.seen <= self.max_gap and now - t.born < 30]
        # One-to-one nearest position matching; no appearance or face features.
        candidates = sorted((hypot(t.point[0] - p[0], t.point[1] - p[1]), i, j)
                            for i, t in enumerate(self.tracks) for j, p in enumerate(points))
        used_tracks, used_points = set(), set()
        matched = []
        for distance, i, j in candidates:
            if distance > .08 or i in used_tracks or j in used_points:
                continue
            used_tracks.add(i)
            used_points.add(j)
            track = self.tracks[i]
            track.point, track.seen = tuple(points[j]), now
            track.hits += 1
            matched.append(track)
        for j, p in enumerate(points):
            if j not in used_points:
                track = Track(tuple(p), now, now)
                self.tracks.append(track)
                matched.append(track)
        for track in matched:
            distance = self._distance(track.point)
            side = 1 if distance > .008 else -1 if distance < -.008 else 0
            if not side:
                continue
            if (track.side and side != track.side and not track.counted and track.hits >= 3
                    and self._crosses_segment(track.anchor, track.point)):
                self.events.append(now)
                track.counted = True
            track.anchor, track.side = track.point, side
        self.samples.append((now, len(points)))
        return self.snapshot(now)

    def snapshot(self, now):
        cutoff = now - self.window
        while self.events and self.events[0] <= cutoff:
            self.events.popleft()
        while self.intervals and self.intervals[0][1] <= cutoff:
            self.intervals.popleft()
        while self.samples and self.samples[0][0] <= now - 1800:
            self.samples.popleft()
        observed = min(self.window, sum(b - max(a, cutoff) for a, b in self.intervals))
        complete = observed >= self.window - .01
        return {"passages_10min": len(self.events), "observed_seconds": round(observed, 1),
                "window_seconds": self.window, "window_complete": complete,
                "rolling_average": round(sum(n for _, n in self.samples) / len(self.samples), 2) if self.samples else None}
