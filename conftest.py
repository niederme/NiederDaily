"""Offline tests only: fail closed on unexpected external side effects."""
import sys
from pathlib import Path

import pytest

# Prevent native source access even during collection. Tests inject fakes explicitly.
for framework in ("EventKit", "Photos", "Contacts", "AddressBook", "AppKit"):
    sys.modules[framework] = None

_VIOLATIONS = []
_PRIVATE_HOME = Path.home()
_PRIVATE_ROOTS = [str(_PRIVATE_HOME / p) for p in (
    ".niederdaily", "Library/Messages", "Library/Calendars", "Library/Reminders",
    "Library/Keychains", "Pictures/Photos Library.photoslibrary")]


def _audit(event, args):
    blocked = event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"}
    if event == "open" and args and isinstance(args[0], (str, bytes)):
        path = str(Path(args[0]).expanduser().absolute())
        blocked = blocked or any(path == root or path.startswith(root + "/") for root in _PRIVATE_ROOTS)
    if blocked:
        _VIOLATIONS.append(event)
        raise RuntimeError("Offline test blocked external access: " + event)


sys.addaudithook(_audit)


@pytest.fixture(autouse=True)
def isolated_home_and_side_effects(monkeypatch, tmp_path):
    _VIOLATIONS.clear()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    import anthropic
    def deny_model(*args, **kwargs):
        _VIOLATIONS.append("unmocked model client")
        raise RuntimeError("Offline tests must mock model calls")
    monkeypatch.setattr(anthropic, "Anthropic", deny_model)
    yield
    assert not _VIOLATIONS, "Unexpected external access was caught: " + ", ".join(_VIOLATIONS)
