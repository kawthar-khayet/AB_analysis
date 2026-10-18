"""Tests des routes d'analyses statistiques et de compatibilité."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_methods_compatibility_endpoint() -> None:
    payload = {
        "group_a": [1.0] * 5 + [0.0] * 45,
        "group_b": [1.0] * 12 + [0.0] * 38,
        "metric_type": "binary",
    }
    response = client.post("/api/v1/methods/compatibility", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "methods" in data
    methods = {m["method"]: m for m in data["methods"]}
    assert methods["two_proportion_z"]["compatible"]
    assert methods["fisher_exact"]["compatible"]
    assert not methods["welch_t"]["compatible"]


def test_execute_analysis_two_proportion_z() -> None:
    payload = {
        "method": "two_proportion_z",
        "group_a": [1.0] * 50 + [0.0] * 450,
        "group_b": [1.0] * 80 + [0.0] * 420,
        "alpha": 0.05,
        "alternative": "two_sided",
        "delta": 0.02,
    }
    response = client.post("/api/v1/analyses", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert data["result"]["method"] == "two_proportion_z"
    assert "p_value" in data["result"]
    assert data["result"]["decision"] == "reject_null"
    assert data["interpretation"] is not None
    assert "case" in data["interpretation"]


def test_execute_analysis_welch_t() -> None:
    payload = {
        "method": "welch_t",
        "group_a": [10.0, 11.0, 10.5, 9.8, 12.0, 11.2, 10.8],
        "group_b": [14.0, 15.0, 13.5, 16.0, 14.8, 15.2, 14.9],
        "alpha": 0.05,
        "alternative": "greater",
        "delta": 1.0,
        "unit": "sec",
    }
    response = client.post("/api/v1/analyses", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["method"] == "welch_t"
    assert data["result"]["p_value"] < 0.01
    assert data["interpretation"]["case"] == "a"
