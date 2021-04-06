import time

import pytest

from hn.api import _to_relative_time

NOW = 1000000


@pytest.mark.parametrize(
    "tstamp,expected",
    [
        (NOW - 1, "1s ago"),
        (NOW - 60, "1m ago"),
        (NOW - 61, "1m ago"),
        (NOW - 3600, "1h ago"),
        (NOW - 4600, "1h ago"),
        (NOW - 86400, "1d ago"),
        (NOW - 86400 * 20, "20d ago"),
        (NOW - 86400 * 400, "1y ago"),
        (NOW - 86400 * 500, "1y ago"),
        (NOW - 86400 * 1200, "3y ago"),
    ],
)
def test_to_relative_time(monkeypatch, tstamp, expected):
    monkeypatch.setattr(time, "time", lambda: NOW)
    assert _to_relative_time(tstamp) == expected
