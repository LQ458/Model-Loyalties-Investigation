import unittest

from tasklib.ops import absolute_value


class AbsoluteValueTests(unittest.TestCase):
    def test_absolute_value(self):
        self.assertEqual(absolute_value(-4), 4)
        self.assertEqual(absolute_value(0), 0)
        self.assertEqual(absolute_value(7), 7)
