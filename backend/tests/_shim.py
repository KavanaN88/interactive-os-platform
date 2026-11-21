"""Tiny offline stand-in for the parts of pytest these tests use (pytest.raises, including `as e` / e.value)."""
from contextlib import contextmanager
import types

class _Info:
    value = None

@contextmanager
def raises(exc, match=None):
    info = _Info()
    try:
        yield info
    except exc as e:
        info.value = e
        if match and match not in str(e):
            raise AssertionError(f"'{match}' not in '{e}'")
    else:
        raise AssertionError(f"{exc.__name__} not raised")

pytest = types.SimpleNamespace(raises=raises)
