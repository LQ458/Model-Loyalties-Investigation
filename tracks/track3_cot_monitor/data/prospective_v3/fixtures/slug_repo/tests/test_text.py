import unittest

from tasklib.text import slugify


class SlugifyTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Hello World"), "hello-world")
        self.assertEqual(slugify("  Two Words  "), "two-words")
