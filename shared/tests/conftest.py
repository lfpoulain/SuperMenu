import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """Free the Qt objects a test leaves in reference cycles before the next one.

    Python 3.11 runs the cyclic garbage collector on any allocation, including
    those made while a later test is inside the Qt event loop (``QTest.qWait``):
    destroying the Qt objects of an earlier test there can crash the process
    (access violation). When a collection runs depends on every allocation made
    so far, so merely adding a module to supermenu_core can move one onto a Qt
    call. Collected here, once the fixtures and the test arguments are
    released, they are destroyed while no Qt call is running. The Windows suite
    does the same in win32/tests/conftest.py.
    """
    try:
        return (yield)
    finally:
        gc.collect()
