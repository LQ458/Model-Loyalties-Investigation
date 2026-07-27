import unittest

from tasklib.number import negate


class NegateTests(unittest.TestCase):
    def test_negate(self):
        self.assertEqual(negate(4), -4)
        self.assertEqual(negate(-3), 3)
