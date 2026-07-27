import unittest

from tasklib.bounds import clamp


class ClampTests(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(clamp(-2, 0, 10), 0)
        self.assertEqual(clamp(4, 0, 10), 4)
        self.assertEqual(clamp(14, 0, 10), 10)
