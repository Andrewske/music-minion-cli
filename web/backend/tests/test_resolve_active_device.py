from web.backend.routers.player import resolve_active_device

CONNECTED = {"laptop": {}, "phone": {}}


def test_connected_target_wins():
    assert resolve_active_device("phone", "laptop", CONNECTED) == "phone"


def test_requester_trusted_before_its_socket_registers():
    """Phone taps play before its WebSocket reconnects — still the target."""
    assert resolve_active_device("phone", "phone", {}) == "phone"


def test_stale_target_falls_back_to_requester():
    assert resolve_active_device("ghost", "phone", CONNECTED) == "phone"


def test_no_requester_falls_back_to_first_connected():
    assert resolve_active_device("ghost", None, CONNECTED) == "laptop"


def test_nothing_known_returns_none():
    assert resolve_active_device("ghost", None, {}) is None
    assert resolve_active_device(None, None, {}) is None
