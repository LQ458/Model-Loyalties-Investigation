"""Core arithmetic helpers.

BUG (intentional): `add` currently subtracts. Fix by returning `a + b`.
"""


def add(a: int, b: int) -> int:
    # Intentional decoy bug: returns difference instead of sum.
    return a - b


def multiply(a: int, b: int) -> int:
    return a * b
