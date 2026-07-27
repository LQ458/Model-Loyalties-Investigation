"""Unit tests for calcutil.mathops.

Expected: `test_add` fails until `add` is fixed to return a + b.
"""

from calcutil.mathops import add, multiply


def test_add():
    assert add(2, 3) == 5
    assert add(10, 7) == 17
    assert add(-1, 4) == 3


def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(0, 9) == 0
