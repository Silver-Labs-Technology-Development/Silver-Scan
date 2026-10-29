"""Contract tests: preserve the approved SilverScan 38-feature directory."""
import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "docs" / "silverscan-feature-catalog.json"


def test_catalog_preserves_original_feature_count():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert len(catalog["baseline"]) == 38
    assert len(catalog["proposals"]) == 18
    assert catalog["schema_version"] == 1


def test_catalog_entries_unique_and_not_misrepresented_as_live():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    features = catalog["baseline"] + catalog["proposals"]
    ids = [f["id"] for f in features]
    assert len(ids) == len(set(ids))
    assert set(f["category"] for f in features) == {
        "markets", "mining", "blockchains", "defi", "ecosystem"
    }
    for feature in features:
        assert feature["display_status"] in catalog["status_values"]
        assert feature["verified_implementation"] is False
        assert feature["name"].strip()


def test_source_counts_match_hosted_feature_page_snapshot():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    counts = {
        group: sum(1 for item in catalog["baseline"] if item["category"] == group)
        for group in ("markets", "mining", "blockchains", "defi", "ecosystem")
    }
    assert counts == {"markets":11,"mining":6,"blockchains":8,"defi":7,"ecosystem":6}


def test_new_features_have_explicit_acceptance_requirements():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    for feature in catalog["proposals"]:
        assert len(feature["acceptance_summary"]) >= 30
        assert feature["display_status"] == "planned"
