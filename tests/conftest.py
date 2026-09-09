"""Keep synthetic localhost HTTP tests off the user's configured upstream proxy."""
import os
import pytest


@pytest.fixture(autouse=True)
def loopback_http_bypasses_proxy(monkeypatch):
    existing = os.environ.get("no_proxy", os.environ.get("NO_PROXY", ""))
    value = ",".join(filter(None, [existing, "127.0.0.1", "localhost", "::1"]))
    monkeypatch.setenv("no_proxy", value)
    monkeypatch.setenv("NO_PROXY", value)
