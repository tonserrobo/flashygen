"""Tests for CLI startup UTF-8 handling (issue #19)."""
import sys

from main import force_utf8_stdio


class _FakeStream:
    """A stream that records the encoding it was reconfigured to."""

    def __init__(self):
        self.encoding = "cp1252"
        self.reconfigured = []

    def reconfigure(self, encoding=None, **kwargs):
        self.reconfigured.append(encoding)
        self.encoding = encoding


class _NoReconfigureStream:
    """A stream without reconfigure support — must not crash."""

    encoding = "cp1252"


def test_force_utf8_stdio_reconfigures_stdout_and_stderr(monkeypatch):
    out, err = _FakeStream(), _FakeStream()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    force_utf8_stdio()
    assert out.encoding == "utf-8"
    assert err.encoding == "utf-8"


def test_force_utf8_stdio_tolerates_streams_without_reconfigure(monkeypatch):
    monkeypatch.setattr(sys, "stdout", _NoReconfigureStream())
    monkeypatch.setattr(sys, "stderr", _NoReconfigureStream())
    force_utf8_stdio()  # must not raise
