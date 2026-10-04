import unittest
from counting import PassageCounter


class PassageTests(unittest.TestCase):
    def test_crossing_once_and_jitter(self):
        c = PassageCounter([[.2, .5], [.8, .5]])
        for i, y in enumerate([.44, .46, .49, .499, .501, .51, .54, .51, .48]):
            result = c.update([(.5, y)], i * .1)
        self.assertEqual(result['passages_10min'], 1)

    def test_both_directions_and_finite_line(self):
        c = PassageCounter([[.2, .5], [.8, .5]])
        for i, y in enumerate([.44, .47, .53, .56]):
            result = c.update([(.4, y), (.6, 1-y), (.1, y)], i * .1)
        self.assertEqual(result['passages_10min'], 2)

    def test_gap_does_not_count_crossing_or_observation(self):
        c = PassageCounter([[.2, .5], [.8, .5]])
        c.update([(.5, .46)], 0)
        c.update([(.5, .48)], .1)
        result = c.update([(.5, .53)], 20)
        self.assertEqual(result['passages_10min'], 0)
        self.assertEqual(result['observed_seconds'], .1)
        self.assertFalse(result['window_complete'])

    def test_rolling_window_and_reconnect(self):
        c = PassageCounter([[.2, .5], [.8, .5]])
        for i in range(601):
            result = c.update([], float(i))
        self.assertTrue(result['window_complete'])
        self.assertEqual(result['observed_seconds'], 600)
        c.disconnect()
        result = c.update([], 620)
        self.assertEqual(result['observed_seconds'], 580)
        self.assertFalse(result['window_complete'])
        result = c.snapshot(1221)
        self.assertEqual(result['observed_seconds'], 0)

    def test_counts_expire(self):
        c = PassageCounter([[.2, .5], [.8, .5]])
        for i, y in enumerate([.46, .48, .53]):
            c.update([(.5, y)], i * .1)
        self.assertEqual(c.snapshot(1)['passages_10min'], 1)
        self.assertEqual(c.snapshot(601)['passages_10min'], 0)

    def test_no_tracks_after_disconnect(self):
        c = PassageCounter([[.2, .5], [.8, .5]])
        c.update([(.5, .46)], 0)
        c.disconnect()
        self.assertEqual(c.tracks, [])


if __name__ == '__main__':
    unittest.main()
