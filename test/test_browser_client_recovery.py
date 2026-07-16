"""Fast, no-network checks of crash recovery and env-var configuration.

Uses fake Page/Context stand-ins instead of a real browser, so this runs as
part of the normal (non-integration) test suite.
"""

from __future__ import annotations

import pytest

from dsv_tracking.browser_client import TrackingClient
from dsv_tracking.models import ShipmentNotFound

ENV_VARS = (
    "TRACKING_HEADLESS",
    "TRACKING_MIN_DELAY",
    "TRACKING_MAX_DELAY",
    "TRACKING_COOLDOWN",
    "TRACKING_RESPONSE_TIMEOUT",
    "TRACKING_USER_DATA_DIR",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


class FakePage:
    def __init__(self, closed: bool = False):
        self._closed = closed

    def is_closed(self) -> bool:
        return self._closed


class FakeContext:
    def __init__(self):
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _started_client(page: FakePage | None = None, **kwargs) -> TrackingClient:
    client = TrackingClient(min_delay=0, max_delay=0, cooldown=0, **kwargs)
    client._context = FakeContext()  # type: ignore[assignment]
    client._page = page or FakePage(closed=False)  # type: ignore[assignment]
    return client


def test_is_healthy_false_before_start():
    client = TrackingClient()
    assert client._is_healthy() is False


def test_is_healthy_false_when_page_closed():
    client = _started_client(page=FakePage(closed=True))
    assert client._is_healthy() is False


def test_is_healthy_true_when_page_open():
    client = _started_client()
    assert client._is_healthy() is True


@pytest.mark.asyncio
async def test_track_recovers_proactively_when_never_started(monkeypatch):
    client = TrackingClient(min_delay=0, max_delay=0, cooldown=0)
    recover_calls = 0

    async def fake_recover():
        nonlocal recover_calls
        recover_calls += 1
        client._context = FakeContext()  # type: ignore[assignment]
        client._page = FakePage(closed=False)  # type: ignore[assignment]

    async def fake_track_locked(reference_number):
        return "summary", "detail", None

    monkeypatch.setattr(client, "_recover", fake_recover)
    monkeypatch.setattr(client, "_track_locked", fake_track_locked)

    result = await client.track("ref123")

    assert recover_calls == 1
    assert result == ("summary", "detail", None)


@pytest.mark.asyncio
async def test_track_recovers_and_retries_once_after_mid_call_crash(monkeypatch):
    page = FakePage(closed=False)
    client = _started_client(page=page)
    call_count = 0
    recover_calls = 0

    async def fake_track_locked(reference_number):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            page._closed = True  # simulate the crash killing the page
            raise RuntimeError("Target crashed")
        return "summary", "detail", None

    async def fake_recover():
        nonlocal recover_calls
        recover_calls += 1
        client._context = FakeContext()  # type: ignore[assignment]
        client._page = FakePage(closed=False)  # type: ignore[assignment]

    monkeypatch.setattr(client, "_track_locked", fake_track_locked)
    monkeypatch.setattr(client, "_recover", fake_recover)

    result = await client.track("ref123")

    assert call_count == 2
    assert recover_calls == 1
    assert result == ("summary", "detail", None)


@pytest.mark.asyncio
async def test_track_does_not_recover_on_shipment_not_found(monkeypatch):
    client = _started_client()
    recover_calls = 0

    async def fake_track_locked(reference_number):
        raise ShipmentNotFound(reference_number)

    async def fake_recover():
        nonlocal recover_calls
        recover_calls += 1

    monkeypatch.setattr(client, "_track_locked", fake_track_locked)
    monkeypatch.setattr(client, "_recover", fake_recover)

    with pytest.raises(ShipmentNotFound):
        await client.track("ref123")

    assert recover_calls == 0


def test_defaults_when_no_env_or_args():
    client = TrackingClient()
    assert client._headless is True
    assert client._min_delay == 1.0
    assert client._max_delay == 3.0
    assert client._cooldown == 7.0
    assert client._response_timeout == 45.0


def test_env_vars_override_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKING_HEADLESS", "false")
    monkeypatch.setenv("TRACKING_RESPONSE_TIMEOUT", "12.5")
    monkeypatch.setenv("TRACKING_USER_DATA_DIR", str(tmp_path))

    client = TrackingClient()

    assert client._headless is False
    assert client._response_timeout == 12.5
    assert client._user_data_dir == tmp_path


def test_explicit_args_win_over_env(monkeypatch):
    monkeypatch.setenv("TRACKING_HEADLESS", "false")

    client = TrackingClient(headless=True)

    assert client._headless is True
