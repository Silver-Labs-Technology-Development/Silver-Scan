"""Offline HTTP adapter tests, without running a server."""
from app.direct_venue_data import VenueStore
from app.direct_venue_api import handle_get


def test_local_read_only_api_empty(tmp_path):
    store = VenueStore(tmp_path / "sample.sqlite")
    code, data = handle_get("/api/direct-venues/latest?limit=10", store)
    assert code == 200
    assert data["observations"] == []
    assert data["verified_asset_identity"] is False
    assert "sampled" in data["coverage"]
    code, data = handle_get("/api/direct-venues/sources", store)
    assert code == 200
    assert data["checked_live"] is False


def test_api_rejects_unbounded_inputs(tmp_path):
    store = VenueStore(tmp_path / "sample.sqlite")
    for path in ("/api/direct-venues/latest?limit=9999",
                 "/api/direct-venues/latest?limit=not-a-number",
                 "/api/direct-venues/sources?private=1",
                 "/api/direct-venues/latest?limit=1&limit=2"):
        code, body = handle_get(path, store)
        assert code == 400
        assert "error" in body
    assert handle_get("/api/account/login", store) is None
